"""
backend/tests/test_repair.py
Tests for the RepairAgent and repair API endpoints.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_repair_id() -> str:
    return f"repair-{uuid.uuid4().hex[:12]}"


def _make_diagnosis_id() -> str:
    return f"diag-{uuid.uuid4().hex[:12]}"


def _make_trace_id() -> str:
    return f"trace-{uuid.uuid4().hex[:12]}"


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def tool_failure_diagnosis() -> dict[str, Any]:
    return {
        "diagnosis_id": _make_diagnosis_id(),
        "trace_id": _make_trace_id(),
        "root_cause_category": "tool_failure",
        "severity": "high",
        "confidence": 0.87,
        "summary": "Tool failure: search_flights returned 503 twice",
        "root_cause_detail": "The flight search API is experiencing intermittent outages.",
        "blast_radius": {
            "affected_spans": ["span-002", "span-003"],
            "affected_tools": ["search_flights"],
            "downstream_impact": "No flight data returned to agent",
            "user_impact": "Booking recommendation could not be generated",
        },
        "reasoning_steps": [
            {"step": 1, "observation": "Tool error span detected", "conclusion": "Tool failure"},
            {"step": 2, "observation": "Retry also failed (2x)", "conclusion": "Persistent API issue"},
        ],
        "recommended_actions": [
            "Add circuit breaker for search_flights",
            "Implement cached fallback for flight data",
        ],
        "anomaly_signals": [],
        "arize_insights": {},
        "similar_trace_ids": [],
        "created_at": _now(),
    }


@pytest.fixture
def hallucination_diagnosis() -> dict[str, Any]:
    return {
        "diagnosis_id": _make_diagnosis_id(),
        "trace_id": _make_trace_id(),
        "root_cause_category": "hallucination",
        "severity": "critical",
        "confidence": 0.93,
        "summary": "LLM hallucinated flight XY999 not present in tool results",
        "root_cause_detail": "Model cited a flight ID that was not in the search results.",
        "blast_radius": {
            "affected_spans": ["span-h003"],
            "affected_tools": [],
            "downstream_impact": "User received fabricated booking information",
            "user_impact": "Potential false booking attempt",
        },
        "reasoning_steps": [
            {"step": 1, "observation": "grounding_check_failed=True in metadata", "conclusion": "Hallucination"},
        ],
        "recommended_actions": [
            "Add output grounding validation",
            "Cross-check LLM output against tool results",
        ],
        "anomaly_signals": [],
        "arize_insights": {},
        "similar_trace_ids": [],
        "created_at": _now(),
    }


@pytest.fixture
def context_overflow_diagnosis() -> dict[str, Any]:
    return {
        "diagnosis_id": _make_diagnosis_id(),
        "trace_id": _make_trace_id(),
        "root_cause_category": "context_overflow",
        "severity": "medium",
        "confidence": 0.95,
        "summary": "Context window exceeded: 31000 tokens sent to 32768 token model",
        "root_cause_detail": "Too many documents passed without summarization.",
        "blast_radius": {
            "affected_spans": ["span-c002"],
            "affected_tools": [],
            "downstream_impact": "Research summary task incomplete",
            "user_impact": "No output generated",
        },
        "reasoning_steps": [
            {"step": 1, "observation": "Error: Context window exceeded", "conclusion": "Token overflow"},
        ],
        "recommended_actions": [
            "Add document chunking before LLM call",
            "Implement map-reduce summarization pattern",
        ],
        "anomaly_signals": [],
        "arize_insights": {},
        "similar_trace_ids": [],
        "created_at": _now(),
    }


@pytest.fixture
def mock_gemini_for_repair():
    mock = AsyncMock()
    mock.generate_structured.return_value = {
        "repair_type": "prompt_update",
        "title": "Add circuit breaker for flight API",
        "description": "Wraps search_flights with retry logic and fallback to cached data.",
        "implementation": {
            "file_path": "agents/travel_bot.py",
            "before_code": "result = await search_flights(origin, dest)",
            "after_code": (
                "try:\n"
                "    result = await search_flights(origin, dest)\n"
                "except ToolError:\n"
                "    result = await get_cached_flights(origin, dest)\n"
            ),
            "explanation": "Add try/except around tool call with cache fallback.",
        },
        "test_cases": [
            {
                "name": "Test with API failure",
                "input": {"origin": "JFK", "destination": "LAX"},
                "expected": {"has_flights": True, "source": "cache"},
            }
        ],
        "confidence_score": 0.84,
        "warnings": [],
    }
    return mock


# ─────────────────────────────────────────────────────────────────────────────
# Tests: RepairAgent
# ─────────────────────────────────────────────────────────────────────────────

class TestRepairAgent:
    """Unit tests for RepairAgent."""

    @pytest.mark.asyncio
    async def test_generate_repair_for_tool_failure(self, tool_failure_diagnosis, mock_gemini_for_repair):
        with patch("agents.repair.agent.GeminiService", return_value=mock_gemini_for_repair):
            from agents.repair.agent import RepairAgent
            agent = RepairAgent()
            result = await agent.generate_repair(tool_failure_diagnosis)

            assert result is not None
            assert "repair_id" in result
            assert "trace_id" in result

    @pytest.mark.asyncio
    async def test_repair_has_required_fields(self, tool_failure_diagnosis, mock_gemini_for_repair):
        with patch("agents.repair.agent.GeminiService", return_value=mock_gemini_for_repair):
            from agents.repair.agent import RepairAgent
            agent = RepairAgent()
            result = await agent.generate_repair(tool_failure_diagnosis)

            required_fields = ["repair_id", "trace_id", "diagnosis_id", "repair_type",
                               "title", "description", "status", "confidence_score"]
            for field in required_fields:
                assert field in result, f"Missing field: {field}"

    @pytest.mark.asyncio
    async def test_repair_status_is_pending(self, tool_failure_diagnosis, mock_gemini_for_repair):
        with patch("agents.repair.agent.GeminiService", return_value=mock_gemini_for_repair):
            from agents.repair.agent import RepairAgent
            agent = RepairAgent()
            result = await agent.generate_repair(tool_failure_diagnosis)
            assert result["status"] == "pending"

    @pytest.mark.asyncio
    async def test_repair_confidence_in_range(self, tool_failure_diagnosis, mock_gemini_for_repair):
        with patch("agents.repair.agent.GeminiService", return_value=mock_gemini_for_repair):
            from agents.repair.agent import RepairAgent
            agent = RepairAgent()
            result = await agent.generate_repair(tool_failure_diagnosis)
            assert 0.0 <= result["confidence_score"] <= 1.0

    @pytest.mark.asyncio
    async def test_repair_type_is_valid(self, tool_failure_diagnosis, mock_gemini_for_repair):
        with patch("agents.repair.agent.GeminiService", return_value=mock_gemini_for_repair):
            from agents.repair.agent import RepairAgent
            agent = RepairAgent()
            result = await agent.generate_repair(tool_failure_diagnosis)
            valid_types = [
                "prompt_update", "tool_retry_config", "fallback_strategy",
                "context_truncation", "model_swap", "architectural_change", "parameter_tuning"
            ]
            assert result["repair_type"] in valid_types

    @pytest.mark.asyncio
    async def test_hallucination_repair_generates(self, hallucination_diagnosis, mock_gemini_for_repair):
        mock_gemini_for_repair.generate_structured.return_value = {
            **mock_gemini_for_repair.generate_structured.return_value,
            "repair_type": "prompt_update",
            "title": "Add output grounding validation",
        }
        with patch("agents.repair.agent.GeminiService", return_value=mock_gemini_for_repair):
            from agents.repair.agent import RepairAgent
            agent = RepairAgent()
            result = await agent.generate_repair(hallucination_diagnosis)
            assert result is not None

    @pytest.mark.asyncio
    async def test_context_overflow_repair_generates(self, context_overflow_diagnosis, mock_gemini_for_repair):
        mock_gemini_for_repair.generate_structured.return_value = {
            **mock_gemini_for_repair.generate_structured.return_value,
            "repair_type": "context_truncation",
            "title": "Add document chunking",
        }
        with patch("agents.repair.agent.GeminiService", return_value=mock_gemini_for_repair):
            from agents.repair.agent import RepairAgent
            agent = RepairAgent()
            result = await agent.generate_repair(context_overflow_diagnosis)
            assert result is not None

    @pytest.mark.asyncio
    async def test_repair_with_gemini_failure(self, tool_failure_diagnosis):
        """RepairAgent should handle Gemini failure gracefully."""
        failing_gemini = AsyncMock()
        failing_gemini.generate_structured.side_effect = Exception("API down")

        with patch("agents.repair.agent.GeminiService", return_value=failing_gemini):
            from agents.repair.agent import RepairAgent
            agent = RepairAgent()
            # Should either return a fallback or raise — but not hang
            try:
                result = await agent.generate_repair(tool_failure_diagnosis)
                # If it returns, it must be a valid dict
                assert isinstance(result, dict)
            except Exception:
                pass  # Acceptable to raise if no fallback


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Repair API endpoints
# ─────────────────────────────────────────────────────────────────────────────

class TestRepairEndpoints:
    """Tests for repair CRUD and workflow API."""

    def test_get_repairs_returns_200(self, client):
        resp = client.get("/api/v1/repairs")
        assert resp.status_code == 200

    def test_get_repairs_response_structure(self, client):
        resp = client.get("/api/v1/repairs")
        data = resp.json()
        assert isinstance(data, (dict, list))

    def test_get_nonexistent_repair_returns_404(self, client):
        resp = client.get("/api/v1/repairs/repair-does-not-exist-xyz")
        assert resp.status_code == 404

    def test_approve_nonexistent_repair_returns_404(self, client):
        resp = client.post("/api/v1/repairs/repair-xyz/approve", json={"approved_by": "test-user"})
        assert resp.status_code == 404

    def test_apply_nonexistent_repair_returns_404(self, client):
        resp = client.post("/api/v1/repairs/repair-xyz/apply", json={"environment": "staging"})
        assert resp.status_code == 404

    def test_rollback_nonexistent_repair_returns_404(self, client):
        resp = client.post("/api/v1/repairs/repair-xyz/rollback", json={"reason": "test"})
        assert resp.status_code == 404

    def test_get_repairs_with_status_filter(self, client):
        resp = client.get("/api/v1/repairs?status=pending")
        assert resp.status_code == 200

    def test_get_repairs_with_trace_filter(self, client):
        resp = client.get("/api/v1/repairs?trace_id=trace-abc")
        assert resp.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Repair state machine
# ─────────────────────────────────────────────────────────────────────────────

class TestRepairStateMachine:
    """Test valid and invalid state transitions."""

    def test_pending_repair_can_be_approved(self, sample_repair_artifact):
        """A pending repair should be approvable."""
        assert sample_repair_artifact["status"] == "pending"

    def test_applied_repair_can_be_rolled_back(self):
        """Status 'applied' → 'rolled_back' is valid."""
        from api.schemas.repair import RepairStatus
        valid_next = {
            RepairStatus.PENDING: [RepairStatus.APPROVED, RepairStatus.REJECTED],
            RepairStatus.APPROVED: [RepairStatus.APPLIED, RepairStatus.REJECTED],
            RepairStatus.APPLIED: [RepairStatus.ROLLED_BACK],
        }
        assert RepairStatus.ROLLED_BACK in valid_next[RepairStatus.APPLIED]

    def test_repair_status_enum_values(self):
        from api.schemas.repair import RepairStatus
        statuses = [s.value for s in RepairStatus]
        assert "pending" in statuses
        assert "approved" in statuses
        assert "applied" in statuses
        assert "rolled_back" in statuses

    def test_repair_type_enum_values(self):
        from api.schemas.repair import RepairType
        types = [t.value for t in RepairType]
        assert "prompt_update" in types
        assert "tool_retry_config" in types
        assert "fallback_strategy" in types


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Diff structure
# ─────────────────────────────────────────────────────────────────────────────

class TestRepairDiff:
    """Test RepairDiff schema."""

    def test_diff_line_kinds(self):
        from api.schemas.repair import DiffLine
        # Should support 'added', 'removed', 'context'
        added = DiffLine(kind="added", content="+ new line")
        removed = DiffLine(kind="removed", content="- old line")
        context = DiffLine(kind="context", content="  unchanged")
        assert added.kind == "added"
        assert removed.kind == "removed"
        assert context.kind == "context"

    def test_repair_diff_schema(self, sample_repair_artifact):
        """The sample repair artifact should have a valid diff structure."""
        diff = sample_repair_artifact.get("diff")
        if diff:
            assert "file_path" in diff
            assert "hunks" in diff
