# backend/api/schemas/dashboard.py
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AgentStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class TrendDirection(str, Enum):
    UP = "up"
    DOWN = "down"
    STABLE = "stable"


class MetricDataPoint(BaseModel):
    """A single time-series data point."""
    timestamp: datetime
    value: float
    label: str | None = None


class AgentHealthMetrics(BaseModel):
    """Health metrics for an agent."""
    error_rate: float = 0.0          # 0-1
    latency_p50_ms: float = 0.0
    latency_p95_ms: float = 0.0
    latency_p99_ms: float = 0.0
    success_rate: float = 1.0        # 0-1
    throughput_rph: float = 0.0      # requests per hour
    tool_failure_rate: float = 0.0
    hallucination_rate: float = 0.0
    staleness_events: int = 0
    context_overflow_events: int = 0


class AgentHealth(BaseModel):
    """Health summary for a single agent."""
    agent_id: str
    agent_name: str
    agent_version: str | None = None
    status: AgentStatus
    status_reason: str | None = None
    metrics: AgentHealthMetrics
    last_seen: datetime | None = None
    last_failure: datetime | None = None
    uptime_hours: float = 0.0
    open_incidents: int = 0
    resolved_incidents_24h: int = 0
    traces_24h: int = 0
    health_score: float = Field(ge=0.0, le=100.0, default=100.0)
    trend: TrendDirection = TrendDirection.STABLE
    sparkline: list[float] = Field(default_factory=list)  # last 24 data points


class IncidentSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IncidentStatus(str, Enum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    REPAIR_PENDING = "repair_pending"
    REPAIR_APPLIED = "repair_applied"
    RESOLVED = "resolved"


class IncidentSummary(BaseModel):
    """Summary of a single incident (failed trace with diagnosis)."""
    incident_id: str
    trace_id: str
    diagnosis_id: str | None = None
    repair_id: str | None = None
    agent_id: str
    agent_name: str
    title: str
    description: str
    severity: IncidentSeverity
    status: IncidentStatus
    failure_type: str
    root_cause_category: str | None = None
    started_at: datetime
    resolved_at: datetime | None = None
    duration_open_minutes: float | None = None
    affected_users: int = 0
    confidence: float | None = None


class SystemOverview(BaseModel):
    """Top-level system overview metrics."""
    total_agents: int = 0
    healthy_agents: int = 0
    degraded_agents: int = 0
    critical_agents: int = 0
    offline_agents: int = 0

    total_traces_24h: int = 0
    failed_traces_24h: int = 0
    success_rate_24h: float = 1.0
    avg_latency_ms: float = 0.0

    open_incidents: int = 0
    resolved_incidents_24h: int = 0
    pending_repairs: int = 0
    applied_repairs_24h: int = 0

    traces_per_hour: list[MetricDataPoint] = Field(default_factory=list)
    error_rate_trend: list[MetricDataPoint] = Field(default_factory=list)


class DashboardOverview(BaseModel):
    """Complete dashboard overview response."""
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    system: SystemOverview
    agent_health: list[AgentHealth] = Field(default_factory=list)
    recent_incidents: list[IncidentSummary] = Field(default_factory=list)
    top_failure_types: list[dict[str, Any]] = Field(default_factory=list)
    repair_stats: dict[str, int] = Field(default_factory=dict)
    mttr_minutes: float | None = None  # Mean Time To Repair
    mtbf_hours: float | None = None    # Mean Time Between Failures


class IncidentListResponse(BaseModel):
    """Paginated list of incidents."""
    incidents: list[IncidentSummary]
    total: int
    open_count: int
    page: int
    page_size: int
    has_next: bool
