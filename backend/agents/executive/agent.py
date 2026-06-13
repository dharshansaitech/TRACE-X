# backend/agents/executive/agent.py
from __future__ import annotations

from typing import Any

import structlog

from api.config import Settings
from api.schemas.diagnosis import DiagnosisResult
from api.schemas.repair import RepairArtifact
from api.schemas.trace import AgentTrace

logger = structlog.get_logger(__name__)

EXECUTIVE_SUMMARY_PROMPT = """Generate an executive summary of this AI agent incident.

## INCIDENT DATA
Agent: {agent_name}
Failure: {failure_type}
Severity: {severity}
Duration: {duration_ms}ms
Occurred: {occurred_at}

## ROOT CAUSE
{root_cause}

## BLAST RADIUS
{blast_radius}

## REPAIR
Type: {repair_type}
Confidence: {repair_confidence}
Status: {repair_status}

## TASK
Write a concise 3-paragraph executive summary:
1. What happened (non-technical)
2. Impact and risk
3. What we're doing about it

Return JSON:
{{
    "title": "incident title",
    "executive_summary": "3-paragraph text",
    "business_impact": "1 sentence",
    "technical_summary": "1-2 sentences for engineering",
    "priority": "P0|P1|P2|P3",
    "estimated_resolution_hours": 0.0
}}"""


class ExecutiveAgent:
    """
    Executive Agent — generates high-level summaries and orchestration decisions.

    Responsibilities:
    1. Generate executive incident summaries
    2. Decide prioritization of repairs
    3. Escalation recommendations
    4. Cross-incident pattern detection
    """

    def __init__(self, settings: Settings, gemini_service: Any) -> None:
        self.settings = settings
        self.gemini = gemini_service

    async def generate_incident_summary(
        self,
        trace: AgentTrace,
        diagnosis: DiagnosisResult,
        repair: RepairArtifact | None = None,
    ) -> dict[str, Any]:
        """Generate an executive summary for an incident."""

        blast = diagnosis.blast_radius
        blast_text = (
            f"Affected agents: {blast.affected_agents}, "
            f"Services: {blast.downstream_services}, "
            f"Data risk: {blast.data_integrity_risk}"
        )

        prompt = EXECUTIVE_SUMMARY_PROMPT.format(
            agent_name=trace.agent_name,
            failure_type=trace.failure_type.value,
            severity=diagnosis.severity.value,
            duration_ms=trace.duration_ms or 0,
            occurred_at=trace.started_at.isoformat(),
            root_cause=diagnosis.root_cause_description[:300],
            blast_radius=blast_text,
            repair_type=repair.repair_type.value if repair else "none",
            repair_confidence=repair.confidence if repair else 0,
            repair_status=repair.status.value if repair else "none",
        )

        try:
            result = await self.gemini.generate_structured(
                prompt=prompt,
                system_instruction="You are a site reliability engineering executive. Write clear, concise incident reports.",
                temperature=0.3,
            )
            return result
        except Exception as exc:
            logger.warning("executive_summary_failed", error=str(exc))
            return {
                "title": f"{trace.failure_type.value} incident in {trace.agent_name}",
                "executive_summary": diagnosis.root_cause_description,
                "business_impact": f"Agent {trace.agent_name} experienced a {diagnosis.severity.value} failure",
                "technical_summary": diagnosis.root_cause_description[:200],
                "priority": "P2" if diagnosis.severity.value in ("critical", "high") else "P3",
                "estimated_resolution_hours": 4.0,
            }

    async def prioritize_repairs(
        self, repairs: list[RepairArtifact]
    ) -> list[RepairArtifact]:
        """Sort repairs by priority (severity × feasibility × confidence)."""
        def priority_score(r: RepairArtifact) -> float:
            # Higher is better
            return r.confidence * (1.0 if r.risk_level == "low" else 0.7)

        return sorted(repairs, key=priority_score, reverse=True)

    async def should_escalate(
        self, diagnosis: DiagnosisResult
    ) -> tuple[bool, str]:
        """Determine if an incident needs human escalation."""
        from api.schemas.diagnosis import SeverityLevel

        if diagnosis.severity == SeverityLevel.CRITICAL:
            return True, "Critical severity requires immediate human attention"

        if diagnosis.blast_radius.data_integrity_risk:
            return True, "Data integrity risk detected — human review required"

        if diagnosis.confidence < 0.4:
            return True, "Low diagnosis confidence — manual investigation needed"

        if not diagnosis.blast_radius.containment_possible:
            return True, "Failure cannot be automatically contained"

        return False, "No escalation needed"
