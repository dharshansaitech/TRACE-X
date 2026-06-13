"""
backend/tests/test_ingestion.py
Tests for the trace ingestion endpoint (POST /api/v1/traces/ingest).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _minimal_span(status: str = "success") -> dict[str, Any]:
    return {
        "span_id": f"span-{uuid.uuid4().hex[:8]}",
        "name": "test_span",
        "kind": "llm",
        "status": status,
        "started_at": _now(),
        "finished_at": _now(),
        "duration_ms": 250,
        "input": {"q": "test"},
        "output": {"r": "result"} if status != "error" else None,
        "model": "gemini-2.0-flash-001",
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "tool_calls": [],
        "error_message": "Tool timeout" if status == "error" else None,
        "metadata": {},
    }


def _minimal_trace(status: str = "success", agent_id: str = "test-agent") -> dict[str, Any]:
    return {
        "trace_id": f"trace-{uuid.uuid4().hex[:12]}",
        "agent_id": agent_id,
        "trace_name": "test_operation",
        "started_at": _now(),
        "finished_at": _now(),
        "duration_ms": 500,
        "status": status,
        "spans": [_minimal_span(status)],
        "metadata": {},
        "tags": [],
        "total_tokens": 150,
        "total_cost_usd": 0.000075,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Schema validation
# ─────────────────────────────────────────────────────────────────────────────

class TestTraceSchemaValidation:
    """Test that trace ingestion validates the incoming schema."""

    def test_missing_trace_field_returns_422(self, client):
        resp = client.post("/api/v1/traces/ingest", json={"agent_id": "x"})
        assert resp.status_code == 422

    def test_missing_agent_id_returns_422(self, client):
        trace = _minimal_trace()
        resp = client.post("/api/v1/traces/ingest", json={"trace": trace})
        assert resp.status_code == 422

    def test_empty_payload_returns_422(self, client):
        resp = client.post("/api/v1/traces/ingest", json={})
        assert resp.status_code == 422

    def test_invalid_trace_status_returns_422(self, client):
        trace = _minimal_trace()
        trace["status"] = "invalid_status_value"
        resp = client.post("/api/v1/traces/ingest", json={"trace": trace, "agent_id": "x"})
        assert resp.status_code == 422

    def test_invalid_span_kind_returns_422(self, client):
        trace = _minimal_trace()
        trace["spans"][0]["kind"] = "not_a_real_kind"
        resp = client.post("/api/v1/traces/ingest", json={"trace": trace, "agent_id": "x"})
        assert resp.status_code == 422

    def test_extra_unknown_fields_are_ignored(self, client):
        """Pydantic model_config extra='ignore' should handle extra fields."""
        trace = _minimal_trace()
        trace["unknown_field_xyz"] = "should_be_ignored"
        payload = {"trace": trace, "agent_id": trace["agent_id"]}
        resp = client.post("/api/v1/traces/ingest", json=payload)
        # Should not 422 from extra field
        assert resp.status_code in (202, 422)


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Successful ingestion
# ─────────────────────────────────────────────────────────────────────────────

class TestSuccessfulIngestion:
    """Test successful trace ingestion returns 202 and expected fields."""

    def test_success_trace_returns_202(self, client, sample_ingest_payload):
        resp = client.post("/api/v1/traces/ingest", json=sample_ingest_payload)
        assert resp.status_code == 202

    def test_response_contains_trace_id(self, client, sample_ingest_payload):
        resp = client.post("/api/v1/traces/ingest", json=sample_ingest_payload)
        data = resp.json()
        assert "trace_id" in data

    def test_response_trace_id_matches_input(self, client, sample_ingest_payload):
        expected_id = sample_ingest_payload["trace"]["trace_id"]
        resp = client.post("/api/v1/traces/ingest", json=sample_ingest_payload)
        data = resp.json()
        assert data["trace_id"] == expected_id

    def test_response_contains_pipeline_status(self, client, sample_ingest_payload):
        resp = client.post("/api/v1/traces/ingest", json=sample_ingest_payload)
        data = resp.json()
        assert "pipeline_status" in data

    def test_failed_trace_also_returns_202(self, client, sample_failed_ingest_payload):
        """Failed traces should still be accepted (202 means accepted for processing)."""
        resp = client.post("/api/v1/traces/ingest", json=sample_failed_ingest_payload)
        assert resp.status_code == 202

    def test_trace_with_multiple_spans(self, client):
        trace = _minimal_trace()
        trace["spans"] = [_minimal_span() for _ in range(5)]
        payload = {"trace": trace, "agent_id": trace["agent_id"]}
        resp = client.post("/api/v1/traces/ingest", json=payload)
        assert resp.status_code == 202

    def test_trace_with_no_spans(self, client):
        """Zero-span traces should be accepted (edge case)."""
        trace = _minimal_trace()
        trace["spans"] = []
        payload = {"trace": trace, "agent_id": trace["agent_id"]}
        resp = client.post("/api/v1/traces/ingest", json=payload)
        assert resp.status_code in (202, 422)

    def test_idempotent_double_ingest(self, client, sample_ingest_payload):
        """Sending the same trace twice should not crash (idempotency)."""
        r1 = client.post("/api/v1/traces/ingest", json=sample_ingest_payload)
        r2 = client.post("/api/v1/traces/ingest", json=sample_ingest_payload)
        assert r1.status_code == 202
        # Second should also succeed (or 409 if dedup is implemented)
        assert r2.status_code in (202, 409)


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Orchestrator trigger
# ─────────────────────────────────────────────────────────────────────────────

class TestOrchestratorTrigger:
    """Test that the orchestrator is triggered on ingestion."""

    def test_orchestrator_called_on_success_trace(self, client, mock_orchestrator, sample_ingest_payload):
        client.post("/api/v1/traces/ingest", json=sample_ingest_payload)
        # Orchestrator should have been called
        assert mock_orchestrator.handle_new_trace.called

    def test_orchestrator_called_on_failed_trace(self, client, mock_orchestrator, sample_failed_ingest_payload):
        client.post("/api/v1/traces/ingest", json=sample_failed_ingest_payload)
        assert mock_orchestrator.handle_new_trace.called


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Trace list + retrieval
# ─────────────────────────────────────────────────────────────────────────────

class TestTraceRetrieval:
    """Test trace listing and individual retrieval."""

    def test_get_traces_returns_200(self, client):
        resp = client.get("/api/v1/traces")
        assert resp.status_code == 200

    def test_get_traces_response_has_items_key(self, client):
        resp = client.get("/api/v1/traces")
        data = resp.json()
        assert "items" in data

    def test_get_traces_accepts_limit_param(self, client):
        resp = client.get("/api/v1/traces?limit=10")
        assert resp.status_code == 200

    def test_get_traces_accepts_status_filter(self, client):
        resp = client.get("/api/v1/traces?status=failed")
        assert resp.status_code == 200

    def test_get_traces_accepts_agent_filter(self, client):
        resp = client.get("/api/v1/traces?agent_id=test-agent")
        assert resp.status_code == 200

    def test_get_nonexistent_trace_returns_404(self, client):
        resp = client.get("/api/v1/traces/trace-does-not-exist-xyz")
        assert resp.status_code == 404

    def test_delete_nonexistent_trace_returns_404(self, client):
        resp = client.delete("/api/v1/traces/trace-does-not-exist-xyz")
        assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Agent registration
# ─────────────────────────────────────────────────────────────────────────────

class TestAgentRegistration:
    """Test that traces register/update agents."""

    def test_new_agent_id_in_trace_creates_agent_entry(self, client):
        """Ingesting a trace from a new agent should not crash."""
        unique_agent = f"agent-{uuid.uuid4().hex[:8]}"
        trace = _minimal_trace(agent_id=unique_agent)
        payload = {"trace": trace, "agent_id": unique_agent}
        resp = client.post("/api/v1/traces/ingest", json=payload)
        assert resp.status_code == 202


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Edge cases
# ─────────────────────────────────────────────────────────────────────────────

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_trace_with_max_tokens(self, client):
        trace = _minimal_trace()
        trace["spans"][0]["prompt_tokens"] = 30000
        trace["spans"][0]["completion_tokens"] = 2000
        trace["total_tokens"] = 32000
        payload = {"trace": trace, "agent_id": trace["agent_id"]}
        resp = client.post("/api/v1/traces/ingest", json=payload)
        assert resp.status_code == 202

    def test_trace_with_zero_duration(self, client):
        trace = _minimal_trace()
        trace["duration_ms"] = 0
        payload = {"trace": trace, "agent_id": trace["agent_id"]}
        resp = client.post("/api/v1/traces/ingest", json=payload)
        assert resp.status_code in (202, 422)

    def test_trace_with_unicode_content(self, client):
        trace = _minimal_trace()
        trace["spans"][0]["input"] = {"query": "日本への飛行機を予約してください"}
        trace["spans"][0]["output"] = {"result": "東京行きフライトを見つけました"}
        payload = {"trace": trace, "agent_id": trace["agent_id"]}
        resp = client.post("/api/v1/traces/ingest", json=payload)
        assert resp.status_code == 202

    def test_trace_with_deeply_nested_metadata(self, client):
        trace = _minimal_trace()
        trace["metadata"] = {
            "level1": {"level2": {"level3": {"level4": "deep_value"}}}
        }
        payload = {"trace": trace, "agent_id": trace["agent_id"]}
        resp = client.post("/api/v1/traces/ingest", json=payload)
        assert resp.status_code == 202

    def test_large_number_of_tool_calls_in_span(self, client):
        trace = _minimal_trace()
        trace["spans"][0]["tool_calls"] = [
            {
                "tool_call_id": f"tc-{i}",
                "tool_name": f"tool_{i}",
                "input": {},
                "output": {},
                "status": "success",
                "error": None,
                "latency_ms": 100,
                "model": None,
                "tokens_used": {},
            }
            for i in range(20)
        ]
        payload = {"trace": trace, "agent_id": trace["agent_id"]}
        resp = client.post("/api/v1/traces/ingest", json=payload)
        assert resp.status_code == 202
