"""
demo/inject_failure.py
Injects specific failure modes directly into TRACE-X backend for demo purposes.

Supports three failure categories:
  - staleness: Stale context / outdated tool data
  - hallucination: LLM fabricated response
  - tool_error: Tool call that hard-fails

Usage:
    python demo/inject_failure.py --type staleness
    python demo/inject_failure.py --type hallucination
    python demo/inject_failure.py --type tool_error
    python demo/inject_failure.py --all
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

BACKEND_URL = __import__("os").environ.get("TRACEX_BACKEND_URL", "http://localhost:8000")
API_KEY = __import__("os").environ.get("TRACEX_API_KEY", "dev-key")

HEADERS = {
    "Content-Type": "application/json",
    "X-API-Key": API_KEY,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ago_iso(minutes: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()


def _make_base_trace(agent_id: str, trace_name: str, duration_ms: int = 2500) -> dict[str, Any]:
    """Build a minimal valid trace envelope."""
    trace_id = f"trace-{uuid.uuid4().hex[:12]}"
    start_ts = _ago_iso(2)
    end_ts = _now_iso()

    return {
        "trace_id": trace_id,
        "agent_id": agent_id,
        "trace_name": trace_name,
        "started_at": start_ts,
        "finished_at": end_ts,
        "duration_ms": duration_ms,
        "status": "failed",
        "spans": [],
        "metadata": {},
        "tags": ["demo", "injected"],
        "total_tokens": 0,
        "total_cost_usd": 0.0,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Staleness failure
# ─────────────────────────────────────────────────────────────────────────────

def build_staleness_trace() -> dict[str, Any]:
    """
    Simulates an agent that used 6-month-old flight price data and produced
    a completely wrong recommendation. Observer catches stale context signal.
    """
    trace = _make_base_trace(
        agent_id="travel-bot-v1",
        trace_name="travel_booking_request",
        duration_ms=3100,
    )

    stale_timestamp = (datetime.now(timezone.utc) - timedelta(days=183)).isoformat()
    trace["spans"] = [
        {
            "span_id": f"span-{uuid.uuid4().hex[:8]}",
            "name": "parse_intent",
            "kind": "llm",
            "status": "success",
            "started_at": _ago_iso(2),
            "finished_at": _ago_iso(1),
            "duration_ms": 410,
            "input": {"message": "Book JFK→LAX for 2 pax next month"},
            "output": {"destination": "LAX", "passengers": 2},
            "model": "gemini-2.0-flash-001",
            "prompt_tokens": 150,
            "completion_tokens": 85,
            "tool_calls": [],
            "error_message": None,
            "metadata": {},
        },
        {
            "span_id": f"span-{uuid.uuid4().hex[:8]}",
            "name": "search_flights",
            "kind": "tool",
            "status": "success",
            "started_at": _ago_iso(1),
            "finished_at": _ago_iso(0),
            "duration_ms": 310,
            "input": {"origin": "JFK", "destination": "LAX"},
            "output": {
                "flights": [
                    {"flight_id": "AA101", "price": 149.00, "seats": 12},
                ],
                # This timestamp is 6 months old — staleness signal
                "data_timestamp": stale_timestamp,
                "currency": "USD",
            },
            "model": None,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "tool_calls": [],
            "error_message": None,
            "metadata": {"data_age_days": 183, "stale": True},
        },
        {
            "span_id": f"span-{uuid.uuid4().hex[:8]}",
            "name": "generate_recommendation",
            "kind": "llm",
            "status": "success",
            "started_at": _now_iso(),
            "finished_at": _now_iso(),
            "duration_ms": 580,
            "input": {"flights": [{"price": 149.00}], "intent": {"budget": 500}},
            "output": {
                "recommendation": "I recommend AA101 at $149/person — excellent value! Total $298 for 2 passengers."
            },
            "model": "gemini-2.0-flash-001",
            "prompt_tokens": 380,
            "completion_tokens": 140,
            "tool_calls": [],
            "error_message": None,
            "metadata": {"hallucinated_price": False, "stale_context": True},
        },
    ]

    trace["total_tokens"] = 755
    trace["total_cost_usd"] = 0.00038
    trace["failure_type"] = "stale_context"
    trace["metadata"] = {
        "user_message": "Book JFK→LAX for 2 pax next month",
        "context_age_days": 183,
        "injected_failure": "staleness",
    }

    return trace


# ─────────────────────────────────────────────────────────────────────────────
# Hallucination failure
# ─────────────────────────────────────────────────────────────────────────────

def build_hallucination_trace() -> dict[str, Any]:
    """
    Simulates an LLM that hallucinated a non-existent flight (XY999 / SkyBridge Airlines)
    with fabricated pricing and services.
    """
    trace = _make_base_trace(
        agent_id="travel-bot-v1",
        trace_name="travel_booking_request",
        duration_ms=2800,
    )

    trace["spans"] = [
        {
            "span_id": f"span-{uuid.uuid4().hex[:8]}",
            "name": "parse_intent",
            "kind": "llm",
            "status": "success",
            "started_at": _ago_iso(2),
            "finished_at": _ago_iso(1),
            "duration_ms": 395,
            "input": {"message": "Find me the cheapest JFK→LAX flight for tomorrow"},
            "output": {"destination": "LAX", "passengers": 1, "budget": 200},
            "model": "gemini-2.0-flash-001",
            "prompt_tokens": 140,
            "completion_tokens": 65,
            "tool_calls": [],
            "error_message": None,
            "metadata": {},
        },
        {
            "span_id": f"span-{uuid.uuid4().hex[:8]}",
            "name": "search_flights",
            "kind": "tool",
            "status": "success",
            "started_at": _ago_iso(1),
            "finished_at": _ago_iso(0),
            "duration_ms": 290,
            "input": {"origin": "JFK", "destination": "LAX", "passengers": 1},
            "output": {
                "flights": [
                    {"flight_id": "SW404", "price": 249.00, "duration_min": 400, "seats": 30},
                ],
                "data_timestamp": datetime.now(timezone.utc).isoformat(),
                "currency": "USD",
            },
            "model": None,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "tool_calls": [],
            "error_message": None,
            "metadata": {},
        },
        {
            "span_id": f"span-{uuid.uuid4().hex[:8]}",
            "name": "generate_recommendation",
            "kind": "llm",
            # LLM produced hallucinated content — span itself "succeeded" but output is wrong
            "status": "success",
            "started_at": _now_iso(),
            "finished_at": _now_iso(),
            "duration_ms": 610,
            "input": {
                "flights": [{"flight_id": "SW404", "price": 249.00}],
                "intent": {"budget": 200},
            },
            "output": {
                # Hallucination: recommends a flight (XY999) that was NOT in the tool results
                "recommendation": (
                    "I recommend booking flight XY999 operated by SkyBridge Airlines "
                    "for $189 per person — this is their new direct service launched last month. "
                    "They offer complimentary lounge access and free checked baggage."
                )
            },
            "model": "gemini-2.0-flash-001",
            "prompt_tokens": 390,
            "completion_tokens": 155,
            "tool_calls": [],
            "error_message": None,
            "metadata": {
                "grounding_check_failed": True,
                "cited_flight_id": "XY999",
                "available_flight_ids": ["SW404"],
            },
        },
    ]

    trace["total_tokens"] = 750
    trace["total_cost_usd"] = 0.000375
    trace["failure_type"] = "hallucination"
    trace["metadata"] = {
        "user_message": "Find me the cheapest JFK→LAX flight for tomorrow",
        "hallucinated_entity": "XY999/SkyBridge Airlines",
        "injected_failure": "hallucination",
    }

    return trace


# ─────────────────────────────────────────────────────────────────────────────
# Tool error failure
# ─────────────────────────────────────────────────────────────────────────────

def build_tool_error_trace() -> dict[str, Any]:
    """
    Simulates cascading tool failures: flight API returns 503, hotel API returns
    auth error, agent retries and eventually gives up with degraded response.
    """
    trace = _make_base_trace(
        agent_id="travel-bot-v1",
        trace_name="travel_booking_request",
        duration_ms=8200,
    )

    trace["spans"] = [
        {
            "span_id": f"span-{uuid.uuid4().hex[:8]}",
            "name": "parse_intent",
            "kind": "llm",
            "status": "success",
            "started_at": _ago_iso(3),
            "finished_at": _ago_iso(2),
            "duration_ms": 420,
            "input": {"message": "Book JFK→ORD for 3 passengers this weekend"},
            "output": {"destination": "ORD", "passengers": 3},
            "model": "gemini-2.0-flash-001",
            "prompt_tokens": 155,
            "completion_tokens": 72,
            "tool_calls": [],
            "error_message": None,
            "metadata": {},
        },
        # First flight search attempt — 503
        {
            "span_id": f"span-{uuid.uuid4().hex[:8]}",
            "name": "search_flights",
            "kind": "tool",
            "status": "error",
            "started_at": _ago_iso(2),
            "finished_at": _ago_iso(1),
            "duration_ms": 5003,
            "input": {"origin": "JFK", "destination": "ORD", "passengers": 3},
            "output": None,
            "model": None,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "tool_calls": [],
            "error_message": "Flight API timeout: upstream provider returned 503",
            "metadata": {"retry_attempt": 1, "http_status": 503},
        },
        # Retry attempt — also fails
        {
            "span_id": f"span-{uuid.uuid4().hex[:8]}",
            "name": "search_flights",
            "kind": "tool",
            "status": "error",
            "started_at": _ago_iso(1),
            "finished_at": _ago_iso(0),
            "duration_ms": 5010,
            "input": {"origin": "JFK", "destination": "ORD", "passengers": 3},
            "output": None,
            "model": None,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "tool_calls": [],
            "error_message": "Flight API timeout: upstream provider returned 503",
            "metadata": {"retry_attempt": 2, "http_status": 503},
        },
        # Hotel search — also fails (auth error)
        {
            "span_id": f"span-{uuid.uuid4().hex[:8]}",
            "name": "search_hotels",
            "kind": "tool",
            "status": "error",
            "started_at": _now_iso(),
            "finished_at": _now_iso(),
            "duration_ms": 215,
            "input": {"location": "ORD", "guests": 3},
            "output": None,
            "model": None,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "tool_calls": [],
            "error_message": "Hotel API error: invalid API credentials",
            "metadata": {"retry_attempt": 1, "http_status": 401},
        },
        # Degraded fallback recommendation
        {
            "span_id": f"span-{uuid.uuid4().hex[:8]}",
            "name": "generate_recommendation",
            "kind": "llm",
            "status": "success",
            "started_at": _now_iso(),
            "finished_at": _now_iso(),
            "duration_ms": 450,
            "input": {"flights": [], "hotels": [], "intent": {"destination": "ORD"}},
            "output": {
                "recommendation": "I was unable to fetch flight or hotel data at this time. Please try again later or check directly with airlines."
            },
            "model": "gemini-2.0-flash-001",
            "prompt_tokens": 200,
            "completion_tokens": 55,
            "tool_calls": [],
            "error_message": None,
            "metadata": {"degraded_response": True, "missing_data": ["flights", "hotels"]},
        },
    ]

    trace["total_tokens"] = 482
    trace["total_cost_usd"] = 0.000241
    trace["failure_type"] = "tool_failure"
    trace["metadata"] = {
        "user_message": "Book JFK→ORD for 3 passengers this weekend",
        "failed_tools": ["search_flights", "search_hotels"],
        "total_retries": 2,
        "injected_failure": "tool_error",
    }

    return trace


# ─────────────────────────────────────────────────────────────────────────────
# Inject via API
# ─────────────────────────────────────────────────────────────────────────────

async def inject_trace(client: httpx.AsyncClient, trace: dict, label: str) -> None:
    print(f"\n▸ Injecting {label} trace [{trace['trace_id']}]...")

    payload = {"trace": trace, "agent_id": trace["agent_id"]}

    try:
        resp = await client.post(
            f"{BACKEND_URL}/api/v1/traces/ingest",
            json=payload,
            headers=HEADERS,
            timeout=30.0,
        )

        if resp.status_code == 202:
            data = resp.json()
            print(f"  ✓ Accepted (trace_id={data.get('trace_id', trace['trace_id'])})")
            print(f"  ✓ Pipeline: {data.get('pipeline_status', 'queued')}")
        else:
            print(f"  ✗ HTTP {resp.status_code}: {resp.text[:200]}")

    except httpx.ConnectError:
        print(f"  ✗ Cannot connect to {BACKEND_URL}")
        print("    Make sure the backend is running: docker-compose up backend")
    except Exception as exc:
        print(f"  ✗ Error: {exc}")


async def main():
    parser = argparse.ArgumentParser(description="TRACE-X Failure Injector")
    parser.add_argument(
        "--type",
        choices=["staleness", "hallucination", "tool_error"],
        help="Failure type to inject",
    )
    parser.add_argument("--all", action="store_true", help="Inject all failure types")
    parser.add_argument("--backend", default=BACKEND_URL, help="Backend URL")
    args = parser.parse_args()

    if not args.all and not args.type:
        parser.error("Provide --type or --all")

    print("━" * 60)
    print("  TRACE-X Failure Injector")
    print(f"  Backend: {args.backend}")
    print("━" * 60)

    BUILDERS = {
        "staleness": (build_staleness_trace, "Staleness / Stale Context"),
        "hallucination": (build_hallucination_trace, "Hallucination"),
        "tool_error": (build_tool_error_trace, "Tool Error / Cascading Failure"),
    }

    to_inject = list(BUILDERS.keys()) if args.all else [args.type]

    async with httpx.AsyncClient() as client:
        for failure_type in to_inject:
            builder_fn, label = BUILDERS[failure_type]
            trace = builder_fn()
            await inject_trace(client, trace, label)
            if args.all:
                await asyncio.sleep(0.5)

    print("\n✓ Injection complete. Check the TRACE-X dashboard to see the failures.")
    print(f"  Dashboard: http://localhost:3000")


if __name__ == "__main__":
    asyncio.run(main())
