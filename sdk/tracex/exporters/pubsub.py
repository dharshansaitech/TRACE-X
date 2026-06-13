# sdk/tracex/exporters/pubsub.py
from __future__ import annotations

import asyncio
import json
from typing import Any

import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from tracex.exporters.base import BaseExporter

logger = structlog.get_logger(__name__)


class PubSubExporter(BaseExporter):
    """
    Exports traces to Google Cloud Pub/Sub.
    Preferred for high-throughput production environments.
    """

    def __init__(
        self,
        project_id: str,
        topic_name: str,
        api_key: str | None = None,
    ) -> None:
        self.project_id = project_id
        self.topic_name = topic_name
        self.api_key = api_key
        self._publisher = None
        self._topic_path: str | None = None

    def _get_publisher(self):
        if self._publisher is None:
            from google.cloud import pubsub_v1
            self._publisher = pubsub_v1.PublisherClient()
            self._topic_path = self._publisher.topic_path(
                self.project_id, self.topic_name
            )
        return self._publisher

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
    )
    async def export(self, trace_data: dict[str, Any]) -> bool:
        """Publish a trace to Pub/Sub."""
        loop = asyncio.get_event_loop()

        def _publish():
            try:
                publisher = self._get_publisher()
                message_data = json.dumps(trace_data, default=str).encode("utf-8")
                future = publisher.publish(
                    self._topic_path,
                    data=message_data,
                    message_type="trace",
                    agent_id=str(trace_data.get("agent_id", "")),
                    source="tracex-sdk",
                )
                message_id = future.result(timeout=10)
                logger.debug("pubsub_exported", trace_id=trace_data.get("trace_id"), message_id=message_id)
                return True
            except Exception as exc:
                logger.error("pubsub_export_failed", error=str(exc))
                return False

        return await loop.run_in_executor(None, _publish)

    async def export_batch(self, traces: list[dict[str, Any]]) -> int:
        """Export multiple traces."""
        count = 0
        for trace in traces:
            if await self.export(trace):
                count += 1
        return count

    async def close(self) -> None:
        """Close the publisher."""
        if self._publisher:
            try:
                self._publisher.close()
            except Exception:
                pass
