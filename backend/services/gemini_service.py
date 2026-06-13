# backend/services/gemini_service.py
from __future__ import annotations

import json
import time
from typing import Any, Type, TypeVar

import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from api.config import Settings

logger = structlog.get_logger(__name__)

T = TypeVar("T")


class GeminiServiceError(Exception):
    """Raised when Gemini service call fails."""


class GeminiService:
    """
    Vertex AI Gemini 2.0 Flash client with structured output, retry logic,
    and token tracking.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._model = None
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Lazy initialization of Vertex AI."""
        if self._initialized:
            return
        try:
            import vertexai
            from vertexai.generative_models import GenerativeModel, GenerationConfig

            vertexai.init(
                project=self.settings.gcp_project_id,
                location=self.settings.vertex_ai_location,
            )
            self._model = GenerativeModel(self.settings.gemini_model)
            self._GenerationConfig = GenerationConfig
            self._initialized = True
            logger.info(
                "gemini_initialized",
                model=self.settings.gemini_model,
                location=self.settings.vertex_ai_location,
            )
        except Exception as exc:
            logger.warning("gemini_init_failed", error=str(exc))
            self._initialized = False
            raise GeminiServiceError(f"Failed to initialize Gemini: {exc}") from exc

    @retry(
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
    )
    async def generate_text(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Generate plain text response from Gemini."""
        import asyncio

        self._ensure_initialized()

        temp = temperature if temperature is not None else self.settings.gemini_temperature
        max_out = max_tokens if max_tokens is not None else self.settings.gemini_max_output_tokens

        def _call():
            start = time.perf_counter()
            try:
                from vertexai.generative_models import GenerativeModel, GenerationConfig, Content, Part

                # Create model with system instruction if provided
                model = self._model
                if system_instruction:
                    model = GenerativeModel(
                        self.settings.gemini_model,
                        system_instruction=system_instruction,
                    )

                config = GenerationConfig(
                    temperature=temp,
                    max_output_tokens=max_out,
                    top_p=self.settings.gemini_top_p,
                )
                response = model.generate_content(
                    prompt,
                    generation_config=config,
                )
                duration = (time.perf_counter() - start) * 1000
                logger.debug(
                    "gemini_call",
                    duration_ms=round(duration, 2),
                    tokens=response.usage_metadata.total_token_count if hasattr(response, 'usage_metadata') else None,
                )
                return response.text
            except Exception as exc:
                logger.error("gemini_generate_failed", error=str(exc))
                raise GeminiServiceError(f"Gemini generation failed: {exc}") from exc

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _call)

    async def generate_structured(
        self,
        prompt: str,
        system_instruction: str | None = None,
        response_schema: dict[str, Any] | None = None,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        """
        Generate structured JSON response from Gemini.
        Returns parsed dictionary.
        """
        # Build prompt asking for JSON
        json_prompt = prompt
        if response_schema:
            schema_str = json.dumps(response_schema, indent=2)
            json_prompt = (
                f"{prompt}\n\n"
                f"Respond with valid JSON matching this schema:\n{schema_str}\n"
                f"Return ONLY the JSON, no markdown, no explanation."
            )
        else:
            json_prompt = f"{prompt}\n\nRespond with valid JSON only. No markdown, no explanation."

        raw = await self.generate_text(
            prompt=json_prompt,
            system_instruction=system_instruction,
            temperature=temperature or 0.1,
        )

        # Parse response
        try:
            # Clean up common LLM JSON wrapping
            clean = raw.strip()
            if clean.startswith("```json"):
                clean = clean[7:]
            if clean.startswith("```"):
                clean = clean[3:]
            if clean.endswith("```"):
                clean = clean[:-3]
            clean = clean.strip()
            return json.loads(clean)
        except json.JSONDecodeError as exc:
            logger.warning("gemini_json_parse_failed", raw=raw[:200], error=str(exc))
            # Return raw text wrapped in a dict
            return {"raw_response": raw, "parse_error": str(exc)}

    async def generate_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        system_instruction: str | None = None,
    ) -> dict[str, Any]:
        """Generate response with tool use (function calling)."""
        import asyncio

        self._ensure_initialized()

        def _call():
            try:
                from vertexai.generative_models import (
                    GenerativeModel,
                    GenerationConfig,
                    Tool,
                    FunctionDeclaration,
                )

                model = GenerativeModel(
                    self.settings.gemini_model,
                    system_instruction=system_instruction,
                )

                # Convert tools to Vertex AI format
                function_declarations = []
                for tool in tools:
                    fd = FunctionDeclaration(
                        name=tool["name"],
                        description=tool.get("description", ""),
                        parameters=tool.get("parameters", {}),
                    )
                    function_declarations.append(fd)

                vertex_tools = [Tool(function_declarations=function_declarations)]

                # Build the prompt from messages
                prompt = "\n".join(
                    f"{m.get('role', 'user').upper()}: {m.get('content', '')}"
                    for m in messages
                )

                config = GenerationConfig(
                    temperature=self.settings.gemini_temperature,
                    max_output_tokens=self.settings.gemini_max_output_tokens,
                )
                response = model.generate_content(
                    prompt,
                    tools=vertex_tools,
                    generation_config=config,
                )

                # Extract tool calls if present
                result: dict[str, Any] = {"text": "", "tool_calls": []}
                for part in response.candidates[0].content.parts:
                    if hasattr(part, "function_call") and part.function_call:
                        result["tool_calls"].append({
                            "name": part.function_call.name,
                            "args": dict(part.function_call.args),
                        })
                    elif hasattr(part, "text") and part.text:
                        result["text"] += part.text

                return result
            except Exception as exc:
                logger.error("gemini_tools_failed", error=str(exc))
                raise GeminiServiceError(f"Gemini tool call failed: {exc}") from exc

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _call)

    async def estimate_tokens(self, text: str) -> int:
        """Rough token count estimate (4 chars per token)."""
        return len(text) // 4

    async def summarize(self, text: str, max_sentences: int = 3) -> str:
        """Summarize text in N sentences."""
        prompt = (
            f"Summarize the following in {max_sentences} sentences or fewer. "
            f"Be concise and technical:\n\n{text}"
        )
        return await self.generate_text(prompt, temperature=0.1)

    async def generate_incident_report(
        self,
        trace: Any,
        diagnosis: Any | None,
        repair: Any | None,
    ) -> str:
        """Generate a human-readable markdown incident postmortem for a failed trace."""
        failing_span = trace.spans[-1] if trace.spans else None

        context_parts = [
            f"Agent: {trace.agent_name} (ID: {trace.agent_id}, version {trace.agent_version or 'unknown'})",
            f"Trace ID: {trace.trace_id}",
            f"Status: {trace.status}",
            f"Failure type: {trace.failure_type}",
            f"Failure reason: {trace.failure_reason or 'none recorded'}",
            f"Started at: {trace.started_at}",
            f"Duration: {(trace.duration_ms or 0) / 1000:.2f}s across {len(trace.spans)} spans",
        ]
        if failing_span:
            context_parts.append(
                f"Failing span: {failing_span.span_name} ({failing_span.kind}) — "
                f"{failing_span.error_type}: {failing_span.error_message}"
            )
        if diagnosis:
            context_parts.append(
                f"Diagnosis: root cause={diagnosis.root_cause_category} "
                f"(confidence {diagnosis.confidence:.0%}, severity {diagnosis.severity}). "
                f"{diagnosis.evidence_summary or diagnosis.root_cause_description}"
            )
            if diagnosis.immediate_actions:
                context_parts.append("Immediate actions: " + "; ".join(diagnosis.immediate_actions))
            if diagnosis.long_term_recommendations:
                context_parts.append("Long-term recommendations: " + "; ".join(diagnosis.long_term_recommendations))
        if repair:
            context_parts.append(
                f"Repair: {repair.title} ({repair.repair_type}, status={repair.status}, "
                f"confidence {repair.confidence:.0%}). {repair.description}"
            )
            if repair.validation_passed is not None:
                context_parts.append(
                    f"Validation: {'passed' if repair.validation_passed else 'failed'} "
                    f"(score {repair.validation_score})"
                )

        context = "\n".join(f"- {p}" for p in context_parts)

        prompt = (
            "Write a concise incident postmortem report in Markdown for an AI agent "
            "failure, based on the following trace, diagnosis, and repair data:\n\n"
            f"{context}\n\n"
            "Structure the report with these sections: '# Incident Report — <agent name>', "
            "'## Summary', '## Root Cause Analysis', '## Remediation', and "
            "'## Recommendations'. Be factual, technical, and concise."
        )

        return await self.generate_text(
            prompt,
            system_instruction=(
                "You are an SRE writing incident postmortems for an AI agent "
                "reliability platform. Be precise and avoid speculation beyond the "
                "provided data."
            ),
            temperature=0.3,
        )
