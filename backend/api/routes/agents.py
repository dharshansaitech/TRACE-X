# backend/api/routes/agents.py
from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from api.dependencies import ApiKeyDep, get_firestore_service
from api.schemas.dashboard import AgentHealth, AgentStatus

logger = structlog.get_logger(__name__)
router = APIRouter()


class AgentRegistration(BaseModel):
    agent_id: str
    agent_name: str
    agent_version: str | None = None
    description: str | None = None
    tags: list[str] = []
    metadata: dict = {}


class AgentRecord(BaseModel):
    agent_id: str
    agent_name: str
    agent_version: str | None = None
    description: str | None = None
    tags: list[str] = []
    metadata: dict = {}
    registered_at: str | None = None
    last_seen: str | None = None
    status: AgentStatus = AgentStatus.UNKNOWN


class AgentListResponse(BaseModel):
    agents: list[AgentRecord]
    total: int


@router.get(
    "/agents",
    response_model=AgentListResponse,
    summary="List all registered agents",
)
async def list_agents(
    status_filter: AgentStatus | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    _key: ApiKeyDep = None,
    firestore_svc=Depends(get_firestore_service),
) -> AgentListResponse:
    """Return all registered agents with optional status filter."""
    agents = await firestore_svc.list_agents(
        status_filter=status_filter,
        page=page,
        page_size=page_size,
    )
    return AgentListResponse(agents=agents, total=len(agents))


@router.get(
    "/agents/{agent_id}",
    response_model=AgentRecord,
    summary="Get agent details",
)
async def get_agent(
    agent_id: str,
    _key: ApiKeyDep = None,
    firestore_svc=Depends(get_firestore_service),
) -> AgentRecord:
    """Retrieve a single agent record."""
    agent = await firestore_svc.get_agent(agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id} not found",
        )
    return agent


@router.get(
    "/agents/{agent_id}/health",
    response_model=AgentHealth,
    summary="Get agent health metrics",
)
async def get_agent_health(
    agent_id: str,
    _key: ApiKeyDep = None,
    firestore_svc=Depends(get_firestore_service),
) -> AgentHealth:
    """Compute and return health metrics for a specific agent."""
    health = await firestore_svc.get_agent_health(agent_id)
    if not health:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No health data for agent {agent_id}",
        )
    return health


@router.post(
    "/agents",
    response_model=AgentRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new agent",
)
async def register_agent(
    payload: AgentRegistration,
    _key: ApiKeyDep = None,
    firestore_svc=Depends(get_firestore_service),
) -> AgentRecord:
    """Register a new agent in TRACE-X."""
    agent = await firestore_svc.register_agent(payload)
    return agent


@router.delete(
    "/agents/{agent_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deregister an agent",
)
async def deregister_agent(
    agent_id: str,
    _key: ApiKeyDep = None,
    firestore_svc=Depends(get_firestore_service),
) -> None:
    """Remove an agent from TRACE-X."""
    deleted = await firestore_svc.delete_agent(agent_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id} not found",
        )
