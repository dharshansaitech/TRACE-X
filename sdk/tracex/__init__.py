# sdk/tracex/__init__.py
"""
TRACE-X SDK — The Flight Recorder for AI Agents.

Quick start:
    import tracex

    # Initialize once at startup
    tracex.init(
        api_key="your-api-key",
        agent_id="my-agent-v1",
        agent_name="My AI Agent",
        exporter="http",
        endpoint="https://api.tracex.io/api/v1",
    )

    # Wrap any callable
    @tracex.trace("my_agent_call")
    async def run_agent(prompt: str):
        ...

    # Or use the context manager
    async with tracex.span("llm_call", kind="llm") as span:
        response = await llm.generate(prompt)
        span.set_output(response.text)
        span.set_tokens(prompt_tokens=100, completion_tokens=200)
"""
from __future__ import annotations

from tracex.recorder import AgentWrapper, _global_recorder
from tracex.span import AgentSpan, SpanContext, ToolCallRecord


def init(
    api_key: str,
    agent_id: str,
    agent_name: str,
    agent_version: str = "1.0.0",
    exporter: str = "http",
    endpoint: str = "http://localhost:8000/api/v1",
    pubsub_project: str | None = None,
    pubsub_topic: str = "tracex-traces",
    environment: str = "production",
    auto_flush: bool = True,
    flush_interval_seconds: float = 5.0,
    debug: bool = False,
) -> None:
    """
    Initialize the TRACE-X SDK.

    Args:
        api_key: Your TRACE-X API key.
        agent_id: Unique identifier for this agent.
        agent_name: Human-readable agent name.
        agent_version: Agent version string.
        exporter: "http" or "pubsub".
        endpoint: HTTP endpoint URL (for http exporter).
        pubsub_project: GCP project ID (for pubsub exporter).
        pubsub_topic: Pub/Sub topic name.
        environment: "production", "staging", "development".
        auto_flush: Automatically flush traces.
        flush_interval_seconds: How often to flush.
        debug: Enable debug logging.
    """
    from tracex.recorder import get_global_recorder

    recorder = get_global_recorder()
    recorder.initialize(
        api_key=api_key,
        agent_id=agent_id,
        agent_name=agent_name,
        agent_version=agent_version,
        exporter_type=exporter,
        endpoint=endpoint,
        pubsub_project=pubsub_project,
        pubsub_topic=pubsub_topic,
        environment=environment,
        auto_flush=auto_flush,
        flush_interval_seconds=flush_interval_seconds,
        debug=debug,
    )


def wrap(agent_callable, name: str | None = None) -> AgentWrapper:
    """
    Wrap an agent callable with TRACE-X instrumentation.

    Args:
        agent_callable: The agent function or class to wrap.
        name: Optional display name for the agent.

    Returns:
        Wrapped agent that records all calls.
    """
    from tracex.recorder import get_global_recorder
    recorder = get_global_recorder()
    return recorder.wrap(agent_callable, name)


def trace(
    span_name: str,
    kind: str = "agent",
    record_input: bool = True,
    record_output: bool = True,
):
    """
    Decorator to trace a function call.

    Usage:
        @tracex.trace("my_function")
        async def my_function(arg1, arg2):
            ...
    """
    import functools
    import asyncio
    from tracex.recorder import get_global_recorder

    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            recorder = get_global_recorder()
            async with recorder.create_span(span_name, kind=kind) as span:
                if record_input:
                    span.set_input({"args": str(args)[:500], "kwargs": str(kwargs)[:500]})
                try:
                    result = await func(*args, **kwargs)
                    if record_output:
                        span.set_output(str(result)[:1000])
                    return result
                except Exception as exc:
                    span.set_error(str(exc), type(exc).__name__)
                    raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            recorder = get_global_recorder()
            with recorder.create_span_sync(span_name, kind=kind) as span:
                if record_input:
                    span.set_input({"args": str(args)[:500], "kwargs": str(kwargs)[:500]})
                try:
                    result = func(*args, **kwargs)
                    if record_output:
                        span.set_output(str(result)[:1000])
                    return result
                except Exception as exc:
                    span.set_error(str(exc), type(exc).__name__)
                    raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


async def flush() -> None:
    """Flush all pending traces immediately."""
    from tracex.recorder import get_global_recorder
    await get_global_recorder().flush()


async def shutdown() -> None:
    """Flush and shutdown the SDK."""
    from tracex.recorder import get_global_recorder
    await get_global_recorder().shutdown()


__all__ = [
    "init",
    "wrap",
    "trace",
    "flush",
    "shutdown",
    "AgentWrapper",
    "AgentSpan",
    "SpanContext",
    "ToolCallRecord",
]

__version__ = "1.0.0"
