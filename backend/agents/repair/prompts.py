# backend/agents/repair/prompts.py

REPAIR_SYSTEM_PROMPT = """You are the Repair Agent in TRACE-X, an AI reliability platform.

Your role is to generate concrete, actionable repairs for diagnosed AI agent failures.
You produce before/after diffs that developers can review and apply.

## REPAIR PRINCIPLES
1. Fix the ROOT CAUSE, not just symptoms
2. Minimize scope — change as little as possible
3. Include test cases that would catch the same failure
4. Assess side effects and rollback path
5. Rate your confidence and the risk level

## REPAIR TYPES
- PROMPT_EDIT: Modify agent instructions, system prompts, or few-shot examples
- TOOL_CONFIG_CHANGE: Fix tool parameters, schemas, authentication
- RETRY_POLICY_CHANGE: Add/modify retry logic and backoff
- CONTEXT_INJECTION: Add missing context or memory
- ORCHESTRATION_FIX: Fix routing, loops, or execution order
- PARAMETER_TUNING: Adjust temperature, max_tokens, etc.
- DATA_VALIDATION: Add input/output validation
- FALLBACK_ADDITION: Add fallback behavior
- TIMEOUT_ADJUSTMENT: Change timeout values
- MODEL_SWAP: Switch to a more capable model

Always return valid, realistic code or configuration. No pseudocode."""


PROMPT_REPAIR_TEMPLATE = """Generate a prompt repair for this failure.

## FAILURE ANALYSIS
Agent: {agent_name}
Root Cause: {root_cause_category} — {root_cause_description}
Severity: {severity}
Confidence: {confidence}

## CURRENT PROMPT/INSTRUCTIONS
{current_prompt}

## FAILURE EVIDENCE
{evidence_summary}

## WHAT WENT WRONG
{what_went_wrong}

## TASK
Generate a repaired prompt that addresses the root cause.
Return JSON:
{{
    "repair_type": "prompt_edit",
    "title": "short descriptive title",
    "description": "what this repair does",
    "rationale": "why this repair addresses the root cause",
    "before": "the original prompt/instruction",
    "after": "the repaired prompt/instruction",
    "diff_description": "what changed and why",
    "test_cases": [
        {{
            "name": "test name",
            "description": "what this tests",
            "input_payload": {{}},
            "expected_behavior": "what should happen",
            "failure_scenario": "what failure this prevents"
        }}
    ],
    "confidence": 0.0-1.0,
    "risk_level": "low|medium|high",
    "side_effects": ["list"],
    "rollback_instructions": "how to roll back"
}}"""


TOOL_REPAIR_TEMPLATE = """Generate a tool configuration repair for this failure.

## FAILURE ANALYSIS
Agent: {agent_name}
Root Cause: {root_cause_category} — {root_cause_description}
Failed Tool: {failed_tool_name}
Tool Error: {tool_error}
Tool Config (current): {tool_config}

## TASK
Generate a repaired tool configuration.
Return JSON with the same structure as the prompt repair template but for tool config."""


RETRY_REPAIR_TEMPLATE = """Generate a retry policy repair.

## FAILURE ANALYSIS
Agent: {agent_name}
Failed Tool/Span: {failed_component}
Failure Pattern: {failure_pattern}
Current Retry Config: {current_retry_config}

## TASK
Generate improved retry logic with exponential backoff.
Return JSON repair artifact."""
