# backend/api/routes/repairs.py
from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from api.dependencies import ApiKeyDep, get_firestore_service
from api.schemas.repair import (
    RepairArtifact,
    RepairApproveRequest,
    RepairApplyRequest,
    RepairListResponse,
    RepairRollbackRequest,
    RepairStatus,
)

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get(
    "/repairs",
    response_model=RepairListResponse,
    summary="List all repair artifacts",
)
async def list_repairs(
    repair_status: RepairStatus | None = Query(None, alias="status"),
    agent_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _key: ApiKeyDep = None,
    firestore_svc=Depends(get_firestore_service),
) -> RepairListResponse:
    """List all repair artifacts with optional filtering."""
    repairs, total = await firestore_svc.list_repairs(
        status_filter=repair_status,
        agent_id=agent_id,
        page=page,
        page_size=page_size,
    )

    pending = sum(1 for r in repairs if r.status == RepairStatus.PENDING)
    approved = sum(1 for r in repairs if r.status == RepairStatus.APPROVED)
    applied = sum(1 for r in repairs if r.status == RepairStatus.APPLIED)

    return RepairListResponse(
        repairs=repairs,
        total=total,
        pending_count=pending,
        approved_count=approved,
        applied_count=applied,
    )


@router.get(
    "/repairs/{repair_id}",
    response_model=RepairArtifact,
    summary="Get a single repair artifact",
)
async def get_repair(
    repair_id: str,
    _key: ApiKeyDep = None,
    firestore_svc=Depends(get_firestore_service),
) -> RepairArtifact:
    """Retrieve a single repair artifact by ID."""
    repair = await firestore_svc.get_repair(repair_id)
    if not repair:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repair {repair_id} not found",
        )
    return repair


@router.post(
    "/repairs/{repair_id}/approve",
    response_model=RepairArtifact,
    summary="Approve a pending repair",
)
async def approve_repair(
    repair_id: str,
    payload: RepairApproveRequest,
    request: Request,
    _key: ApiKeyDep = None,
    firestore_svc=Depends(get_firestore_service),
) -> RepairArtifact:
    """Approve a pending repair artifact for application."""
    repair = await firestore_svc.get_repair(repair_id)
    if not repair:
        raise HTTPException(status_code=404, detail=f"Repair {repair_id} not found")

    if repair.status != RepairStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Repair is in status {repair.status}, can only approve PENDING repairs",
        )

    from datetime import datetime
    repair.status = RepairStatus.APPROVED
    repair.approved_at = datetime.utcnow()
    repair.applied_by = payload.approved_by
    if payload.notes:
        repair.validation_notes = payload.notes

    updated = await firestore_svc.upsert_repair(repair)

    # Notify via WebSocket
    ws_manager = request.app.state.ws_manager
    await ws_manager.broadcast_to_channel(
        "repairs",
        {
            "type": "repair_approved",
            "repair_id": repair_id,
            "approved_by": payload.approved_by,
        },
    )

    return updated


@router.post(
    "/repairs/{repair_id}/apply",
    response_model=RepairArtifact,
    summary="Apply an approved repair",
)
async def apply_repair(
    repair_id: str,
    payload: RepairApplyRequest,
    request: Request,
    _key: ApiKeyDep = None,
    firestore_svc=Depends(get_firestore_service),
) -> RepairArtifact:
    """Apply an approved repair. In production this would trigger deployment."""
    repair = await firestore_svc.get_repair(repair_id)
    if not repair:
        raise HTTPException(status_code=404, detail=f"Repair {repair_id} not found")

    if repair.status not in (RepairStatus.APPROVED, RepairStatus.PENDING):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Repair status is {repair.status}, must be APPROVED or PENDING to apply",
        )

    if payload.dry_run:
        return repair  # Return without modifying

    from datetime import datetime
    repair.status = RepairStatus.APPLIED
    repair.applied_at = datetime.utcnow()
    repair.applied_by = payload.applied_by

    updated = await firestore_svc.upsert_repair(repair)

    ws_manager = request.app.state.ws_manager
    await ws_manager.broadcast_to_channel(
        "repairs",
        {
            "type": "repair_applied",
            "repair_id": repair_id,
            "applied_by": payload.applied_by,
        },
    )
    logger.info("repair_applied", repair_id=repair_id, applied_by=payload.applied_by)

    return updated


@router.post(
    "/repairs/{repair_id}/rollback",
    response_model=RepairArtifact,
    summary="Roll back an applied repair",
)
async def rollback_repair(
    repair_id: str,
    payload: RepairRollbackRequest,
    request: Request,
    _key: ApiKeyDep = None,
    firestore_svc=Depends(get_firestore_service),
) -> RepairArtifact:
    """Roll back a previously applied repair."""
    repair = await firestore_svc.get_repair(repair_id)
    if not repair:
        raise HTTPException(status_code=404, detail=f"Repair {repair_id} not found")

    if repair.status != RepairStatus.APPLIED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Repair status is {repair.status}, can only rollback APPLIED repairs",
        )

    from datetime import datetime
    repair.status = RepairStatus.ROLLED_BACK
    repair.rolled_back_at = datetime.utcnow()
    repair.rolled_back_by = payload.rolled_back_by
    repair.validation_notes = f"Rolled back: {payload.reason}"

    updated = await firestore_svc.upsert_repair(repair)

    ws_manager = request.app.state.ws_manager
    await ws_manager.broadcast_to_channel(
        "repairs",
        {
            "type": "repair_rolled_back",
            "repair_id": repair_id,
            "rolled_back_by": payload.rolled_back_by,
            "reason": payload.reason,
        },
    )
    logger.info("repair_rolled_back", repair_id=repair_id, reason=payload.reason)

    return updated
