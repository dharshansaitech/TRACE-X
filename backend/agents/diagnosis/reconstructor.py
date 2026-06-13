# backend/agents/diagnosis/reconstructor.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import structlog

from api.schemas.trace import AgentSpan, AgentTrace, SpanStatus, ToolCallRecord

logger = structlog.get_logger(__name__)


@dataclass
class DivergencePoint:
    """The point in execution where the trace diverged from expected behavior."""
    span_id: str
    span_name: str
    timestamp: datetime
    divergence_type: str
    description: str
    relative_time_ms: float
    confidence: float = 0.8
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionGraph:
    """Reconstructed execution graph from trace spans."""
    trace_id: str
    root_spans: list[str] = field(default_factory=list)
    children: dict[str, list[str]] = field(default_factory=dict)
    span_map: dict[str, AgentSpan] = field(default_factory=dict)
    critical_path: list[str] = field(default_factory=list)
    divergence_points: list[DivergencePoint] = field(default_factory=list)


class TraceReconstructor:
    """
    Reconstructs agent execution from trace spans.
    Detects divergence points where execution deviated from expected behavior.
    """

    def __init__(self) -> None:
        pass

    def reconstruct(self, trace: AgentTrace) -> ExecutionGraph:
        """Build an execution graph from trace spans."""
        graph = ExecutionGraph(trace_id=trace.trace_id)

        # Index spans
        for span in trace.spans:
            graph.span_map[span.span_id] = span
            if span.parent_span_id is None:
                graph.root_spans.append(span.span_id)
            else:
                if span.parent_span_id not in graph.children:
                    graph.children[span.parent_span_id] = []
                graph.children[span.parent_span_id].append(span.span_id)

        # Find critical path (longest path through the graph)
        graph.critical_path = self._find_critical_path(graph)

        # Detect divergence points
        graph.divergence_points = self._detect_divergence_points(trace, graph)

        return graph

    def _find_critical_path(self, graph: ExecutionGraph) -> list[str]:
        """Find the critical execution path (longest sequence by duration)."""
        if not graph.root_spans:
            return []

        def dfs(span_id: str) -> list[str]:
            children = graph.children.get(span_id, [])
            if not children:
                return [span_id]

            # Find child with longest subtree duration
            best_child_path: list[str] = []
            best_duration = -1.0

            for child_id in children:
                child_path = dfs(child_id)
                total_duration = sum(
                    graph.span_map[sid].duration_ms or 0
                    for sid in child_path
                    if sid in graph.span_map
                )
                if total_duration > best_duration:
                    best_duration = total_duration
                    best_child_path = child_path

            return [span_id] + best_child_path

        all_paths = [dfs(root) for root in graph.root_spans]
        if not all_paths:
            return []

        return max(all_paths, key=len)

    def _detect_divergence_points(
        self, trace: AgentTrace, graph: ExecutionGraph
    ) -> list[DivergencePoint]:
        """Detect where execution diverged from expected behavior."""
        divergences: list[DivergencePoint] = []
        trace_start = trace.started_at

        for span in sorted(trace.spans, key=lambda s: s.started_at):
            relative_ms = (span.started_at - trace_start).total_seconds() * 1000

            # Pattern 1: Error span
            if span.status == SpanStatus.ERROR:
                divergences.append(
                    DivergencePoint(
                        span_id=span.span_id,
                        span_name=span.span_name,
                        timestamp=span.started_at,
                        divergence_type="span_error",
                        description=f"Span '{span.span_name}' failed: {span.error_message}",
                        relative_time_ms=relative_ms,
                        confidence=0.95,
                    )
                )

            # Pattern 2: Excessive retries
            for tool_call in span.tool_calls:
                if tool_call.retry_count > 2:
                    tc_relative = (tool_call.started_at - trace_start).total_seconds() * 1000
                    divergences.append(
                        DivergencePoint(
                            span_id=span.span_id,
                            span_name=f"{span.span_name}/{tool_call.tool_name}",
                            timestamp=tool_call.started_at,
                            divergence_type="excessive_retries",
                            description=f"Tool '{tool_call.tool_name}' required {tool_call.retry_count} retries",
                            relative_time_ms=tc_relative,
                            confidence=0.8,
                        )
                    )

                # Pattern 3: Tool error
                if tool_call.status == SpanStatus.ERROR and tool_call.error:
                    tc_relative = (tool_call.started_at - trace_start).total_seconds() * 1000
                    divergences.append(
                        DivergencePoint(
                            span_id=span.span_id,
                            span_name=f"{span.span_name}/{tool_call.tool_name}",
                            timestamp=tool_call.started_at,
                            divergence_type="tool_error",
                            description=f"Tool error: {tool_call.error[:200]}",
                            relative_time_ms=tc_relative,
                            confidence=0.9,
                        )
                    )

            # Pattern 4: Token budget exhaustion signal
            if span.total_tokens and span.total_tokens > 100000:
                divergences.append(
                    DivergencePoint(
                        span_id=span.span_id,
                        span_name=span.span_name,
                        timestamp=span.started_at,
                        divergence_type="token_exhaustion",
                        description=f"Span consumed {span.total_tokens} tokens",
                        relative_time_ms=relative_ms,
                        confidence=0.7,
                    )
                )

            # Pattern 5: Abnormal finish reason
            if span.finish_reason and span.finish_reason not in ("stop", "end_turn", None):
                divergences.append(
                    DivergencePoint(
                        span_id=span.span_id,
                        span_name=span.span_name,
                        timestamp=span.started_at,
                        divergence_type="abnormal_finish",
                        description=f"Abnormal finish reason: {span.finish_reason}",
                        relative_time_ms=relative_ms,
                        confidence=0.85,
                        context={"finish_reason": span.finish_reason},
                    )
                )

        # Sort by time, return earliest first
        divergences.sort(key=lambda d: d.relative_time_ms)
        return divergences

    def get_span_timeline_text(self, trace: AgentTrace) -> str:
        """Format spans as a readable timeline for LLM prompts."""
        lines = []
        trace_start = trace.started_at

        for i, span in enumerate(
            sorted(trace.spans, key=lambda s: s.started_at)[:20]
        ):
            rel_ms = (span.started_at - trace_start).total_seconds() * 1000
            status_emoji = "✓" if span.status.value == "ok" else "✗"
            duration = f"{span.duration_ms:.0f}ms" if span.duration_ms else "?ms"
            tools = f", tools: {len(span.tool_calls)}" if span.tool_calls else ""
            lines.append(
                f"  [{i+1}] {status_emoji} +{rel_ms:.0f}ms | {span.span_name} "
                f"({duration}{tools})"
                + (f" ERR: {span.error_message[:80]}" if span.error_message else "")
            )

        return "\n".join(lines)

    def get_tool_chain_text(self, trace: AgentTrace) -> str:
        """Format tool calls as readable chain for LLM prompts."""
        lines = []
        for span in trace.spans:
            for tc in span.tool_calls:
                status = "OK" if tc.status.value == "ok" else "FAIL"
                retries = f" ({tc.retry_count} retries)" if tc.retry_count else ""
                duration = f"{tc.duration_ms:.0f}ms" if tc.duration_ms else "?ms"
                lines.append(
                    f"  [{status}] {tc.tool_name}{retries} → {duration}"
                    + (f"\n    Error: {tc.error[:100]}" if tc.error else "")
                    + (f"\n    Input: {str(tc.input_args)[:100]}" if tc.input_args else "")
                )

        return "\n".join(lines[:15]) if lines else "No tool calls"

    def get_llm_interactions_text(self, trace: AgentTrace) -> str:
        """Format LLM interactions for prompts."""
        lines = []
        for span in trace.spans:
            if span.model and span.output_content:
                tokens = f"({span.total_tokens or 0} tokens)"
                lines.append(
                    f"  Model: {span.model} {tokens}\n"
                    f"  Output: {(span.output_content or '')[:300]}...\n"
                    f"  Finish: {span.finish_reason or 'unknown'}\n"
                )
        return "\n".join(lines[:5]) if lines else "No LLM interactions recorded"
