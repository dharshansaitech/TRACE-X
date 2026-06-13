# backend/agents/observer/agent.py
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

import structlog

from api.config import Settings
from api.schemas.diagnosis import AnomalySignal, SeverityLevel
from api.schemas.trace import AgentSpan, AgentTrace, FailureType, SpanStatus, TraceStatus
from agents.observer.prompts import (
    CLASSIFICATION_PROMPT_TEMPLATE,
    OBSERVER_SYSTEM_PROMPT,
)

logger = structlog.get_logger(__name__)


@dataclass
class ObservationResult:
    """Result from the observer agent."""
    trace_id: str
    failure_detected: bool
    confidence: float
    failure_classification: FailureType
    severity: SeverityLevel
    anomaly_signals: list[AnomalySignal] = field(default_factory=list)
    reasoning: str = ""
    affected_components: list[str] = field(default_factory=list)
    needs_detailed_diagnosis: bool = False
    duration_ms: float = 0.0


class ObserverAgent:
    """
    Observer Agent — first-pass anomaly detection and failure classification.

    Uses a combination of:
    1. Rule-based heuristics (fast, deterministic)
    2. LLM-powered classification (deep pattern matching)
    """

    def __init__(self, settings: Settings, gemini_service: Any) -> None:
        self.settings = settings
        self.gemini = gemini_service

    async def analyze(self, trace: AgentTrace) -> ObservationResult:
        """Full analysis of a trace — heuristics + LLM classification."""
        start = time.perf_counter()

        # Step 1: Fast heuristic checks
        heuristic_result = self._run_heuristics(trace)

        # Step 2: If heuristics detect failure or trace is labeled as failed,
        # run LLM classification for deep analysis
        if heuristic_result["has_failure"] or trace.status == TraceStatus.FAILURE:
            try:
                llm_result = await self._classify_with_llm(trace)
            except Exception as exc:
                logger.warning("observer_llm_failed", error=str(exc))
                llm_result = None
        else:
            llm_result = None

        duration_ms = (time.perf_counter() - start) * 1000

        # Merge results
        return self._merge_results(trace, heuristic_result, llm_result, duration_ms)

    def _run_heuristics(self, trace: AgentTrace) -> dict[str, Any]:
        """Fast rule-based anomaly detection."""
        signals = []
        failure_types = []

        # Check 1: Explicit failure status
        if trace.status == TraceStatus.FAILURE:
            failure_types.append(trace.failure_type.value)

        # Check 2: Error spans
        error_spans = [s for s in trace.spans if s.status == SpanStatus.ERROR]
        if error_spans:
            signals.append({
                "signal_type": "span_errors",
                "description": f"{len(error_spans)} spans with ERROR status",
                "anomaly_score": min(len(error_spans) / max(len(trace.spans), 1), 1.0),
            })
            failure_types.append("tool_error")

        # Check 3: Tool failure rate
        all_tool_calls = [tc for s in trace.spans for tc in s.tool_calls]
        failed_tools = [tc for tc in all_tool_calls if tc.status == SpanStatus.ERROR]
        if all_tool_calls:
            tool_failure_rate = len(failed_tools) / len(all_tool_calls)
            if tool_failure_rate > self.settings.observer_tool_failure_rate_threshold:
                signals.append({
                    "signal_type": "high_tool_failure_rate",
                    "description": f"Tool failure rate: {tool_failure_rate:.1%}",
                    "anomaly_score": min(tool_failure_rate * 2, 1.0),
                })
                failure_types.append("tool_error")

        # Check 4: High latency
        if trace.duration_ms:
            if trace.duration_ms > self.settings.observer_latency_p99_threshold_ms:
                signals.append({
                    "signal_type": "high_latency",
                    "description": f"Duration {trace.duration_ms:.0f}ms exceeds threshold",
                    "anomaly_score": min(trace.duration_ms / (self.settings.observer_latency_p99_threshold_ms * 2), 1.0),
                })

        # Check 5: Context overflow
        context_spans = [
            s for s in trace.spans
            if s.error_type and "context" in s.error_type.lower()
        ]
        if context_spans:
            signals.append({
                "signal_type": "context_overflow",
                "description": f"Context overflow detected in {len(context_spans)} spans",
                "anomaly_score": 0.9,
            })
            failure_types.append("context_overflow")

        # Check 6: Loop detection (same tool called many times)
        if all_tool_calls:
            tool_name_counts: dict[str, int] = {}
            for tc in all_tool_calls:
                tool_name_counts[tc.tool_name] = tool_name_counts.get(tc.tool_name, 0) + 1
            repeated = {k: v for k, v in tool_name_counts.items() if v > 5}
            if repeated:
                signals.append({
                    "signal_type": "tool_loop",
                    "description": f"Repeated tool calls detected: {repeated}",
                    "anomaly_score": 0.85,
                })
                failure_types.append("loop")

        # Check 7: Token threshold
        if trace.total_tokens > 100000:
            signals.append({
                "signal_type": "excessive_tokens",
                "description": f"Total tokens: {trace.total_tokens}",
                "anomaly_score": 0.6,
            })

        has_failure = len(failure_types) > 0 or len(signals) > 0
        max_score = max((s["anomaly_score"] for s in signals), default=0.0)

        return {
            "has_failure": has_failure,
            "failure_types": failure_types,
            "signals": signals,
            "max_anomaly_score": max_score,
            "error_spans": error_spans,
            "failed_tools": failed_tools,
        }

    async def _classify_with_llm(self, trace: AgentTrace) -> dict[str, Any] | None:
        """Deep LLM-based failure classification."""
        # Prepare error span summaries
        error_spans = [s for s in trace.spans if s.status == SpanStatus.ERROR]
        error_span_text = "\n".join(
            f"  - [{s.span_id[:8]}] {s.span_name}: {s.error_message or 'No message'}"
            for s in error_spans[:5]
        )

        # Tool failures
        all_tools = [tc for s in trace.spans for tc in s.tool_calls]
        failed_tools = [tc for tc in all_tools if tc.status == SpanStatus.ERROR]
        tool_failure_text = "\n".join(
            f"  - {tc.tool_name}: {tc.error or 'Unknown error'} (attempt {tc.retry_count})"
            for tc in failed_tools[:5]
        )

        # LLM output samples for hallucination check
        llm_outputs = []
        for span in trace.spans[:10]:
            if span.output_content:
                llm_outputs.append(f"  [{span.span_name}]: {span.output_content[:200]}...")
        llm_output_text = "\n".join(llm_outputs[:3])

        prompt = CLASSIFICATION_PROMPT_TEMPLATE.format(
            agent_name=trace.agent_name,
            agent_id=trace.agent_id,
            status=trace.status.value,
            duration_ms=trace.duration_ms or 0,
            span_count=len(trace.spans),
            tool_call_count=trace.total_tool_calls,
            total_tokens=trace.total_tokens,
            error_count=trace.error_count,
            failure_type=trace.failure_type.value,
            error_spans=error_span_text or "None",
            tool_failures=tool_failure_text or "None",
            llm_outputs=llm_output_text or "None",
            metadata=str(trace.metadata)[:500],
        )

        result = await self.gemini.generate_structured(
            prompt=prompt,
            system_instruction=OBSERVER_SYSTEM_PROMPT,
            temperature=0.1,
        )
        return result

    def _merge_results(
        self,
        trace: AgentTrace,
        heuristic: dict[str, Any],
        llm: dict[str, Any] | None,
        duration_ms: float,
    ) -> ObservationResult:
        """Merge heuristic and LLM results into a final observation."""

        # Determine primary failure type
        if llm and not llm.get("parse_error"):
            failure_str = llm.get("failure_classification", "none")
            try:
                failure_type = FailureType(failure_str)
            except ValueError:
                failure_type = trace.failure_type
            confidence = float(llm.get("confidence", 0.8))
            severity_str = llm.get("severity", "medium")
            try:
                severity = SeverityLevel(severity_str)
            except ValueError:
                severity = SeverityLevel.MEDIUM
            failure_detected = bool(llm.get("failure_detected", heuristic["has_failure"]))
            reasoning = llm.get("reasoning", "")
            affected = llm.get("affected_components", [])
            needs_diag = bool(llm.get("needs_detailed_diagnosis", True))
        else:
            # Fall back to heuristics
            failure_type = trace.failure_type
            if heuristic["failure_types"]:
                try:
                    failure_type = FailureType(heuristic["failure_types"][0])
                except ValueError:
                    pass
            confidence = min(heuristic["max_anomaly_score"] + 0.2, 1.0)
            severity = SeverityLevel.HIGH if confidence > 0.8 else SeverityLevel.MEDIUM
            failure_detected = heuristic["has_failure"] or trace.status == TraceStatus.FAILURE
            reasoning = f"Heuristic detection: {heuristic['failure_types']}"
            affected = []
            needs_diag = failure_detected

        # Build anomaly signals
        anomaly_signals: list[AnomalySignal] = []
        for sig in heuristic["signals"]:
            anomaly_signals.append(
                AnomalySignal(
                    signal_type=sig["signal_type"],
                    span_id=sig.get("span_id", ""),
                    description=sig["description"],
                    anomaly_score=sig["anomaly_score"],
                )
            )

        if llm and not llm.get("parse_error"):
            for sig in llm.get("anomaly_signals", []):
                anomaly_signals.append(
                    AnomalySignal(
                        signal_type=sig.get("signal_type", "unknown"),
                        span_id=sig.get("span_id") or "",
                        description=sig.get("description", ""),
                        anomaly_score=float(sig.get("anomaly_score", 0.5)),
                    )
                )

        return ObservationResult(
            trace_id=trace.trace_id,
            failure_detected=failure_detected,
            confidence=confidence,
            failure_classification=failure_type,
            severity=severity,
            anomaly_signals=anomaly_signals,
            reasoning=reasoning,
            affected_components=affected,
            needs_detailed_diagnosis=needs_diag,
            duration_ms=duration_ms,
        )
