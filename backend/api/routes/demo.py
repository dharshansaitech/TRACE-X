# backend/api/routes/demo.py
from __future__ import annotations

import random
import time
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from api.dependencies import ApiKeyDep, get_firestore_service, get_orchestrator
from api.schemas.trace import FailureType
from services.demo_seed import AGENTS, _generate_trace, _weighted_failure_type

logger = structlog.get_logger(__name__)
router = APIRouter()


class InjectFailureRequest(BaseModel):
    """Optional overrides for the injected failure trace."""
    failure_type: FailureType | None = None
    agent_id: str | None = None


class InjectFailureResponse(BaseModel):
    trace_id: str
    agent_id: str
    agent_name: str
    failure_type: FailureType
    message: str = "Failure injected — pipeline running live"


@router.post(
    "/demo/inject-failure",
    response_model=InjectFailureResponse,
    summary="Inject a live simulated failure and run it through the agent pipeline",
)
async def inject_failure(
    payload: InjectFailureRequest,
    request: Request,
    _key: ApiKeyDep = None,
    firestore_svc=Depends(get_firestore_service),
    orchestrator=Depends(get_orchestrator),
) -> InjectFailureResponse:
    """
    Generates a realistic failed agent trace on demand and feeds it through the
    real Observer → Diagnosis → Repair → Validation pipeline, broadcasting each
    stage over the "failures" WebSocket channel as it happens.
    """
    agent = None
    if payload.agent_id:
        agent = next((a for a in AGENTS if a["agent_id"] == payload.agent_id), None)
    if agent is None:
        agent = random.choice(AGENTS)

    failure_type = payload.failure_type or _weighted_failure_type()

    trace = _generate_trace(agent, datetime.utcnow(), is_failed=True, failure_type=failure_type)
    trace.tags = ["injected", "live-demo"]
    trace.metadata = {"injected": True, "injected_at": datetime.now(timezone.utc).isoformat()}

    await firestore_svc.upsert_trace(trace)

    ws_manager = request.app.state.ws_manager
    await ws_manager.broadcast_to_channel(
        "failures",
        {
            "type": "failure_injected",
            "trace_id": trace.trace_id,
            "agent_id": trace.agent_id,
            "agent_name": trace.agent_name,
            "failure_type": trace.failure_type,
            "timestamp": time.time(),
        },
    )

    logger.info(
        "failure_injected",
        trace_id=trace.trace_id,
        agent_id=trace.agent_id,
        failure_type=trace.failure_type,
    )

    # Run the real pipeline live (Observer → Diagnosis → Repair → Validation)
    await orchestrator.handle_new_trace(trace)

    return InjectFailureResponse(
        trace_id=trace.trace_id,
        agent_id=trace.agent_id,
        agent_name=trace.agent_name,
        failure_type=trace.failure_type,
    )
