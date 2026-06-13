# backend/api/routes/diagnoses.py
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status

from api.config import get_settings
from api.dependencies import ApiKeyDep, get_firestore_service, get_gemini_service_sync, get_orchestrator
from api.schemas.diagnosis import (
    DiagnosisResult,
    DiagnosisTriggerRequest,
    DiagnosisTriggerResponse,
)
from mcp.arize_mcp_client import ArizeMCPClient

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get(
    "/diagnoses/{trace_id}",
    response_model=DiagnosisResult,
    summary="Get diagnosis for a trace",
)
async def get_diagnosis(
    trace_id: str,
    _key: ApiKeyDep = None,
    firestore_svc=Depends(get_firestore_service),
) -> DiagnosisResult:
    """Retrieve the diagnosis result for a specific trace."""
    diagnosis = await firestore_svc.get_diagnosis_by_trace(trace_id)
    if not diagnosis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No diagnosis found for trace {trace_id}",
        )
    return diagnosis


@router.post(
    "/diagnoses/trigger",
    response_model=DiagnosisTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger diagnosis for a trace",
)
async def trigger_diagnosis(
    payload: DiagnosisTriggerRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    _key: ApiKeyDep = None,
    firestore_svc=Depends(get_firestore_service),
    orchestrator=Depends(get_orchestrator),
) -> DiagnosisTriggerResponse:
    """
    Manually trigger a diagnosis run for a trace.
    Useful for re-diagnosing after new information is available.
    """
    # Check trace exists
    trace = await firestore_svc.get_trace(payload.trace_id)
    if not trace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trace {payload.trace_id} not found",
        )

    # Check for existing diagnosis
    if not payload.force_rediagnose:
        existing = await firestore_svc.get_diagnosis_by_trace(payload.trace_id)
        if existing:
            return DiagnosisTriggerResponse(
                trace_id=payload.trace_id,
                diagnosis_id=existing.diagnosis_id,
                status="already_exists",
                estimated_completion_seconds=0,
                message="Diagnosis already exists. Use force_rediagnose=true to re-run.",
            )

    # Create placeholder diagnosis ID
    import uuid
    diagnosis_id = str(uuid.uuid4())

    # Run diagnosis in background
    async def run_diagnosis():
        try:
            await orchestrator.run_diagnosis_pipeline(trace, context=payload.context)
            ws_manager = request.app.state.ws_manager
            await ws_manager.broadcast_to_channel(
                "failures",
                {
                    "type": "diagnosis_complete",
                    "trace_id": payload.trace_id,
                    "diagnosis_id": diagnosis_id,
                },
            )
        except Exception as exc:
            logger.error("background_diagnosis_failed", trace_id=payload.trace_id, error=str(exc))

    background_tasks.add_task(run_diagnosis)

    return DiagnosisTriggerResponse(
        trace_id=payload.trace_id,
        diagnosis_id=diagnosis_id,
        status="triggered",
        estimated_completion_seconds=15.0,
        message="Diagnosis pipeline triggered. Results will be available shortly.",
    )


@router.get(
    "/diagnoses",
    summary="List recent diagnoses",
)
async def list_diagnoses(
    agent_id: str | None = None,
    limit: int = 20,
    _key: ApiKeyDep = None,
    firestore_svc=Depends(get_firestore_service),
) -> dict:
    """List recent diagnosis results."""
    diagnoses = await firestore_svc.list_diagnoses(agent_id=agent_id, limit=limit)
    return {"diagnoses": diagnoses, "total": len(diagnoses)}


@router.get(
    "/diagnoses/{trace_id}/insights",
    summary="Get Arize MCP insights (similar failures, drift, baselines) for a trace",
)
async def get_diagnosis_insights(
    trace_id: str,
    _key: ApiKeyDep = None,
    firestore_svc=Depends(get_firestore_service),
) -> dict:
    """
    Surfaces "similar historical failures" and drift/performance signals from
    Arize MCP for the agent behind this trace, contextualized to its failure type.
    """
    trace = await firestore_svc.get_trace(trace_id)
    if not trace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trace {trace_id} not found",
        )

    arize = ArizeMCPClient(get_settings())

    similar, drift, baseline = await asyncio.gather(
        arize.search_similar_traces(
            agent_id=trace.agent_id,
            failure_type=trace.failure_type.value,
        ),
        arize.get_feature_drift(model_id=trace.agent_id),
        arize.get_performance_baseline(agent_id=trace.agent_id),
    )

    return {
        "trace_id": trace_id,
        "agent_id": trace.agent_id,
        "similar_traces": similar.get("similar_traces", []),
        "pattern_insights": similar.get("insights", {}),
        "drift": drift,
        "performance_baseline": baseline,
    }


@router.get(
    "/diagnoses/{trace_id}/report",
    summary="Generate an AI incident postmortem report for a trace",
)
async def get_incident_report(
    trace_id: str,
    _key: ApiKeyDep = None,
    firestore_svc=Depends(get_firestore_service),
) -> dict:
    """Generates a human-readable incident postmortem from the trace, its
    diagnosis, and (if available) its repair, using Gemini."""
    trace = await firestore_svc.get_trace(trace_id)
    if not trace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trace {trace_id} not found",
        )

    diagnosis = await firestore_svc.get_diagnosis_by_trace(trace_id)
    repair = await firestore_svc.get_repair_by_trace(trace_id)

    gemini = get_gemini_service_sync()
    report = await gemini.generate_incident_report(trace, diagnosis, repair)

    return {
        "trace_id": trace_id,
        "report": report,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
