# backend/api/config.py
from __future__ import annotations

import os
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ───────────────────────────────────────────────────────────────
    app_name: str = "TRACE-X Backend"
    app_version: str = "1.0.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    log_level: str = "INFO"

    # ── Server ────────────────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1
    reload: bool = False

    # ── Security ──────────────────────────────────────────────────────────
    api_secret_key: str = Field(default="dev-secret-change-in-production-please-use-32-chars")
    api_keys: list[str] = Field(default_factory=lambda: ["demo-api-key-tracex-hackathon"])
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:3001", "*"]
    )
    cors_allow_credentials: bool = True

    # ── Google Cloud ──────────────────────────────────────────────────────
    gcp_project_id: str = Field(default="tracex-hackathon")
    gcp_region: str = "us-central1"
    google_application_credentials: str | None = None

    # ── Firestore ─────────────────────────────────────────────────────────
    firestore_database: str = "(default)"
    firestore_traces_collection: str = "traces"
    firestore_agents_collection: str = "agents"
    firestore_diagnoses_collection: str = "diagnoses"
    firestore_repairs_collection: str = "repairs"
    firestore_simulations_collection: str = "simulations"

    # ── BigQuery ──────────────────────────────────────────────────────────
    bigquery_dataset: str = "tracex_analytics"
    bigquery_traces_table: str = "traces"
    bigquery_events_table: str = "events"
    bigquery_metrics_table: str = "metrics"

    # ── Pub/Sub ───────────────────────────────────────────────────────────
    pubsub_traces_topic: str = "tracex-traces"
    pubsub_events_topic: str = "tracex-events"
    pubsub_repairs_topic: str = "tracex-repairs"
    pubsub_subscription_traces: str = "tracex-traces-sub"
    pubsub_subscription_events: str = "tracex-events-sub"

    # ── Vertex AI / Gemini ────────────────────────────────────────────────
    vertex_ai_location: str = "us-central1"
    gemini_model: str = "gemini-2.0-flash-001"
    gemini_temperature: float = 0.2
    gemini_max_output_tokens: int = 8192
    gemini_top_p: float = 0.95

    # ── Arize MCP ─────────────────────────────────────────────────────────
    arize_api_key: str = Field(default="demo-arize-key")
    arize_space_key: str = Field(default="demo-space-key")
    arize_mcp_server_url: str = "http://localhost:8765"

    # ── Agent Thresholds ──────────────────────────────────────────────────
    observer_error_rate_threshold: float = 0.05          # 5%
    observer_latency_p99_threshold_ms: float = 5000.0    # 5 seconds
    observer_staleness_threshold_hours: float = 2.0
    observer_hallucination_confidence_threshold: float = 0.6
    observer_tool_failure_rate_threshold: float = 0.1    # 10%

    # ── Replay ────────────────────────────────────────────────────────────
    replay_max_frames: int = 1000
    replay_default_fps: float = 10.0

    # ── Rate Limiting ─────────────────────────────────────────────────────
    rate_limit_requests_per_minute: int = 600
    rate_limit_ingest_per_second: int = 100

    # ── WebSocket ─────────────────────────────────────────────────────────
    ws_heartbeat_interval_seconds: int = 30
    ws_max_connections: int = 500

    @field_validator("api_keys", mode="before")
    @classmethod
    def parse_api_keys(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [k.strip() for k in v.split(",") if k.strip()]
        return v

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
