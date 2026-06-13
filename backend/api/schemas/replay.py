# backend/api/schemas/replay.py
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class FrameType(str, Enum):
    SPAN_START = "span_start"
    SPAN_END = "span_end"
    LLM_PROMPT = "llm_prompt"
    LLM_RESPONSE = "llm_response"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    TOOL_ERROR = "tool_error"
    AGENT_DECISION = "agent_decision"
    CONTEXT_WINDOW = "context_window"
    ERROR_EVENT = "error_event"
    ANOMALY_DETECTED = "anomaly_detected"
    DIVERGENCE_POINT = "divergence_point"
    STATE_SNAPSHOT = "state_snapshot"


class ReplayAnnotation(BaseModel):
    """An annotation attached to a replay frame."""
    annotation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    annotation_type: str  # "warning", "error", "info", "diagnosis", "repair_suggestion"
    title: str
    body: str
    severity: str = "info"
    auto_generated: bool = True
    linked_diagnosis_id: str | None = None
    linked_repair_id: str | None = None


class ReplayFrame(BaseModel):
    """A single frame in the replay timeline."""
    frame_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    frame_index: int
    frame_type: FrameType
    timestamp: datetime
    relative_time_ms: float  # ms from trace start

    # Associated IDs
    span_id: str | None = None
    tool_call_id: str | None = None
    agent_id: str

    # Frame content (type-specific payload)
    content: dict[str, Any] = Field(default_factory=dict)

    # Visual state at this frame
    active_spans: list[str] = Field(default_factory=list)
    context_tokens_used: int | None = None
    context_tokens_max: int | None = None
    memory_state: dict[str, Any] = Field(default_factory=dict)

    # Annotations
    annotations: list[ReplayAnnotation] = Field(default_factory=list)
    is_failure_frame: bool = False
    is_divergence_point: bool = False


class ReplaySession(BaseModel):
    """Complete replay session built from an agent trace."""
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str
    agent_id: str
    agent_name: str

    # Timing
    trace_started_at: datetime
    trace_ended_at: datetime | None = None
    total_duration_ms: float

    # Frames
    frames: list[ReplayFrame] = Field(default_factory=list)
    total_frames: int = 0

    # Highlighted frames
    failure_frame_indices: list[int] = Field(default_factory=list)
    divergence_frame_index: int | None = None
    key_event_indices: list[int] = Field(default_factory=list)

    # Summary
    span_count: int = 0
    tool_call_count: int = 0
    llm_call_count: int = 0
    error_count: int = 0

    # Linked analysis
    diagnosis_id: str | None = None
    repair_id: str | None = None

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    replay_fps: float = 10.0


class ReplayPlaybackState(BaseModel):
    """Current playback state for a replay session."""
    session_id: str
    current_frame: int = 0
    is_playing: bool = False
    fps: float = 10.0
    loop: bool = False
    speed_multiplier: float = 1.0


class ReplayResponse(BaseModel):
    """API response for a replay session."""
    session: ReplaySession
    playback: ReplayPlaybackState
