# backend/agents/diagnosis/agent.py
from __future__ import annotations

import time
import uuid
from typing import Any

import structlog

from api.config import Settings
from api.schemas.diagnosis import (
    AnomalySignal,
    BlastRadius,
    DiagnosisResult,
    ReasoningStep,
    RootCauseCategory,
    SeverityLevel,
)
from api.schemas.trace import AgentTrace
from agents.diagnosis.prompts import DIAGNOSIS_SYSTEM_PROMPT, ROOT_CAUSE_ANALYSIS_PROMPT
from agents.diagnosis.reconstructor import TraceReconstructor

logger = structlog.get_logger(__name__)


class DiagnosisAgent:
    """
    Diagnosis Agent — multi-step root cause analysis using Gemini 2.0 Flash.

    Pipeline:
    1. Reconstruct execution graph
    2. Identify divergence points
    3. Query Arize MCP for similar failures
    4. Run LLM root cause analysis
    5. Generate structured DiagnosisResult
    """

    def __init__(self, settings: Settings, gemini_service: Any) -> None:
        self.settings = settings
        self.gemini = gemini_service
        self.reconstructor = TraceReconstructor()

    async def diagnose(
        self,
        trace: AgentTrace,
        observation: Any | None = None,
        context: dict[str, Any] | None = None,
    ) -> DiagnosisResult:
        """Perform full root cause analysis on a failed trace."""
        start = time.perf_counter()
        logger.info("diagnosis_start", trace_id=trace.trace_id)

        # Step 1: Reconstruct execution
        graph = self.reconstructor.reconstruct(trace)

        # Step 2: Get Arize insights
        arize_insights: dict[str, Any] = {}
        similar_traces: list[str] = []
        try:
            from mcp.arize_mcp_client import ArizeMCPClient
            arize = ArizeMCPClient(self.settings)
            arize_data = await arize.search_similar_traces(
                agent_id=trace.agent_id,
                failure_type=trace.failure_type.value,
                limit=5,
            )
            arize_insights = arize_data.get("insights", {})
            similar_traces = [t["trace_id"] for t in arize_data.get("similar_traces", [])]
        except Exception as exc:
            logger.debug("arize_mcp_skipped", error=str(exc))

        # Step 3: Build prompt context
        failing_span = None
        divergence_span_id = None
        if graph.divergence_points:
            first_divergence = graph.divergence_points[0]
            divergence_span_id = first_divergence.span_id
            failing_span = graph.span_map.get(divergence_span_id)

        # Format failing span details
        failing_span_text = "No failing span identified"
        if failing_span:
            failing_span_text = (
                f"Span ID: {failing_span.span_id}\n"
                f"Name: {failing_span.span_name}\n"
                f"Kind: {failing_span.kind.value}\n"
                f"Status: {failing_span.status.value}\n"
                f"Error: {failing_span.error_message or 'None'}\n"
                f"Error Type: {failing_span.error_type or 'None'}\n"
                f"Duration: {failing_span.duration_ms or '?'}ms\n"
                f"Model: {failing_span.model or 'N/A'}\n"
                f"Tokens: {failing_span.total_tokens or 'N/A'}"
            )

        # Format anomaly signals
        anomaly_text = ""
        if observation and hasattr(observation, "anomaly_signals"):
            anomaly_text = "\n".join(
                f"  [{s.signal_type}] {s.description} (score: {s.anomaly_score:.2f})"
                for s in observation.anomaly_signals
            )

        # Format similar failures from Arize
        similar_text = ""
        if similar_traces:
            similar_text = f"Found {len(similar_traces)} similar failures: {similar_traces[:3]}"
        elif arize_insights:
            similar_text = str(arize_insights)[:500]
        else:
            similar_text = "No similar failures found in historical data"

        prompt = ROOT_CAUSE_ANALYSIS_PROMPT.format(
            agent_name=trace.agent_name,
            agent_id=trace.agent_id,
            failure_type=trace.failure_type.value,
            observer_classification=observation.failure_classification.value if observation else "unknown",
            observer_confidence=observation.confidence if observation else 0.5,
            duration_ms=trace.duration_ms or 0,
            span_timeline=self.reconstructor.get_span_timeline_text(trace),
            failing_span_details=failing_span_text,
            tool_call_chain=self.reconstructor.get_tool_chain_text(trace),
            llm_interactions=self.reconstructor.get_llm_interactions_text(trace),
            anomaly_signals=anomaly_text or "None provided",
            similar_failures=similar_text,
        )

        # Step 4: LLM root cause analysis
        try:
            llm_result = await self.gemini.generate_structured(
                prompt=prompt,
                system_instruction=DIAGNOSIS_SYSTEM_PROMPT,
                temperature=0.1,
            )
        except Exception as exc:
            logger.error("diagnosis_llm_failed", error=str(exc))
            llm_result = self._fallback_diagnosis(trace, graph)

        duration_ms = (time.perf_counter() - start) * 1000

        # Step 5: Build DiagnosisResult
        return self._build_result(
            trace=trace,
            llm_result=llm_result,
            graph=graph,
            failing_span_id=divergence_span_id,
            arize_insights=arize_insights,
            similar_traces=similar_traces,
            duration_ms=duration_ms,
        )

    def _build_result(
        self,
        trace: AgentTrace,
        llm_result: dict[str, Any],
        graph: Any,
        failing_span_id: str | None,
        arize_insights: dict[str, Any],
        similar_traces: list[str],
        duration_ms: float,
    ) -> DiagnosisResult:
        """Build the final DiagnosisResult from LLM output."""

        # Parse root cause category
        rcc_str = llm_result.get("root_cause_category", "unknown")
        try:
            root_cause_category = RootCauseCategory(rcc_str)
        except ValueError:
            root_cause_category = RootCauseCategory.UNKNOWN

        # Parse severity
        sev_str = llm_result.get("severity", "medium")
        try:
            severity = SeverityLevel(sev_str)
        except ValueError:
            severity = SeverityLevel.MEDIUM

        # Parse reasoning chain
        reasoning_chain: list[ReasoningStep] = []
        for step_data in llm_result.get("reasoning_chain", []):
            try:
                reasoning_chain.append(
                    ReasoningStep(
                        step_number=step_data.get("step_number", len(reasoning_chain) + 1),
                        hypothesis=step_data.get("hypothesis", ""),
                        evidence=step_data.get("evidence", []),
                        evidence_spans=step_data.get("evidence_spans", []),
                        confidence=float(step_data.get("confidence", 0.5)),
                        conclusion=step_data.get("conclusion", ""),
                        eliminated_alternatives=step_data.get("eliminated_alternatives", []),
                    )
                )
            except Exception:
                pass

        # Parse blast radius
        blast_data = llm_result.get("blast_radius", {})
        blast_radius = BlastRadius(
            affected_agents=blast_data.get("affected_agents", []),
            downstream_services=blast_data.get("downstream_services", []),
            data_integrity_risk=bool(blast_data.get("data_integrity_risk", False)),
            containment_possible=bool(blast_data.get("containment_possible", True)),
        )

        # Collect anomaly signals from divergence points
        anomaly_signals: list[AnomalySignal] = []
        for dp in graph.divergence_points:
            anomaly_signals.append(
                AnomalySignal(
                    signal_type=dp.divergence_type,
                    span_id=dp.span_id,
                    description=dp.description,
                    anomaly_score=dp.confidence,
                    timestamp=dp.timestamp,
                )
            )

        return DiagnosisResult(
            diagnosis_id=str(uuid.uuid4()),
            trace_id=trace.trace_id,
            agent_id=trace.agent_id,
            diagnosis_duration_ms=duration_ms,
            root_cause_category=root_cause_category,
            root_cause_description=llm_result.get(
                "root_cause_description", "Root cause could not be determined"
            ),
            severity=severity,
            confidence=float(llm_result.get("confidence", 0.5)),
            reasoning_chain=reasoning_chain,
            anomaly_signals=anomaly_signals,
            blast_radius=blast_radius,
            failing_span_id=llm_result.get("failing_span_id") or failing_span_id,
            divergence_point_span_id=llm_result.get("divergence_point_span_id") or failing_span_id,
            contributing_spans=llm_result.get("contributing_spans", []),
            evidence_summary=llm_result.get("evidence_summary", ""),
            immediate_actions=llm_result.get("immediate_actions", []),
            long_term_recommendations=llm_result.get("long_term_recommendations", []),
            repair_feasibility=float(llm_result.get("repair_feasibility", 0.7)),
            arize_insights=arize_insights,
            similar_traces=similar_traces,
            model_used=self.settings.gemini_model,
            raw_llm_response=str(llm_result)[:2000],
        )

    def _fallback_diagnosis(self, trace: AgentTrace, graph: Any) -> dict[str, Any]:
        """Fallback diagnosis when LLM is unavailable."""
        failing_span_id = (
            graph.divergence_points[0].span_id if graph.divergence_points else None
        )
        return {
            "root_cause_category": trace.failure_type.value
            if trace.failure_type.value != "none"
            else "unknown",
            "root_cause_description": f"Automated analysis: {trace.failure_type.value} failure detected in agent {trace.agent_name}",
            "severity": "high",
            "confidence": 0.4,
            "reasoning_chain": [
                {
                    "step_number": 1,
                    "hypothesis": "Failure occurred due to reported failure type",
                    "evidence": [f"Failure type: {trace.failure_type.value}", f"Error count: {trace.error_count}"],
                    "evidence_spans": [failing_span_id] if failing_span_id else [],
                    "confidence": 0.4,
                    "conclusion": "Heuristic-based analysis (LLM unavailable)",
                    "eliminated_alternatives": [],
                }
            ],
            "failing_span_id": failing_span_id,
            "divergence_point_span_id": failing_span_id,
            "contributing_spans": [failing_span_id] if failing_span_id else [],
            "evidence_summary": "LLM analysis unavailable. Heuristic-based diagnosis.",
            "blast_radius": {"affected_agents": [], "downstream_services": [], "data_integrity_risk": False, "containment_possible": True},
            "immediate_actions": ["Investigate the failing span", "Check tool configurations"],
            "long_term_recommendations": ["Enable LLM-powered diagnosis for deeper analysis"],
            "repair_feasibility": 0.5,
        }
