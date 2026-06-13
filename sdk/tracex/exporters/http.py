# sdk/tracex/exporters/http.py
from __future__ import annotations

import json
from typing import Any

import httpx
import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from tracex.exporters.base import BaseExporter

logger = structlog.get_logger(__name__)


class HttpExporter(BaseExporter):
    """
    HTTP exporter — sends traces to the TRACE-X backend via REST API.
    Used as fallback when Pub/Sub is unavailable.
    """

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        timeout_seconds: float = 10.0,
        max_batch_size: int = 10,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout_seconds
        self.max_batch_size = max_batch_size
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={
                    "X-API-Key": self.api_key,
                    "Content-Type": "application/json",
                    "User-Agent": "tracex-sdk/1.0.0",
                },
            )
        return self._client

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        stop=stop_after_attempt(3),
    )
    async def export(self, trace_data: dict[str, Any]) -> bool:
        """Export a single trace via HTTP POST."""
        # Build the ingest payload matching the TraceIngestRequest schema
        payload = {
            "trace": self._ensure_trace_schema(trace_data),
            "source": "sdk",
            "sdk_version": "1.0.0",
        }

        try:
            client = self._get_client()
            response = await client.post(
                f"{self.endpoint}/traces/ingest",
                content=json.dumps(payload, default=str),
            )
            response.raise_for_status()
            logger.debug(
                "http_exported",
                trace_id=trace_data.get("trace_id"),
                status=response.status_code,
            )
            return True
        except httpx.HTTPStatusError as exc:
            logger.error(
                "http_export_http_error",
                status=exc.response.status_code,
                trace_id=trace_data.get("trace_id"),
            )
            return False
        except Exception as exc:
            logger.error("http_export_failed", error=str(exc))
            raise  # Let tenacity retry

    async def export_batch(self, traces: list[dict[str, Any]]) -> int:
        """Export multiple traces, respecting batch size."""
        count = 0
        for i in range(0, len(traces), self.max_batch_size):
            batch = traces[i : i + self.max_batch_size]
            for trace in batch:
                if await self.export(trace):
                    count += 1
        return count

    def _ensure_trace_schema(self, trace_data: dict[str, Any]) -> dict[str, Any]:
        """Ensure trace data matches the expected schema."""
        # Make a copy and fix any missing fields
        data = dict(trace_data)

        # Ensure required fields
        import uuid
        if not data.get("trace_id"):
            data["trace_id"] = str(uuid.uuid4())

        if not data.get("status"):
            data["status"] = "unknown"

        if not data.get("failure_type"):
            data["failure_type"] = "none"

        if not data.get("agent_id"):
            data["agent_id"] = "unknown"

        if not data.get("agent_name"):
            data["agent_name"] = "unknown"

        if not data.get("started_at"):
            from datetime import datetime
            data["started_at"] = datetime.utcnow().isoformat()

        return data

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
