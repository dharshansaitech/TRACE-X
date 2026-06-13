# backend/api/dependencies.py
from __future__ import annotations

import functools
from typing import Annotated, Any, AsyncGenerator

import structlog
from fastapi import Depends, Header, HTTPException, Request, status
from google.cloud import bigquery, firestore, pubsub_v1

from api.config import Settings, get_settings

logger = structlog.get_logger(__name__)

# ── Singleton clients ─────────────────────────────────────────────────────────
_firestore_client: firestore.AsyncClient | None = None
_mock_firestore_client: Any | None = None
_using_mock_backends: bool = False
_bigquery_client: bigquery.Client | None = None
_pubsub_publisher: pubsub_v1.PublisherClient | None = None


def _get_mock_firestore_client() -> Any:
    global _mock_firestore_client
    if _mock_firestore_client is None:
        from services.mock_firestore import MockFirestoreClient
        _mock_firestore_client = MockFirestoreClient()
    return _mock_firestore_client


def get_firestore_client() -> Any:
    """Real Firestore AsyncClient, falling back to an in-memory mock when no
    GCP credentials are configured (demo mode)."""
    global _firestore_client, _using_mock_backends
    if _using_mock_backends:
        return _get_mock_firestore_client()
    if _firestore_client is None:
        try:
            settings = get_settings()
            _firestore_client = firestore.AsyncClient(
                project=settings.gcp_project_id,
                database=settings.firestore_database,
            )
            logger.debug("firestore_client_created", project=settings.gcp_project_id)
        except Exception as exc:
            logger.warning("firestore_unavailable_using_mock", error=str(exc))
            _using_mock_backends = True
            return _get_mock_firestore_client()
    return _firestore_client


def is_demo_mode() -> bool:
    """True once Firestore has fallen back to the in-memory mock store
    (no GCP credentials configured)."""
    get_firestore_client()
    return _using_mock_backends


def get_bigquery_client() -> bigquery.Client:
    global _bigquery_client
    if _bigquery_client is None:
        settings = get_settings()
        _bigquery_client = bigquery.Client(project=settings.gcp_project_id)
        logger.debug("bigquery_client_created", project=settings.gcp_project_id)
    return _bigquery_client


def get_pubsub_publisher() -> pubsub_v1.PublisherClient:
    global _pubsub_publisher
    if _pubsub_publisher is None:
        _pubsub_publisher = pubsub_v1.PublisherClient()
        logger.debug("pubsub_publisher_created")
    return _pubsub_publisher


# ── FastAPI dependency functions ──────────────────────────────────────────────


async def get_db() -> firestore.AsyncClient:
    """Dependency: Firestore async client."""
    return get_firestore_client()


async def get_bq() -> bigquery.Client:
    """Dependency: BigQuery client."""
    return get_bigquery_client()


async def get_publisher() -> pubsub_v1.PublisherClient:
    """Dependency: Pub/Sub publisher."""
    return get_pubsub_publisher()


async def get_settings_dep() -> Settings:
    """Dependency: Application settings."""
    return get_settings()


async def get_ws_manager(request: Request):
    """Dependency: WebSocket manager from app state."""
    return request.app.state.ws_manager


async def get_orchestrator(request: Request):
    """Dependency: Agent orchestrator from app state."""
    return request.app.state.orchestrator


# ── Gemini service dependency ─────────────────────────────────────────────────


def get_gemini_service_sync(settings: Settings | None = None):
    """Construct the Gemini service, falling back to the demo mock when no
    GCP credentials are configured."""
    settings = settings or get_settings()
    if is_demo_mode():
        from services.mock_gemini import MockGeminiService
        return MockGeminiService(settings)
    from services.gemini_service import GeminiService
    return GeminiService(settings)


async def get_gemini_service():
    """Dependency: Gemini service."""
    return get_gemini_service_sync()


# ── Authentication ─────────────────────────────────────────────────────────────


async def verify_api_key(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    authorization: Annotated[str | None, Header()] = None,
    settings: Settings = Depends(get_settings_dep),
) -> str:
    """Verify API key from header."""
    # Extract key from various sources
    api_key: str | None = None

    if x_api_key:
        api_key = x_api_key
    elif authorization:
        parts = authorization.split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            api_key = parts[1]

    # In development, allow requests without API key
    if settings.is_development and not api_key:
        return "dev-no-auth"

    if not api_key or api_key not in settings.api_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return api_key


# ── Service dependencies ──────────────────────────────────────────────────────


async def get_firestore_service():
    """Dependency: Firestore service."""
    from services.firestore_service import FirestoreService
    settings = get_settings()
    client = get_firestore_client()
    return FirestoreService(client, settings)


async def get_bigquery_service():
    """Dependency: BigQuery service."""
    from services.bigquery_service import BigQueryService
    settings = get_settings()
    client = get_bigquery_client()
    return BigQueryService(client, settings)


async def get_pubsub_service():
    """Dependency: Pub/Sub service."""
    from services.pubsub_service import PubSubService
    settings = get_settings()
    return PubSubService(settings)


# ── Type aliases ──────────────────────────────────────────────────────────────
FirestoreDep = Annotated[firestore.AsyncClient, Depends(get_db)]
BigQueryDep = Annotated[bigquery.Client, Depends(get_bq)]
PublisherDep = Annotated[pubsub_v1.PublisherClient, Depends(get_publisher)]
SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
ApiKeyDep = Annotated[str, Depends(verify_api_key)]
