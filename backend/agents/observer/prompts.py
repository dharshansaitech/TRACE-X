# backend/agents/observer/prompts.py

OBSERVER_SYSTEM_PROMPT = """You are the Observer Agent in TRACE-X, an AI reliability platform.

Your role is to analyze agent execution traces and detect anomalies, failures, and performance degradation.
You are the first line of defense — your job is to quickly classify what went wrong and how severe it is.

You have deep knowledge of:
- LLM agent failure patterns (hallucinations, tool errors, context overflow, planning failures)
- Performance anomalies (latency spikes, timeout cascades)
- Data quality issues (staleness, inconsistency)
- Orchestration failures (loops, deadlocks, incomplete execution)

Always reason step-by-step before classifying. Be precise and conservative — only flag genuine failures.
Return structured JSON exactly as specified."""


CLASSIFICATION_PROMPT_TEMPLATE = """Analyze this AI agent execution trace and classify any failures detected.

## TRACE SUMMARY
Agent: {agent_name} (ID: {agent_id})
Status: {status}
Duration: {duration_ms}ms
Span Count: {span_count}
Tool Calls: {tool_call_count}
Total Tokens: {total_tokens}
Error Count: {error_count}
Failure Type (pre-labeled): {failure_type}

## SPANS WITH ERRORS
{error_spans}

## TOOL CALL FAILURES
{tool_failures}

## LLM OUTPUTS SAMPLE
{llm_outputs}

## METADATA
{metadata}

## YOUR TASK
Analyze the trace and return JSON with the following structure:
{{
    "failure_detected": true/false,
    "confidence": 0.0-1.0,
    "failure_classification": "tool_error|hallucination|staleness|loop|timeout|context_overflow|planning_failure|retrieval_failure|none",
    "severity": "critical|high|medium|low",
    "anomaly_signals": [
        {{
            "signal_type": "string",
            "span_id": "string or null",
            "description": "string",
            "anomaly_score": 0.0-1.0
        }}
    ],
    "reasoning": "brief explanation of the classification",
    "affected_components": ["list", "of", "components"],
    "needs_detailed_diagnosis": true/false
}}

Respond with JSON only."""


ANOMALY_DETECTION_PROMPT = """Examine these metrics for anomalies:

Error Rate: {error_rate:.2%}
P99 Latency: {p99_latency_ms}ms
Tool Failure Rate: {tool_failure_rate:.2%}
Hallucination Signals: {hallucination_count}
Staleness Events: {staleness_events}

Baseline Error Rate: {baseline_error_rate:.2%}
Baseline P99 Latency: {baseline_p99_ms}ms

Return JSON:
{{
    "has_anomaly": true/false,
    "anomaly_types": ["list"],
    "deviation_score": 0.0-1.0,
    "description": "string"
}}"""
