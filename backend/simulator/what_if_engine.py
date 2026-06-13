# backend/simulator/what_if_engine.py
from __future__ import annotations

import asyncio
import random
from datetime import datetime
from typing import Any

import structlog

from api.routes.simulator import SimulationMetrics, SimulationPreset, SimulationResult, WhatIfVariable
from api.schemas.trace import AgentTrace

logger = structlog.get_logger(__name__)

# Preset failure injection scenarios
PRESET_CONFIGS: dict[SimulationPreset, dict[str, Any]] = {
    SimulationPreset.NORMAL: {
        "error_rate_multiplier": 1.0,
        "latency_multiplier": 1.0,
        "tool_failure_rate": 0.02,
        "hallucination_probability": 0.01,
    },
    SimulationPreset.HIGH_LOAD: {
        "error_rate_multiplier": 2.5,
        "latency_multiplier": 3.5,
        "tool_failure_rate": 0.08,
        "hallucination_probability": 0.05,
    },
    SimulationPreset.TOOL_FAILURE: {
        "error_rate_multiplier": 5.0,
        "latency_multiplier": 1.5,
        "tool_failure_rate": 0.60,
        "hallucination_probability": 0.02,
    },
    SimulationPreset.STALE_DATA: {
        "error_rate_multiplier": 2.0,
        "latency_multiplier": 1.2,
        "tool_failure_rate": 0.10,
        "hallucination_probability": 0.35,
        "staleness_hours": 6.0,
    },
    SimulationPreset.HALLUCINATION: {
        "error_rate_multiplier": 1.5,
        "latency_multiplier": 1.1,
        "tool_failure_rate": 0.05,
        "hallucination_probability": 0.70,
    },
    SimulationPreset.CASCADING_FAILURE: {
        "error_rate_multiplier": 8.0,
        "latency_multiplier": 5.0,
        "tool_failure_rate": 0.80,
        "hallucination_probability": 0.20,
        "cascade_depth": 3,
    },
    SimulationPreset.NETWORK_PARTITION: {
        "error_rate_multiplier": 6.0,
        "latency_multiplier": 8.0,
        "tool_failure_rate": 0.90,
        "hallucination_probability": 0.05,
        "timeout_rate": 0.80,
    },
    SimulationPreset.CONTEXT_OVERFLOW: {
        "error_rate_multiplier": 3.0,
        "latency_multiplier": 2.0,
        "tool_failure_rate": 0.10,
        "hallucination_probability": 0.50,
        "context_usage_ratio": 0.99,
    },
    SimulationPreset.CUSTOM: {
        "error_rate_multiplier": 1.0,
        "latency_multiplier": 1.0,
        "tool_failure_rate": 0.05,
        "hallucination_probability": 0.05,
    },
}


class WhatIfEngine:
    """
    What-If Simulation Engine.

    Simulates AI agent behavior under different conditions by applying
    parameterized failure injection to trace replays.
    """

    async def run_simulation(
        self,
        trace: AgentTrace | None,
        preset: SimulationPreset,
        variables: list[WhatIfVariable],
        iterations: int = 10,
    ) -> SimulationResult:
        """Run a simulation with the given preset and variables."""

        # Get baseline metrics from trace or defaults
        baseline = self._compute_baseline(trace)

        # Get preset config
        config = PRESET_CONFIGS.get(preset, PRESET_CONFIGS[SimulationPreset.NORMAL]).copy()

        # Apply custom variables
        for var in variables:
            if var.name in config:
                config[var.name] = var.what_if_value

        # Run simulation iterations
        iteration_results: list[dict[str, float]] = []
        for _ in range(iterations):
            await asyncio.sleep(0.01)  # Simulate computation
            result = self._run_single_iteration(baseline, config)
            iteration_results.append(result)

        # Aggregate results
        what_if_metrics = self._aggregate_metrics(iteration_results)

        # Compare baseline vs what-if
        comparison = self._compare_metrics(baseline, what_if_metrics)

        # Generate insights
        insights = self._generate_insights(preset, config, comparison)
        recommended_actions = self._recommend_actions(preset, config, comparison)

        risk = self._assess_risk(comparison)

        return SimulationResult(
            simulation_id="placeholder",  # Will be replaced by caller
            trace_id=trace.trace_id if trace else None,
            agent_id=trace.agent_id if trace else None,
            preset=preset,
            status="completed",
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            iterations_completed=iterations,
            baseline_metrics=SimulationMetrics(**baseline),
            what_if_metrics=what_if_metrics,
            comparison=comparison,
            insights=insights,
            recommended_actions=recommended_actions,
            risk_assessment=risk,
        )

    def _compute_baseline(self, trace: AgentTrace | None) -> dict[str, float]:
        """Compute baseline metrics from trace or use defaults."""
        if trace:
            all_tool_calls = [tc for s in trace.spans for tc in s.tool_calls]
            failed_tools = sum(1 for tc in all_tool_calls if tc.status.value == "error")
            return {
                "success_rate": 0.94 if trace.status.value == "success" else 0.71,
                "avg_latency_ms": trace.duration_ms or 1200,
                "p95_latency_ms": (trace.duration_ms or 1200) * 1.5,
                "error_rate": 0.06 if trace.status.value == "success" else 0.29,
                "tool_failure_rate": failed_tools / max(len(all_tool_calls), 1) if all_tool_calls else 0.02,
                "estimated_cost_usd": (trace.total_tokens or 5000) * 0.0000015,
                "hallucination_probability": 0.02,
            }
        else:
            return {
                "success_rate": 0.94,
                "avg_latency_ms": 1200,
                "p95_latency_ms": 3500,
                "error_rate": 0.06,
                "tool_failure_rate": 0.02,
                "estimated_cost_usd": 0.008,
                "hallucination_probability": 0.01,
            }

    def _run_single_iteration(
        self, baseline: dict[str, float], config: dict[str, Any]
    ) -> dict[str, float]:
        """Run a single simulation iteration."""
        noise = random.gauss(1.0, 0.05)
        error_mult = config.get("error_rate_multiplier", 1.0) * noise
        latency_mult = config.get("latency_multiplier", 1.0) * noise

        error_rate = min(baseline["error_rate"] * error_mult, 1.0)
        avg_latency = baseline["avg_latency_ms"] * latency_mult
        tool_failure = min(config.get("tool_failure_rate", baseline["tool_failure_rate"]) * noise, 1.0)
        hal_prob = min(config.get("hallucination_probability", baseline["hallucination_probability"]) * noise, 1.0)

        return {
            "success_rate": max(1.0 - error_rate, 0.0),
            "avg_latency_ms": avg_latency,
            "p95_latency_ms": avg_latency * 2.5,
            "error_rate": error_rate,
            "tool_failure_rate": tool_failure,
            "estimated_cost_usd": baseline["estimated_cost_usd"] * latency_mult,
            "hallucination_probability": hal_prob,
        }

    def _aggregate_metrics(
        self, results: list[dict[str, float]]
    ) -> SimulationMetrics:
        """Aggregate iteration results into summary metrics."""
        n = len(results)
        if n == 0:
            return SimulationMetrics(
                success_rate=0, avg_latency_ms=0, p95_latency_ms=0,
                error_rate=0, tool_failure_rate=0, estimated_cost_usd=0,
                hallucination_probability=0,
            )

        return SimulationMetrics(
            success_rate=sum(r["success_rate"] for r in results) / n,
            avg_latency_ms=sum(r["avg_latency_ms"] for r in results) / n,
            p95_latency_ms=sum(r["p95_latency_ms"] for r in results) / n,
            error_rate=sum(r["error_rate"] for r in results) / n,
            tool_failure_rate=sum(r["tool_failure_rate"] for r in results) / n,
            estimated_cost_usd=sum(r["estimated_cost_usd"] for r in results) / n,
            hallucination_probability=sum(r["hallucination_probability"] for r in results) / n,
        )

    def _compare_metrics(
        self, baseline: dict[str, float], what_if: SimulationMetrics
    ) -> dict[str, Any]:
        """Compare baseline vs what-if metrics."""
        return {
            "success_rate_delta": what_if.success_rate - baseline["success_rate"],
            "success_rate_pct_change": (what_if.success_rate - baseline["success_rate"]) / max(baseline["success_rate"], 0.001) * 100,
            "latency_delta_ms": what_if.avg_latency_ms - baseline["avg_latency_ms"],
            "latency_pct_change": (what_if.avg_latency_ms - baseline["avg_latency_ms"]) / max(baseline["avg_latency_ms"], 1) * 100,
            "error_rate_delta": what_if.error_rate - baseline["error_rate"],
            "tool_failure_delta": what_if.tool_failure_rate - baseline["tool_failure_rate"],
            "cost_delta_usd": what_if.estimated_cost_usd - baseline["estimated_cost_usd"],
        }

    def _generate_insights(
        self,
        preset: SimulationPreset,
        config: dict[str, Any],
        comparison: dict[str, Any],
    ) -> list[str]:
        """Generate human-readable insights from simulation."""
        insights = []

        sr_change = comparison["success_rate_pct_change"]
        if sr_change < -10:
            insights.append(
                f"Success rate drops by {abs(sr_change):.1f}% under {preset.value} conditions"
            )

        latency_change = comparison["latency_pct_change"]
        if latency_change > 50:
            insights.append(
                f"P95 latency increases {latency_change:.0f}% — users will experience significant slowdown"
            )

        if comparison["tool_failure_delta"] > 0.1:
            insights.append(
                f"Tool failure rate increases by {comparison['tool_failure_delta']:.1%} — check tool resilience"
            )

        if preset == SimulationPreset.CASCADING_FAILURE:
            insights.append("Cascading failure detected — single tool failure propagates to multiple downstream services")

        if preset == SimulationPreset.STALE_DATA:
            insights.append("Stale data scenario shows elevated hallucination risk — implement data freshness checks")

        if not insights:
            insights.append(f"System performs {'adequately' if sr_change > -5 else 'poorly'} under {preset.value} conditions")

        return insights

    def _recommend_actions(
        self,
        preset: SimulationPreset,
        config: dict[str, Any],
        comparison: dict[str, Any],
    ) -> list[str]:
        """Generate recommended actions based on simulation results."""
        actions = []

        if comparison["error_rate_delta"] > 0.1:
            actions.append("Add circuit breakers to prevent cascade failures")
            actions.append("Implement retry logic with exponential backoff")

        if comparison["latency_delta_ms"] > 2000:
            actions.append("Add timeout guards to all tool calls")
            actions.append("Consider async tool execution for non-blocking operations")

        if preset == SimulationPreset.HIGH_LOAD:
            actions.append("Implement rate limiting and request queuing")
            actions.append("Consider horizontal scaling for high-load scenarios")

        if preset in (SimulationPreset.STALE_DATA, SimulationPreset.HALLUCINATION):
            actions.append("Add input data freshness validation")
            actions.append("Implement output confidence scoring")

        return actions or ["Monitor baseline metrics and set alert thresholds"]

    def _assess_risk(self, comparison: dict[str, Any]) -> str:
        """Assess overall risk level of the what-if scenario."""
        score = 0
        if comparison["success_rate_pct_change"] < -20:
            score += 3
        elif comparison["success_rate_pct_change"] < -10:
            score += 2
        elif comparison["success_rate_pct_change"] < -5:
            score += 1

        if comparison["latency_pct_change"] > 200:
            score += 2
        elif comparison["latency_pct_change"] > 100:
            score += 1

        if score >= 4:
            return "critical"
        elif score >= 2:
            return "high"
        elif score >= 1:
            return "medium"
        else:
            return "low"
