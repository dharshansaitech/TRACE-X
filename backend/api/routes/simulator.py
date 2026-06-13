# backend/api/routes/simulator.py
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from api.dependencies import ApiKeyDep, get_firestore_service

logger = structlog.get_logger(__name__)
router = APIRouter()


class SimulationPreset(str, Enum):
    NORMAL = "normal"
    HIGH_LOAD = "high_load"
    TOOL_FAILURE = "tool_failure"
    STALE_DATA = "stale_data"
    HALLUCINATION = "hallucination"
    CASCADING_FAILURE = "cascading_failure"
    NETWORK_PARTITION = "network_partition"
    CONTEXT_OVERFLOW = "context_overflow"
    CUSTOM = "custom"


class WhatIfVariable(BaseModel):
    name: str
    current_value: Any
    what_if_value: Any
    description: str = ""


class SimulationRequest(BaseModel):
    trace_id: str | None = None
    agent_id: str | None = None
    preset: SimulationPreset = SimulationPreset.NORMAL
    what_if_variables: list[WhatIfVariable] = Field(default_factory=list)
    iterations: int = Field(default=10, ge=1, le=100)
    timeout_seconds: float = Field(default=60.0, ge=1.0, le=300.0)
    description: str | None = None


class SimulationMetrics(BaseModel):
    success_rate: float
    avg_latency_ms: float
    p95_latency_ms: float
    error_rate: float
    tool_failure_rate: float
    estimated_cost_usd: float
    hallucination_probability: float


class SimulationResult(BaseModel):
    simulation_id: str
    trace_id: str | None = None
    agent_id: str | None = None
    preset: SimulationPreset
    status: str  # "running", "completed", "failed"
    started_at: datetime
    completed_at: datetime | None = None
    iterations_completed: int = 0
    baseline_metrics: SimulationMetrics | None = None
    what_if_metrics: SimulationMetrics | None = None
    comparison: dict[str, Any] = Field(default_factory=dict)
    insights: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    risk_assessment: str = "unknown"


@router.post(
    "/simulate",
    response_model=SimulationResult,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Run a What-If simulation",
)
async def run_simulation(
    payload: SimulationRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    _key: ApiKeyDep = None,
    firestore_svc=Depends(get_firestore_service),
) -> SimulationResult:
    """
    Run a What-If simulation with modified parameters.
    Returns initial result immediately and runs simulation in background.
    """
    simulation_id = str(uuid.uuid4())

    # Fetch trace context if provided
    trace = None
    if payload.trace_id:
        trace = await firestore_svc.get_trace(payload.trace_id)
        if not trace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Trace {payload.trace_id} not found",
            )

    # Create initial result
    result = SimulationResult(
        simulation_id=simulation_id,
        trace_id=payload.trace_id,
        agent_id=payload.agent_id or (trace.agent_id if trace else None),
        preset=payload.preset,
        status="running",
        started_at=datetime.utcnow(),
    )

    # Save initial state
    await firestore_svc.upsert_simulation(result.model_dump())

    async def run_in_background():
        try:
            from simulator.what_if_engine import WhatIfEngine
            engine = WhatIfEngine()
            completed = await engine.run_simulation(
                trace=trace,
                preset=payload.preset,
                variables=payload.what_if_variables,
                iterations=payload.iterations,
            )
            completed.simulation_id = simulation_id
            completed.status = "completed"
            completed.completed_at = datetime.utcnow()
            await firestore_svc.upsert_simulation(completed.model_dump())

            # Broadcast result
            ws_manager = request.app.state.ws_manager
            await ws_manager.broadcast_to_channel(
                "traces",
                {
                    "type": "simulation_complete",
                    "simulation_id": simulation_id,
                    "preset": payload.preset,
                    "success_rate": completed.what_if_metrics.success_rate
                    if completed.what_if_metrics
                    else None,
                },
            )
        except Exception as exc:
            logger.error("simulation_failed", simulation_id=simulation_id, error=str(exc))

    background_tasks.add_task(run_in_background)
    return result


@router.get(
    "/simulate/{simulation_id}",
    response_model=SimulationResult,
    summary="Get simulation result",
)
async def get_simulation(
    simulation_id: str,
    _key: ApiKeyDep = None,
    firestore_svc=Depends(get_firestore_service),
) -> SimulationResult:
    """Retrieve a simulation result by ID."""
    sim_data = await firestore_svc.get_simulation(simulation_id)
    if not sim_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )
    return SimulationResult(**sim_data)
