# backend/simulator/twin_manager.py
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import structlog

from api.config import Settings
from api.schemas.trace import AgentTrace

logger = structlog.get_logger(__name__)


@dataclass
class DigitalTwin:
    """A Digital Twin of an AI agent for testing repairs and scenarios."""
    twin_id: str
    agent_id: str
    agent_name: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    base_trace_id: str | None = None
    active_tests: list[str] = field(default_factory=list)
    test_results: list[dict[str, Any]] = field(default_factory=list)
    configuration: dict[str, Any] = field(default_factory=dict)
    repair_applied: dict[str, Any] | None = None


@dataclass
class TwinTestResult:
    """Result from running a test on a Digital Twin."""
    test_id: str
    twin_id: str
    scenario: str
    passed: bool
    success_rate: float
    avg_latency_ms: float
    error_details: list[str]
    started_at: datetime
    completed_at: datetime
    iterations: int


class DigitalTwinManager:
    """
    Digital Twin Manager.

    Creates and manages Digital Twin instances of AI agents.
    Used for:
    1. Testing repairs before applying to production
    2. Running regression test suites
    3. Simulating edge cases
    4. Pre-production validation
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._twins: dict[str, DigitalTwin] = {}

    async def create_twin(
        self,
        agent_id: str,
        agent_name: str,
        base_trace: AgentTrace | None = None,
        configuration: dict[str, Any] | None = None,
    ) -> DigitalTwin:
        """Create a new Digital Twin for an agent."""
        twin = DigitalTwin(
            twin_id=str(uuid.uuid4()),
            agent_id=agent_id,
            agent_name=agent_name,
            base_trace_id=base_trace.trace_id if base_trace else None,
            configuration=configuration or {},
        )
        self._twins[twin.twin_id] = twin
        logger.info("twin_created", twin_id=twin.twin_id, agent_id=agent_id)
        return twin

    async def apply_repair_to_twin(
        self, twin_id: str, repair_artifact: dict[str, Any]
    ) -> DigitalTwin:
        """Apply a repair to a Digital Twin (not production)."""
        twin = self._twins.get(twin_id)
        if not twin:
            raise ValueError(f"Twin {twin_id} not found")

        twin.repair_applied = repair_artifact
        twin.configuration["repaired"] = True
        twin.configuration["repair_type"] = repair_artifact.get("repair_type")

        logger.info(
            "repair_applied_to_twin",
            twin_id=twin_id,
            repair_type=repair_artifact.get("repair_type"),
        )
        return twin

    async def run_test_suite(
        self,
        twin_id: str,
        test_scenarios: list[dict[str, Any]],
        iterations_per_scenario: int = 5,
    ) -> list[TwinTestResult]:
        """Run a test suite on a Digital Twin."""
        twin = self._twins.get(twin_id)
        if not twin:
            raise ValueError(f"Twin {twin_id} not found")

        results: list[TwinTestResult] = []

        for scenario in test_scenarios:
            test_id = str(uuid.uuid4())
            twin.active_tests.append(test_id)

            start = datetime.utcnow()
            result = await self._run_scenario(
                twin=twin,
                scenario=scenario,
                iterations=iterations_per_scenario,
            )

            test_result = TwinTestResult(
                test_id=test_id,
                twin_id=twin_id,
                scenario=scenario.get("name", "unknown"),
                passed=result["success_rate"] >= 0.8,
                success_rate=result["success_rate"],
                avg_latency_ms=result["avg_latency_ms"],
                error_details=result["errors"],
                started_at=start,
                completed_at=datetime.utcnow(),
                iterations=iterations_per_scenario,
            )
            results.append(test_result)
            twin.active_tests.remove(test_id)
            twin.test_results.append(test_result.__dict__ if hasattr(test_result, '__dict__') else {})

        return results

    async def _run_scenario(
        self,
        twin: DigitalTwin,
        scenario: dict[str, Any],
        iterations: int,
    ) -> dict[str, Any]:
        """Simulate a single scenario on the twin."""
        successes = 0
        total_latency = 0.0
        errors: list[str] = []

        for _ in range(iterations):
            await asyncio.sleep(0.01)  # Simulate execution

            # Determine if repair improves things
            base_success_rate = scenario.get("expected_success_rate", 0.5)
            if twin.repair_applied:
                repair_confidence = twin.repair_applied.get("confidence", 0.5)
                effective_rate = base_success_rate + (1 - base_success_rate) * repair_confidence * 0.8
            else:
                effective_rate = base_success_rate

            import random
            success = random.random() < effective_rate
            if success:
                successes += 1
                latency = scenario.get("expected_latency_ms", 1000) * random.uniform(0.8, 1.3)
            else:
                latency = scenario.get("expected_latency_ms", 1000) * random.uniform(1.5, 3.0)
                errors.append(f"Iteration {_}: {scenario.get('failure_scenario', 'Unknown failure')}")

            total_latency += latency

        return {
            "success_rate": successes / iterations,
            "avg_latency_ms": total_latency / iterations,
            "errors": errors[:5],
        }

    async def get_twin(self, twin_id: str) -> DigitalTwin | None:
        """Get a Digital Twin by ID."""
        return self._twins.get(twin_id)

    async def list_twins(self, agent_id: str | None = None) -> list[DigitalTwin]:
        """List all Digital Twins."""
        twins = list(self._twins.values())
        if agent_id:
            twins = [t for t in twins if t.agent_id == agent_id]
        return twins

    async def delete_twin(self, twin_id: str) -> bool:
        """Delete a Digital Twin."""
        if twin_id in self._twins:
            del self._twins[twin_id]
            return True
        return False
