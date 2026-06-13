# backend/agents/repair/generators/tool_repair.py
from __future__ import annotations

import json
from typing import Any

import structlog

from api.config import Settings
from api.schemas.diagnosis import DiagnosisResult
from api.schemas.trace import AgentTrace, SpanStatus
from agents.repair.prompts import REPAIR_SYSTEM_PROMPT, TOOL_REPAIR_TEMPLATE

logger = structlog.get_logger(__name__)


class ToolRepairGenerator:
    """Generates tool configuration repairs for tool-related failures."""

    def __init__(self, settings: Settings, gemini_service: Any) -> None:
        self.settings = settings
        self.gemini = gemini_service

    async def generate(
        self,
        trace: AgentTrace,
        diagnosis: DiagnosisResult,
    ) -> dict[str, Any]:
        """Generate a tool configuration repair."""

        failed_tool_name, tool_error, tool_config = self._extract_tool_failure(trace)

        prompt = TOOL_REPAIR_TEMPLATE.format(
            agent_name=trace.agent_name,
            root_cause_category=diagnosis.root_cause_category.value,
            root_cause_description=diagnosis.root_cause_description[:500],
            failed_tool_name=failed_tool_name,
            tool_error=tool_error,
            tool_config=json.dumps(tool_config, indent=2)[:1000],
        )

        result = await self.gemini.generate_structured(
            prompt=prompt,
            system_instruction=REPAIR_SYSTEM_PROMPT,
            temperature=0.2,
        )

        # Ensure basic fields
        if "repair_type" not in result or result.get("parse_error"):
            result = self._generate_fallback_tool_repair(
                trace, diagnosis, failed_tool_name, tool_error
            )

        return result

    def _extract_tool_failure(
        self, trace: AgentTrace
    ) -> tuple[str, str, dict[str, Any]]:
        """Extract the first failed tool call details."""
        for span in trace.spans:
            for tc in span.tool_calls:
                if tc.status == SpanStatus.ERROR and tc.error:
                    config = {
                        "tool_name": tc.tool_name,
                        "tool_version": tc.tool_version,
                        "input_args": tc.input_args,
                        "retry_count": tc.retry_count,
                        "metadata": tc.metadata,
                    }
                    return tc.tool_name, tc.error, config

        # No explicit tool error, use trace metadata
        return (
            trace.metadata.get("failed_tool", "unknown_tool"),
            trace.failure_reason or "Unknown tool error",
            {},
        )

    def _generate_fallback_tool_repair(
        self,
        trace: AgentTrace,
        diagnosis: DiagnosisResult,
        tool_name: str,
        tool_error: str,
    ) -> dict[str, Any]:
        """Fallback tool repair when LLM fails."""
        before = f"""# Tool: {tool_name}
config = {{
    "timeout": 30,
    "retry_count": 1,
    "validate_input": False
}}"""

        after = f"""# Tool: {tool_name} (repaired)
config = {{
    "timeout": 60,          # Increased timeout
    "retry_count": 3,        # Added retry logic
    "retry_backoff": 2.0,    # Exponential backoff
    "validate_input": True,  # Added input validation
    "fallback_enabled": True # Added fallback
}}"""

        return {
            "repair_type": "tool_config_change",
            "title": f"Fix {tool_name} configuration",
            "description": f"Repair configuration for failing tool '{tool_name}'",
            "rationale": f"Tool error: {tool_error[:200]}. Increasing timeout and adding retry logic.",
            "before": before,
            "after": after,
            "test_cases": [
                {
                    "name": f"test_{tool_name}_recovers_on_retry",
                    "description": f"Verify {tool_name} succeeds with improved config",
                    "input_payload": {},
                    "expected_behavior": f"Tool {tool_name} succeeds within 3 retries",
                    "failure_scenario": f"Tool fails due to: {tool_error[:100]}",
                }
            ],
            "confidence": 0.6,
            "risk_level": "low",
            "side_effects": ["Increased timeout may slow down execution slightly"],
            "rollback_instructions": f"Revert config changes for {tool_name}",
        }
