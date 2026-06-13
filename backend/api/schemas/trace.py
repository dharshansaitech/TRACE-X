# backend/api/schemas/trace.py
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


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


class ToolCallRecord(BaseModel):
    """Record of a single tool invocation within an agent span."""
    tool_call_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tool_name: str
    tool_version: str | None = None
    input_args: dict[str, Any] = Field(default_factory=dict)
    output: Any | None = None
    error: str | None = None
    started_at: datetime
    ended_at: datetime | None = None
    duration_ms: float | None = None
    status: SpanStatus = SpanStatus.OK
    retry_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("duration_ms", mode="before")
    @classmethod
    def compute_duration(cls, v: float | None, info: Any) -> float | None:
        if v is not None:
            return v
        data = info.data
        started = data.get("started_at")
        ended = data.get("ended_at")
        if started and ended:
            delta = (ended - started).total_seconds() * 1000
            return round(delta, 2)
        return None


class AgentSpan(BaseModel):
    """A single span within an agent execution trace."""
    span_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str
    parent_span_id: str | None = None
    agent_id: str
    agent_name: str
    span_name: str
    kind: SpanKind = SpanKind.AGENT

    # Timing
    started_at: datetime
    ended_at: datetime | None = None
    duration_ms: float | None = None

    # Status
    status: SpanStatus = SpanStatus.OK
    error_message: str | None = None
    error_type: str | None = None

    # LLM specifics
    model: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    temperature: float | None = None
    input_messages: list[dict[str, Any]] = Field(default_factory=list)
    output_content: str | None = None
    finish_reason: str | None = None

    # Tool calls
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)

    # Context
    metadata: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)


class TraceStatus(str, Enum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class FailureType(str, Enum):
    TOOL_ERROR = "tool_error"
    HALLUCINATION = "hallucination"
    STALENESS = "staleness"
    LOOP = "loop"
    TIMEOUT = "timeout"
    CONTEXT_OVERFLOW = "context_overflow"
    SAFETY_VIOLATION = "safety_violation"
    PLANNING_FAILURE = "planning_failure"
    RETRIEVAL_FAILURE = "retrieval_failure"
    NONE = "none"


class AgentTrace(BaseModel):
    """Complete execution trace for an agent run."""
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str
    agent_name: str
    agent_version: str | None = None

    # Execution
    started_at: datetime
    ended_at: datetime | None = None
    duration_ms: float | None = None

    # Status
    status: TraceStatus = TraceStatus.UNKNOWN
    failure_type: FailureType = FailureType.NONE
    failure_reason: str | None = None

    # Spans
    spans: list[AgentSpan] = Field(default_factory=list)

    # Input/Output
    input_payload: dict[str, Any] = Field(default_factory=dict)
    output_payload: dict[str, Any] = Field(default_factory=dict)

    # Metrics
    total_tokens: int = 0
    total_tool_calls: int = 0
    error_count: int = 0
    llm_calls: int = 0

    # Session context
    session_id: str | None = None
    user_id: str | None = None
    environment: str = "production"

    # Tags and metadata
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TraceIngestRequest(BaseModel):
    """Request body for ingesting a new trace."""
    trace: AgentTrace
    source: str = "sdk"
    sdk_version: str | None = None


class TraceIngestResponse(BaseModel):
    """Response after successful trace ingestion."""
    trace_id: str
    status: str = "accepted"
    message: str = "Trace ingested successfully"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class TracePreview(BaseModel):
    """Lightweight preview for trace listing."""
    trace_id: str
    agent_id: str
    agent_name: str
    started_at: datetime
    ended_at: datetime | None = None
    duration_ms: float | None = None
    status: TraceStatus
    failure_type: FailureType
    span_count: int
    tool_call_count: int
    total_tokens: int
    has_diagnosis: bool = False
    has_repair: bool = False
    tags: list[str] = Field(default_factory=list)


class TraceListResponse(BaseModel):
    """Paginated list of trace previews."""
    traces: list[TracePreview]
    total: int
    page: int
    page_size: int
    has_next: bool


class TraceFilter(BaseModel):
    """Filters for trace queries."""
    agent_id: str | None = None
    status: TraceStatus | None = None
    failure_type: FailureType | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    min_duration_ms: float | None = None
    max_duration_ms: float | None = None
    tags: list[str] = Field(default_factory=list)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
