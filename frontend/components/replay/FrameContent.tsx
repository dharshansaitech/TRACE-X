"use client";
// frontend/components/replay/FrameContent.tsx
import { motion } from "framer-motion";
import { AlertCircle, CheckCircle, Wrench, Cpu, MessageSquare, AlertTriangle, Zap } from "lucide-react";
import type { ReplayFrame } from "@/types";
import { SeverityBadge } from "@/components/shared/SeverityBadge";

interface Props {
  frame: ReplayFrame;
}

const FRAME_ICONS: Record<string, any> = {
  span_start: Zap,
  span_end: CheckCircle,
  llm_prompt: MessageSquare,
  llm_response: Cpu,
  tool_call: Wrench,
  tool_result: CheckCircle,
  tool_error: AlertCircle,
  error_event: AlertCircle,
  divergence_point: AlertTriangle,
  state_snapshot: Zap,
};

const FRAME_COLORS: Record<string, string> = {
  tool_error: "border-danger/50 bg-danger/5",
  error_event: "border-danger/50 bg-danger/5",
  divergence_point: "border-warning/50 bg-warning/5",
  span_end: "border-success/30 bg-success/5",
  default: "border-border/30",
};

export function FrameContent({ frame }: Props) {
  const Icon = FRAME_ICONS[frame.frame_type] ?? Zap;
  const borderClass = FRAME_COLORS[frame.frame_type] ?? FRAME_COLORS.default;

  return (
    <motion.div
      key={frame.frame_id}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
      className="space-y-4 cinematic-frame"
    >
      {/* Frame header */}
      <div className={`flex items-center gap-3 p-3 rounded-lg border transition-colors duration-300 ${borderClass}`}>
        <div className={`w-8 h-8 rounded-lg flex items-center justify-center transition-colors duration-300 ${
          frame.is_failure_frame ? "bg-danger/20" : frame.is_divergence_point ? "bg-warning/20" : "bg-tracex-500/10"
        }`}>
          <Icon className={`w-4 h-4 ${
            frame.is_failure_frame ? "text-danger" : frame.is_divergence_point ? "text-warning" : "text-tracex-400"
          }`} />
        </div>
        <div className="flex-1">
          <p className="font-medium text-sm capitalize">
            {frame.frame_type.replace(/_/g, " ")}
          </p>
          <p className="text-xs text-muted-foreground font-mono">
            +{frame.relative_time_ms?.toFixed(2)}ms
          </p>
        </div>
        {frame.is_failure_frame && (
          <span className="badge-high text-xs px-2 py-0.5 rounded">FAILURE</span>
        )}
        {frame.is_divergence_point && (
          <span className="badge-medium text-xs px-2 py-0.5 rounded">DIVERGENCE</span>
        )}
      </div>

      {/* Frame content based on type */}
      <FrameTypeContent frame={frame} />

      {/* Annotations */}
      {frame.annotations?.length > 0 && (
        <div className="space-y-2">
          {frame.annotations.map((ann) => (
            <div
              key={ann.annotation_id}
              className={`p-3 rounded-lg border text-sm ${
                ann.severity === "error" ? "border-danger/40 bg-danger/5" :
                ann.severity === "warning" ? "border-warning/40 bg-warning/5" :
                "border-border/30 bg-muted/20"
              }`}
            >
              <p className="font-medium text-xs uppercase tracking-wider mb-1 text-muted-foreground">
                {ann.annotation_type.toUpperCase()} · {ann.title}
              </p>
              <p className="text-sm">{ann.body}</p>
            </div>
          ))}
        </div>
      )}

      {/* Context info */}
      {frame.context_tokens_used != null && (
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span>Context: {frame.context_tokens_used?.toLocaleString()} / {frame.context_tokens_max?.toLocaleString() ?? "∞"} tokens</span>
          {frame.context_tokens_max && (
            <div className="flex-1 max-w-32 h-1.5 bg-muted rounded-full overflow-hidden">
              <div
                className="h-full bg-tracex-400 transition-all"
                style={{ width: `${(frame.context_tokens_used / frame.context_tokens_max) * 100}%` }}
              />
            </div>
          )}
        </div>
      )}

      {/* Active spans */}
      {frame.active_spans?.length > 0 && (
        <div>
          <p className="text-xs text-muted-foreground mb-1">Active spans:</p>
          <div className="flex flex-wrap gap-1">
            {frame.active_spans.slice(0, 5).map((spanId) => (
              <span key={spanId} className="text-xs font-mono px-2 py-0.5 bg-tracex-500/10 text-tracex-400 rounded">
                {spanId.slice(0, 8)}
              </span>
            ))}
          </div>
        </div>
      )}
    </motion.div>
  );
}

function FrameTypeContent({ frame }: { frame: ReplayFrame }) {
  const content = frame.content ?? {};

  switch (frame.frame_type) {
    case "llm_prompt":
      return (
        <div className="space-y-2">
          <p className="text-xs text-muted-foreground">Model: <span className="text-foreground">{content.model ?? "unknown"}</span></p>
          <p className="text-xs text-muted-foreground">Prompt tokens: {content.prompt_tokens ?? "?"}</p>
          {content.messages?.length > 0 && (
            <div className="space-y-1">
              {content.messages.slice(-2).map((msg: any, i: number) => (
                <div key={i} className="p-2 bg-muted/30 rounded text-xs">
                  <span className="text-muted-foreground uppercase">{msg.role}: </span>
                  <span className="font-mono">{typeof msg.content === "string" ? msg.content.slice(0, 300) : JSON.stringify(msg.content).slice(0, 300)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      );

    case "llm_response":
      return (
        <div className="space-y-2">
          <p className="text-xs text-muted-foreground">
            Model: <span className="text-foreground">{content.model ?? "unknown"}</span> ·
            Finish: <span className="text-foreground">{content.finish_reason ?? "?"}</span> ·
            Tokens: <span className="text-foreground">{content.total_tokens ?? "?"}</span>
          </p>
          {content.output && (
            <div className="p-3 bg-muted/30 rounded text-xs font-mono whitespace-pre-wrap">
              {content.output}
            </div>
          )}
        </div>
      );

    case "tool_call":
      return (
        <div className="space-y-2">
          <p className="font-medium text-sm">{content.tool_name}</p>
          {content.input_args && Object.keys(content.input_args).length > 0 && (
            <pre className="p-3 bg-muted/30 rounded text-xs font-mono overflow-x-auto">
              {JSON.stringify(content.input_args, null, 2).slice(0, 500)}
            </pre>
          )}
        </div>
      );

    case "tool_result":
    case "tool_error":
      return (
        <div className="space-y-2">
          <p className="font-medium text-sm">{content.tool_name} · {content.duration_ms?.toFixed(0)}ms</p>
          {content.output != null && (
            <pre className="p-3 bg-success/5 border border-success/20 rounded text-xs font-mono overflow-x-auto">
              {typeof content.output === "string" ? content.output.slice(0, 500) : JSON.stringify(content.output, null, 2).slice(0, 500)}
            </pre>
          )}
          {content.error && (
            <div className="p-3 bg-danger/5 border border-danger/30 rounded text-xs font-mono text-danger">
              {content.error}
            </div>
          )}
        </div>
      );

    case "error_event":
      return (
        <div className="p-3 bg-danger/5 border border-danger/30 rounded text-sm space-y-1">
          <p className="font-medium text-danger">{content.error_type ?? "Error"}</p>
          <p className="font-mono text-xs">{content.error_message}</p>
        </div>
      );

    case "divergence_point":
      return (
        <div className="p-3 bg-warning/5 border border-warning/30 rounded text-sm">
          <p className="font-medium text-warning mb-1">Execution diverged from expected behavior</p>
          <p className="text-xs text-muted-foreground">{content.span_name}</p>
        </div>
      );

    default:
      return (
        <pre className="p-3 bg-muted/20 rounded text-xs font-mono overflow-x-auto text-muted-foreground">
          {JSON.stringify(content, null, 2).slice(0, 600)}
        </pre>
      );
  }
}
