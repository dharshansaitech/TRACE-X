# backend/replay/engine.py
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import structlog

from api.schemas.diagnosis import DiagnosisResult
from api.schemas.replay import (
    FrameType,
    ReplayAnnotation,
    ReplayFrame,
    ReplaySession,
)
from api.schemas.trace import AgentSpan, AgentTrace, SpanStatus, SpanKind, ToolCallRecord

logger = structlog.get_logger(__name__)


class ReplayEngine:
    """
    Builds a ReplaySession from an AgentTrace.

    Creates a frame for every meaningful event:
    - Span start/end
    - LLM prompt/response
    - Tool call/result/error
    - Agent decisions
    - Error events
    - Annotated with diagnosis insights
    """

    def build_session(
        self,
        trace: AgentTrace,
        diagnosis: DiagnosisResult | None = None,
    ) -> ReplaySession:
        """Build a complete replay session from trace + optional diagnosis."""
        logger.info("replay_build_start", trace_id=trace.trace_id)

        trace_start = trace.started_at
        trace_end = trace.ended_at

        # Calculate total duration
        if trace_end:
            total_duration_ms = (trace_end - trace_start).total_seconds() * 1000
        else:
            total_duration_ms = trace.duration_ms or 0.0

        frames: list[ReplayFrame] = []
        frame_index = 0

        # Track active spans at each frame
        active_spans: set[str] = set()

        # Sort spans by start time
        sorted_spans = sorted(trace.spans, key=lambda s: s.started_at)

        # Collect all events with timestamps
        events: list[tuple[datetime, str, Any]] = []

        for span in sorted_spans:
            events.append((span.started_at, "span_start", span))
            if span.ended_at:
                events.append((span.ended_at, "span_end", span))

            # LLM events
            if span.input_messages:
                events.append((span.started_at, "llm_prompt", span))
            if span.output_content:
                output_time = span.ended_at or span.started_at
                events.append((output_time, "llm_response", span))

            # Tool call events
            for tc in span.tool_calls:
                events.append((tc.started_at, "tool_call", (span, tc)))
                if tc.ended_at:
                    event_type = "tool_error" if tc.status == SpanStatus.ERROR else "tool_result"
                    events.append((tc.ended_at, event_type, (span, tc)))

            # Error events
            if span.status == SpanStatus.ERROR:
                events.append((span.ended_at or span.started_at, "error_event", span))

        # Sort all events by timestamp
        events.sort(key=lambda e: e[0])

        # Find failure frames
        failure_frames: list[int] = []
        divergence_frame: int | None = None

        # Get divergence point span ID from diagnosis
        divergence_span_id = None
        if diagnosis and diagnosis.divergence_point_span_id:
            divergence_span_id = diagnosis.divergence_point_span_id

        for event_time, event_type, data in events:
            relative_ms = (event_time - trace_start).total_seconds() * 1000

            frame = self._build_frame(
                frame_index=frame_index,
                event_type=event_type,
                data=data,
                event_time=event_time,
                relative_ms=relative_ms,
                active_spans=list(active_spans),
                trace=trace,
                diagnosis=diagnosis,
                divergence_span_id=divergence_span_id,
            )

            if event_type == "span_start":
                span = data
                active_spans.add(span.span_id)
            elif event_type == "span_end":
                span = data
                active_spans.discard(span.span_id)

            # Track failure frames
            if frame.is_failure_frame:
                failure_frames.append(frame_index)
            if frame.is_divergence_point and divergence_frame is None:
                divergence_frame = frame_index

            frames.append(frame)
            frame_index += 1

        # Add final state frame
        if frames:
            frames.append(self._build_final_frame(
                frame_index=frame_index,
                trace=trace,
                diagnosis=diagnosis,
                relative_ms=total_duration_ms,
            ))

        # Find key events (tool calls, errors, divergence)
        key_events = [
            i for i, f in enumerate(frames)
            if f.frame_type in (
                FrameType.ERROR_EVENT,
                FrameType.TOOL_ERROR,
                FrameType.DIVERGENCE_POINT,
                FrameType.ANOMALY_DETECTED,
            )
        ]

        session = ReplaySession(
            session_id=str(uuid.uuid4()),
            trace_id=trace.trace_id,
            agent_id=trace.agent_id,
            agent_name=trace.agent_name,
            trace_started_at=trace_start,
            trace_ended_at=trace_end,
            total_duration_ms=total_duration_ms,
            frames=frames,
            total_frames=len(frames),
            failure_frame_indices=failure_frames,
            divergence_frame_index=divergence_frame,
            key_event_indices=key_events[:10],
            span_count=len(sorted_spans),
            tool_call_count=trace.total_tool_calls,
            llm_call_count=trace.llm_calls,
            error_count=trace.error_count,
            diagnosis_id=diagnosis.diagnosis_id if diagnosis else None,
        )

        logger.info(
            "replay_build_complete",
            trace_id=trace.trace_id,
            total_frames=len(frames),
            failure_frames=len(failure_frames),
        )
        return session

    def _build_frame(
        self,
        frame_index: int,
        event_type: str,
        data: Any,
        event_time: datetime,
        relative_ms: float,
        active_spans: list[str],
        trace: AgentTrace,
        diagnosis: DiagnosisResult | None,
        divergence_span_id: str | None,
    ) -> ReplayFrame:
        """Build a single replay frame."""
        annotations: list[ReplayAnnotation] = []
        is_failure = False
        is_divergence = False
        content: dict[str, Any] = {}
        span_id: str | None = None
        tool_call_id: str | None = None

        if event_type == "span_start":
            span: AgentSpan = data
            span_id = span.span_id
            frame_type = FrameType.SPAN_START
            content = {
                "span_name": span.span_name,
                "kind": span.kind.value,
                "model": span.model,
                "tags": span.tags,
            }

        elif event_type == "span_end":
            span: AgentSpan = data
            span_id = span.span_id
            frame_type = FrameType.SPAN_END
            content = {
                "span_name": span.span_name,
                "status": span.status.value,
                "duration_ms": span.duration_ms,
                "tokens": span.total_tokens,
            }
            if span.status == SpanStatus.ERROR:
                is_failure = True

        elif event_type == "llm_prompt":
            span: AgentSpan = data
            span_id = span.span_id
            frame_type = FrameType.LLM_PROMPT
            content = {
                "model": span.model,
                "message_count": len(span.input_messages),
                "messages": span.input_messages[-3:] if span.input_messages else [],
                "prompt_tokens": span.prompt_tokens,
            }

        elif event_type == "llm_response":
            span: AgentSpan = data
            span_id = span.span_id
            frame_type = FrameType.LLM_RESPONSE
            content = {
                "model": span.model,
                "output": (span.output_content or "")[:500],
                "completion_tokens": span.completion_tokens,
                "finish_reason": span.finish_reason,
                "total_tokens": span.total_tokens,
            }

        elif event_type == "tool_call":
            span, tc = data
            span_id = span.span_id
            tool_call_id = tc.tool_call_id
            frame_type = FrameType.TOOL_CALL
            content = {
                "tool_name": tc.tool_name,
                "input_args": tc.input_args,
                "tool_version": tc.tool_version,
            }

        elif event_type == "tool_result":
            span, tc = data
            span_id = span.span_id
            tool_call_id = tc.tool_call_id
            frame_type = FrameType.TOOL_RESULT
            content = {
                "tool_name": tc.tool_name,
                "output": tc.output,
                "duration_ms": tc.duration_ms,
            }

        elif event_type == "tool_error":
            span, tc = data
            span_id = span.span_id
            tool_call_id = tc.tool_call_id
            frame_type = FrameType.TOOL_ERROR
            is_failure = True
            content = {
                "tool_name": tc.tool_name,
                "error": tc.error,
                "retry_count": tc.retry_count,
                "duration_ms": tc.duration_ms,
            }
            annotations.append(
                ReplayAnnotation(
                    annotation_type="error",
                    title=f"Tool Error: {tc.tool_name}",
                    body=tc.error or "Unknown error",
                    severity="error",
                )
            )

        elif event_type == "error_event":
            span: AgentSpan = data
            span_id = span.span_id
            frame_type = FrameType.ERROR_EVENT
            is_failure = True
            content = {
                "span_name": span.span_name,
                "error_message": span.error_message,
                "error_type": span.error_type,
            }
            annotations.append(
                ReplayAnnotation(
                    annotation_type="error",
                    title=f"Span Error: {span.span_name}",
                    body=span.error_message or "Unknown error",
                    severity="error",
                )
            )

        else:
            frame_type = FrameType.STATE_SNAPSHOT
            content = {"event_type": event_type}

        # Check if this is the divergence point
        if span_id and span_id == divergence_span_id:
            is_divergence = True
            frame_type = FrameType.DIVERGENCE_POINT
            if diagnosis:
                annotations.append(
                    ReplayAnnotation(
                        annotation_type="diagnosis",
                        title="Divergence Point",
                        body=f"Root cause: {diagnosis.root_cause_description[:200]}",
                        severity="warning",
                        auto_generated=True,
                        linked_diagnosis_id=diagnosis.diagnosis_id,
                    )
                )

        return ReplayFrame(
            frame_id=str(uuid.uuid4()),
            frame_index=frame_index,
            frame_type=frame_type,
            timestamp=event_time,
            relative_time_ms=relative_ms,
            span_id=span_id,
            tool_call_id=tool_call_id,
            agent_id=trace.agent_id,
            content=content,
            active_spans=active_spans,
            annotations=annotations,
            is_failure_frame=is_failure,
            is_divergence_point=is_divergence,
        )

    def _build_final_frame(
        self,
        frame_index: int,
        trace: AgentTrace,
        diagnosis: DiagnosisResult | None,
        relative_ms: float,
    ) -> ReplayFrame:
        """Build the final summary frame."""
        annotations = []
        if diagnosis:
            annotations.append(
                ReplayAnnotation(
                    annotation_type="diagnosis",
                    title="Root Cause Analysis",
                    body=diagnosis.root_cause_description,
                    severity="info",
                    auto_generated=True,
                    linked_diagnosis_id=diagnosis.diagnosis_id,
                )
            )

        return ReplayFrame(
            frame_id=str(uuid.uuid4()),
            frame_index=frame_index,
            frame_type=FrameType.STATE_SNAPSHOT,
            timestamp=trace.ended_at or trace.started_at,
            relative_time_ms=relative_ms,
            agent_id=trace.agent_id,
            content={
                "type": "trace_complete",
                "status": trace.status.value,
                "total_spans": len(trace.spans),
                "total_tokens": trace.total_tokens,
                "total_tool_calls": trace.total_tool_calls,
            },
            active_spans=[],
            annotations=annotations,
            is_failure_frame=trace.status.value == "failure",
        )
