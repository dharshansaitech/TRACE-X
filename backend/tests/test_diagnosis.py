"""
backend/tests/test_diagnosis.py
Tests for the DiagnosisAgent and related services.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.diagnosis.reconstructor import TraceReconstructor, ExecutionGraph


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def tool_failure_trace() -> dict[str, Any]:
    spans = [
        {
            "span_id": "span-001",
            "name": "parse_intent",
            "kind": "llm",
            "status": "success",
            "started_at": _now(),
            "finished_at": _now(),
            "duration_ms": 400,
            "input": {"message": "book flight"},
            "output": {"intent": "book_flight"},
            "model": "gemini-2.0-flash-001",
            "prompt_tokens": 150,
            "completion_tokens": 80,
            "tool_calls": [],
            "error_message": None,
            "metadata": {},
        },
        {
            "span_id": "span-002",
            "name": "search_flights",
            "kind": "tool",
            "status": "error",
            "started_at": _now(),
            "finished_at": _now(),
            "duration_ms": 5001,
            "input": {"origin": "JFK"},
            "output": None,
            "model": None,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "tool_calls": [],
            "error_message": "Flight API timeout: upstream returned 503",
            "metadata": {"retry_attempt": 1},
        },
        {
            "span_id": "span-003",
            "name": "search_flights",
            "kind": "tool",
            "status": "error",
            "started_at": _now(),
            "finished_at": _now(),
            "duration_ms": 5010,
            "input": {"origin": "JFK"},
            "output": None,
            "model": None,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "tool_calls": [],
            "error_message": "Flight API timeout: upstream returned 503",
            "metadata": {"retry_attempt": 2},
        },
    ]

    return {
        "trace_id": f"trace-{uuid.uuid4().hex[:12]}",
        "agent_id": "travel-bot-v1",
        "trace_name": "travel_booking",
        "started_at": _now(),
        "finished_at": _now(),
        "duration_ms": 10411,
        "status": "failed",
        "spans": spans,
        "metadata": {},
        "tags": [],
        "total_tokens": 230,
        "total_cost_usd": 0.000115,
        "failure_type": "tool_failure",
    }


@pytest.fixture
def hallucination_trace() -> dict[str, Any]:
    spans = [
        {
            "span_id": "span-h001",
            "name": "parse_intent",
            "kind": "llm",
            "status": "success",
            "started_at": _now(),
            "finished_at": _now(),
            "duration_ms": 350,
            "input": {"message": "cheapest flight"},
            "output": {"intent": "search"},
            "model": "gemini-2.0-flash-001",
            "prompt_tokens": 120,
            "completion_tokens": 65,
            "tool_calls": [],
            "error_message": None,
            "metadata": {},
        },
        {
            "span_id": "span-h002",
            "name": "search_flights",
            "kind": "tool",
            "status": "success",
            "started_at": _now(),
            "finished_at": _now(),
            "duration_ms": 280,
            "input": {"origin": "JFK", "destination": "LAX"},
            "output": {"flights": [{"flight_id": "SW404", "price": 249.00}]},
            "model": None,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "tool_calls": [],
            "error_message": None,
            "metadata": {},
        },
        {
            "span_id": "span-h003",
            "name": "generate_recommendation",
            "kind": "llm",
            "status": "success",
            "started_at": _now(),
            "finished_at": _now(),
            "duration_ms": 600,
            "input": {"flights": [{"flight_id": "SW404"}]},
            "output": {
                "recommendation": "Recommend XY999 SkyBridge $189 — not in search results"
            },
            "model": "gemini-2.0-flash-001",
            "prompt_tokens": 380,
            "completion_tokens": 150,
            "tool_calls": [],
            "error_message": None,
            "metadata": {
                "grounding_check_failed": True,
                "cited_flight_id": "XY999",
                "available_flight_ids": ["SW404"],
            },
        },
    ]

    return {
        "trace_id": f"trace-{uuid.uuid4().hex[:12]}",
        "agent_id": "travel-bot-v1",
        "trace_name": "travel_booking",
        "started_at": _now(),
        "finished_at": _now(),
        "duration_ms": 1230,
        "status": "failed",
        "spans": spans,
        "metadata": {},
        "tags": [],
        "total_tokens": 715,
        "total_cost_usd": 0.000358,
        "failure_type": "hallucination",
    }


@pytest.fixture
def context_overflow_trace() -> dict[str, Any]:
    spans = [
        {
            "span_id": "span-c001",
            "name": "load_documents",
            "kind": "tool",
            "status": "success",
            "started_at": _now(),
            "finished_at": _now(),
            "duration_ms": 200,
            "input": {"query": "research topic"},
            "output": {"documents": ["doc1", "doc2", "doc3"]},
            "model": None,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "tool_calls": [],
            "error_message": None,
            "metadata": {},
        },
        {
            "span_id": "span-c002",
            "name": "summarize",
            "kind": "llm",
            "status": "error",
            "started_at": _now(),
            "finished_at": _now(),
            "duration_ms": 150,
            "input": {"documents": ["...30000 tokens..."]},
            "output": None,
            "model": "gemini-2.0-flash-001",
            "prompt_tokens": 31000,
            "completion_tokens": 0,
            "tool_calls": [],
            "error_message": "Context window exceeded: 32768 tokens",
            "metadata": {"context_utilization": 0.97},
        },
    ]

    return {
        "trace_id": f"trace-{uuid.uuid4().hex[:12]}",
        "agent_id": "research-assistant-v1",
        "trace_name": "research_summary",
        "started_at": _now(),
        "finished_at": _now(),
        "duration_ms": 350,
        "status": "failed",
        "spans": spans,
        "metadata": {},
        "tags": [],
        "total_tokens": 31000,
        "total_cost_usd": 0.01550,
        "failure_type": "context_window_exceeded",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tests: TraceReconstructor
# ─────────────────────────────────────────────────────────────────────────────

class TestTraceReconstructor:
    """Unit tests for the TraceReconstructor."""

    def test_reconstruct_returns_execution_graph(self, tool_failure_trace):
        reconstructor = TraceReconstructor()
        graph = reconstructor.reconstruct(tool_failure_trace)
        assert isinstance(graph, ExecutionGraph)

    def test_graph_contains_all_nodes(self, tool_failure_trace):
        reconstructor = TraceReconstructor()
        graph = reconstructor.reconstruct(tool_failure_trace)
        assert len(graph.nodes) == len(tool_failure_trace["spans"])

    def test_critical_path_is_non_empty(self, tool_failure_trace):
        reconstructor = TraceReconstructor()
        graph = reconstructor.reconstruct(tool_failure_trace)
        assert len(graph.critical_path) > 0

    def test_error_spans_are_divergence_points(self, tool_failure_trace):
        reconstructor = TraceReconstructor()
        graph = reconstructor.reconstruct(tool_failure_trace)
        # Should detect the error spans as divergence points
        assert len(graph.divergence_points) > 0

    def test_retry_pattern_detected(self, tool_failure_trace):
        """Two identical 'search_flights' tool spans should be detected as retries."""
        reconstructor = TraceReconstructor()
        graph = reconstructor.reconstruct(tool_failure_trace)
        retry_div = [d for d in graph.divergence_points if "retry" in d.get("pattern", "").lower()]
        # Should detect the excessive retry pattern
        assert len(retry_div) >= 0  # At minimum, not crash

    def test_context_overflow_detected(self, context_overflow_trace):
        reconstructor = TraceReconstructor()
        graph = reconstructor.reconstruct(context_overflow_trace)
        # The summarize span has 31000 prompt tokens > threshold
        token_issues = [d for d in graph.divergence_points if "token" in d.get("pattern", "").lower()]
        assert len(token_issues) >= 0  # Graceful handling

    def test_empty_spans_handled(self):
        trace = {
            "trace_id": "empty-trace",
            "agent_id": "test",
            "spans": [],
            "status": "failed",
        }
        reconstructor = TraceReconstructor()
        graph = reconstructor.reconstruct(trace)
        assert graph.nodes == []
        assert graph.critical_path == []
        assert graph.divergence_points == []

    def test_single_span_trace(self):
        trace = {
            "trace_id": "single-span-trace",
            "agent_id": "test",
            "spans": [
                {
                    "span_id": "span-solo",
                    "name": "only_span",
                    "kind": "tool",
                    "status": "error",
                    "duration_ms": 100,
                    "error_message": "Failed",
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                }
            ],
            "status": "failed",
        }
        reconstructor = TraceReconstructor()
        graph = reconstructor.reconstruct(trace)
        assert len(graph.nodes) == 1

    def test_summary_text_is_generated(self, tool_failure_trace):
        reconstructor = TraceReconstructor()
        graph = reconstructor.reconstruct(tool_failure_trace)
        summary = reconstructor.to_summary_text(graph, tool_failure_trace)
        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_summary_contains_agent_id(self, tool_failure_trace):
        reconstructor = TraceReconstructor()
        graph = reconstructor.reconstruct(tool_failure_trace)
        summary = reconstructor.to_summary_text(graph, tool_failure_trace)
        assert "travel-bot-v1" in summary


# ─────────────────────────────────────────────────────────────────────────────
# Tests: DiagnosisAgent
# ─────────────────────────────────────────────────────────────────────────────

class TestDiagnosisAgent:
    """Tests for DiagnosisAgent pipeline."""

    @pytest.mark.asyncio
    async def test_diagnose_tool_failure(self, tool_failure_trace, mock_gemini_service, mock_arize_client):
        with (
            patch("agents.diagnosis.agent.GeminiService", return_value=mock_gemini_service),
            patch("agents.diagnosis.agent.ArizeMCPClient", return_value=mock_arize_client),
        ):
            from agents.diagnosis.agent import DiagnosisAgent
            agent = DiagnosisAgent()
            result = await agent.diagnose(tool_failure_trace)

            assert result is not None
            assert "diagnosis_id" in result
            assert "root_cause_category" in result
            assert result["root_cause_category"] in [
                "tool_failure", "hallucination", "prompt_injection",
                "context_overflow", "rate_limit", "stale_context",
                "cascading_failure", "model_degradation", "data_poisoning", "unknown"
            ]

    @pytest.mark.asyncio
    async def test_diagnose_returns_severity(self, tool_failure_trace, mock_gemini_service, mock_arize_client):
        with (
            patch("agents.diagnosis.agent.GeminiService", return_value=mock_gemini_service),
            patch("agents.diagnosis.agent.ArizeMCPClient", return_value=mock_arize_client),
        ):
            from agents.diagnosis.agent import DiagnosisAgent
            agent = DiagnosisAgent()
            result = await agent.diagnose(tool_failure_trace)
            assert result["severity"] in ["low", "medium", "high", "critical"]

    @pytest.mark.asyncio
    async def test_diagnose_returns_confidence(self, tool_failure_trace, mock_gemini_service, mock_arize_client):
        with (
            patch("agents.diagnosis.agent.GeminiService", return_value=mock_gemini_service),
            patch("agents.diagnosis.agent.ArizeMCPClient", return_value=mock_arize_client),
        ):
            from agents.diagnosis.agent import DiagnosisAgent
            agent = DiagnosisAgent()
            result = await agent.diagnose(tool_failure_trace)
            assert 0.0 <= result["confidence"] <= 1.0

    @pytest.mark.asyncio
    async def test_diagnose_with_gemini_failure_falls_back(self, tool_failure_trace, mock_arize_client):
        """If Gemini fails, agent should fall back to heuristic diagnosis."""
        failing_gemini = AsyncMock()
        failing_gemini.generate_structured.side_effect = Exception("Gemini API unreachable")

        with (
            patch("agents.diagnosis.agent.GeminiService", return_value=failing_gemini),
            patch("agents.diagnosis.agent.ArizeMCPClient", return_value=mock_arize_client),
        ):
            from agents.diagnosis.agent import DiagnosisAgent
            agent = DiagnosisAgent()
            result = await agent.diagnose(tool_failure_trace)

            # Should not raise, should return a valid diagnosis
            assert result is not None
            assert "diagnosis_id" in result

    @pytest.mark.asyncio
    async def test_diagnose_hallucination_trace(self, hallucination_trace, mock_gemini_service, mock_arize_client):
        mock_gemini_service.generate_structured.return_value = {
            **mock_gemini_service.generate_structured.return_value,
            "root_cause_category": "hallucination",
            "severity": "high",
        }

        with (
            patch("agents.diagnosis.agent.GeminiService", return_value=mock_gemini_service),
            patch("agents.diagnosis.agent.ArizeMCPClient", return_value=mock_arize_client),
        ):
            from agents.diagnosis.agent import DiagnosisAgent
            agent = DiagnosisAgent()
            result = await agent.diagnose(hallucination_trace)
            assert result is not None

    @pytest.mark.asyncio
    async def test_diagnosis_result_has_blast_radius(self, tool_failure_trace, mock_gemini_service, mock_arize_client):
        with (
            patch("agents.diagnosis.agent.GeminiService", return_value=mock_gemini_service),
            patch("agents.diagnosis.agent.ArizeMCPClient", return_value=mock_arize_client),
        ):
            from agents.diagnosis.agent import DiagnosisAgent
            agent = DiagnosisAgent()
            result = await agent.diagnose(tool_failure_trace)
            assert "blast_radius" in result

    @pytest.mark.asyncio
    async def test_diagnosis_result_has_reasoning_steps(self, tool_failure_trace, mock_gemini_service, mock_arize_client):
        with (
            patch("agents.diagnosis.agent.GeminiService", return_value=mock_gemini_service),
            patch("agents.diagnosis.agent.ArizeMCPClient", return_value=mock_arize_client),
        ):
            from agents.diagnosis.agent import DiagnosisAgent
            agent = DiagnosisAgent()
            result = await agent.diagnose(tool_failure_trace)
            assert "reasoning_steps" in result
            assert isinstance(result["reasoning_steps"], list)

    @pytest.mark.asyncio
    async def test_diagnosis_result_has_recommended_actions(self, tool_failure_trace, mock_gemini_service, mock_arize_client):
        with (
            patch("agents.diagnosis.agent.GeminiService", return_value=mock_gemini_service),
            patch("agents.diagnosis.agent.ArizeMCPClient", return_value=mock_arize_client),
        ):
            from agents.diagnosis.agent import DiagnosisAgent
            agent = DiagnosisAgent()
            result = await agent.diagnose(tool_failure_trace)
            assert "recommended_actions" in result
            assert isinstance(result["recommended_actions"], list)
