# backend/services/firestore_service.py
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from google.cloud import firestore

from api.config import Settings
from api.schemas.dashboard import (
    AgentHealth,
    AgentHealthMetrics,
    AgentStatus,
    DashboardOverview,
    IncidentListResponse,
    IncidentSeverity,
    IncidentStatus,
    IncidentSummary,
    MetricDataPoint,
    SystemOverview,
    TrendDirection,
)
from api.schemas.diagnosis import DiagnosisResult, SeverityLevel
from api.schemas.repair import RepairArtifact, RepairStatus
from api.schemas.trace import (
    AgentTrace,
    FailureType,
    TraceFilter,
    TraceListResponse,
    TracePreview,
    TraceStatus,
)

logger = structlog.get_logger(__name__)


class FirestoreService:
    """Full Firestore CRUD service for all TRACE-X collections."""

    def __init__(self, client: firestore.AsyncClient, settings: Settings) -> None:
        self.db = client
        self.settings = settings

    # ── Collection references ─────────────────────────────────────────────

    @property
    def traces_col(self):
        return self.db.collection(self.settings.firestore_traces_collection)

    @property
    def agents_col(self):
        return self.db.collection(self.settings.firestore_agents_collection)

    @property
    def diagnoses_col(self):
        return self.db.collection(self.settings.firestore_diagnoses_collection)

    @property
    def repairs_col(self):
        return self.db.collection(self.settings.firestore_repairs_collection)

    @property
    def simulations_col(self):
        return self.db.collection(self.settings.firestore_simulations_collection)

    # ── Traces ────────────────────────────────────────────────────────────

    async def upsert_trace(self, trace: AgentTrace) -> None:
        """Upsert a trace document."""
        doc_data = trace.model_dump(mode="json")
        await self.traces_col.document(trace.trace_id).set(doc_data, merge=True)
        logger.debug("trace_upserted", trace_id=trace.trace_id)

    async def get_trace(self, trace_id: str) -> AgentTrace | None:
        """Retrieve a trace by ID."""
        doc = await self.traces_col.document(trace_id).get()
        if not doc.exists:
            return None
        try:
            return AgentTrace(**doc.to_dict())
        except Exception as exc:
            logger.error("trace_parse_error", trace_id=trace_id, error=str(exc))
            return None

    async def list_traces(self, filters: TraceFilter) -> TraceListResponse:
        """List traces with filtering and pagination."""
        query = self.traces_col.order_by("started_at", direction=firestore.Query.DESCENDING)

        if filters.agent_id:
            query = query.where("agent_id", "==", filters.agent_id)
        if filters.status:
            query = query.where("status", "==", filters.status.value)
        if filters.failure_type:
            query = query.where("failure_type", "==", filters.failure_type.value)

        # Count total (approximate)
        try:
            all_docs = [doc async for doc in query.stream()]
        except Exception as exc:
            logger.warning("firestore_list_error", error=str(exc))
            all_docs = []

        total = len(all_docs)
        start = (filters.page - 1) * filters.page_size
        end = start + filters.page_size
        page_docs = all_docs[start:end]

        previews: list[TracePreview] = []
        for doc in page_docs:
            data = doc.to_dict()
            try:
                preview = TracePreview(
                    trace_id=data["trace_id"],
                    agent_id=data["agent_id"],
                    agent_name=data.get("agent_name", "unknown"),
                    started_at=data["started_at"],
                    ended_at=data.get("ended_at"),
                    duration_ms=data.get("duration_ms"),
                    status=TraceStatus(data.get("status", "unknown")),
                    failure_type=FailureType(data.get("failure_type", "none")),
                    span_count=len(data.get("spans", [])),
                    tool_call_count=data.get("total_tool_calls", 0),
                    total_tokens=data.get("total_tokens", 0),
                    tags=data.get("tags", []),
                )
                previews.append(preview)
            except Exception as exc:
                logger.warning("trace_preview_parse_error", error=str(exc))

        return TraceListResponse(
            traces=previews,
            total=total,
            page=filters.page,
            page_size=filters.page_size,
            has_next=end < total,
        )

    async def delete_trace(self, trace_id: str) -> bool:
        """Delete a trace document."""
        doc_ref = self.traces_col.document(trace_id)
        doc = await doc_ref.get()
        if not doc.exists:
            return False
        await doc_ref.delete()
        return True

    async def get_recent_traces(self, hours: int = 24, limit: int = 100) -> list[AgentTrace]:
        """Get traces from the last N hours."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        query = (
            self.traces_col
            .where("started_at", ">=", cutoff.isoformat())
            .order_by("started_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )
        traces: list[AgentTrace] = []
        async for doc in query.stream():
            try:
                traces.append(AgentTrace(**doc.to_dict()))
            except Exception:
                pass
        return traces

    # ── Agents ────────────────────────────────────────────────────────────

    async def register_agent(self, payload: Any) -> Any:
        """Register a new agent."""
        from datetime import datetime
        data = payload.model_dump() if hasattr(payload, "model_dump") else payload
        data["registered_at"] = datetime.utcnow().isoformat()
        data["last_seen"] = datetime.utcnow().isoformat()
        data["status"] = AgentStatus.UNKNOWN.value
        await self.agents_col.document(data["agent_id"]).set(data, merge=True)
        return data

    async def get_agent(self, agent_id: str) -> Any | None:
        """Get agent by ID."""
        doc = await self.agents_col.document(agent_id).get()
        if not doc.exists:
            return None
        return doc.to_dict()

    async def list_agents(
        self,
        status_filter: AgentStatus | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> list[Any]:
        """List all agents."""
        query = self.agents_col
        try:
            docs = [doc async for doc in query.stream()]
        except Exception:
            docs = []

        agents = [doc.to_dict() for doc in docs]
        if status_filter:
            agents = [a for a in agents if a.get("status") == status_filter.value]

        start = (page - 1) * page_size
        return agents[start : start + page_size]

    async def delete_agent(self, agent_id: str) -> bool:
        """Delete an agent."""
        doc_ref = self.agents_col.document(agent_id)
        doc = await doc_ref.get()
        if not doc.exists:
            return False
        await doc_ref.delete()
        return True

    async def get_agent_health(self, agent_id: str) -> AgentHealth | None:
        """Compute health metrics for an agent from recent traces."""
        traces = await self.get_recent_traces(hours=24, limit=500)
        agent_traces = [t for t in traces if t.agent_id == agent_id]

        if not agent_traces:
            return None

        agent = await self.get_agent(agent_id)
        agent_name = agent.get("agent_name", agent_id) if agent else agent_id

        total = len(agent_traces)
        failed = sum(1 for t in agent_traces if t.status == TraceStatus.FAILURE)
        durations = [t.duration_ms for t in agent_traces if t.duration_ms]

        error_rate = failed / total if total else 0.0
        success_rate = 1.0 - error_rate
        avg_latency = sum(durations) / len(durations) if durations else 0.0
        sorted_d = sorted(durations)
        p95 = sorted_d[int(len(sorted_d) * 0.95)] if sorted_d else 0.0
        p99 = sorted_d[int(len(sorted_d) * 0.99)] if sorted_d else 0.0

        tool_failures = sum(
            1 for t in agent_traces if t.failure_type == FailureType.TOOL_ERROR
        )
        tool_failure_rate = tool_failures / total if total else 0.0

        hallucinations = sum(
            1 for t in agent_traces if t.failure_type == FailureType.HALLUCINATION
        )
        hal_rate = hallucinations / total if total else 0.0

        # Health score (0-100)
        health_score = max(0.0, 100.0 - (error_rate * 60) - (tool_failure_rate * 20) - (hal_rate * 20))

        if error_rate > 0.2:
            status = AgentStatus.CRITICAL
        elif error_rate > 0.05:
            status = AgentStatus.DEGRADED
        else:
            status = AgentStatus.HEALTHY

        last_failure = None
        failed_traces = [t for t in agent_traces if t.status == TraceStatus.FAILURE]
        if failed_traces:
            last_failure = max(t.started_at for t in failed_traces)

        return AgentHealth(
            agent_id=agent_id,
            agent_name=agent_name,
            status=status,
            metrics=AgentHealthMetrics(
                error_rate=round(error_rate, 4),
                latency_p50_ms=round(avg_latency, 2),
                latency_p95_ms=round(p95, 2),
                latency_p99_ms=round(p99, 2),
                success_rate=round(success_rate, 4),
                throughput_rph=total,
                tool_failure_rate=round(tool_failure_rate, 4),
                hallucination_rate=round(hal_rate, 4),
            ),
            last_seen=max(t.started_at for t in agent_traces),
            last_failure=last_failure,
            traces_24h=total,
            health_score=round(health_score, 1),
            trend=TrendDirection.STABLE,
            sparkline=[round(error_rate * 100, 1)] * 24,
        )

    # ── Diagnoses ─────────────────────────────────────────────────────────

    async def upsert_diagnosis(self, diagnosis: DiagnosisResult) -> DiagnosisResult:
        """Upsert a diagnosis document."""
        data = diagnosis.model_dump(mode="json")
        await self.diagnoses_col.document(diagnosis.diagnosis_id).set(data, merge=True)
        return diagnosis

    async def get_diagnosis_by_trace(self, trace_id: str) -> DiagnosisResult | None:
        """Get diagnosis for a specific trace."""
        query = self.diagnoses_col.where("trace_id", "==", trace_id).limit(1)
        async for doc in query.stream():
            try:
                return DiagnosisResult(**doc.to_dict())
            except Exception as exc:
                logger.warning("diagnosis_parse_error", error=str(exc))
        return None

    async def list_diagnoses(
        self, agent_id: str | None = None, limit: int = 20
    ) -> list[dict]:
        """List recent diagnoses."""
        query = self.diagnoses_col.order_by(
            "diagnosed_at", direction=firestore.Query.DESCENDING
        ).limit(limit)
        results = []
        async for doc in query.stream():
            data = doc.to_dict()
            if agent_id and data.get("agent_id") != agent_id:
                continue
            results.append(data)
        return results

    # ── Repairs ───────────────────────────────────────────────────────────

    async def upsert_repair(self, repair: RepairArtifact) -> RepairArtifact:
        """Upsert a repair artifact."""
        data = repair.model_dump(mode="json")
        await self.repairs_col.document(repair.repair_id).set(data, merge=True)
        return repair

    async def get_repair(self, repair_id: str) -> RepairArtifact | None:
        """Get a repair by ID."""
        doc = await self.repairs_col.document(repair_id).get()
        if not doc.exists:
            return None
        try:
            return RepairArtifact(**doc.to_dict())
        except Exception as exc:
            logger.warning("repair_parse_error", error=str(exc))
            return None

    async def get_repair_by_trace(self, trace_id: str) -> RepairArtifact | None:
        """Get the (most recent) repair generated for a specific trace."""
        query = self.repairs_col.where("trace_id", "==", trace_id).limit(1)
        async for doc in query.stream():
            try:
                return RepairArtifact(**doc.to_dict())
            except Exception as exc:
                logger.warning("repair_parse_error", error=str(exc))
        return None

    async def list_repairs(
        self,
        status_filter: RepairStatus | None = None,
        agent_id: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[RepairArtifact], int]:
        """List repairs with optional filtering."""
        query = self.repairs_col.order_by(
            "created_at", direction=firestore.Query.DESCENDING
        )
        try:
            docs = [doc async for doc in query.stream()]
        except Exception:
            docs = []

        repairs: list[RepairArtifact] = []
        for doc in docs:
            try:
                r = RepairArtifact(**doc.to_dict())
                if status_filter and r.status != status_filter:
                    continue
                if agent_id and r.agent_id != agent_id:
                    continue
                repairs.append(r)
            except Exception:
                pass

        total = len(repairs)
        start = (page - 1) * page_size
        return repairs[start : start + page_size], total

    # ── Simulations ───────────────────────────────────────────────────────

    async def upsert_simulation(self, data: dict) -> None:
        """Upsert a simulation result."""
        sim_id = data.get("simulation_id", "unknown")
        await self.simulations_col.document(sim_id).set(data, merge=True)

    async def get_simulation(self, simulation_id: str) -> dict | None:
        """Get simulation by ID."""
        doc = await self.simulations_col.document(simulation_id).get()
        if not doc.exists:
            return None
        return doc.to_dict()

    # ── Dashboard ─────────────────────────────────────────────────────────

    async def get_dashboard_overview(self) -> DashboardOverview:
        """Build the complete dashboard overview."""
        traces_24h = await self.get_recent_traces(hours=24, limit=1000)

        total_traces = len(traces_24h)
        failed_traces = sum(1 for t in traces_24h if t.status == TraceStatus.FAILURE)
        success_rate = 1.0 - (failed_traces / total_traces if total_traces else 0)

        durations = [t.duration_ms for t in traces_24h if t.duration_ms]
        avg_latency = sum(durations) / len(durations) if durations else 0.0

        # Agent health
        agent_ids = list(set(t.agent_id for t in traces_24h))
        agent_health_list: list[AgentHealth] = []
        for aid in agent_ids[:20]:  # cap at 20
            health = await self.get_agent_health(aid)
            if health:
                agent_health_list.append(health)

        healthy = sum(1 for h in agent_health_list if h.status == AgentStatus.HEALTHY)
        degraded = sum(1 for h in agent_health_list if h.status == AgentStatus.DEGRADED)
        critical = sum(1 for h in agent_health_list if h.status == AgentStatus.CRITICAL)

        # Pending repairs
        pending_repairs_list, _ = await self.list_repairs(
            status_filter=RepairStatus.PENDING
        )

        # Recent incidents (failed traces with diagnoses)
        recent_incidents: list[IncidentSummary] = []
        failed = [t for t in traces_24h if t.status == TraceStatus.FAILURE][:10]
        for trace in failed:
            diag = await self.get_diagnosis_by_trace(trace.trace_id)
            incident = IncidentSummary(
                incident_id=trace.trace_id,
                trace_id=trace.trace_id,
                diagnosis_id=diag.diagnosis_id if diag else None,
                agent_id=trace.agent_id,
                agent_name=trace.agent_name,
                title=f"{trace.failure_type.value.replace('_', ' ').title()} in {trace.agent_name}",
                description=trace.failure_reason or "Failure detected",
                severity=IncidentSeverity.HIGH
                if diag and diag.severity in (SeverityLevel.CRITICAL, SeverityLevel.HIGH)
                else IncidentSeverity.MEDIUM,
                status=IncidentStatus.INVESTIGATING if diag else IncidentStatus.OPEN,
                failure_type=trace.failure_type.value,
                root_cause_category=diag.root_cause_category.value if diag else None,
                started_at=trace.started_at,
                confidence=diag.confidence if diag else None,
            )
            recent_incidents.append(incident)

        # Failure type breakdown
        failure_counts: dict[str, int] = {}
        for t in traces_24h:
            if t.failure_type != FailureType.NONE:
                key = t.failure_type.value
                failure_counts[key] = failure_counts.get(key, 0) + 1

        top_failure_types = [
            {"type": k, "count": v}
            for k, v in sorted(failure_counts.items(), key=lambda x: -x[1])
        ]

        # Trend data (last 24 hours, hourly)
        now = datetime.utcnow()
        traces_per_hour: list[MetricDataPoint] = []
        error_rate_trend: list[MetricDataPoint] = []
        for h in range(24):
            hour_start = now - timedelta(hours=24 - h)
            hour_end = hour_start + timedelta(hours=1)
            hour_traces = [
                t for t in traces_24h
                if hour_start <= t.started_at.replace(tzinfo=None) < hour_end
            ]
            hour_errors = sum(1 for t in hour_traces if t.status == TraceStatus.FAILURE)
            traces_per_hour.append(MetricDataPoint(timestamp=hour_start, value=len(hour_traces)))
            error_rate_trend.append(
                MetricDataPoint(
                    timestamp=hour_start,
                    value=hour_errors / len(hour_traces) * 100 if hour_traces else 0.0,
                )
            )

        system = SystemOverview(
            total_agents=len(agent_ids),
            healthy_agents=healthy,
            degraded_agents=degraded,
            critical_agents=critical,
            total_traces_24h=total_traces,
            failed_traces_24h=failed_traces,
            success_rate_24h=round(success_rate, 4),
            avg_latency_ms=round(avg_latency, 2),
            open_incidents=len(failed),
            pending_repairs=len(pending_repairs_list),
            traces_per_hour=traces_per_hour,
            error_rate_trend=error_rate_trend,
        )

        return DashboardOverview(
            system=system,
            agent_health=agent_health_list,
            recent_incidents=recent_incidents,
            top_failure_types=top_failure_types,
            repair_stats={
                "pending": len(pending_repairs_list),
                "approved": 0,
                "applied": 0,
            },
        )

    async def list_incidents(
        self,
        status_filter: str | None = None,
        severity: str | None = None,
        agent_id: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> IncidentListResponse:
        """List incidents (failed traces)."""
        traces = await self.get_recent_traces(hours=168, limit=500)  # 7 days
        failed = [t for t in traces if t.status == TraceStatus.FAILURE]

        if agent_id:
            failed = [t for t in failed if t.agent_id == agent_id]

        incidents: list[IncidentSummary] = []
        for trace in failed:
            diag = await self.get_diagnosis_by_trace(trace.trace_id)
            incident = IncidentSummary(
                incident_id=trace.trace_id,
                trace_id=trace.trace_id,
                diagnosis_id=diag.diagnosis_id if diag else None,
                agent_id=trace.agent_id,
                agent_name=trace.agent_name,
                title=f"{trace.failure_type.value.replace('_', ' ').title()} in {trace.agent_name}",
                description=trace.failure_reason or "Failure detected",
                severity=IncidentSeverity.HIGH
                if diag and diag.severity in (SeverityLevel.CRITICAL, SeverityLevel.HIGH)
                else IncidentSeverity.MEDIUM,
                status=IncidentStatus.INVESTIGATING if diag else IncidentStatus.OPEN,
                failure_type=trace.failure_type.value,
                root_cause_category=diag.root_cause_category.value if diag else None,
                started_at=trace.started_at,
                confidence=diag.confidence if diag else None,
            )
            incidents.append(incident)

        if status_filter:
            incidents = [i for i in incidents if i.status.value == status_filter]
        if severity:
            incidents = [i for i in incidents if i.severity.value == severity]

        total = len(incidents)
        open_count = sum(1 for i in incidents if i.status == IncidentStatus.OPEN)
        start = (page - 1) * page_size
        page_incidents = incidents[start : start + page_size]

        return IncidentListResponse(
            incidents=page_incidents,
            total=total,
            open_count=open_count,
            page=page,
            page_size=page_size,
            has_next=(start + page_size) < total,
        )
