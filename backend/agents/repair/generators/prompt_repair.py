# backend/agents/repair/generators/prompt_repair.py
from __future__ import annotations

from typing import Any

import structlog

from api.config import Settings
from api.schemas.diagnosis import DiagnosisResult
from api.schemas.repair import DiffLine, RepairDiff
from api.schemas.trace import AgentTrace
from agents.repair.prompts import PROMPT_REPAIR_TEMPLATE, REPAIR_SYSTEM_PROMPT

logger = structlog.get_logger(__name__)


class PromptRepairGenerator:
    """Generates prompt-specific repairs for prompt design failures."""

    def __init__(self, settings: Settings, gemini_service: Any) -> None:
        self.settings = settings
        self.gemini = gemini_service

    async def generate(
        self,
        trace: AgentTrace,
        diagnosis: DiagnosisResult,
    ) -> dict[str, Any]:
        """Generate a prompt repair for the diagnosed failure."""

        # Extract current prompt from spans
        current_prompt = self._extract_current_prompt(trace)

        # Determine what went wrong
        what_went_wrong = self._describe_failure(trace, diagnosis)

        prompt = PROMPT_REPAIR_TEMPLATE.format(
            agent_name=trace.agent_name,
            root_cause_category=diagnosis.root_cause_category.value,
            root_cause_description=diagnosis.root_cause_description[:500],
            severity=diagnosis.severity.value,
            confidence=diagnosis.confidence,
            current_prompt=current_prompt[:1000],
            evidence_summary=diagnosis.evidence_summary[:500],
            what_went_wrong=what_went_wrong,
        )

        result = await self.gemini.generate_structured(
            prompt=prompt,
            system_instruction=REPAIR_SYSTEM_PROMPT,
            temperature=0.2,
        )

        # Post-process: add diff lines
        if "before" in result and "after" in result:
            result["diff_lines"] = self._compute_diff_lines(
                result["before"], result["after"]
            )

        return result

    def _extract_current_prompt(self, trace: AgentTrace) -> str:
        """Extract the agent's current system prompt/instructions from the trace."""
        for span in trace.spans:
            if span.input_messages:
                for msg in span.input_messages:
                    if isinstance(msg, dict) and msg.get("role") == "system":
                        content = msg.get("content", "")
                        if isinstance(content, str) and len(content) > 20:
                            return content[:2000]

        # Fallback: extract from metadata
        prompt = trace.metadata.get("system_prompt", "")
        if prompt:
            return str(prompt)[:2000]

        return f"[System prompt for agent {trace.agent_name} not captured in trace]"

    def _describe_failure(self, trace: AgentTrace, diagnosis: DiagnosisResult) -> str:
        """Describe what went wrong in plain terms."""
        parts = [
            f"Agent: {trace.agent_name}",
            f"Failure: {trace.failure_type.value}",
            f"Root cause: {diagnosis.root_cause_description[:300]}",
        ]
        if diagnosis.reasoning_chain:
            last_step = diagnosis.reasoning_chain[-1]
            parts.append(f"Key finding: {last_step.conclusion}")
        return "\n".join(parts)

    def _compute_diff_lines(self, before: str, after: str) -> list[dict]:
        """Compute unified diff lines between before and after."""
        import difflib

        before_lines = before.splitlines(keepends=True)
        after_lines = after.splitlines(keepends=True)

        diff = list(difflib.unified_diff(
            before_lines,
            after_lines,
            fromfile="before",
            tofile="after",
            lineterm="",
        ))

        result = []
        line_num = 0
        for line in diff:
            line_num += 1
            if line.startswith("+"):
                change_type = "added"
            elif line.startswith("-"):
                change_type = "removed"
            else:
                change_type = "context"
            result.append({
                "line_number": line_num,
                "content": line.rstrip(),
                "change_type": change_type,
            })

        return result
