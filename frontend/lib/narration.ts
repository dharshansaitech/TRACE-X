// frontend/lib/narration.ts
import type { ReplayFrame } from "@/types";

function truncate(text: string, max = 80): string {
  if (text.length <= max) return text;
  return `${text.slice(0, max).trim()}…`;
}

export function narrateFrame(frame: ReplayFrame, agentName = "The agent"): string {
  const content = frame.content ?? {};

  if (frame.is_divergence_point) {
    return `This is the moment execution diverges from expected behavior — everything after this point follows the failure path.`;
  }

  switch (frame.frame_type) {
    case "span_start":
      return `${agentName} begins "${content.span_name ?? "a new step"}".`;

    case "span_end":
      return `${agentName} finishes "${content.span_name ?? "this step"}"${
        content.duration_ms ? ` in ${content.duration_ms.toFixed(0)}ms` : ""
      }.`;

    case "llm_prompt":
      return `${agentName} sends a prompt to ${content.model ?? "the model"}${
        content.prompt_tokens ? ` (${content.prompt_tokens} tokens)` : ""
      }.`;

    case "llm_response":
      if (frame.is_failure_frame) {
        return `${content.model ?? "The model"} responds — but the output looks suspect (finish reason: ${
          content.finish_reason ?? "unknown"
        }).`;
      }
      return `${content.model ?? "The model"} responds${
        content.finish_reason ? ` — finish reason: ${content.finish_reason}` : ""
      }.`;

    case "tool_call":
      return `${agentName} calls the "${content.tool_name ?? "tool"}" tool${
        content.input_args && Object.keys(content.input_args).length
          ? ` with ${Object.keys(content.input_args).length} argument(s)`
          : ""
      }.`;

    case "tool_result":
      return `"${content.tool_name ?? "Tool"}" returns a result${
        content.duration_ms ? ` after ${content.duration_ms.toFixed(0)}ms` : ""
      }.`;

    case "tool_error":
      return `"${content.tool_name ?? "Tool"}" fails${
        content.duration_ms ? ` after ${content.duration_ms.toFixed(0)}ms` : ""
      }${content.error ? ` — ${truncate(String(content.error))}` : ""}.`;

    case "error_event":
      return `An error occurs: ${content.error_type ?? "unexpected error"}${
        content.error_message ? ` — ${truncate(String(content.error_message))}` : ""
      }.`;

    case "state_snapshot":
      return `${agentName}'s internal state is captured at this point.`;

    default:
      return frame.is_failure_frame
        ? `${agentName} hits a failure during "${frame.frame_type.replace(/_/g, " ")}".`
        : `${agentName} proceeds through "${frame.frame_type.replace(/_/g, " ")}".`;
  }
}
