# backend/services/demo_seed.py
"""Seeds the in-memory mock Firestore store with realistic demo data.

Generates a fleet of agents with varying health, ~48 hours of traces (mixed
success/failure), diagnoses for failed traces, and a repair queue with mixed
statuses — so the dashboard, agent, trace, repair, and replay views all show
rich data immediately in demo mode (no GCP credentials required).
"""
from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta

import structlog

from api.schemas.diagnosis import (
    AnomalySignal,
    BlastRadius,
    DiagnosisResult,
    ReasoningStep,
    RootCauseCategory,
    SeverityLevel,
)
from api.schemas.repair import (
    RepairArtifact,
    RepairDiff,
    RepairStatus,
    RepairType,
    TestCase,
)
from api.schemas.trace import (
    AgentSpan,
    AgentTrace,
    FailureType,
    SpanKind,
    SpanStatus,
    ToolCallRecord,
    TraceStatus,
)
from services.firestore_service import FirestoreService
from services.mock_gemini import _FAILURE_TO_ROOT_CAUSE, _SEVERITY_BY_FAILURE

logger = structlog.get_logger(__name__)

AGENTS: list[dict] = [
    {
        "agent_id": "travel-bot-v1",
        "agent_name": "Travel Booking Bot",
        "agent_version": "1.4.2",
        "description": "Books flights, hotels, and rental cars based on user itineraries.",
        "tags": ["customer-facing", "bookings"],
        "tools": ["search_flights", "search_hotels", "get_weather", "check_availability", "process_payment"],
        "failure_rate": 0.06,
    },
    {
        "agent_id": "customer-support-v2",
        "agent_name": "Customer Support Agent",
        "agent_version": "2.1.0",
        "description": "Handles support tickets — order lookups, refunds, and escalations.",
        "tags": ["customer-facing", "support"],
        "tools": ["lookup_order", "fetch_customer_profile", "send_email", "update_ticket", "escalate_ticket"],
        "failure_rate": 0.04,
    },
    {
        "agent_id": "research-assistant-v1",
        "agent_name": "Research Assistant",
        "agent_version": "1.0.5",
        "description": "Answers research questions by searching and summarizing web sources.",
        "tags": ["internal", "research"],
        "tools": ["web_search", "fetch_url", "extract_text", "summarize_document", "cite_sources"],
        "failure_rate": 0.12,
    },
    {
        "agent_id": "code-reviewer-v3",
        "agent_name": "Code Reviewer",
        "agent_version": "3.2.1",
        "description": "Reviews pull requests for bugs, style issues, and missing tests.",
        "tags": ["internal", "engineering"],
        "tools": ["fetch_diff", "run_linter", "check_tests", "fetch_pr_context", "post_review"],
        "failure_rate": 0.03,
    },
    {
        "agent_id": "data-pipeline-agent-v1",
        "agent_name": "Data Pipeline Agent",
        "agent_version": "0.9.0",
        "description": "Monitors and repairs nightly ETL pipelines, retrying failed jobs.",
        "tags": ["internal", "data-platform"],
        "tools": ["check_job_status", "rerun_job", "query_warehouse", "send_alert", "update_dag"],
        "failure_rate": 0.27,
    },
]

_FAILURE_TYPE_WEIGHTS: list[tuple[FailureType, float]] = [
    (FailureType.TOOL_ERROR, 0.30),
    (FailureType.HALLUCINATION, 0.18),
    (FailureType.STALENESS, 0.12),
    (FailureType.LOOP, 0.10),
    (FailureType.TIMEOUT, 0.12),
    (FailureType.CONTEXT_OVERFLOW, 0.10),
    (FailureType.SAFETY_VIOLATION, 0.03),
    (FailureType.PLANNING_FAILURE, 0.03),
    (FailureType.RETRIEVAL_FAILURE, 0.02),
]

_ERROR_MESSAGES: dict[FailureType, tuple[str, str]] = {
    FailureType.TOOL_ERROR: ("Tool returned HTTP 503: Service Unavailable", "ToolExecutionError"),
    FailureType.HALLUCINATION: ("Response referenced an ID that does not exist in any tool result", "HallucinationDetected"),
    FailureType.STALENESS: ("Agent used cached data fetched 14 hours ago instead of refreshing", "StaleDataError"),
    FailureType.LOOP: ("Tool was called 9 times with identical arguments without progress", "LoopDetected"),
    FailureType.TIMEOUT: ("Upstream call exceeded 30000ms timeout", "TimeoutError"),
    FailureType.CONTEXT_OVERFLOW: ("Context window exceeded: 33120/32768 tokens", "ContextOverflowError"),
    FailureType.SAFETY_VIOLATION: ("Response blocked by safety filter: policy violation", "SafetyFilterError"),
    FailureType.PLANNING_FAILURE: ("Plan was missing a required step before completion", "PlanningError"),
    FailureType.RETRIEVAL_FAILURE: ("Search returned 0 results above the similarity threshold", "RetrievalError"),
}

# Failure types whose error manifests in a tool span (vs. an LLM span)
_TOOL_FAILURE_TYPES = {FailureType.TOOL_ERROR, FailureType.LOOP, FailureType.RETRIEVAL_FAILURE, FailureType.TIMEOUT}

_REPAIR_TYPE_BY_ROOT_CAUSE: dict[RootCauseCategory, RepairType] = {
    RootCauseCategory.PROMPT_DESIGN: RepairType.PROMPT_EDIT,
    RootCauseCategory.TOOL_CONFIGURATION: RepairType.TOOL_CONFIG_CHANGE,
    RootCauseCategory.EXTERNAL_SERVICE: RepairType.TOOL_CONFIG_CHANGE,
    RootCauseCategory.ORCHESTRATION_LOGIC: RepairType.ORCHESTRATION_FIX,
    RootCauseCategory.CONTEXT_MANAGEMENT: RepairType.CONTEXT_INJECTION,
    RootCauseCategory.RESOURCE_CONSTRAINT: RepairType.TIMEOUT_ADJUSTMENT,
    RootCauseCategory.MODEL_LIMITATION: RepairType.PARAMETER_TUNING,
    RootCauseCategory.DATA_QUALITY: RepairType.DATA_VALIDATION,
    RootCauseCategory.SECURITY_POLICY: RepairType.FALLBACK_ADDITION,
    RootCauseCategory.UNKNOWN: RepairType.PARAMETER_TUNING,
}


def _weighted_failure_type() -> FailureType:
    items, weights = zip(*_FAILURE_TYPE_WEIGHTS)
    return random.choices(items, weights=weights)[0]


def _generate_trace(agent: dict, started_at: datetime, is_failed: bool, failure_type: FailureType | None) -> AgentTrace:
    trace_id = f"trace-{uuid.uuid4().hex[:12]}"
    agent_id = agent["agent_id"]
    agent_name = agent["agent_name"]
    n_spans = random.randint(3, 6)

    error_in_tool = is_failed and failure_type in _TOOL_FAILURE_TYPES

    spans: list[AgentSpan] = []
    cursor = started_at
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_tool_calls = 0
    llm_calls = 0

    for i in range(n_spans):
        span_started = cursor
        is_last = i == n_spans - 1
        is_error_span = is_failed and is_last

        if i == 0:
            kind = SpanKind.LLM
            span_name = "parse_intent"
        elif is_last:
            kind = SpanKind.TOOL if (is_error_span and error_in_tool) else SpanKind.LLM
            span_name = random.choice(agent["tools"]) if kind == SpanKind.TOOL else "generate_response"
        else:
            kind = SpanKind.TOOL if random.random() < 0.6 else SpanKind.LLM
            span_name = random.choice(agent["tools"]) if kind == SpanKind.TOOL else f"reasoning_step_{i}"

        span_duration = random.uniform(150, 1800)
        if is_error_span and failure_type == FailureType.TIMEOUT:
            span_duration = random.uniform(28000, 32000)
        span_ended = span_started + timedelta(milliseconds=span_duration)

        tool_calls: list[ToolCallRecord] = []
        prompt_tok = completion_tok = total_tok = None
        output_content = None
        input_messages: list[dict] = []
        status = SpanStatus.OK
        error_message = error_type = None

        if kind == SpanKind.LLM:
            llm_calls += 1
            prompt_tok = random.randint(150, 900)
            completion_tok = random.randint(40, 400)
            if is_error_span and failure_type == FailureType.CONTEXT_OVERFLOW:
                prompt_tok = random.randint(31000, 33500)
            total_tok = prompt_tok + completion_tok
            total_prompt_tokens += prompt_tok
            total_completion_tokens += completion_tok
            input_messages = [
                {"role": "system", "content": f"You are {agent_name}, version {agent['agent_version']}."},
                {"role": "user", "content": f"Step {i + 1} of execution for trace {trace_id}."},
            ]
            output_content = f"[step {i + 1}] {span_name} produced output for {agent_name}."
        else:
            total_tool_calls += 1
            tool_status = SpanStatus.OK
            tool_error = None
            if is_error_span and error_in_tool:
                tool_status = SpanStatus.ERROR
                tool_error, _ = _ERROR_MESSAGES[failure_type]
            tool_calls.append(
                ToolCallRecord(
                    tool_name=span_name,
                    input_args={"query": f"step_{i + 1}_input"},
                    output=None if tool_status == SpanStatus.ERROR else {"result": f"step_{i + 1}_output"},
                    error=tool_error,
                    started_at=span_started,
                    ended_at=span_ended,
                    status=tool_status,
                    retry_count=2 if failure_type == FailureType.LOOP else 0,
                )
            )

        if is_error_span:
            status = SpanStatus.ERROR
            error_message, error_type = _ERROR_MESSAGES.get(failure_type, ("Unknown error", "UnknownError"))

        span = AgentSpan(
            trace_id=trace_id,
            agent_id=agent_id,
            agent_name=agent_name,
            span_name=span_name,
            kind=kind,
            started_at=span_started,
            ended_at=span_ended,
            duration_ms=round(span_duration, 2),
            status=status,
            error_message=error_message,
            error_type=error_type,
            model="gemini-2.0-flash-001" if kind == SpanKind.LLM else None,
            prompt_tokens=prompt_tok,
            completion_tokens=completion_tok,
            total_tokens=total_tok,
            input_messages=input_messages,
            output_content=output_content,
            tool_calls=tool_calls,
        )
        spans.append(span)
        cursor = span_ended + timedelta(milliseconds=random.uniform(10, 80))

    ended_at = cursor
    duration_ms = (ended_at - started_at).total_seconds() * 1000

    failure_reason = None
    if is_failed and failure_type:
        failure_reason, _ = _ERROR_MESSAGES.get(failure_type, ("Unknown failure", ""))

    return AgentTrace(
        trace_id=trace_id,
        agent_id=agent_id,
        agent_name=agent_name,
        agent_version=agent["agent_version"],
        started_at=started_at,
        ended_at=ended_at,
        duration_ms=round(duration_ms, 2),
        status=TraceStatus.FAILURE if is_failed else TraceStatus.SUCCESS,
        failure_type=failure_type if is_failed else FailureType.NONE,
        failure_reason=failure_reason,
        spans=spans,
        input_payload={"request": f"demo request for {agent_name}"},
        output_payload={} if is_failed else {"result": "completed successfully"},
        total_tokens=total_prompt_tokens + total_completion_tokens,
        total_tool_calls=total_tool_calls,
        error_count=1 if is_failed else 0,
        llm_calls=llm_calls,
        session_id=f"session-{uuid.uuid4().hex[:8]}",
        environment="production",
        tags=["seeded", "demo"],
        metadata={"seeded": True},
    )


def _build_diagnosis(trace: AgentTrace) -> DiagnosisResult:
    failure_type = trace.failure_type.value
    root_cause_str, description = _FAILURE_TO_ROOT_CAUSE.get(failure_type, _FAILURE_TO_ROOT_CAUSE["none"])
    severity_str = _SEVERITY_BY_FAILURE.get(failure_type, "medium")
    failing_span = trace.spans[-1] if trace.spans else None
    failing_span_id = failing_span.span_id if failing_span else None
    confidence = round(random.uniform(0.7, 0.95), 2)
    diagnosed_at = (trace.ended_at or trace.started_at) + timedelta(seconds=random.uniform(5, 30))

    return DiagnosisResult(
        trace_id=trace.trace_id,
        agent_id=trace.agent_id,
        diagnosed_at=diagnosed_at,
        diagnosis_duration_ms=round(random.uniform(800, 4500), 2),
        root_cause_category=RootCauseCategory(root_cause_str),
        root_cause_description=f"{description} Observed in {trace.agent_name}.",
        severity=SeverityLevel(severity_str),
        confidence=confidence,
        reasoning_chain=[
            ReasoningStep(
                step_number=1,
                hypothesis=f"The {failure_type.replace('_', ' ')} failure originates in the final execution span.",
                evidence=[
                    f"Trace status is FAILURE with failure_type={failure_type}",
                    f"Span '{failing_span.span_name}' has status=ERROR" if failing_span else "Error span present",
                ],
                evidence_spans=[failing_span_id] if failing_span_id else [],
                confidence=confidence,
                conclusion=f"Failure pattern is consistent with a {root_cause_str.replace('_', ' ')} issue.",
            ),
            ReasoningStep(
                step_number=2,
                hypothesis="The agent had no recovery path once the failure occurred.",
                evidence=["No retry or fallback span follows the failing span"],
                evidence_spans=[failing_span_id] if failing_span_id else [],
                confidence=round(max(confidence - 0.1, 0.5), 2),
                conclusion="Lack of error handling escalated a recoverable error into a trace failure.",
            ),
        ],
        anomaly_signals=[
            AnomalySignal(
                signal_type=failure_type,
                span_id=failing_span_id or "",
                description=trace.failure_reason or "Failure detected",
                anomaly_score=round(random.uniform(0.6, 0.95), 2),
                timestamp=failing_span.started_at if failing_span else trace.started_at,
            )
        ],
        blast_radius=BlastRadius(
            data_integrity_risk=failure_type in ("staleness", "hallucination"),
            containment_possible=True,
        ),
        failing_span_id=failing_span_id,
        divergence_point_span_id=failing_span_id,
        contributing_spans=[failing_span_id] if failing_span_id else [],
        evidence_summary=(
            f"{trace.agent_name} failed with `{failure_type}`. Root cause classified as "
            f"`{root_cause_str}`. {description}"
        ),
        immediate_actions=[
            f"Review the failing span ({failing_span_id}) and reproduce locally" if failing_span_id else "Review the trace timeline",
            "Add a guard/fallback for this failure mode before re-running in production",
        ],
        long_term_recommendations=[
            "Add automated regression tests covering this failure scenario",
            "Add monitoring alerts for this failure signature",
        ],
        repair_feasibility=round(random.uniform(0.35, 0.92), 2),
        model_used="gemini-2.0-flash-001",
    )


def _repair_content(trace: AgentTrace, diagnosis: DiagnosisResult, repair_type: RepairType) -> tuple[str, str, str, str, str]:
    """Returns (before, after, description, rationale, title)."""
    agent_name = trace.agent_name
    rationale = (
        f"Diagnosis identified `{diagnosis.root_cause_category.value}` as the root cause "
        f"(confidence {diagnosis.confidence:.0%}); this repair directly addresses it."
    )

    if repair_type == RepairType.PROMPT_EDIT:
        before = f"You are {agent_name}. Complete the user's request using the available tools."
        after = (
            before
            + "\n\n# Repaired guidance\n"
            + "- Validate tool outputs before using them in your final answer.\n"
            + "- Never invent results when a tool fails — state the failure explicitly.\n"
            + "- Escalate after 2 failed retries instead of looping."
        )
        return before, after, "Add grounding and failure-handling guidance to the system prompt.", rationale, f"Tighten instructions for {agent_name}"

    if repair_type == RepairType.TOOL_CONFIG_CHANGE:
        tool_name = next((s.tool_calls[0].tool_name for s in reversed(trace.spans) if s.tool_calls), "tool")
        before = f'# Tool: {tool_name}\nconfig = {{"timeout_seconds": 30, "retry_count": 1, "validate_response_schema": False}}'
        after = (
            f"# Tool: {tool_name} (repaired)\n"
            'config = {\n'
            '    "timeout_seconds": 60,             # increased timeout\n'
            '    "retry_count": 3,                  # added retries\n'
            '    "retry_backoff_factor": 2.0,       # exponential backoff\n'
            '    "validate_response_schema": True,  # reject malformed responses early\n'
            '    "circuit_breaker_threshold": 5,    # trip breaker after repeated failures\n'
            "}"
        )
        return before, after, f"Add retries, backoff, and response validation to `{tool_name}`.", rationale, f"Harden `{tool_name}` configuration for {agent_name}"

    if repair_type == RepairType.ORCHESTRATION_FIX:
        before = "while not task_complete:\n    result = call_tool(next_tool, args)\n    update_state(result)\n    # no max-iteration guard, no progress check"
        after = (
            "MAX_ITERATIONS = 8\n\n"
            "for iteration in range(MAX_ITERATIONS):\n"
            "    result = call_tool(next_tool, args)\n"
            "    if not made_progress(result, previous_state):\n"
            '        escalate_to_human("No progress after repeated tool calls")\n'
            "        break\n"
            "    update_state(result)\n"
            "    if task_complete:\n"
            "        break\n"
            "else:\n"
            '    escalate_to_human("Max iterations reached without completion")'
        )
        return before, after, "Bound the agent's execution loop and escalate when no progress is made.", rationale, f"Add iteration guard to {agent_name}'s control loop"

    if repair_type == RepairType.CONTEXT_INJECTION:
        max_tokens = max((s.total_tokens or 0 for s in trace.spans), default=8192)
        before = 'MAX_CONTEXT_TOKENS = 8192\nCONTEXT_STRATEGY = "truncate_oldest"\nSUMMARY_ENABLED = False'
        after = (
            f"MAX_CONTEXT_TOKENS = {min(max_tokens + 4000, 32000)}  # increased limit\n"
            'CONTEXT_STRATEGY = "sliding_window"      # better truncation strategy\n'
            "SUMMARY_ENABLED = True                   # compress older turns\n"
            "SUMMARY_INTERVAL = 10                    # summarize every 10 turns"
        )
        return before, after, "Increase the context window and add a summarization strategy.", rationale, f"Fix context management for {agent_name}"

    if repair_type == RepairType.TIMEOUT_ADJUSTMENT:
        before = "MAX_TOKENS_PER_CALL = 4096\nTIMEOUT_SECONDS = 30\nMAX_RETRIES = 1"
        after = (
            "MAX_TOKENS_PER_CALL = 8192       # doubled token limit\n"
            "TIMEOUT_SECONDS = 120            # increased timeout\n"
            "MAX_RETRIES = 3                  # added retries\n"
            "BACKOFF_FACTOR = 2.0             # exponential backoff\n"
            "CIRCUIT_BREAKER_THRESHOLD = 5   # circuit breaker protection"
        )
        return before, after, "Adjust timeout and token limits to prevent resource exhaustion.", rationale, f"Fix resource constraints for {agent_name}"

    if repair_type == RepairType.DATA_VALIDATION:
        before = "data = fetch_from_cache(key)\nuse(data)"
        after = (
            "data = fetch_from_cache(key)\n"
            "if is_stale(data, max_age_seconds=300):\n"
            "    data = refetch_from_source(key)\n"
            "use(data)"
        )
        return before, after, "Add a staleness check before using cached data.", rationale, f"Fix stale data handling for {agent_name}"

    if repair_type == RepairType.FALLBACK_ADDITION:
        before = "response = model.generate(prompt)\nreturn response"
        after = (
            "response = model.generate(prompt)\n"
            "if response.blocked_by_safety_filter:\n"
            "    return fallback_response(reason=response.block_reason)\n"
            "return response"
        )
        return before, after, "Add a graceful fallback when the safety filter blocks a response.", rationale, f"Add safety-filter fallback for {agent_name}"

    # PARAMETER_TUNING / default
    before = f"# Agent configuration for {agent_name}\ntemperature = 0.7\nmax_tokens = 4096\nretry_enabled = False\nvalidation_enabled = False"
    after = (
        f"# Agent configuration for {agent_name} (repaired)\n"
        "temperature = 0.2              # reduced for consistency\n"
        "max_tokens = 8192              # increased limit\n"
        "retry_enabled = True           # enable retries\n"
        "retry_count = 3\n"
        "validation_enabled = True      # enable output validation"
    )
    return before, after, f"Tune generation parameters and enable validation for {agent_name}.", rationale, f"General repair for {trace.failure_type.value} in {agent_name}"


def _build_repair(trace: AgentTrace, diagnosis: DiagnosisResult, status: RepairStatus) -> RepairArtifact:
    repair_type = _REPAIR_TYPE_BY_ROOT_CAUSE.get(diagnosis.root_cause_category, RepairType.PARAMETER_TUNING)
    before, after, description, rationale, title = _repair_content(trace, diagnosis, repair_type)

    test_cases = [
        TestCase(
            name=f"test_{trace.failure_type.value}_resolved",
            description=f"Verify {trace.agent_name} no longer exhibits {trace.failure_type.value}",
            expected_behavior="Trace completes with status=success",
            failure_scenario=trace.failure_reason or "Unknown failure",
        )
    ]

    diff = RepairDiff(
        target_type=repair_type.value,
        before=before,
        after=after,
        description=description,
    )

    created_at = (trace.ended_at or trace.started_at) + timedelta(minutes=random.uniform(2, 20))

    repair = RepairArtifact(
        trace_id=trace.trace_id,
        diagnosis_id=diagnosis.diagnosis_id,
        agent_id=trace.agent_id,
        repair_type=repair_type,
        title=title,
        description=description,
        rationale=rationale,
        diff=diff,
        test_cases=test_cases,
        tests_total=len(test_cases),
        confidence=round(random.uniform(0.6, 0.9), 2),
        risk_level=random.choice(["low", "low", "medium"]),
        side_effects=["Minor increase in latency due to added validation/retries"],
        rollback_instructions="Revert this diff to restore the previous configuration.",
        status=status,
        created_at=created_at,
        model_used="gemini-2.0-flash-001",
        generation_duration_ms=round(random.uniform(1200, 5000), 2),
    )

    if status in (RepairStatus.APPROVED, RepairStatus.APPLIED, RepairStatus.VALIDATED):
        repair.approved_at = created_at + timedelta(minutes=random.uniform(5, 60))
    if status in (RepairStatus.APPLIED, RepairStatus.VALIDATED):
        repair.applied_at = repair.approved_at + timedelta(minutes=random.uniform(5, 30))
        repair.applied_by = "demo-engineer"
    if status == RepairStatus.VALIDATED:
        repair.validation_passed = True
        repair.validation_score = round(random.uniform(0.75, 0.95), 2)
        repair.validation_notes = "Validated against the regression test suite."
        repair.tests_passed = len(test_cases)
        repair.tests_total = len(test_cases)
        for tc in repair.test_cases:
            tc.passed = True
            tc.actual_output = "Trace replay completed successfully"

    return repair


_REPAIR_STATUS_WEIGHTS = [
    (RepairStatus.PENDING, 0.40),
    (RepairStatus.APPROVED, 0.25),
    (RepairStatus.APPLIED, 0.20),
    (RepairStatus.VALIDATED, 0.15),
]


async def seed_demo_data(firestore_service: FirestoreService, hours: int = 48) -> None:
    """Populate the (mock) Firestore store with a realistic demo dataset."""
    now = datetime.utcnow()
    status_items, status_weights = zip(*_REPAIR_STATUS_WEIGHTS)

    total_traces = 0
    total_diagnoses = 0
    total_repairs = 0

    for agent in AGENTS:
        traces_n = random.randint(25, 45)
        agent_status = "critical" if agent["failure_rate"] > 0.2 else ("degraded" if agent["failure_rate"] > 0.05 else "healthy")

        for _ in range(traces_n):
            hours_ago = random.uniform(0, min(12, hours)) if random.random() < 0.4 else random.uniform(0, hours)
            started_at = now - timedelta(hours=hours_ago)
            is_failed = random.random() < agent["failure_rate"]
            failure_type = _weighted_failure_type() if is_failed else None

            trace = _generate_trace(agent, started_at, is_failed, failure_type)
            await firestore_service.upsert_trace(trace)
            total_traces += 1

            if is_failed and random.random() < 0.75:
                diagnosis = _build_diagnosis(trace)
                await firestore_service.upsert_diagnosis(diagnosis)
                total_diagnoses += 1

                if diagnosis.repair_feasibility >= 0.3:
                    repair_status = random.choices(status_items, weights=status_weights)[0]
                    repair = _build_repair(trace, diagnosis, repair_status)
                    await firestore_service.upsert_repair(repair)
                    total_repairs += 1

        agent_record = {
            "agent_id": agent["agent_id"],
            "agent_name": agent["agent_name"],
            "agent_version": agent["agent_version"],
            "description": agent["description"],
            "tags": agent["tags"],
            "metadata": {"demo": True},
            "registered_at": (now - timedelta(days=14)).isoformat(),
            "last_seen": now.isoformat(),
            "status": agent_status,
        }
        await firestore_service.agents_col.document(agent["agent_id"]).set(agent_record, merge=True)

    logger.info(
        "demo_data_seeded",
        agents=len(AGENTS),
        traces=total_traces,
        diagnoses=total_diagnoses,
        repairs=total_repairs,
    )
