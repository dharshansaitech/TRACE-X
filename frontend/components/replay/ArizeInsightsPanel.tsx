"use client";
// frontend/components/replay/ArizeInsightsPanel.tsx
import Link from "next/link";
import { Sparkles, TrendingUp, GitCompare, Loader2 } from "lucide-react";
import { useDiagnosisInsights } from "@/hooks/useTraces";

interface Props {
  traceId: string;
}

export function ArizeInsightsPanel({ traceId }: Props) {
  const { data, isLoading, error } = useDiagnosisInsights(traceId);

  if (isLoading) {
    return (
      <div className="glass-card rounded-xl p-6 flex items-center justify-center h-full min-h-[160px]">
        <Loader2 className="w-5 h-5 animate-spin text-tracex-400" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="glass-card rounded-xl p-6 text-sm text-muted-foreground">
        Arize MCP insights unavailable for this trace.
      </div>
    );
  }

  const { similar_traces = [], pattern_insights, drift, performance_baseline } = data;
  const baseline = performance_baseline?.baseline;
  const current = performance_baseline?.current;

  return (
    <div className="glass-card rounded-xl overflow-hidden h-full flex flex-col">
      <div className="px-4 py-3 border-b border-border/50 flex items-center gap-2">
        <Sparkles className="w-4 h-4 text-tracex-400" />
        <h3 className="text-sm font-semibold">Arize MCP Insights</h3>
      </div>

      <div className="p-4 space-y-4 text-sm overflow-y-auto">
        {pattern_insights?.pattern && (
          <div className="p-3 rounded-lg bg-warning/10 border border-warning/20 text-xs">
            <p className="font-medium text-warning">{pattern_insights.pattern}</p>
            <p className="mt-1 text-muted-foreground">
              {pattern_insights.frequency}
              {pattern_insights.common_root_cause && ` · Likely cause: ${pattern_insights.common_root_cause}`}
            </p>
          </div>
        )}

        <div>
          <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
            Similar Historical Failures
          </h4>
          {similar_traces.length === 0 ? (
            <p className="text-xs text-muted-foreground">No similar traces found.</p>
          ) : (
            <div className="space-y-1.5">
              {similar_traces.map((t: any) => (
                <Link
                  key={t.trace_id}
                  href={`/replay/${t.trace_id}`}
                  className="flex items-center justify-between px-2.5 py-1.5 rounded-lg bg-surface-elevated/40 hover:bg-surface-elevated/70 transition-colors text-xs"
                >
                  <span className="font-mono truncate">{t.trace_id}</span>
                  <span className="text-tracex-400 flex-shrink-0 ml-2">
                    {Math.round((t.similarity_score ?? 0) * 100)}% match
                  </span>
                </Link>
              ))}
            </div>
          )}
        </div>

        {drift && (
          <div>
            <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <TrendingUp className="w-3.5 h-3.5" />
              Feature Drift
            </h4>
            <div className="flex items-center justify-between text-xs">
              <span>{drift.drift_detected ? "Drift detected" : "No drift detected"}</span>
              <span className={drift.drift_detected ? "text-warning font-medium" : "text-success font-medium"}>
                {((drift.drift_score ?? 0) * 100).toFixed(0)}%
              </span>
            </div>
            {drift.drifted_features?.length > 0 && (
              <p className="text-xs text-muted-foreground mt-1">
                Drifted: {drift.drifted_features.join(", ")}
              </p>
            )}
          </div>
        )}

        {baseline && current && (
          <div>
            <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <GitCompare className="w-3.5 h-3.5" />
              Performance vs. Baseline
            </h4>
            <table className="w-full text-xs">
              <thead>
                <tr className="text-muted-foreground">
                  <th className="text-left font-normal pb-1">Metric</th>
                  <th className="text-right font-normal pb-1">Baseline</th>
                  <th className="text-right font-normal pb-1">Current</th>
                </tr>
              </thead>
              <tbody className="text-foreground/90">
                <tr>
                  <td className="py-0.5">Avg latency</td>
                  <td className="text-right py-0.5">{baseline.avg_latency_ms}ms</td>
                  <td className="text-right py-0.5 text-warning">{current.avg_latency_ms}ms</td>
                </tr>
                <tr>
                  <td className="py-0.5">P95 latency</td>
                  <td className="text-right py-0.5">{baseline.p95_latency_ms}ms</td>
                  <td className="text-right py-0.5 text-warning">{current.p95_latency_ms}ms</td>
                </tr>
                <tr>
                  <td className="py-0.5">Success rate</td>
                  <td className="text-right py-0.5">{((baseline.success_rate ?? 0) * 100).toFixed(0)}%</td>
                  <td className="text-right py-0.5 text-warning">{((current.success_rate ?? 0) * 100).toFixed(0)}%</td>
                </tr>
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
