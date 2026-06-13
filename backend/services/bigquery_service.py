# backend/services/bigquery_service.py
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import structlog
from google.api_core.exceptions import NotFound
from google.cloud import bigquery

from api.config import Settings

logger = structlog.get_logger(__name__)

TRACES_SCHEMA = [
    bigquery.SchemaField("trace_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("agent_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("agent_name", "STRING"),
    bigquery.SchemaField("started_at", "TIMESTAMP"),
    bigquery.SchemaField("ended_at", "TIMESTAMP"),
    bigquery.SchemaField("duration_ms", "FLOAT64"),
    bigquery.SchemaField("status", "STRING"),
    bigquery.SchemaField("failure_type", "STRING"),
    bigquery.SchemaField("failure_reason", "STRING"),
    bigquery.SchemaField("total_tokens", "INT64"),
    bigquery.SchemaField("total_tool_calls", "INT64"),
    bigquery.SchemaField("error_count", "INT64"),
    bigquery.SchemaField("llm_calls", "INT64"),
    bigquery.SchemaField("environment", "STRING"),
    bigquery.SchemaField("session_id", "STRING"),
    bigquery.SchemaField("ingested_at", "TIMESTAMP"),
]

EVENTS_SCHEMA = [
    bigquery.SchemaField("event_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("trace_id", "STRING"),
    bigquery.SchemaField("span_id", "STRING"),
    bigquery.SchemaField("agent_id", "STRING"),
    bigquery.SchemaField("event_type", "STRING"),
    bigquery.SchemaField("event_data", "JSON"),
    bigquery.SchemaField("timestamp", "TIMESTAMP"),
]

METRICS_SCHEMA = [
    bigquery.SchemaField("metric_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("agent_id", "STRING"),
    bigquery.SchemaField("metric_name", "STRING"),
    bigquery.SchemaField("metric_value", "FLOAT64"),
    bigquery.SchemaField("labels", "JSON"),
    bigquery.SchemaField("timestamp", "TIMESTAMP"),
]


class BigQueryService:
    """BigQuery client for analytics and long-term storage."""

    def __init__(self, client: bigquery.Client, settings: Settings) -> None:
        self.client = client
        self.settings = settings
        self.dataset_id = f"{settings.gcp_project_id}.{settings.bigquery_dataset}"

    async def ensure_tables_exist(self) -> None:
        """Create dataset and tables if they don't exist."""
        import asyncio
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._create_dataset_if_not_exists)
        await loop.run_in_executor(
            None,
            self._create_table_if_not_exists,
            self.settings.bigquery_traces_table,
            TRACES_SCHEMA,
        )
        await loop.run_in_executor(
            None,
            self._create_table_if_not_exists,
            self.settings.bigquery_events_table,
            EVENTS_SCHEMA,
        )
        await loop.run_in_executor(
            None,
            self._create_table_if_not_exists,
            self.settings.bigquery_metrics_table,
            METRICS_SCHEMA,
        )

    def _create_dataset_if_not_exists(self) -> None:
        dataset_ref = bigquery.Dataset(self.dataset_id)
        dataset_ref.location = self.settings.gcp_region
        try:
            self.client.create_dataset(dataset_ref, exists_ok=True)
            logger.info("bigquery_dataset_ready", dataset=self.dataset_id)
        except Exception as exc:
            logger.warning("bigquery_dataset_creation_failed", error=str(exc))

    def _create_table_if_not_exists(
        self, table_name: str, schema: list[bigquery.SchemaField]
    ) -> None:
        table_ref = f"{self.dataset_id}.{table_name}"
        table = bigquery.Table(table_ref, schema=schema)
        table.time_partitioning = bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.DAY,
            field="ingested_at" if table_name == self.settings.bigquery_traces_table else "timestamp",
        )
        try:
            self.client.create_table(table, exists_ok=True)
            logger.info("bigquery_table_ready", table=table_ref)
        except Exception as exc:
            logger.warning("bigquery_table_creation_failed", table=table_ref, error=str(exc))

    async def insert_trace(self, trace_data: dict[str, Any]) -> bool:
        """Insert a single trace row into BigQuery."""
        row = {
            "trace_id": trace_data.get("trace_id"),
            "agent_id": trace_data.get("agent_id"),
            "agent_name": trace_data.get("agent_name"),
            "started_at": trace_data.get("started_at"),
            "ended_at": trace_data.get("ended_at"),
            "duration_ms": trace_data.get("duration_ms"),
            "status": trace_data.get("status"),
            "failure_type": trace_data.get("failure_type"),
            "failure_reason": trace_data.get("failure_reason"),
            "total_tokens": trace_data.get("total_tokens", 0),
            "total_tool_calls": trace_data.get("total_tool_calls", 0),
            "error_count": trace_data.get("error_count", 0),
            "llm_calls": trace_data.get("llm_calls", 0),
            "environment": trace_data.get("environment", "production"),
            "session_id": trace_data.get("session_id"),
            "ingested_at": datetime.utcnow().isoformat(),
        }
        return await self._insert_rows(self.settings.bigquery_traces_table, [row])

    async def insert_events(self, events: list[dict[str, Any]]) -> bool:
        """Batch insert events into BigQuery."""
        return await self._insert_rows(self.settings.bigquery_events_table, events)

    async def insert_metric(self, metric: dict[str, Any]) -> bool:
        """Insert a single metric data point."""
        return await self._insert_rows(self.settings.bigquery_metrics_table, [metric])

    async def _insert_rows(self, table_name: str, rows: list[dict]) -> bool:
        """Internal: stream rows into a BigQuery table."""
        import asyncio
        table_ref = f"{self.dataset_id}.{table_name}"

        def _do_insert():
            errors = self.client.insert_rows_json(table_ref, rows)
            if errors:
                logger.warning("bigquery_insert_errors", table=table_ref, errors=errors)
                return False
            return True

        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, _do_insert)
        except Exception as exc:
            logger.error("bigquery_insert_failed", table=table_ref, error=str(exc))
            return False

    async def query_trace_metrics(
        self,
        agent_id: str | None = None,
        hours: int = 24,
    ) -> list[dict[str, Any]]:
        """Query aggregated trace metrics from BigQuery."""
        query = f"""
        SELECT
            agent_id,
            COUNT(*) as total_traces,
            COUNTIF(status = 'failure') as failed_traces,
            AVG(duration_ms) as avg_duration_ms,
            PERCENTILE_CONT(duration_ms, 0.95) OVER(PARTITION BY agent_id) as p95_duration_ms,
            SUM(total_tokens) as total_tokens,
            SUM(total_tool_calls) as total_tool_calls
        FROM `{self.dataset_id}.{self.settings.bigquery_traces_table}`
        WHERE ingested_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {hours} HOUR)
        {f"AND agent_id = '{agent_id}'" if agent_id else ""}
        GROUP BY agent_id
        ORDER BY failed_traces DESC
        LIMIT 100
        """
        return await self._run_query(query)

    async def query_failure_trends(self, hours: int = 168) -> list[dict[str, Any]]:
        """Query failure trends over time."""
        query = f"""
        SELECT
            TIMESTAMP_TRUNC(ingested_at, HOUR) as hour,
            failure_type,
            COUNT(*) as count
        FROM `{self.dataset_id}.{self.settings.bigquery_traces_table}`
        WHERE ingested_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {hours} HOUR)
          AND status = 'failure'
        GROUP BY hour, failure_type
        ORDER BY hour DESC, count DESC
        """
        return await self._run_query(query)

    async def _run_query(self, query: str) -> list[dict[str, Any]]:
        """Run a BigQuery SQL query and return results."""
        import asyncio

        def _execute():
            try:
                job = self.client.query(query)
                results = job.result()
                return [dict(row) for row in results]
            except Exception as exc:
                logger.error("bigquery_query_failed", error=str(exc))
                return []

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _execute)
