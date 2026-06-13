# backend/mcp/arize_mcp_client.py
from __future__ import annotations

import json
from typing import Any

import httpx
import structlog

from api.config import Settings

logger = structlog.get_logger(__name__)


class ArizeMCPClient:
    """
    Client for the Arize MCP Server.

    Wraps all Arize tool calls for:
    - Trace similarity search
    - Feature drift detection
    - Model performance baselines
    - Embedding space analysis
    - Anomaly pattern retrieval
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.base_url = settings.arize_mcp_server_url
        self.api_key = settings.arize_api_key
        self.space_key = settings.arize_space_key

    async def _call_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Make an MCP tool call via HTTP."""
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "id": 1,
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        }

        try:
            timeout = httpx.Timeout(5.0, connect=1.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{self.base_url}/mcp",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "X-Space-Key": self.space_key,
                        "Content-Type": "application/json",
                    },
                )
                response.raise_for_status()
                data = response.json()
                if "result" in data:
                    content = data["result"].get("content", [{}])
                    if content and isinstance(content, list):
                        return json.loads(content[0].get("text", "{}"))
                return {}
        except Exception as exc:
            logger.debug("arize_mcp_call_failed", tool=tool_name, error=str(exc))
            return self._get_mock_response(tool_name, arguments)

    def _get_mock_response(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Return mock data when Arize MCP is unavailable (demo mode)."""
        import random

        if tool_name == "search_similar_traces":
            return {
                "similar_traces": [
                    {
                        "trace_id": f"mock-trace-{i}",
                        "similarity_score": round(0.9 - i * 0.1, 2),
                        "failure_type": arguments.get("failure_type", "tool_error"),
                        "agent_id": arguments.get("agent_id", "unknown"),
                    }
                    for i in range(3)
                ],
                "insights": {
                    "pattern": "Recurring tool failure pattern detected",
                    "frequency": "3 times in last 24h",
                    "common_root_cause": "Configuration drift",
                },
            }

        elif tool_name == "get_feature_drift":
            return {
                "drift_detected": random.choice([True, False]),
                "drift_score": round(random.uniform(0.1, 0.9), 3),
                "drifted_features": ["user_query_length", "tool_input_schema"],
                "baseline_period": "last_7_days",
            }

        elif tool_name == "get_performance_baseline":
            return {
                "baseline": {
                    "avg_latency_ms": 1200,
                    "p95_latency_ms": 3500,
                    "success_rate": 0.94,
                    "avg_tokens": 2500,
                },
                "current": {
                    "avg_latency_ms": 2800,
                    "p95_latency_ms": 7200,
                    "success_rate": 0.71,
                    "avg_tokens": 4100,
                },
                "deviation_score": 0.78,
            }

        elif tool_name == "get_embedding_clusters":
            return {
                "clusters": [
                    {"cluster_id": "0", "size": 45, "failure_rate": 0.02},
                    {"cluster_id": "1", "size": 23, "failure_rate": 0.61},
                ],
                "outlier_count": 5,
            }

        return {"status": "ok", "mock": True}

    async def search_similar_traces(
        self,
        agent_id: str,
        failure_type: str,
        limit: int = 5,
    ) -> dict[str, Any]:
        """Search for similar historical failures."""
        return await self._call_tool(
            "search_similar_traces",
            {
                "agent_id": agent_id,
                "failure_type": failure_type,
                "limit": limit,
                "include_insights": True,
            },
        )

    async def get_feature_drift(
        self,
        model_id: str,
        baseline_days: int = 7,
    ) -> dict[str, Any]:
        """Detect feature drift compared to baseline."""
        return await self._call_tool(
            "get_feature_drift",
            {
                "model_id": model_id,
                "baseline_days": baseline_days,
            },
        )

    async def get_performance_baseline(
        self,
        agent_id: str,
        metric: str = "latency",
    ) -> dict[str, Any]:
        """Get performance baseline and compare current metrics."""
        return await self._call_tool(
            "get_performance_baseline",
            {
                "agent_id": agent_id,
                "metric": metric,
            },
        )

    async def get_embedding_clusters(
        self,
        agent_id: str,
        embedding_type: str = "input",
    ) -> dict[str, Any]:
        """Get embedding space clusters for anomaly detection."""
        return await self._call_tool(
            "get_embedding_clusters",
            {
                "agent_id": agent_id,
                "embedding_type": embedding_type,
            },
        )

    async def log_evaluation(
        self,
        trace_id: str,
        model_id: str,
        prediction: dict[str, Any],
        actual: dict[str, Any] | None = None,
        tags: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Log an evaluation record to Arize Phoenix."""
        return await self._call_tool(
            "log_evaluation",
            {
                "trace_id": trace_id,
                "model_id": model_id,
                "prediction": prediction,
                "actual": actual or {},
                "tags": tags or {},
            },
        )

    async def get_hallucination_score(
        self,
        trace_id: str,
        output_text: str,
        context: str,
    ) -> dict[str, Any]:
        """Get hallucination detection score for an LLM output."""
        return await self._call_tool(
            "get_hallucination_score",
            {
                "trace_id": trace_id,
                "output_text": output_text,
                "context": context,
            },
        )

    async def query_traces(
        self,
        agent_id: str,
        time_range_hours: int = 24,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query traces from Arize Phoenix."""
        result = await self._call_tool(
            "query_traces",
            {
                "agent_id": agent_id,
                "time_range_hours": time_range_hours,
                "limit": limit,
            },
        )
        return result.get("traces", [])
