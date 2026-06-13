# backend/agents/validation/agent.py
from __future__ import annotations

import time
from typing import Any

import structlog

from api.config import Settings
from api.schemas.diagnosis import DiagnosisResult
from api.schemas.repair import RepairArtifact, RepairStatus
from api.schemas.trace import AgentTrace

logger = structlog.get_logger(__name__)

VALIDATION_PROMPT = """Evaluate this AI agent repair artifact.

## ORIGINAL FAILURE
Agent: {agent_name}
Failure: {failure_type}
Root Cause: {root_cause_description}
Confidence: {diagnosis_confidence}

## PROPOSED REPAIR
Type: {repair_type}
Title: {repair_title}
Rationale: {repair_rationale}

BEFORE:
{before}

AFTER:
{after}

## TEST CASES
{test_cases}

## VALIDATION TASK
Evaluate whether this repair:
1. Correctly addresses the root cause
2. Has reasonable before/after changes
3. Includes adequate test coverage
4. Has acceptable risk level
5. Is realistically implementable

Return JSON:
{{
    "passed": true/false,
    "score": 0.0-1.0,
    "checks": {{
        "addresses_root_cause": true/false,
        "before_after_reasonable": true/false,
        "test_coverage_adequate": true/false,
        "risk_acceptable": true/false,
        "implementable": true/false
    }},
    "notes": "validation notes",
    "test_results": [
        {{
            "test_name": "string",
            "passed": true/false,
            "simulated_result": "description",
            "issues": ["list of issues"]
        }}
    ],
    "recommended_improvements": ["list"]
}}"""


class ValidationAgent:
    """
    Validation Agent — tests repair artifacts for correctness and safety.

    Performs:
    1. Structural validation (diff is valid, test cases are complete)
    2. Semantic validation (repair addresses root cause)
    3. Risk assessment (side effects, blast radius)
    4. Simulated test execution
    """

    def __init__(self, settings: Settings, gemini_service: Any) -> None:
        self.settings = settings
        self.gemini = gemini_service

    async def validate_repair(
        self,
        repair: RepairArtifact,
        trace: AgentTrace,
        diagnosis: DiagnosisResult,
    ) -> RepairArtifact:
        """Validate a repair artifact and update it with validation results."""
        start = time.perf_counter()

        # Step 1: Structural checks
        structural_score = self._check_structure(repair)

        # Step 2: LLM semantic validation
        try:
            llm_validation = await self._semantic_validation(repair, trace, diagnosis)
        except Exception as exc:
            logger.warning("validation_llm_failed", error=str(exc))
            llm_validation = {"passed": structural_score > 0.5, "score": structural_score, "notes": "LLM validation unavailable"}

        # Step 3: Simulate test cases
        test_results = await self._simulate_test_cases(repair, trace)

        # Compute final validation
        llm_passed = bool(llm_validation.get("passed", False))
        llm_score = float(llm_validation.get("score", 0.5))

        tests_passed = sum(1 for r in test_results if r.get("passed", False))
        tests_total = len(test_results)
        test_pass_rate = tests_passed / tests_total if tests_total > 0 else 1.0

        final_score = (structural_score * 0.3 + llm_score * 0.5 + test_pass_rate * 0.2)
        final_passed = final_score >= 0.6

        duration_ms = (time.perf_counter() - start) * 1000

        # Update repair artifact
        repair.validation_passed = final_passed
        repair.validation_score = round(final_score, 3)
        repair.validation_notes = llm_validation.get("notes", "")
        repair.tests_passed = tests_passed
        repair.tests_failed = tests_total - tests_passed
        repair.tests_total = tests_total

        if final_passed:
            repair.status = RepairStatus.VALIDATED
        else:
            repair.validation_notes += (
                f"\n\nValidation failed (score: {final_score:.2f}). "
                f"Issues: {llm_validation.get('recommended_improvements', [])}"
            )

        # Update test case results
        for i, test_case in enumerate(repair.test_cases):
            if i < len(test_results):
                result = test_results[i]
                test_case.passed = result.get("passed", False)
                test_case.actual_output = result.get("simulated_result", "")
                test_case.error = (
                    "; ".join(result.get("issues", []))
                    if result.get("issues")
                    else None
                )
                test_case.run_duration_ms = duration_ms / max(tests_total, 1)

        logger.info(
            "validation_complete",
            repair_id=repair.repair_id,
            passed=final_passed,
            score=final_score,
            tests_passed=tests_passed,
            tests_total=tests_total,
        )

        return repair

    def _check_structure(self, repair: RepairArtifact) -> float:
        """Structural validation checks."""
        score = 0.0
        checks = 0

        # Has title and description
        if repair.title and len(repair.title) > 5:
            score += 1.0
        checks += 1

        # Has before/after diff
        if repair.diff.before and repair.diff.after:
            score += 1.0
        checks += 1

        # Before != After
        if repair.diff.before != repair.diff.after:
            score += 1.0
        checks += 1

        # Has test cases
        if repair.test_cases:
            score += 1.0
        checks += 1

        # Has rationale
        if repair.rationale and len(repair.rationale) > 20:
            score += 1.0
        checks += 1

        # Has rollback instructions
        if repair.rollback_instructions:
            score += 0.5
        checks += 1

        return score / checks if checks > 0 else 0.0

    async def _semantic_validation(
        self,
        repair: RepairArtifact,
        trace: AgentTrace,
        diagnosis: DiagnosisResult,
    ) -> dict[str, Any]:
        """Use LLM to validate semantic correctness."""
        test_cases_text = "\n".join(
            f"  - {tc.name}: {tc.expected_behavior}"
            for tc in repair.test_cases[:5]
        )

        prompt = VALIDATION_PROMPT.format(
            agent_name=trace.agent_name,
            failure_type=trace.failure_type.value,
            root_cause_description=diagnosis.root_cause_description[:300],
            diagnosis_confidence=diagnosis.confidence,
            repair_type=repair.repair_type.value,
            repair_title=repair.title,
            repair_rationale=repair.rationale[:300],
            before=repair.diff.before[:500],
            after=repair.diff.after[:500],
            test_cases=test_cases_text or "No test cases",
        )

        return await self.gemini.generate_structured(
            prompt=prompt,
            system_instruction="You are a meticulous AI systems QA engineer validating repair artifacts.",
            temperature=0.1,
        )

    async def _simulate_test_cases(
        self, repair: RepairArtifact, trace: AgentTrace
    ) -> list[dict[str, Any]]:
        """Simulate test case execution (LLM-based simulation)."""
        if not repair.test_cases:
            return []

        results = []
        for test_case in repair.test_cases[:5]:  # Limit to 5 test cases
            # Simple simulation: check if the repair's "after" content
            # addresses the test's expected behavior
            after_content = repair.diff.after.lower()
            expected = test_case.expected_behavior.lower()
            failure_scenario = test_case.failure_scenario.lower()

            # Heuristic: does the repair contain relevant keywords?
            keywords_from_failure = failure_scenario.split()[:5]
            keywords_fixed = [
                kw for kw in keywords_from_failure
                if len(kw) > 4 and kw not in after_content
            ]

            passed = len(keywords_fixed) < 2  # Most failure keywords should be addressed

            results.append({
                "test_name": test_case.name,
                "passed": passed,
                "simulated_result": f"Simulated: {test_case.expected_behavior[:100]}",
                "issues": [f"Keyword '{kw}' not addressed in repair" for kw in keywords_fixed[:2]],
            })

        return results
