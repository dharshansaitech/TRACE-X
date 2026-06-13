// frontend/app/(dashboard)/traces/[traceId]/page.tsx
"use client";

import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useTrace, useTraceDiagnosis } from "@/hooks/useTraces";
import { SeverityBadge } from "@/components/shared/SeverityBadge";
import { ConfidenceBar } from "@/components/shared/ConfidenceBar";
import {
  ArrowLeft, Play, Cpu, AlertCircle, CheckCircle,
  Clock, Zap, Hash, ChevronDown, ChevronRight
} from "lucide-react";
import { formatDistanceToNow, format } from "date-fns";
import { useState } from "react";

export default function TraceDetailPage() {
  const params = useParams();
  const router = useRouter();
  const traceId = params.traceId as string;
  const [expandedSpans, setExpandedSpans] = useState<Set<string>>(new Set());

  const { data: trace, isLoading } = useTrace(traceId);
  const { data: diagnosis } = useTraceDiagnosis(traceId);

  const toggleSpan = (spanId: string) => {
    setExpandedSpans((prev) => {
      const next = new Set(prev);
      next.has(spanId) ? next.delete(spanId) : next.add(spanId);
      return next;
    });
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin w-8 h-8 border-2 border-tracex-400 border-t-transparent rounded-full" />
      </div>
    );
  }

  if (!trace) {
    return (
      <div className="text-center py-20 text-muted-foreground">
        Trace {traceId} not found
      </div>
    );
  }

  const statusColor = trace.status === "success" ? "text-success" : trace.status === "failure" ? "text-danger" : "text-warning";

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-4 flex-wrap">
        <button onClick={() => router.back()} className="p-2 rounded-lg hover:bg-surface-elevated transition-colors">
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold truncate">Trace {trace.trace_id.slice(0, 16)}...</h1>
            <span className={`font-medium text-sm ${statusColor}`}>{trace.status}</span>
          </div>
          <p className="text-muted-foreground text-sm">
            {trace.agent_name} · {formatDistanceToNow(new Date(trace.started_at), { addSuffix: true })}
          </p>
        </div>
        {trace.status === "failure" && (
          <Link
            href={`/replay/${trace.trace_id}`}
            className="flex items-center gap-2 px-4 py-2 bg-warning/20 hover:bg-warning/30 text-warning border border-warning/50 rounded-lg transition-colors text-sm font-medium"
          >
            <Play className="w-4 h-4" />
            Replay Failure
          </Link>
        )}
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {[
          { label: "Duration", value: trace.duration_ms ? `${(trace.duration_ms / 1000).toFixed(2)}s` : "—", icon: Clock },
          { label: "Spans", value: trace.spans?.length ?? 0, icon: Zap },
          { label: "Tool Calls", value: trace.total_tool_calls ?? 0, icon: Cpu },
          { label: "Tokens", value: trace.total_tokens?.toLocaleString() ?? "0", icon: Hash },
          { label: "Errors", value: trace.error_count ?? 0, icon: AlertCircle },
        ].map(({ label, value, icon: Icon }) => (
          <div key={label} className="glass-card p-3 rounded-xl text-center">
            <Icon className="w-4 h-4 mx-auto mb-1 text-tracex-400" />
            <div className="text-lg font-bold">{value}</div>
            <div className="text-xs text-muted-foreground">{label}</div>
          </div>
        ))}
      </div>

      {/* Diagnosis Card */}
      {diagnosis && (
        <div className="glass-card p-5 rounded-xl border border-tracex-500/30">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold text-tracex-300 flex items-center gap-2">
              <AlertCircle className="w-4 h-4" />
              Root Cause Analysis
            </h2>
            <SeverityBadge severity={diagnosis.severity} />
          </div>
          <p className="text-sm text-foreground/90 mb-3">{diagnosis.root_cause_description}</p>
          <div className="flex items-center gap-4 text-sm">
            <span className="text-muted-foreground">Category: <span className="text-foreground">{diagnosis.root_cause_category.replace(/_/g, " ")}</span></span>
            <span className="text-muted-foreground">Confidence:</span>
            <div className="flex-1 max-w-32">
              <ConfidenceBar value={diagnosis.confidence} />
            </div>
          </div>
          {diagnosis.immediate_actions?.length > 0 && (
            <div className="mt-3">
              <p className="text-xs font-medium text-muted-foreground mb-2">IMMEDIATE ACTIONS</p>
              <ul className="space-y-1">
                {diagnosis.immediate_actions.slice(0, 3).map((action: string, i: number) => (
                  <li key={i} className="text-sm flex items-start gap-2">
                    <ChevronRight className="w-4 h-4 text-tracex-400 mt-0.5 flex-shrink-0" />
                    {action}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Spans Timeline */}
      <div className="glass-card rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-border/50">
          <h2 className="font-semibold">Execution Timeline</h2>
          <p className="text-xs text-muted-foreground mt-0.5">{trace.spans?.length ?? 0} spans</p>
        </div>
        <div className="divide-y divide-border/20">
          {(trace.spans ?? []).slice(0, 50).map((span: any) => {
            const isExpanded = expandedSpans.has(span.span_id);
            const isError = span.status === "error";
            return (
              <div key={span.span_id} className={`${isError ? "bg-danger/5" : ""}`}>
                <button
                  onClick={() => toggleSpan(span.span_id)}
                  className="w-full flex items-center gap-3 px-5 py-3 hover:bg-surface-elevated/50 transition-colors text-left"
                >
                  {isExpanded ? (
                    <ChevronDown className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                  )}
                  <div className={`w-2 h-2 rounded-full flex-shrink-0 ${isError ? "bg-danger" : "bg-success"}`} />
                  <span className="font-medium text-sm flex-1 truncate">{span.span_name}</span>
                  <span className="text-xs text-muted-foreground font-mono">{span.kind}</span>
                  {span.model && <span className="text-xs text-tracex-400 font-mono">{span.model}</span>}
                  <span className="text-xs text-muted-foreground font-mono ml-2">
                    {span.duration_ms ? `${span.duration_ms.toFixed(0)}ms` : "—"}
                  </span>
                </button>
                {isExpanded && (
                  <div className="px-12 pb-4 space-y-2">
                    {span.error_message && (
                      <div className="p-3 bg-danger/10 rounded-lg border border-danger/30">
                        <p className="text-xs font-medium text-danger mb-1">ERROR</p>
                        <p className="text-sm font-mono">{span.error_message}</p>
                      </div>
                    )}
                    {span.output_content && (
                      <div className="p-3 bg-muted/30 rounded-lg">
                        <p className="text-xs font-medium text-muted-foreground mb-1">OUTPUT</p>
                        <p className="text-sm font-mono whitespace-pre-wrap">{span.output_content.slice(0, 500)}</p>
                      </div>
                    )}
                    {span.total_tokens && (
                      <p className="text-xs text-muted-foreground">
                        Tokens: {span.prompt_tokens ?? "?"} prompt + {span.completion_tokens ?? "?"} completion = {span.total_tokens}
                      </p>
                    )}
                    {span.tool_calls?.length > 0 && (
                      <div>
                        <p className="text-xs font-medium text-muted-foreground mb-1">TOOL CALLS ({span.tool_calls.length})</p>
                        {span.tool_calls.map((tc: any) => (
                          <div key={tc.tool_call_id} className={`flex items-center gap-2 py-1 text-sm ${tc.status === "error" ? "text-danger" : "text-muted-foreground"}`}>
                            <div className={`w-1.5 h-1.5 rounded-full ${tc.status === "error" ? "bg-danger" : "bg-success"}`} />
                            <span className="font-mono">{tc.tool_name}</span>
                            {tc.duration_ms && <span>{tc.duration_ms.toFixed(0)}ms</span>}
                            {tc.error && <span className="text-danger text-xs">{tc.error.slice(0, 80)}</span>}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
