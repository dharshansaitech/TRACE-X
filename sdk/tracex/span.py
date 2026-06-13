# sdk/tracex/span.py
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class SpanStatus(str, Enum):
    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class SpanKind(str, Enum):
    AGENT = "agent"
    TOOL = "tool"
    LLM = "llm"
    RETRIEVAL = "retrieval"
    EMBEDDING = "embedding"
    CHAIN = "chain"
    INTERNAL = "internal"


@dataclass
class ToolCallRecord:
    """Records a single tool invocation."""
    tool_call_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tool_name: str = ""
    tool_version: str | None = None
    input_args: dict[str, Any] = field(default_factory=dict)
    output: Any | None = None
    error: str | None = None
    started_at: datetime = field(default_factory=datetime.utcnow)
    ended_at: datetime | None = None
    duration_ms: float | None = None
    status: SpanStatus = SpanStatus.OK
    retry_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def finish(self, output: Any = None, error: str | None = None) -> None:
        """Finish this tool call record."""
        self.ended_at = datetime.utcnow()
        if self.started_at:
            self.duration_ms = (self.ended_at - self.started_at).total_seconds() * 1000
        if error:
            self.error = error
            self.status = SpanStatus.ERROR
        else:
            self.output = output
            self.status = SpanStatus.OK

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_call_id": self.tool_call_id,
            "tool_name": self.tool_name,
            "tool_version": self.tool_version,
            "input_args": self.input_args,
            "output": self.output,
            "error": self.error,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration_ms": self.duration_ms,
            "status": self.status.value,
            "retry_count": self.retry_count,
            "metadata": self.metadata,
        }


@dataclass
class SpanContext:
    """Context propagated between spans."""
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    baggage: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentSpan:
    """A single span in an agent execution trace."""
    span_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = ""
    parent_span_id: str | None = None
    agent_id: str = ""
    agent_name: str = ""
    span_name: str = ""
    kind: SpanKind = SpanKind.AGENT

    started_at: datetime = field(default_factory=datetime.utcnow)
    ended_at: datetime | None = None
    duration_ms: float | None = None

    status: SpanStatus = SpanStatus.UNKNOWN
    error_message: str | None = None
    error_type: str | None = None

    model: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    temperature: float | None = None
    input_messages: list[dict[str, Any]] = field(default_factory=list)
    output_content: str | None = None
    finish_reason: str | None = None

    tool_calls: list[ToolCallRecord] = field(default_factory=list)

    metadata: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)

    # Active tool call being recorded
    _active_tool_call: ToolCallRecord | None = field(default=None, repr=False)

    def set_input(self, data: Any) -> None:
        """Set span input data."""
        if isinstance(data, list):
            self.input_messages = data
        elif isinstance(data, dict):
            self.attributes["input"] = data
        else:
            self.attributes["input"] = str(data)

    def set_output(self, output: str) -> None:
        """Set span output content."""
        self.output_content = output

    def set_error(self, message: str, error_type: str | None = None) -> None:
        """Mark span as failed."""
        self.status = SpanStatus.ERROR
        self.error_message = message
        self.error_type = error_type

    def set_tokens(
        self,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        total_tokens: int | None = None,
    ) -> None:
        """Set token counts."""
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens or (
            (prompt_tokens or 0) + (completion_tokens or 0)
        )

    def set_model(
        self,
        model: str,
        temperature: float | None = None,
        finish_reason: str | None = None,
    ) -> None:
        """Set LLM model metadata."""
        self.model = model
        if temperature is not None:
            self.temperature = temperature
        if finish_reason:
            self.finish_reason = finish_reason

    def start_tool_call(self, tool_name: str, input_args: dict | None = None) -> ToolCallRecord:
        """Start recording a tool call."""
        tc = ToolCallRecord(
            tool_name=tool_name,
            input_args=input_args or {},
            started_at=datetime.utcnow(),
        )
        self._active_tool_call = tc
        return tc

    def finish_tool_call(
        self, output: Any = None, error: str | None = None
    ) -> ToolCallRecord | None:
        """Finish the active tool call."""
        if self._active_tool_call:
            self._active_tool_call.finish(output=output, error=error)
            self.tool_calls.append(self._active_tool_call)
            tc = self._active_tool_call
            self._active_tool_call = None
            return tc
        return None

    def finish(self, status: SpanStatus = SpanStatus.OK) -> None:
        """Mark span as complete."""
        self.ended_at = datetime.utcnow()
        self.duration_ms = (self.ended_at - self.started_at).total_seconds() * 1000
        if self.status == SpanStatus.UNKNOWN:
            self.status = status

    def to_dict(self) -> dict[str, Any]:
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "span_name": self.span_name,
            "kind": self.kind.value,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration_ms": self.duration_ms,
            "status": self.status.value,
            "error_message": self.error_message,
            "error_type": self.error_type,
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "temperature": self.temperature,
            "input_messages": self.input_messages,
            "output_content": self.output_content,
            "finish_reason": self.finish_reason,
            "tool_calls": [tc.to_dict() for tc in self.tool_calls],
            "metadata": self.metadata,
            "tags": self.tags,
            "attributes": self.attributes,
        }
