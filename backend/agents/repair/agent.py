# backend/agents/repair/agent.py
from __future__ import annotations

import time
import uuid
from typing import Any

import structlog

from api.config import Settings
from api.schemas.diagnosis import DiagnosisResult, RootCauseCategory
from api.schemas.repair import (
    DiffLine,
    RepairArtifact,
    RepairDiff,
    RepairStatus,
    RepairType,
    TestCase,
)
from api.schemas.trace import AgentTrace, FailureType

logger = structlog.get_logger(__name__)


class RepairAgent:
    """
    Repair Agent — generates before/after repair artifacts for diagnosed failures.

    Routes to specialized generators based on root cause category:
    - PROMPT_DESIGN → PromptRepairGenerator
    - TOOL_CONFIGURATION → ToolRepairGenerator
    - ORCHESTRATION_LOGIC → Orchestration repair (inline)
    - Others → Generic repair with LLM guidance
    """

    def __init__(self, settings: Settings, gemini_service: Any) -> None:
        self.settings = settings
        self.gemini = gemini_service

    async def generate_repair(
        self,
        trace: AgentTrace,
        diagnosis: DiagnosisResult,
    ) -> RepairArtifact | None:
        """Generate a repair artifact for a diagnosed failure."""
        if diagnosis.repair_feasibility < 0.3:
            logger.info(
                "repair_skipped_low_feasibility",
                trace_id=trace.trace_id,
                feasibility=diagnosis.repair_feasibility,
            )
            return None

        start = time.perf_counter()
        logger.info(
            "repair_generation_start",
            trace_id=trace.trace_id,
            root_cause=diagnosis.root_cause_category,
        )

        try:
            repair_data = await self._route_to_generator(trace, diagnosis)
        except Exception as exc:
            logger.error("repair_generation_failed", error=str(exc))
            repair_data = self._generate_generic_repair(trace, diagnosis)

        generation_ms = (time.perf_counter() - start) * 1000

        # Build the RepairArtifact
        return self._build_artifact(trace, diagnosis, repair_data, generation_ms)

    async def _route_to_generator(
        self, trace: AgentTrace, diagnosis: DiagnosisResult
    ) -> dict[str, Any]:
        """Route to the appropriate specialized generator."""
        category = diagnosis.root_cause_category

        if category == RootCauseCategory.PROMPT_DESIGN:
            from agents.repair.generators.prompt_repair import PromptRepairGenerator
            gen = PromptRepairGenerator(self.settings, self.gemini)
            return await gen.generate(trace, diagnosis)

        elif category in (
            RootCauseCategory.TOOL_CONFIGURATION,
            RootCauseCategory.EXTERNAL_SERVICE,
        ):
            from agents.repair.generators.tool_repair import ToolRepairGenerator
            gen = ToolRepairGenerator(self.settings, self.gemini)
            return await gen.generate(trace, diagnosis)

        elif category == RootCauseCategory.ORCHESTRATION_LOGIC:
            return await self._generate_orchestration_repair(trace, diagnosis)

        elif category == RootCauseCategory.CONTEXT_MANAGEMENT:
            return await self._generate_context_repair(trace, diagnosis)

        elif category == RootCauseCategory.RESOURCE_CONSTRAINT:
            return await self._generate_resource_repair(trace, diagnosis)

        else:
            return self._generate_generic_repair(trace, diagnosis)

    async def _generate_orchestration_repair(
        self, trace: AgentTrace, diagnosis: DiagnosisResult
    ) -> dict[str, Any]:
        """Generate repair for orchestration logic failures."""
        prompt = f"""Generate an orchestration repair for this AI agent failure.

Agent: {trace.agent_name}
Root Cause: {diagnosis.root_cause_description}
Failure Type: {trace.failure_type.value}
Evidence: {diagnosis.evidence_summary[:400]}

The repair should fix the agent's orchestration logic — loop conditions, routing, exit criteria.
Return a JSON repair artifact with: repair_type, title, description, rationale, before, after, test_cases, confidence, risk_level, side_effects, rollback_instructions."""

        result = await self.gemini.generate_structured(
            prompt=prompt,
            system_instruction="You are an expert AI agent repair engineer. Generate concrete, realistic repairs.",
            temperature=0.2,
        )
        if result.get("parse_error") or not result.get("before"):
            return self._generate_generic_repair(trace, diagnosis)
        result["repair_type"] = "orchestration_fix"
        return result

    async def _generate_context_repair(
        self, trace: AgentTrace, diagnosis: DiagnosisResult
    ) -> dict[str, Any]:
        """Generate repair for context management failures."""
        # Find max tokens used
        max_tokens = max(
            (s.total_tokens or 0 for s in trace.spans), default=0
        )

        before = f"""# Agent context configuration
MAX_CONTEXT_TOKENS = 8192
CONTEXT_STRATEGY = "truncate_oldest"
SUMMARY_ENABLED = False"""

        after = f"""# Agent context configuration (repaired)
MAX_CONTEXT_TOKENS = {min(max_tokens + 2000, 32000)}  # Increased limit
CONTEXT_STRATEGY = "sliding_window"      # Better strategy
SUMMARY_ENABLED = True                   # Enable compression
SUMMARY_INTERVAL = 10                    # Summarize every 10 turns
CRITICAL_CONTEXT_PRESERVED = True       # Never drop system context"""

        return {
            "repair_type": "context_injection",
            "title": f"Fix context management for {trace.agent_name}",
            "description": "Increase context window and add compression strategy",
            "rationale": f"Context management failure detected. Agent used {max_tokens} tokens, causing truncation.",
            "before": before,
            "after": after,
            "test_cases": [
                {
                    "name": "test_long_conversation_handled",
                    "description": "Test that long conversations are handled without context loss",
                    "input_payload": {"conversation_turns": 20},
                    "expected_behavior": "Agent maintains context across all turns",
                    "failure_scenario": "Agent forgets earlier context after turn 10",
                }
            ],
            "confidence": 0.75,
            "risk_level": "low",
            "side_effects": ["Slightly higher token costs due to larger context"],
            "rollback_instructions": "Revert MAX_CONTEXT_TOKENS to previous value",
        }

    async def _generate_resource_repair(
        self, trace: AgentTrace, diagnosis: DiagnosisResult
    ) -> dict[str, Any]:
        """Generate repair for resource constraint failures."""
        return {
            "repair_type": "timeout_adjustment",
            "title": f"Fix resource constraints for {trace.agent_name}",
            "description": "Adjust timeout and token limits to prevent resource exhaustion",
            "rationale": diagnosis.root_cause_description,
            "before": f"""# Resource limits
MAX_TOKENS_PER_CALL = 4096
TIMEOUT_SECONDS = 30
MAX_RETRIES = 1""",
            "after": f"""# Resource limits (repaired)
MAX_TOKENS_PER_CALL = 8192       # Doubled token limit
TIMEOUT_SECONDS = 120            # Increased timeout
MAX_RETRIES = 3                  # Added retries
BACKOFF_FACTOR = 2.0             # Exponential backoff
CIRCUIT_BREAKER_THRESHOLD = 5   # Circuit breaker protection""",
            "test_cases": [
                {
                    "name": "test_large_input_handled",
                    "description": "Test that large inputs complete within timeout",
                    "input_payload": {"size": "large"},
                    "expected_behavior": "Completes within 120 seconds",
                    "failure_scenario": "Timeout after 30 seconds on large input",
                }
            ],
            "confidence": 0.7,
            "risk_level": "low",
            "side_effects": ["Higher timeout may mask genuine hangs"],
            "rollback_instructions": "Revert timeout and retry settings",
        }

    def _generate_generic_repair(
        self, trace: AgentTrace, diagnosis: DiagnosisResult
    ) -> dict[str, Any]:
        """Generic fallback repair."""
        return {
            "repair_type": "parameter_tuning",
            "title": f"General repair for {trace.failure_type.value} in {trace.agent_name}",
            "description": f"Address {diagnosis.root_cause_category.value} failure",
            "rationale": diagnosis.root_cause_description[:300],
            "before": f"""# Agent configuration for {trace.agent_name}
# Current state (before repair)
temperature = 0.7
max_tokens = 4096
retry_enabled = False
validation_enabled = False""",
            "after": f"""# Agent configuration for {trace.agent_name} (repaired)
temperature = 0.2              # Reduced for consistency
max_tokens = 8192              # Increased limit
retry_enabled = True           # Enable retries
retry_count = 3
validation_enabled = True      # Enable output validation
fallback_model = "gemini-1.5-pro"  # Fallback model""",
            "test_cases": [
                {
                    "name": "test_failure_does_not_recur",
                    "description": "Verify the original failure scenario now succeeds",
                    "input_payload": trace.input_payload,
                    "expected_behavior": "Agent completes successfully",
                    "failure_scenario": trace.failure_reason or "Unknown failure",
                }
            ],
            "confidence": 0.5,
            "risk_level": "low",
            "side_effects": ["Lower temperature may reduce creativity"],
            "rollback_instructions": "Revert agent configuration to previous version",
        }

    def _build_artifact(
        self,
        trace: AgentTrace,
        diagnosis: DiagnosisResult,
        repair_data: dict[str, Any],
        generation_ms: float,
    ) -> RepairArtifact:
        """Build a RepairArtifact from generated repair data."""

        # Parse repair type
        repair_type_str = repair_data.get("repair_type", "parameter_tuning")
        try:
            repair_type = RepairType(repair_type_str)
        except ValueError:
            repair_type = RepairType.PARAMETER_TUNING

        # Build diff
        diff_lines_raw = repair_data.get("diff_lines", [])
        diff_lines = []
        for dl in diff_lines_raw:
            if isinstance(dl, dict):
                diff_lines.append(DiffLine(
                    line_number=dl.get("line_number", 0),
                    content=dl.get("content", ""),
                    change_type=dl.get("change_type", "context"),
                ))

        diff = RepairDiff(
            target_type=repair_type_str,
            before=str(repair_data.get("before", "")),
            after=str(repair_data.get("after", "")),
            diff_lines=diff_lines,
            description=repair_data.get("diff_description", repair_data.get("description", "")),
        )

        # Build test cases
        test_cases = []
        for tc_data in repair_data.get("test_cases", []):
            if isinstance(tc_data, dict):
                test_cases.append(TestCase(
                    name=tc_data.get("name", "test"),
                    description=tc_data.get("description", ""),
                    input_payload=tc_data.get("input_payload", {}),
                    expected_behavior=tc_data.get("expected_behavior", ""),
                    failure_scenario=tc_data.get("failure_scenario", ""),
                ))

        return RepairArtifact(
            repair_id=str(uuid.uuid4()),
            trace_id=trace.trace_id,
            diagnosis_id=diagnosis.diagnosis_id,
            agent_id=trace.agent_id,
            repair_type=repair_type,
            title=repair_data.get("title", f"Repair for {trace.failure_type.value}"),
            description=repair_data.get("description", ""),
            rationale=repair_data.get("rationale", ""),
            diff=diff,
            test_cases=test_cases,
            tests_total=len(test_cases),
            confidence=float(repair_data.get("confidence", 0.5)),
            risk_level=repair_data.get("risk_level", "medium"),
            side_effects=repair_data.get("side_effects", []),
            rollback_instructions=repair_data.get("rollback_instructions", ""),
            implementation_instructions=repair_data.get("implementation_instructions", []),
            status=RepairStatus.PENDING,
            model_used=self.settings.gemini_model,
            generation_duration_ms=generation_ms,
        )
