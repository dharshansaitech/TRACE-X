"""
backend/tests/conftest.py
Shared pytest fixtures for TRACE-X backend tests.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient

# ─────────────────────────────────────────────────────────────────────────────
# Pytest configuration
# ─────────────────────────────────────────────────────────────────────────────

def pytest_configure(config):
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "slow: mark test as slow")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_span(
    span_id: str | None = None,
    name: str = "test_span",
    kind: str = "llm",
    status: str = "success",
    error_message: str | None = None,
    duration_ms: int = 300,
    prompt_tokens: int = 100,
    completion_tokens: int = 50,
) -> dict[str, Any]:
    return {
        "span_id": span_id or f"span-{uuid.uuid4().hex[:8]}",
        "name": name,
        "kind": kind,
        "status": status,
        "started_at": _now_iso(),
        "finished_at": _now_iso(),
        "duration_ms": duration_ms,
        "input": {"test": "input"},
        "output": {"test": "output"} if status != "error" else None,
        "model": "gemini-2.0-flash-001" if kind == "llm" else None,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "tool_calls": [],
        "error_message": error_message,
        "metadata": {},
    }


def _make_trace(
    trace_id: str | None = None,
    agent_id: str = "test-agent-v1",
    status: str = "success",
    spans: list | None = None,
    failure_type: str | None = None,
) -> dict[str, Any]:
    if spans is None:
        if status == "failed":
            spans = [
                _make_span(name="parse_input", status="success"),
                _make_span(name="call_tool", kind="tool", status="error",
                           error_message="Tool timeout"),
                _make_span(name="generate_response", status="error",
                           error_message="Upstream failure"),
            ]
        else:
            spans = [
                _make_span(name="parse_input"),
                _make_span(name="call_tool", kind="tool"),
                _make_span(name="generate_response"),
            ]

    return {
        "trace_id": trace_id or f"trace-{uuid.uuid4().hex[:12]}",
        "agent_id": agent_id,
        "trace_name": "test_operation",
        "started_at": _now_iso(),
        "finished_at": _now_iso(),
        "duration_ms": sum(s["duration_ms"] for s in spans),
        "status": status,
        "spans": spans,
        "metadata": {"test": True},
        "tags": ["test"],
        "total_tokens": sum(s.get("prompt_tokens", 0) + s.get("completion_tokens", 0) for s in spans),
        "total_cost_usd": 0.0001,
        "failure_type": failure_type,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures: Test data
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_trace_success() -> dict[str, Any]:
    """A minimal successful trace."""
    return _make_trace(status="success")


@pytest.fixture
def sample_trace_failed() -> dict[str, Any]:
    """A failed trace with tool errors."""
    return _make_trace(status="failed", failure_type="tool_failure")


@pytest.fixture
def sample_trace_hallucination() -> dict[str, Any]:
    """A trace with a hallucination failure."""
    spans = [
        _make_span(name="parse_intent", status="success"),
        _make_span(name="fetch_data", kind="tool", status="success"),
        _make_span(name="generate_response", status="success",
                   prompt_tokens=400, completion_tokens=180),
    ]
    # Metadata signals hallucination
    spans[2]["metadata"] = {"grounding_check_failed": True, "cited_entity": "NONEXISTENT-99"}
    return _make_trace(status="failed", spans=spans, failure_type="hallucination")


@pytest.fixture
def sample_trace_context_overflow() -> dict[str, Any]:
    """A trace that exceeded context window."""
    spans = [
        _make_span(name="parse_intent", status="success"),
        _make_span(name="generate_response", status="error",
                   error_message="Context window exceeded: 32768 tokens",
                   prompt_tokens=30000, completion_tokens=0),
    ]
    return _make_trace(status="failed", spans=spans, failure_type="context_window_exceeded")


@pytest.fixture
def sample_ingest_payload(sample_trace_success) -> dict[str, Any]:
    """A valid trace ingest request payload."""
    return {
        "trace": sample_trace_success,
        "agent_id": sample_trace_success["agent_id"],
    }


@pytest.fixture
def sample_failed_ingest_payload(sample_trace_failed) -> dict[str, Any]:
    """A failed trace ingest payload."""
    return {
        "trace": sample_trace_failed,
        "agent_id": sample_trace_failed["agent_id"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures: Mock services
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_firestore():
    """Mock Firestore client that stores data in memory."""
    store: dict[str, dict] = {}

    mock = MagicMock()

    def collection(name):
        coll_mock = MagicMock()

        def document(doc_id=None):
            doc_id = doc_id or str(uuid.uuid4())
            doc_mock = MagicMock()

            async def set_async(data):
                store[f"{name}/{doc_id}"] = data

            async def get_async():
                doc_snap = MagicMock()
                key = f"{name}/{doc_id}"
                if key in store:
                    doc_snap.exists = True
                    doc_snap.to_dict.return_value = store[key]
                    doc_snap.id = doc_id
                else:
                    doc_snap.exists = False
                    doc_snap.to_dict.return_value = None
                return doc_snap

            doc_mock.set = AsyncMock(side_effect=set_async)
            doc_mock.get = AsyncMock(side_effect=get_async)
            doc_mock.id = doc_id
            return doc_mock

        coll_mock.document = document
        return coll_mock

    mock.collection = collection
    return mock


@pytest.fixture
def mock_gemini_service():
    """Mock Gemini service that returns predictable responses."""
    mock = AsyncMock()

    mock.generate_structured.return_value = {
        "root_cause_category": "tool_failure",
        "severity": "high",
        "confidence": 0.85,
        "summary": "Tool call failed due to upstream timeout",
        "root_cause_detail": "The search_flights tool returned 503 twice in succession.",
        "blast_radius": {
            "affected_spans": ["span-abc", "span-def"],
            "affected_tools": ["search_flights"],
            "downstream_impact": "Agent unable to complete booking recommendation",
            "user_impact": "Request returned degraded response without flight options",
        },
        "reasoning_steps": [
            {"step": 1, "observation": "Tool span returned error status", "conclusion": "Tool failure"},
            {"step": 2, "observation": "Retry also failed", "conclusion": "Persistent upstream issue"},
        ],
        "recommended_actions": [
            "Add circuit breaker for flight API calls",
            "Implement fallback to cached flight data",
        ],
        "anomaly_signals": [],
        "arize_insights": {},
        "similar_trace_ids": [],
    }

    mock.generate_text.return_value = "This is a mock LLM text response for testing."
    mock.is_available.return_value = True

    return mock


@pytest.fixture
def mock_arize_client():
    """Mock Arize MCP client."""
    mock = AsyncMock()

    mock.search_similar_traces.return_value = {
        "similar_traces": [
            {"trace_id": "trace-similar-001", "similarity_score": 0.92, "failure_type": "tool_failure"},
        ],
        "total": 1,
        "mock": True,
    }

    mock.get_feature_drift.return_value = {
        "drift_score": 0.15,
        "drifted_features": [],
        "mock": True,
    }

    mock.get_performance_baseline.return_value = {
        "baseline_success_rate": 0.94,
        "baseline_latency_p50_ms": 1200,
        "baseline_latency_p99_ms": 4500,
        "mock": True,
    }

    mock.get_hallucination_score.return_value = {
        "hallucination_score": 0.12,
        "grounding_score": 0.88,
        "mock": True,
    }

    return mock


@pytest.fixture
def mock_orchestrator():
    """Mock agent orchestrator."""
    mock = AsyncMock()
    mock.handle_new_trace.return_value = None
    return mock


@pytest.fixture
def mock_websocket_manager():
    """Mock WebSocket manager."""
    mock = AsyncMock()
    mock.broadcast_to_channel.return_value = None
    return mock


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures: FastAPI test client
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def app(mock_firestore, mock_orchestrator, mock_websocket_manager):
    """FastAPI app with all external dependencies mocked."""
    with (
        patch("api.dependencies.get_firestore_client", return_value=mock_firestore),
        patch("api.dependencies.get_bigquery_client", return_value=MagicMock()),
        patch("api.dependencies.get_pubsub_service", return_value=AsyncMock()),
        patch("api.main.orchestrator", mock_orchestrator),
        patch("api.main.ws_manager", mock_websocket_manager),
    ):
        from api.main import app as _app
        yield _app


@pytest.fixture
def client(app):
    """Synchronous test client."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
async def async_client(app):
    """Async test client."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures: Diagnosis / Repair
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_diagnosis_result() -> dict[str, Any]:
    """A complete diagnosis result."""
    return {
        "diagnosis_id": f"diag-{uuid.uuid4().hex[:12]}",
        "trace_id": f"trace-{uuid.uuid4().hex[:12]}",
        "root_cause_category": "tool_failure",
        "severity": "high",
        "confidence": 0.87,
        "summary": "Tool failure: search_flights returned 503 twice",
        "root_cause_detail": "The flight search API experienced an outage.",
        "blast_radius": {
            "affected_spans": ["span-abc"],
            "affected_tools": ["search_flights"],
            "downstream_impact": "No flight data available",
            "user_impact": "Booking recommendation failed",
        },
        "reasoning_steps": [
            {"step": 1, "observation": "Error span detected", "conclusion": "Tool failure"},
        ],
        "recommended_actions": ["Add circuit breaker", "Use cached data fallback"],
        "anomaly_signals": [],
        "arize_insights": {},
        "similar_trace_ids": [],
        "created_at": _now_iso(),
    }


@pytest.fixture
def sample_repair_artifact() -> dict[str, Any]:
    """A complete repair artifact."""
    return {
        "repair_id": f"repair-{uuid.uuid4().hex[:12]}",
        "trace_id": f"trace-{uuid.uuid4().hex[:12]}",
        "diagnosis_id": f"diag-{uuid.uuid4().hex[:12]}",
        "repair_type": "prompt_update",
        "title": "Add circuit breaker for flight API",
        "description": "Wraps the flight search tool call with a circuit breaker pattern.",
        "status": "pending",
        "diff": {
            "file_path": "agents/travel_bot.py",
            "hunks": [
                {
                    "header": "@@ -45,7 +45,12 @@",
                    "lines": [
                        {"kind": "context", "content": "  result = await search_flights(origin, dest)"},
                        {"kind": "removed", "content": "  return result"},
                        {"kind": "added", "content": "  if not result.get('flights'):"},
                        {"kind": "added", "content": "    result = await search_flights_cached(origin, dest)"},
                        {"kind": "added", "content": "  return result"},
                    ],
                }
            ],
        },
        "test_cases": [
            {
                "test_id": "tc-001",
                "name": "Test flight search with API failure",
                "input": {"origin": "JFK", "destination": "LAX"},
                "expected_output": {"flights": []},
                "passed": None,
            }
        ],
        "confidence_score": 0.82,
        "validation_passed": None,
        "validation_score": None,
        "tests_passed": 0,
        "tests_failed": 0,
        "tests_total": 1,
        "created_at": _now_iso(),
        "applied_at": None,
        "rolled_back_at": None,
    }
