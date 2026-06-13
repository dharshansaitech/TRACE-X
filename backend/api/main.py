# backend/api/main.py
from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from api.config import get_settings
from api.middleware import RequestLoggingMiddleware, TimingMiddleware
from api.routes import (
    agents,
    dashboard,
    demo,
    diagnoses,
    repairs,
    replay,
    simulator,
    traces,
    websocket as ws_router,
)

logger = structlog.get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown."""
    logger.info(
        "tracex_startup",
        version=settings.app_version,
        environment=settings.environment,
        gcp_project=settings.gcp_project_id,
    )

    # ── Initialize services ───────────────────────────────────────────────
    from api.dependencies import get_firestore_client, get_pubsub_publisher, is_demo_mode
    from services.pubsub_service import PubSubService

    try:
        # Warm up Firestore connection (falls back to in-memory mock store
        # when no GCP credentials are configured)
        _fs = get_firestore_client()
        if is_demo_mode():
            logger.warning(
                "demo_mode_active",
                reason="no GCP credentials found — using in-memory Firestore mock and Gemini mock",
            )
            from services.demo_seed import seed_demo_data
            from services.firestore_service import FirestoreService

            await seed_demo_data(FirestoreService(_fs, settings))
        else:
            logger.info("firestore_connected")
    except Exception as exc:
        logger.warning("firestore_unavailable", error=str(exc))

    try:
        # Start Pub/Sub subscriber in background
        pubsub = PubSubService(settings)
        await pubsub.start_background_subscriber()
        app.state.pubsub = pubsub
        logger.info("pubsub_subscriber_started")
    except Exception as exc:
        logger.warning("pubsub_unavailable", error=str(exc))
        app.state.pubsub = None

    # ── Initialize WebSocket manager ──────────────────────────────────────
    from api.websocket_manager import WebSocketManager
    app.state.ws_manager = WebSocketManager()
    logger.info("websocket_manager_initialized")

    # ── Initialize agent orchestrator ────────────────────────────────────
    from agents.orchestrator import AgentOrchestrator
    app.state.orchestrator = AgentOrchestrator(settings)
    app.state.orchestrator.ws_manager = app.state.ws_manager
    logger.info("agent_orchestrator_initialized")

    yield

    # ── Shutdown ──────────────────────────────────────────────────────────
    logger.info("tracex_shutdown")
    if app.state.pubsub:
        await app.state.pubsub.stop()
    if app.state.ws_manager:
        await app.state.ws_manager.close_all()


def create_app() -> FastAPI:
    app = FastAPI(
        title="TRACE-X API",
        description="The Flight Recorder for AI Agents — reliability platform for autonomous AI systems",
        version=settings.app_version,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Trace-ID", "X-Process-Time"],
    )

    # ── GZip compression ──────────────────────────────────────────────────
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    # ── Custom middleware ─────────────────────────────────────────────────
    app.add_middleware(TimingMiddleware)
    app.add_middleware(RequestLoggingMiddleware)

    # ── Routers ───────────────────────────────────────────────────────────
    api_prefix = "/api/v1"
    app.include_router(traces.router, prefix=api_prefix, tags=["traces"])
    app.include_router(agents.router, prefix=api_prefix, tags=["agents"])
    app.include_router(diagnoses.router, prefix=api_prefix, tags=["diagnoses"])
    app.include_router(repairs.router, prefix=api_prefix, tags=["repairs"])
    app.include_router(replay.router, prefix=api_prefix, tags=["replay"])
    app.include_router(simulator.router, prefix=api_prefix, tags=["simulator"])
    app.include_router(dashboard.router, prefix=api_prefix, tags=["dashboard"])
    app.include_router(demo.router, prefix=api_prefix, tags=["demo"])
    app.include_router(ws_router.router, tags=["websocket"])

    # ── Health check ──────────────────────────────────────────────────────
    @app.get("/health", tags=["health"])
    async def health_check(request: Request) -> dict:
        return {
            "status": "healthy",
            "version": settings.app_version,
            "environment": settings.environment,
            "timestamp": time.time(),
            "services": {
                "websocket_connections": len(request.app.state.ws_manager.connections)
                if hasattr(request.app.state, "ws_manager")
                else 0,
            },
        }

    @app.get("/", tags=["health"])
    async def root() -> dict:
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "description": "The Flight Recorder for AI Agents",
            "docs": "/docs",
        }

    # ── Exception handlers ────────────────────────────────────────────────
    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"detail": "Resource not found", "path": str(request.url.path)},
        )

    @app.exception_handler(500)
    async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled_exception", path=str(request.url.path), error=str(exc))
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run(
        "api.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        workers=settings.workers,
        log_level=settings.log_level.lower(),
    )
