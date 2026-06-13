# backend/api/routes/replay.py
from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from api.dependencies import ApiKeyDep, get_firestore_service
from api.schemas.replay import ReplayPlaybackState, ReplayResponse

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get(
    "/replay/{trace_id}",
    response_model=ReplayResponse,
    summary="Build and return a replay session for a trace",
)
async def get_replay(
    trace_id: str,
    _key: ApiKeyDep = None,
    firestore_svc=Depends(get_firestore_service),
) -> ReplayResponse:
    """
    Build a full replay session from a stored trace.
    The replay session contains all frames with annotations from diagnosis.
    """
    # Fetch the trace
    trace = await firestore_svc.get_trace(trace_id)
    if not trace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trace {trace_id} not found",
        )

    # Fetch associated diagnosis if available
    diagnosis = await firestore_svc.get_diagnosis_by_trace(trace_id)

    # Build replay session using the engine
    from replay.engine import ReplayEngine
    engine = ReplayEngine()
    session = engine.build_session(trace, diagnosis)

    playback = ReplayPlaybackState(
        session_id=session.session_id,
        current_frame=0,
        is_playing=False,
        fps=session.replay_fps,
    )

    return ReplayResponse(session=session, playback=playback)
