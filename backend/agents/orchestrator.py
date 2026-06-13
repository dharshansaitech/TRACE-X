# backend/agents/orchestrator.py
from __future__ import annotations

import asyncio
import time
from typing import Any

import structlog

from api.config import Settings
from api.schemas.trace import AgentTrace, TraceStatus

logger = structlog.get_logger(__name__)


class AgentOrchestrator:
    """
    Main orchestration layer.
    Routes new traces through the agent pipeline:
    Observer → Diagnosis → Repair → Validation
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._observer = None
        self._diagnosis_agent = None
        self._repair_agent = None
        self._validation_agent = None
        self._executive_agent = None
        self._gemini = None
        self.ws_manager = None

    async def _broadcast(self, channel: str, message: dict[str, Any]) -> None:
        """Broadcast a pipeline event over WebSocket, if a manager is wired up."""
        if self.ws_manager is None:
            return
        try:
            message.setdefault("timestamp", time.time())
            await self.ws_manager.broadcast_to_channel(channel, message)
        except Exception as exc:
            logger.warning("ws_broadcast_failed", channel=channel, error=str(exc))

    def _get_gemini(self):
        if self._gemini is None:
            from api.dependencies import get_gemini_service_sync
            self._gemini = get_gemini_service_sync(self.settings)
        return self._gemini

    def _get_observer(self):
        if self._observer is None:
            from agents.observer.agent import ObserverAgent
            self._observer = ObserverAgent(self.settings, self._get_gemini())
        return self._observer

    def _get_diagnosis_agent(self):
        if self._diagnosis_agent is None:
            from agents.diagnosis.agent import DiagnosisAgent
            self._diagnosis_agent = DiagnosisAgent(self.settings, self._get_gemini())
        return self._diagnosis_agent

    def _get_repair_agent(self):
        if self._repair_agent is None:
            from agents.repair.agent import RepairAgent
            self._repair_agent = RepairAgent(self.settings, self._get_gemini())
        return self._repair_agent

    def _get_validation_agent(self):
        if self._validation_agent is None:
            from agents.validation.agent import ValidationAgent
            self._validation_agent = ValidationAgent(self.settings, self._get_gemini())
        return self._validation_agent

    async def handle_new_trace(self, trace: AgentTrace) -> None:
        """
        Entry point for new traces.
        Runs the full pipeline asynchronously.
        """
        logger.info(
            "orchestrator_new_trace",
            trace_id=trace.trace_id,
            agent_id=trace.agent_id,
            status=trace.status,
        )

        # Only run full pipeline for failed traces
        if trace.status == TraceStatus.SUCCESS:
            await self._handle_healthy_trace(trace)
            return

        # Run pipeline for failures
        asyncio.create_task(self._run_failure_pipeline(trace))

    async def _handle_healthy_trace(self, trace: AgentTrace) -> None:
        """Process a healthy trace (metrics update only)."""
        try:
            # Update agent last_seen
            from api.dependencies import get_firestore_client
            from services.firestore_service import FirestoreService
            fs_client = get_firestore_client()
            fs = FirestoreService(fs_client, self.settings)
            await fs.agents_col.document(trace.agent_id).set(
                {
                    "agent_id": trace.agent_id,
                    "agent_name": trace.agent_name,
                    "last_seen": trace.started_at.isoformat(),
                    "status": "healthy",
                },
                merge=True,
            )
        except Exception as exc:
            logger.warning("healthy_trace_update_failed", error=str(exc))

    async def _run_failure_pipeline(self, trace: AgentTrace) -> None:
        """Run the full failure analysis pipeline."""
        start = time.perf_counter()
        logger.info("pipeline_start", trace_id=trace.trace_id)

        try:
            # Step 1: Observer — classify and score the failure
            observer = self._get_observer()
            observation = await observer.analyze(trace)
            logger.info(
                "observer_complete",
                trace_id=trace.trace_id,
                failure_detected=observation.failure_detected,
                confidence=observation.confidence,
            )

            if not observation.failure_detected:
                logger.info("observer_no_failure", trace_id=trace.trace_id)
                return

            await self._broadcast(
                "failures",
                {
                    "type": "failure_detected",
                    "trace_id": trace.trace_id,
                    "agent_id": trace.agent_id,
                    "agent_name": trace.agent_name,
                    "failure_type": observation.failure_classification,
                    "severity": observation.severity,
                    "confidence": observation.confidence,
                },
            )

            # Step 2: Diagnosis — root cause analysis
            await self.run_diagnosis_pipeline(trace, observation=observation)

        except Exception as exc:
            logger.error("pipeline_failed", trace_id=trace.trace_id, error=str(exc), exc_info=True)

        finally:
            duration = (time.perf_counter() - start) * 1000
            logger.info(
                "pipeline_complete",
                trace_id=trace.trace_id,
                duration_ms=round(duration, 2),
            )

    async def run_diagnosis_pipeline(
        self,
        trace: AgentTrace,
        observation: Any | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Run diagnosis → repair → validation pipeline for a trace."""
        from api.dependencies import get_firestore_client
        from services.firestore_service import FirestoreService

        fs_client = get_firestore_client()
        fs = FirestoreService(fs_client, self.settings)

        # Step 2: Diagnosis
        diagnosis_agent = self._get_diagnosis_agent()
        try:
            diagnosis = await diagnosis_agent.diagnose(trace, observation, context)
            await fs.upsert_diagnosis(diagnosis)
            logger.info(
                "diagnosis_complete",
                trace_id=trace.trace_id,
                diagnosis_id=diagnosis.diagnosis_id,
                root_cause=diagnosis.root_cause_category,
                confidence=diagnosis.confidence,
            )
            await self._broadcast(
                "failures",
                {
                    "type": "diagnosis_complete",
                    "trace_id": trace.trace_id,
                    "agent_id": trace.agent_id,
                    "diagnosis_id": diagnosis.diagnosis_id,
                    "root_cause": diagnosis.root_cause_category,
                    "severity": diagnosis.severity,
                    "confidence": diagnosis.confidence,
                },
            )
        except Exception as exc:
            logger.error("diagnosis_failed", trace_id=trace.trace_id, error=str(exc))
            return

        # Step 3: Repair generation
        repair_agent = self._get_repair_agent()
        try:
            repair = await repair_agent.generate_repair(trace, diagnosis)
            if repair:
                await fs.upsert_repair(repair)
                logger.info(
                    "repair_generated",
                    trace_id=trace.trace_id,
                    repair_id=repair.repair_id,
                    repair_type=repair.repair_type,
                    confidence=repair.confidence,
                )
                await self._broadcast(
                    "failures",
                    {
                        "type": "repair_generated",
                        "trace_id": trace.trace_id,
                        "agent_id": trace.agent_id,
                        "repair_id": repair.repair_id,
                        "repair_type": repair.repair_type,
                        "confidence": repair.confidence,
                    },
                )

                # Step 4: Validation
                validation_agent = self._get_validation_agent()
                await validation_agent.validate_repair(repair, trace, diagnosis)
                await fs.upsert_repair(repair)
                logger.info(
                    "validation_complete",
                    repair_id=repair.repair_id,
                    passed=repair.validation_passed,
                    score=repair.validation_score,
                )
                await self._broadcast(
                    "failures",
                    {
                        "type": "validation_complete",
                        "trace_id": trace.trace_id,
                        "agent_id": trace.agent_id,
                        "repair_id": repair.repair_id,
                        "passed": repair.validation_passed,
                        "score": repair.validation_score,
                    },
                )
        except Exception as exc:
            logger.error("repair_generation_failed", trace_id=trace.trace_id, error=str(exc))
