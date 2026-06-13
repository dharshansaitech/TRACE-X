"""
backend/tests/test_replay.py
Tests for the ReplayEngine and replay API endpoints.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from replay.engine import ReplayEngine


def _ts(offset_seconds: float = 0) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)).isoformat()


def _make_llm_span(
    span_id: str,
    name: str,
    status: str = "success",
    offset_s: float = 0,
    duration_ms: int = 400,
    prompt_tokens: int = 200,
    completion_tokens: int = 100,
    error_msg: str | None = None,
) -> dict[str, Any]:
    return {
        "span_id": span_id,
        "name": name,
        "kind": "llm",
        "status": status,
        "started_at": _ts(offset_s),
        "finished_at": _ts(offset_s + duration_ms / 1000),
        "duration_ms": duration_ms,
        "input": {"prompt": f"Test prompt for {name}"},
        "output": {"response": f"Test response from {name}"} if status != "error" else None,
        "model": "gemini-2.0-flash-001",
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "tool_calls": [],
        "error_message": error_msg,
        "metadata": {},
    }


def _make_tool_span(
    span_id: str,
    name: str,
    status: str = "success",
    offset_s: float = 0,
    duration_ms: int = 200,
    error_msg: str | None = None,
    tool_calls: list | None = None,
) -> dict[str, Any]:
    return {
        "span_id": span_id,
        "name": name,
        "kind": "tool",
        "status": status,
        "started_at": _ts(offset_s),
        "finished_at": _ts(offset_s + duration_ms / 1000),
        "duration_ms": duration_ms,
        "input": {"params": "test"},
        "output": {"result": "data"} if status != "error" else None,
        "model": None,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "tool_calls": tool_calls or [],
        "error_message": error_msg,
        "metadata": {},
    }


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def simple_success_trace() -> dict[str, Any]:
    return {
        "trace_id": f"trace-{uuid.uuid4().hex[:12]}",
        "agent_id": "test-agent",
        "trace_name": "simple_task",
        "started_at": _ts(0),
        "finished_at": _ts(2.5),
        "duration_ms": 2500,
        "status": "success",
        "spans": [
            _make_llm_span("span-1", "parse_input", offset_s=0.0, duration_ms=350),
            _make_tool_span("span-2", "fetch_data", offset_s=0.4, duration_ms=250),
            _make_llm_span("span-3", "generate_output", offset_s=0.7, duration_ms=500),
        ],
        "metadata": {},
        "tags": [],
        "total_tokens": 600,
        "total_cost_usd": 0.0003,
    }


@pytest.fixture
def failed_trace_with_tool_error() -> dict[str, Any]:
    return {
        "trace_id": f"trace-{uuid.uuid4().hex[:12]}",
        "agent_id": "travel-bot-v1",
        "trace_name": "travel_booking",
        "started_at": _ts(0),
        "finished_at": _ts(8.5),
        "duration_ms": 8500,
        "status": "failed",
        "spans": [
            _make_llm_span("span-a1", "parse_intent", offset_s=0.0, duration_ms=400),
            _make_tool_span("span-a2", "search_flights", status="error", offset_s=0.45,
                            duration_ms=5001, error_msg="503 upstream timeout"),
            _make_tool_span("span-a3", "search_flights", status="error", offset_s=5.5,
                            duration_ms=5010, error_msg="503 upstream timeout"),
            _make_llm_span("span-a4", "generate_degraded", offset_s=10.6,
                           duration_ms=450, prompt_tokens=180, completion_tokens=55),
        ],
        "metadata": {},
        "tags": [],
        "total_tokens": 835,
        "total_cost_usd": 0.000418,
        "failure_type": "tool_failure",
    }


@pytest.fixture
def diagnosis_for_failed_trace(failed_trace_with_tool_error) -> dict[str, Any]:
    return {
        "diagnosis_id": f"diag-{uuid.uuid4().hex[:12]}",
        "trace_id": failed_trace_with_tool_error["trace_id"],
        "root_cause_category": "tool_failure",
        "severity": "high",
        "confidence": 0.87,
        "summary": "search_flights API returned 503 twice",
        "root_cause_detail": "Upstream flight API unavailable",
        "blast_radius": {
            "affected_spans": ["span-a2", "span-a3"],
            "affected_tools": ["search_flights"],
            "downstream_impact": "No flight data",
            "user_impact": "Degraded response",
        },
        "reasoning_steps": [
            {"step": 1, "observation": "Tool error", "conclusion": "Tool failure"},
        ],
        "recommended_actions": ["Add circuit breaker"],
        "anomaly_signals": [],
        "arize_insights": {},
        "similar_trace_ids": [],
        "created_at": _ts(),
    }


@pytest.fixture
def trace_with_tool_calls_in_spans() -> dict[str, Any]:
    """Trace where span contains explicit tool_calls list."""
    return {
        "trace_id": f"trace-{uuid.uuid4().hex[:12]}",
        "agent_id": "code-reviewer-v1",
        "trace_name": "code_review",
        "started_at": _ts(0),
        "finished_at": _ts(3),
        "duration_ms": 3000,
        "status": "success",
        "spans": [
            {
                "span_id": "span-cr1",
                "name": "analyze_diff",
                "kind": "llm",
                "status": "success",
                "started_at": _ts(0),
                "finished_at": _ts(2.5),
                "duration_ms": 2500,
                "input": {"diff": "--- a/file.py\n+++ b/file.py"},
                "output": {"issues": ["Line 10: unused import"]},
                "model": "gemini-2.0-flash-001",
                "prompt_tokens": 500,
                "completion_tokens": 200,
                "tool_calls": [
                    {
                        "tool_call_id": "tc-1",
                        "tool_name": "run_linter",
                        "input": {"file": "file.py"},
                        "output": {"warnings": 2},
                        "status": "success",
                        "error": None,
                        "latency_ms": 150,
                        "model": None,
                        "tokens_used": {},
                    },
                    {
                        "tool_call_id": "tc-2",
                        "tool_name": "check_tests",
                        "input": {"file": "file.py"},
                        "output": {"passed": True},
                        "status": "success",
                        "error": None,
                        "latency_ms": 220,
                        "model": None,
                        "tokens_used": {},
                    },
                ],
                "error_message": None,
                "metadata": {},
            },
        ],
        "metadata": {},
        "tags": [],
        "total_tokens": 700,
        "total_cost_usd": 0.00035,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tests: ReplayEngine.build_session
# ─────────────────────────────────────────────────────────────────────────────

class TestReplayEngineSession:
    """Tests for the core session-building logic."""

    def test_build_session_returns_dict(self, simple_success_trace):
        engine = ReplayEngine()
        session = engine.build_session(simple_success_trace)
        assert isinstance(session, dict)

    def test_session_has_session_id(self, simple_success_trace):
        engine = ReplayEngine()
        session = engine.build_session(simple_success_trace)
        assert "session_id" in session

    def test_session_trace_id_matches(self, simple_success_trace):
        engine = ReplayEngine()
        session = engine.build_session(simple_success_trace)
        assert session["trace_id"] == simple_success_trace["trace_id"]

    def test_session_has_frames(self, simple_success_trace):
        engine = ReplayEngine()
        session = engine.build_session(simple_success_trace)
        assert "frames" in session
        assert len(session["frames"]) > 0

    def test_frames_count_greater_than_spans(self, simple_success_trace):
        """Each span should generate at least 2 frames (start + end)."""
        engine = ReplayEngine()
        session = engine.build_session(simple_success_trace)
        span_count = len(simple_success_trace["spans"])
        assert len(session["frames"]) >= span_count * 2

    def test_frames_have_required_fields(self, simple_success_trace):
        engine = ReplayEngine()
        session = engine.build_session(simple_success_trace)
        for frame in session["frames"]:
            assert "frame_index" in frame
            assert "frame_type" in frame
            assert "timestamp" in frame

    def test_frames_are_sorted_by_timestamp(self, failed_trace_with_tool_error):
        engine = ReplayEngine()
        session = engine.build_session(failed_trace_with_tool_error)
        timestamps = [f["timestamp"] for f in session["frames"]]
        assert timestamps == sorted(timestamps)

    def test_frames_are_indexed_sequentially(self, simple_success_trace):
        engine = ReplayEngine()
        session = engine.build_session(simple_success_trace)
        for i, frame in enumerate(session["frames"]):
            assert frame["frame_index"] == i

    def test_total_frames_matches_frame_list(self, simple_success_trace):
        engine = ReplayEngine()
        session = engine.build_session(simple_success_trace)
        assert session["total_frames"] == len(session["frames"])

    def test_session_duration_ms_is_positive(self, simple_success_trace):
        engine = ReplayEngine()
        session = engine.build_session(simple_success_trace)
        assert session["duration_ms"] > 0


class TestReplayFrameTypes:
    """Tests for specific frame type generation."""

    def test_llm_prompt_frames_present(self, simple_success_trace):
        engine = ReplayEngine()
        session = engine.build_session(simple_success_trace)
        frame_types = [f["frame_type"] for f in session["frames"]]
        assert "llm_prompt" in frame_types

    def test_llm_response_frames_present(self, simple_success_trace):
        engine = ReplayEngine()
        session = engine.build_session(simple_success_trace)
        frame_types = [f["frame_type"] for f in session["frames"]]
        assert "llm_response" in frame_types

    def test_tool_call_frames_present(self, trace_with_tool_calls_in_spans):
        engine = ReplayEngine()
        session = engine.build_session(trace_with_tool_calls_in_spans)
        frame_types = [f["frame_type"] for f in session["frames"]]
        assert "tool_call" in frame_types

    def test_error_frames_in_failed_trace(self, failed_trace_with_tool_error):
        engine = ReplayEngine()
        session = engine.build_session(failed_trace_with_tool_error)
        frame_types = [f["frame_type"] for f in session["frames"]]
        assert "error_event" in frame_types

    def test_agent_start_frame_is_first(self, simple_success_trace):
        engine = ReplayEngine()
        session = engine.build_session(simple_success_trace)
        first_frame = session["frames"][0]
        assert first_frame["frame_type"] == "agent_start"

    def test_agent_end_frame_is_last(self, simple_success_trace):
        engine = ReplayEngine()
        session = engine.build_session(simple_success_trace)
        last_frame = session["frames"][-1]
        assert last_frame["frame_type"] == "agent_end"


class TestReplayDiagnosisAnnotations:
    """Tests for diagnosis annotations in replay frames."""

    def test_failure_frame_indices_populated(self, failed_trace_with_tool_error, diagnosis_for_failed_trace):
        engine = ReplayEngine()
        session = engine.build_session(failed_trace_with_tool_error, diagnosis_for_failed_trace)
        assert "failure_frame_indices" in session
        assert len(session["failure_frame_indices"]) > 0

    def test_divergence_frame_index_set(self, failed_trace_with_tool_error, diagnosis_for_failed_trace):
        engine = ReplayEngine()
        session = engine.build_session(failed_trace_with_tool_error, diagnosis_for_failed_trace)
        assert "divergence_frame_index" in session

    def test_error_frames_have_annotations(self, failed_trace_with_tool_error, diagnosis_for_failed_trace):
        engine = ReplayEngine()
        session = engine.build_session(failed_trace_with_tool_error, diagnosis_for_failed_trace)
        error_frames = [f for f in session["frames"] if f["frame_type"] == "error_event"]
        assert len(error_frames) > 0

    def test_session_without_diagnosis_works(self, failed_trace_with_tool_error):
        """Session should build successfully without diagnosis."""
        engine = ReplayEngine()
        session = engine.build_session(failed_trace_with_tool_error, diagnosis=None)
        assert session is not None
        assert "frames" in session


class TestReplayEdgeCases:
    """Edge cases for the replay engine."""

    def test_empty_spans_trace(self):
        trace = {
            "trace_id": "empty-trace",
            "agent_id": "test",
            "trace_name": "empty",
            "started_at": _ts(0),
            "finished_at": _ts(1),
            "duration_ms": 1000,
            "status": "failed",
            "spans": [],
            "metadata": {},
            "tags": [],
            "total_tokens": 0,
            "total_cost_usd": 0.0,
        }
        engine = ReplayEngine()
        session = engine.build_session(trace)
        # Should at least have agent_start and agent_end
        assert len(session["frames"]) >= 2

    def test_single_span_trace(self):
        trace = {
            "trace_id": "single-span",
            "agent_id": "test",
            "trace_name": "single",
            "started_at": _ts(0),
            "finished_at": _ts(0.5),
            "duration_ms": 500,
            "status": "success",
            "spans": [_make_llm_span("span-only", "only_step", offset_s=0)],
            "metadata": {},
            "tags": [],
            "total_tokens": 300,
            "total_cost_usd": 0.00015,
        }
        engine = ReplayEngine()
        session = engine.build_session(trace)
        assert len(session["frames"]) >= 3  # start + llm_prompt + llm_response + end

    def test_trace_with_tool_error_frames(self):
        trace = {
            "trace_id": "tool-err",
            "agent_id": "test",
            "trace_name": "failing_tool",
            "started_at": _ts(0),
            "finished_at": _ts(5),
            "duration_ms": 5000,
            "status": "failed",
            "spans": [
                _make_tool_span(
                    "span-err", "bad_tool", status="error",
                    error_msg="Connection refused", offset_s=0
                )
            ],
            "metadata": {},
            "tags": [],
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "failure_type": "tool_failure",
        }
        engine = ReplayEngine()
        session = engine.build_session(trace)
        assert session is not None

    def test_replay_api_endpoint(self, client):
        resp = client.get("/api/v1/traces/nonexistent-trace-id/replay")
        assert resp.status_code == 404
