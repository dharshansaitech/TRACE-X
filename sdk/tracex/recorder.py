# sdk/tracex/recorder.py
from __future__ import annotations

import asyncio
import contextlib
import time
import uuid
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime
from typing import Any, AsyncIterator, Iterator

import structlog

from tracex.span import AgentSpan, SpanKind, SpanStatus, ToolCallRecord

logger = structlog.get_logger(__name__)

_GLOBAL_RECORDER: "TraceRecorder | None" = None


def get_global_recorder() -> "TraceRecorder":
    global _GLOBAL_RECORDER
    if _GLOBAL_RECORDER is None:
        _GLOBAL_RECORDER = TraceRecorder()
    return _GLOBAL_RECORDER


class TraceRecorder:
    """
    Core trace recorder.
    Manages active traces, builds spans, and dispatches to exporters.
    """

    def __init__(self) -> None:
        self._initialized = False
        self._config: dict[str, Any] = {}
        self._exporter = None
        self._active_traces: dict[str, dict[str, Any]] = {}
        self._active_spans: dict[str, AgentSpan] = {}
        self._pending_traces: list[dict[str, Any]] = []
        self._flush_task: asyncio.Task | None = None

    def initialize(
        self,
        api_key: str,
        agent_id: str,
        agent_name: str,
        agent_version: str = "1.0.0",
        exporter_type: str = "http",
        endpoint: str = "http://localhost:8000/api/v1",
        pubsub_project: str | None = None,
        pubsub_topic: str = "tracex-traces",
        environment: str = "production",
        auto_flush: bool = True,
        flush_interval_seconds: float = 5.0,
        debug: bool = False,
    ) -> None:
        """Initialize the recorder."""
        self._config = {
            "api_key": api_key,
            "agent_id": agent_id,
            "agent_name": agent_name,
            "agent_version": agent_version,
            "environment": environment,
        }

        # Set up exporter
        if exporter_type == "pubsub" and pubsub_project:
            from tracex.exporters.pubsub import PubSubExporter
            self._exporter = PubSubExporter(
                project_id=pubsub_project,
                topic_name=pubsub_topic,
                api_key=api_key,
            )
        else:
            from tracex.exporters.http import HttpExporter
            self._exporter = HttpExporter(endpoint=endpoint, api_key=api_key)

        self._auto_flush = auto_flush
        self._flush_interval = flush_interval_seconds
        self._initialized = True

        if debug:
            import structlog
            structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(10))

        logger.info(
            "tracex_initialized",
            agent_id=agent_id,
            exporter=exporter_type,
            environment=environment,
        )

    def start_trace(
        self,
        input_payload: dict[str, Any] | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
        tags: list[str] | None = None,
    ) -> str:
        """Start a new trace and return trace_id."""
        trace_id = str(uuid.uuid4())
        self._active_traces[trace_id] = {
            "trace_id": trace_id,
            "agent_id": self._config.get("agent_id", "unknown"),
            "agent_name": self._config.get("agent_name", "unknown"),
            "agent_version": self._config.get("agent_version", "1.0.0"),
            "started_at": datetime.utcnow().isoformat(),
            "ended_at": None,
            "status": "running",
            "failure_type": "none",
            "failure_reason": None,
            "spans": [],
            "input_payload": input_payload or {},
            "output_payload": {},
            "total_tokens": 0,
            "total_tool_calls": 0,
            "error_count": 0,
            "llm_calls": 0,
            "session_id": session_id,
            "user_id": user_id,
            "environment": self._config.get("environment", "production"),
            "tags": tags or [],
            "metadata": {},
        }
        return trace_id

    def finish_trace(
        self,
        trace_id: str,
        output_payload: dict[str, Any] | None = None,
        status: str = "success",
        failure_type: str = "none",
        failure_reason: str | None = None,
    ) -> None:
        """Finish a trace and queue it for export."""
        trace = self._active_traces.pop(trace_id, None)
        if not trace:
            logger.warning("finish_trace_not_found", trace_id=trace_id)
            return

        trace["ended_at"] = datetime.utcnow().isoformat()
        trace["status"] = status
        trace["failure_type"] = failure_type
        trace["failure_reason"] = failure_reason
        if output_payload:
            trace["output_payload"] = output_payload

        # Compute duration
        from datetime import datetime as dt
        started = dt.fromisoformat(trace["started_at"])
        ended = dt.fromisoformat(trace["ended_at"])
        trace["duration_ms"] = (ended - started).total_seconds() * 1000

        self._pending_traces.append(trace)
        logger.debug("trace_finished", trace_id=trace_id, status=status)

        # Auto-flush if enabled
        if self._auto_flush:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self._flush_if_ready())
            except RuntimeError:
                pass

    def add_span(self, trace_id: str, span: AgentSpan) -> None:
        """Add a completed span to a trace."""
        trace = self._active_traces.get(trace_id)
        if not trace:
            return

        span_dict = span.to_dict()
        trace["spans"].append(span_dict)
        trace["total_tokens"] += span.total_tokens or 0
        trace["total_tool_calls"] += len(span.tool_calls)
        if span.status == SpanStatus.ERROR:
            trace["error_count"] += 1
        if span.model:
            trace["llm_calls"] += 1

    @asynccontextmanager
    async def create_span(
        self,
        name: str,
        kind: str = "agent",
        trace_id: str | None = None,
        parent_span_id: str | None = None,
    ) -> AsyncIterator[AgentSpan]:
        """Async context manager for creating a span."""
        # Auto-create trace if needed
        actual_trace_id = trace_id
        created_trace = False
        if not actual_trace_id:
            actual_trace_id = self.start_trace()
            created_trace = True

        try:
            span_kind = SpanKind(kind)
        except ValueError:
            span_kind = SpanKind.AGENT

        span = AgentSpan(
            trace_id=actual_trace_id,
            parent_span_id=parent_span_id,
            agent_id=self._config.get("agent_id", "unknown"),
            agent_name=self._config.get("agent_name", "unknown"),
            span_name=name,
            kind=span_kind,
            started_at=datetime.utcnow(),
            status=SpanStatus.UNKNOWN,
        )
        self._active_spans[span.span_id] = span

        try:
            yield span
            if span.status == SpanStatus.UNKNOWN:
                span.finish(SpanStatus.OK)
        except Exception as exc:
            span.set_error(str(exc), type(exc).__name__)
            span.finish(SpanStatus.ERROR)
            raise
        finally:
            span_copy = span
            if actual_trace_id:
                self.add_span(actual_trace_id, span_copy)
            self._active_spans.pop(span.span_id, None)

            if created_trace:
                self.finish_trace(
                    actual_trace_id,
                    status="failure" if span.status == SpanStatus.ERROR else "success",
                    failure_type="tool_error" if span.status == SpanStatus.ERROR else "none",
                )

    @contextmanager
    def create_span_sync(
        self,
        name: str,
        kind: str = "agent",
        trace_id: str | None = None,
    ) -> Iterator[AgentSpan]:
        """Sync context manager for creating a span."""
        actual_trace_id = trace_id
        created_trace = False
        if not actual_trace_id:
            actual_trace_id = self.start_trace()
            created_trace = True

        try:
            span_kind = SpanKind(kind)
        except ValueError:
            span_kind = SpanKind.AGENT

        span = AgentSpan(
            trace_id=actual_trace_id,
            agent_id=self._config.get("agent_id", "unknown"),
            agent_name=self._config.get("agent_name", "unknown"),
            span_name=name,
            kind=span_kind,
            started_at=datetime.utcnow(),
            status=SpanStatus.UNKNOWN,
        )

        try:
            yield span
            if span.status == SpanStatus.UNKNOWN:
                span.finish(SpanStatus.OK)
        except Exception as exc:
            span.set_error(str(exc), type(exc).__name__)
            span.finish(SpanStatus.ERROR)
            raise
        finally:
            if actual_trace_id:
                self.add_span(actual_trace_id, span)
            if created_trace:
                self.finish_trace(
                    actual_trace_id,
                    status="failure" if span.status == SpanStatus.ERROR else "success",
                )

    def wrap(self, agent_callable: Any, name: str | None = None) -> "AgentWrapper":
        """Wrap a callable with instrumentation."""
        return AgentWrapper(
            wrapped=agent_callable,
            recorder=self,
            name=name or getattr(agent_callable, "__name__", "wrapped_agent"),
        )

    async def flush(self) -> None:
        """Export all pending traces."""
        if not self._exporter or not self._pending_traces:
            return

        traces_to_send = self._pending_traces.copy()
        self._pending_traces.clear()

        for trace in traces_to_send:
            try:
                await self._exporter.export(trace)
            except Exception as exc:
                logger.error("export_failed", error=str(exc))
                # Re-queue on failure
                self._pending_traces.append(trace)

    async def _flush_if_ready(self) -> None:
        """Flush if there are enough pending traces."""
        if len(self._pending_traces) >= 1:
            await self.flush()

    async def shutdown(self) -> None:
        """Flush and clean up."""
        await self.flush()
        if self._flush_task:
            self._flush_task.cancel()
        logger.info("tracex_shutdown")


class AgentWrapper:
    """
    Wraps an agent callable with transparent TRACE-X instrumentation.
    """

    def __init__(self, wrapped: Any, recorder: TraceRecorder, name: str) -> None:
        self._wrapped = wrapped
        self._recorder = recorder
        self._name = name

    async def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Async invocation with tracing."""
        trace_id = self._recorder.start_trace(
            input_payload={"args": str(args)[:500], "kwargs": str(kwargs)[:500]},
        )
        async with self._recorder.create_span(self._name, trace_id=trace_id) as span:
            try:
                if asyncio.iscoroutinefunction(self._wrapped):
                    result = await self._wrapped(*args, **kwargs)
                else:
                    result = self._wrapped(*args, **kwargs)
                span.set_output(str(result)[:1000])
                self._recorder.finish_trace(trace_id, status="success")
                return result
            except Exception as exc:
                self._recorder.finish_trace(
                    trace_id,
                    status="failure",
                    failure_reason=str(exc),
                )
                raise

    def __getattr__(self, name: str) -> Any:
        """Proxy attribute access to the wrapped object."""
        return getattr(self._wrapped, name)


# Global recorder instance
_global_recorder = get_global_recorder()
