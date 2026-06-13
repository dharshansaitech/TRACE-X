# backend/api/schemas/diagnosis.py
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RootCauseCategory(str, Enum):
    PROMPT_DESIGN = "prompt_design"
    TOOL_CONFIGURATION = "tool_configuration"
    DATA_QUALITY = "data_quality"
    CONTEXT_MANAGEMENT = "context_management"
    MODEL_LIMITATION = "model_limitation"
    ORCHESTRATION_LOGIC = "orchestration_logic"
    EXTERNAL_SERVICE = "external_service"
    RESOURCE_CONSTRAINT = "resource_constraint"
    SECURITY_POLICY = "security_policy"
    UNKNOWN = "unknown"


class SeverityLevel(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ReasoningStep(BaseModel):
    """A single step in the diagnosis reasoning chain."""
    step_number: int
    hypothesis: str
    evidence: list[str] = Field(default_factory=list)
    evidence_spans: list[str] = Field(default_factory=list)  # span IDs supporting this
    confidence: float = Field(ge=0.0, le=1.0)
    conclusion: str
    eliminated_alternatives: list[str] = Field(default_factory=list)


class BlastRadius(BaseModel):
    """Estimated impact of a failure."""
    affected_agents: list[str] = Field(default_factory=list)
    affected_sessions: list[str] = Field(default_factory=list)
    affected_users_estimate: int = 0
    downstream_services: list[str] = Field(default_factory=list)
    data_integrity_risk: bool = False
    financial_impact_estimate: str | None = None
    propagation_path: list[str] = Field(default_factory=list)
    containment_possible: bool = True


class AnomalySignal(BaseModel):
    """An individual anomaly signal detected in the trace."""
    signal_type: str
    span_id: str
    description: str
    observed_value: Any | None = None
    expected_range: str | None = None
    anomaly_score: float = Field(ge=0.0, le=1.0)
    timestamp: datetime | None = None


class DiagnosisResult(BaseModel):
    """Complete diagnosis result for a failed trace."""
    diagnosis_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str
    agent_id: str

    # Timing
    diagnosed_at: datetime = Field(default_factory=datetime.utcnow)
    diagnosis_duration_ms: float | None = None

    # Core diagnosis
    root_cause_category: RootCauseCategory
    root_cause_description: str
    severity: SeverityLevel
    confidence: float = Field(ge=0.0, le=1.0)

    # Detailed analysis
    reasoning_chain: list[ReasoningStep] = Field(default_factory=list)
    anomaly_signals: list[AnomalySignal] = Field(default_factory=list)
    blast_radius: BlastRadius = Field(default_factory=BlastRadius)

    # Evidence
    failing_span_id: str | None = None
    divergence_point_span_id: str | None = None
    contributing_spans: list[str] = Field(default_factory=list)
    evidence_summary: str = ""

    # Recommendations
    immediate_actions: list[str] = Field(default_factory=list)
    long_term_recommendations: list[str] = Field(default_factory=list)
    repair_feasibility: float = Field(default=0.8, ge=0.0, le=1.0)

    # MCP data from Arize
    arize_insights: dict[str, Any] = Field(default_factory=dict)
    similar_traces: list[str] = Field(default_factory=list)  # trace IDs

    # Metadata
    model_used: str = "gemini-2.0-flash"
    raw_llm_response: str | None = None


class DiagnosisTriggerRequest(BaseModel):
    """Request to trigger diagnosis for a trace."""
    trace_id: str
    force_rediagnose: bool = False
    context: dict[str, Any] = Field(default_factory=dict)


class DiagnosisTriggerResponse(BaseModel):
    """Response after triggering diagnosis."""
    trace_id: str
    diagnosis_id: str
    status: str = "triggered"
    estimated_completion_seconds: float = 15.0
    message: str


class DiagnosisSummary(BaseModel):
    """Lightweight diagnosis summary for listings."""
    diagnosis_id: str
    trace_id: str
    root_cause_category: RootCauseCategory
    severity: SeverityLevel
    confidence: float
    diagnosed_at: datetime
    repair_feasibility: float
    one_line_summary: str
