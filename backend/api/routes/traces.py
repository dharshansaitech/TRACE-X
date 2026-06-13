# backend/api/routes/traces.py
from __future__ import annotations

import time
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from api.dependencies import ApiKeyDep, get_firestore_service, get_orchestrator
from api.schemas.trace import (
    AgentTrace,
    FailureType,
    TraceFilter,
    TraceIngestRequest,
    TraceIngestResponse,
    TraceListResponse,
    TraceStatus,
)

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.post(
    "/traces/ingest",
    response_model=TraceIngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest a new agent trace",
)
async def ingest_trace(
    payload: TraceIngestRequest,
    request: Request,
    _key: ApiKeyDep,
    firestore_svc=Depends(get_firestore_service),
    orchestrator=Depends(get_orchestrator),
) -> TraceIngestResponse:
    """
    Accept a new agent execution trace from the SDK.
    Stores it and triggers the observer agent pipeline.
    """
    start = time.perf_counter()
    trace = payload.trace

    try:
        # Persist trace
        await firestore_svc.upsert_trace(trace)

        # Trigger async analysis pipeline
        await orchestrator.handle_new_trace(trace)

        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "trace_ingested",
            trace_id=trace.trace_id,
            agent_id=trace.agent_id,
            status=trace.status,
            duration_ms=round(duration_ms, 2),
        )

        # Broadcast to WebSocket subscribers
        ws_manager = request.app.state.ws_manager
        await ws_manager.broadcast_to_channel(
            "traces",
            {
                "type": "new_trace",
                "trace_id": trace.trace_id,
                "agent_id": trace.agent_id,
                "status": trace.status,
                "failure_type": trace.failure_type,
                "timestamp": time.time(),
            },
        )

        return TraceIngestResponse(
            trace_id=trace.trace_id,
            status="accepted",
            message="Trace ingested and analysis triggered",
        )

    except Exception as exc:
        logger.error("trace_ingest_failed", error=str(exc), trace_id=trace.trace_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to ingest trace: {str(exc)}",
        )


@router.get(
    "/traces",
    response_model=TraceListResponse,
    summary="List traces with filters",
)
async def list_traces(
    agent_id: str | None = Query(None),
    trace_status: TraceStatus | None = Query(None, alias="status"),
    failure_type: FailureType | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _key: ApiKeyDep = None,
    firestore_svc=Depends(get_firestore_service),
) -> TraceListResponse:
    """List traces with optional filtering and pagination."""
    filters = TraceFilter(
        agent_id=agent_id,
        status=trace_status,
        failure_type=failure_type,
        page=page,
        page_size=page_size,
    )
    return await firestore_svc.list_traces(filters)


@router.get(
    "/traces/{trace_id}",
    response_model=AgentTrace,
    summary="Get a single trace by ID",
)
async def get_trace(
    trace_id: str,
    _key: ApiKeyDep = None,
    firestore_svc=Depends(get_firestore_service),
) -> AgentTrace:
    """Retrieve the full trace including all spans."""
    trace = await firestore_svc.get_trace(trace_id)
    if not trace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trace {trace_id} not found",
        )
    return trace


@router.delete(
    "/traces/{trace_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a trace",
)
async def delete_trace(
    trace_id: str,
    _key: ApiKeyDep = None,
    firestore_svc=Depends(get_firestore_service),
) -> None:
    """Delete a trace and all associated data."""
    deleted = await firestore_svc.delete_trace(trace_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trace {trace_id} not found",
        )
