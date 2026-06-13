"""
demo/seed_data.py
Seed 48 hours of realistic trace history into TRACE-X backend.

Generates a mix of:
  - Successful traces (70%)
  - Failed traces with various failure types (30%)
  - Varying latency and token usage
  - Multiple agent types

Usage:
    python demo/seed_data.py
    python demo/seed_data.py --hours 24 --count 200
    python demo/seed_data.py --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
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

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

AGENTS = [
    {"id": "travel-bot-v1", "name": "Travel Booking Bot", "weight": 0.35},
    {"id": "customer-support-v2", "name": "Customer Support Agent", "weight": 0.30},
    {"id": "research-assistant-v1", "name": "Research Assistant", "weight": 0.20},
    {"id": "code-reviewer-v3", "name": "Code Reviewer", "weight": 0.15},
]

FAILURE_TYPES = [
    ("tool_failure", 0.35),
    ("hallucination", 0.25),
    ("stale_context", 0.20),
    ("context_window_exceeded", 0.10),
    ("infinite_loop", 0.05),
    ("rate_limit_exceeded", 0.05),
]

TOOL_NAMES_BY_AGENT = {
    "travel-bot-v1": ["search_flights", "search_hotels", "get_weather", "check_availability", "process_payment"],
    "customer-support-v2": ["lookup_order", "fetch_customer_profile", "send_email", "update_ticket", "escalate_ticket"],
    "research-assistant-v1": ["web_search", "fetch_url", "extract_text", "summarize_document", "cite_sources"],
    "code-reviewer-v3": ["fetch_diff", "run_linter", "check_tests", "fetch_pr_context", "post_review"],
}


def _random_weight(items: list[tuple[Any, float]]) -> Any:
    total = sum(w for _, w in items)
    r = random.uniform(0, total)
    cumulative = 0
    for item, weight in items:
        cumulative += weight
        if r <= cumulative:
            return item
    return items[-1][0]


def _ts_ago(hours: float, minutes: float = 0) -> str:
    dt = datetime.now(timezone.utc) - timedelta(hours=hours, minutes=minutes)
    return dt.isoformat()


def _random_span_status(is_trace_failed: bool, span_index: int, total_spans: int) -> str:
    """For failed traces, make the last 1-2 spans errors."""
    if is_trace_failed and span_index >= total_spans - 2:
        return "error" if random.random() > 0.3 else "success"
    return "success"


# ─────────────────────────────────────────────────────────────────────────────
# Trace generator
# ─────────────────────────────────────────────────────────────────────────────

def generate_trace(
    agent_id: str,
    created_hours_ago: float,
    is_failed: bool,
    failure_type: str | None = None,
) -> dict[str, Any]:
    """Generate a single realistic trace."""
    agent = next(a for a in AGENTS if a["id"] == agent_id)
    tool_names = TOOL_NAMES_BY_AGENT[agent_id]

    trace_id = f"trace-{uuid.uuid4().hex[:12]}"
    total_spans = random.randint(3, 7)
    base_latency = random.uniform(800, 4000)

    if is_failed:
        base_latency = random.uniform(2000, 8500)

    # Simulate peak hours having higher latency
    hour_of_day = (datetime.now(timezone.utc) - timedelta(hours=created_hours_ago)).hour
    if 9 <= hour_of_day <= 17:
        base_latency *= random.uniform(1.2, 1.8)

    started_at_iso = _ts_ago(created_hours_ago)
    ended_at_iso = _ts_ago(created_hours_ago - base_latency / 3_600_000)

    spans = []
    total_prompt_tokens = 0
    total_completion_tokens = 0
    current_offset_ms = 0

    for i in range(total_spans):
        span_duration = random.uniform(100, 800)
        span_id = f"span-{uuid.uuid4().hex[:8]}"
        is_llm_span = i == 0 or i == total_spans - 1 or random.random() > 0.6
        is_last_few = i >= total_spans - 2
        span_status = _random_span_status(is_failed, i, total_spans)

        tool_name = random.choice(tool_names)
        prompt_tok = random.randint(100, 600) if is_llm_span else 0
        completion_tok = random.randint(50, 200) if is_llm_span else 0
        total_prompt_tokens += prompt_tok
        total_completion_tokens += completion_tok

        error_msg = None
        if span_status == "error":
            errors = [
                "Upstream API timeout (503)",
                "Rate limit exceeded (429)",
                "Invalid credentials (401)",
                "Response schema validation failed",
                "Context window exceeded: 32768 tokens",
            ]
            error_msg = random.choice(errors)

        span = {
            "span_id": span_id,
            "name": "parse_intent" if i == 0 else ("generate_response" if i == total_spans - 1 else tool_name),
            "kind": "llm" if is_llm_span else "tool",
            "status": span_status,
            "started_at": _ts_ago(created_hours_ago - current_offset_ms / 3_600_000),
            "finished_at": _ts_ago(created_hours_ago - (current_offset_ms + span_duration) / 3_600_000),
            "duration_ms": int(span_duration),
            "input": {"request": f"step_{i}_input"},
            "output": None if span_status == "error" else {"result": f"step_{i}_output"},
            "model": "gemini-2.0-flash-001" if is_llm_span else None,
            "prompt_tokens": prompt_tok,
            "completion_tokens": completion_tok,
            "tool_calls": [],
            "error_message": error_msg,
            "metadata": {"step": i, "is_critical": is_last_few},
        }

        spans.append(span)
        current_offset_ms += span_duration + random.uniform(10, 50)

    total_tokens = total_prompt_tokens + total_completion_tokens
    total_cost = total_tokens * 0.0000005

    trace = {
        "trace_id": trace_id,
        "agent_id": agent_id,
        "trace_name": f"{agent['name'].lower().replace(' ', '_')}_request",
        "started_at": started_at_iso,
        "finished_at": ended_at_iso,
        "duration_ms": int(base_latency),
        "status": "failed" if is_failed else "success",
        "spans": spans,
        "metadata": {
            "seeded": True,
            "created_hours_ago": round(created_hours_ago, 2),
        },
        "tags": ["seeded", "demo"],
        "total_tokens": total_tokens,
        "total_cost_usd": round(total_cost, 6),
    }

    if is_failed and failure_type:
        trace["failure_type"] = failure_type
        trace["metadata"]["failure_type"] = failure_type

    return trace


# ─────────────────────────────────────────────────────────────────────────────
# Seeder
# ─────────────────────────────────────────────────────────────────────────────

def generate_all_traces(hours: int = 48, count: int = 300) -> list[dict]:
    """Generate a full set of traces spread over `hours` hours."""
    traces = []

    # Traffic pattern: higher volume during business hours
    for i in range(count):
        hours_ago = random.uniform(0, hours)

        # Slight bias towards recent (more traces in last 12h)
        if random.random() > 0.6:
            hours_ago = random.uniform(0, min(12, hours))

        # Pick agent by weight
        agent_weights = [(a["id"], a["weight"]) for a in AGENTS]
        agent_id = _random_weight(agent_weights)

        # Decide success/failure (70/30)
        is_failed = random.random() < 0.30

        failure_type = None
        if is_failed:
            failure_type = _random_weight(FAILURE_TYPES)

        trace = generate_trace(
            agent_id=agent_id,
            created_hours_ago=hours_ago,
            is_failed=is_failed,
            failure_type=failure_type,
        )
        traces.append(trace)

    # Sort by recency (newest first for ingest ordering)
    traces.sort(key=lambda t: t["started_at"], reverse=True)
    return traces


async def ingest_trace(client: httpx.AsyncClient, trace: dict, verbose: bool = False) -> bool:
    """Ingest a single trace into the backend."""
    payload = {"trace": trace, "agent_id": trace["agent_id"]}

    try:
        resp = await client.post(
            f"{BACKEND_URL}/api/v1/traces/ingest",
            json=payload,
            headers=HEADERS,
            timeout=15.0,
        )

        if resp.status_code == 202:
            if verbose:
                data = resp.json()
                print(f"  ✓ {trace['trace_id']} [{trace['status']}] → {data.get('pipeline_status', 'queued')}")
            return True
        else:
            if verbose:
                print(f"  ✗ {trace['trace_id']} HTTP {resp.status_code}: {resp.text[:100]}")
            return False

    except httpx.ConnectError:
        return False
    except Exception as exc:
        if verbose:
            print(f"  ✗ {trace['trace_id']} Error: {exc}")
        return False


async def seed(hours: int, count: int, dry_run: bool, verbose: bool, batch_size: int = 10) -> None:
    print("━" * 60)
    print("  TRACE-X Data Seeder")
    print(f"  Backend: {BACKEND_URL}")
    print(f"  Generating {count} traces over {hours}h window")
    print(f"  Dry run: {dry_run}")
    print("━" * 60)

    traces = generate_all_traces(hours=hours, count=count)

    success_count = sum(1 for t in traces if t["status"] == "success")
    failed_count = len(traces) - success_count

    print(f"\n  Generated: {len(traces)} traces")
    print(f"  Success: {success_count} ({success_count/len(traces)*100:.0f}%)")
    print(f"  Failed:  {failed_count} ({failed_count/len(traces)*100:.0f}%)")

    agent_counts: dict[str, int] = {}
    for t in traces:
        agent_counts[t["agent_id"]] = agent_counts.get(t["agent_id"], 0) + 1

    print("\n  By agent:")
    for agent_id, cnt in sorted(agent_counts.items(), key=lambda x: -x[1]):
        bar = "█" * (cnt // 5)
        print(f"    {agent_id:<30} {cnt:>4}  {bar}")

    if dry_run:
        print("\n  [DRY RUN] No traces were sent to the backend.")
        print("  Sample trace payload:")
        print(json.dumps(traces[0], indent=2)[:800] + "...")
        return

    print(f"\n  Ingesting in batches of {batch_size}...")

    ok = 0
    fail = 0
    start_time = time.monotonic()

    async with httpx.AsyncClient() as client:
        # Test connectivity
        try:
            await client.get(f"{BACKEND_URL}/health", timeout=5.0)
        except Exception:
            print(f"\n  ✗ Cannot reach {BACKEND_URL}")
            print("    Start the backend first: docker-compose up backend")
            return

        for i in range(0, len(traces), batch_size):
            batch = traces[i:i + batch_size]
            tasks = [ingest_trace(client, t, verbose=verbose) for t in batch]
            results = await asyncio.gather(*tasks)

            batch_ok = sum(results)
            batch_fail = len(results) - batch_ok
            ok += batch_ok
            fail += batch_fail

            # Progress bar
            progress = (i + len(batch)) / len(traces)
            bar_len = 30
            filled = int(bar_len * progress)
            bar = "█" * filled + "░" * (bar_len - filled)
            elapsed = time.monotonic() - start_time
            rate = (i + len(batch)) / elapsed if elapsed > 0 else 0

            print(
                f"\r  [{bar}] {i+len(batch):>4}/{len(traces)} "
                f"| ✓{ok} ✗{fail} "
                f"| {rate:.1f}/s",
                end="",
                flush=True,
            )

            # Small delay to avoid overwhelming the backend
            await asyncio.sleep(0.05)

    elapsed = time.monotonic() - start_time
    print(f"\n\n{'━'*60}")
    print(f"  Seeding complete in {elapsed:.1f}s")
    print(f"  Ingested: ✓{ok} successful, ✗{fail} failed")
    print(f"  Rate: {len(traces)/elapsed:.1f} traces/sec")
    if ok > 0:
        print(f"\n  Open the dashboard: http://localhost:3000")
    print("━" * 60)


async def main():
    parser = argparse.ArgumentParser(description="TRACE-X Data Seeder")
    parser.add_argument("--hours", type=int, default=48, help="Hours of history to generate")
    parser.add_argument("--count", type=int, default=300, help="Number of traces to generate")
    parser.add_argument("--dry-run", action="store_true", help="Generate but don't ingest")
    parser.add_argument("--verbose", action="store_true", help="Print each trace result")
    parser.add_argument("--batch-size", type=int, default=10, help="Ingest batch size")
    parser.add_argument("--backend", default=BACKEND_URL, help="Backend URL")
    args = parser.parse_args()

    await seed(
        hours=args.hours,
        count=args.count,
        dry_run=args.dry_run,
        verbose=args.verbose,
        batch_size=args.batch_size,
    )


if __name__ == "__main__":
    asyncio.run(main())
