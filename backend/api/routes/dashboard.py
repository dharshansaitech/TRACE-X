# backend/api/routes/dashboard.py
from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from api.config import get_settings
from api.dependencies import ApiKeyDep, get_firestore_service, is_demo_mode
from api.schemas.dashboard import DashboardOverview, IncidentListResponse

logger = structlog.get_logger(__name__)
router = APIRouter()


class SystemStatus(BaseModel):
    demo_mode: bool
    environment: str
    version: str


@router.get(
    "/system/status",
    response_model=SystemStatus,
    summary="Get system status",
)
async def get_system_status(_key: ApiKeyDep = None) -> SystemStatus:
    """Returns whether the backend is running in demo mode (no GCP credentials)."""
    settings = get_settings()
    return SystemStatus(
        demo_mode=is_demo_mode(),
        environment=settings.environment,
        version=settings.app_version,
    )


@router.get(
    "/dashboard/overview",
    response_model=DashboardOverview,
    summary="Get Flight Deck overview",
)
async def get_dashboard_overview(
    _key: ApiKeyDep = None,
    firestore_svc=Depends(get_firestore_service),
) -> DashboardOverview:
    """
    Returns the complete Flight Deck overview:
    system metrics, agent health, recent incidents, and trends.
    """
    return await firestore_svc.get_dashboard_overview()


@router.get(
    "/dashboard/incidents",
    response_model=IncidentListResponse,
    summary="List incidents",
)
async def list_incidents(
    status_filter: str | None = Query(None, alias="status"),
    severity: str | None = Query(None),
    agent_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _key: ApiKeyDep = None,
    firestore_svc=Depends(get_firestore_service),
) -> IncidentListResponse:
    """List incidents with filtering and pagination."""
    return await firestore_svc.list_incidents(
        status_filter=status_filter,
        severity=severity,
        agent_id=agent_id,
        page=page,
        page_size=page_size,
    )
