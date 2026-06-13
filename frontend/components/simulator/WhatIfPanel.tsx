"use client";
// frontend/components/simulator/WhatIfPanel.tsx
import { useState } from "react";
import { useRunSimulation } from "@/hooks/useTraces";
import { ConfidenceBar } from "@/components/shared/ConfidenceBar";
import { Loader2, Play, AlertTriangle, CheckCircle, TrendingDown, TrendingUp } from "lucide-react";

const PRESETS = [
  { id: "normal", label: "Normal Load", description: "Baseline — no injection", color: "text-success" },
  { id: "high_load", label: "High Load", description: "3x traffic, elevated errors", color: "text-warning" },
  { id: "tool_failure", label: "Tool Failure", description: "60% tool failure rate", color: "text-danger" },
  { id: "stale_data", label: "Stale Data", description: "Data 6h old, hallucination risk", color: "text-orange-400" },
  { id: "hallucination", label: "Hallucination Storm", description: "70% hallucination probability", color: "text-purple-400" },
  { id: "cascading_failure", label: "Cascading Failure", description: "Multi-service outage", color: "text-danger" },
  { id: "network_partition", label: "Network Partition", description: "90% tool timeouts", color: "text-danger" },
  { id: "context_overflow", label: "Context Overflow", description: "Context limit exceeded", color: "text-orange-400" },
];

export function WhatIfPanel() {
  const [selectedPreset, setSelectedPreset] = useState("normal");
  const [traceId, setTraceId] = useState("");
  const [iterations, setIterations] = useState(10);
  const [result, setResult] = useState<any>(null);

  const simulate = useRunSimulation();

  const handleRun = async () => {
    const res = await simulate.mutateAsync({
      preset: selectedPreset,
      trace_id: traceId || undefined,
      iterations,
    });
    setResult(res);
  };

  const formatDelta = (delta: number, suffix = "") => {
    const sign = delta > 0 ? "+" : "";
    return `${sign}${delta.toFixed(2)}${suffix}`;
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Config Panel */}
      <div className="space-y-4">
        {/* Preset selector */}
        <div className="glass-card p-5 rounded-xl">
          <h2 className="font-semibold mb-4">Failure Scenario</h2>
          <div className="grid grid-cols-2 gap-2">
            {PRESETS.map((preset) => (
              <button
                key={preset.id}
                onClick={() => setSelectedPreset(preset.id)}
                className={`p-3 rounded-lg border text-left transition-all ${
                  selectedPreset === preset.id
                    ? "border-tracex-500/50 bg-tracex-500/10"
                    : "border-border/30 hover:border-border/60 bg-surface-elevated/30"
                }`}
              >
                <p className={`text-sm font-medium ${preset.color}`}>{preset.label}</p>
                <p className="text-xs text-muted-foreground mt-0.5">{preset.description}</p>
              </button>
            ))}
          </div>
        </div>

        {/* Options */}
        <div className="glass-card p-5 rounded-xl space-y-4">
          <h2 className="font-semibold">Simulation Options</h2>
          <div>
            <label className="block text-sm font-medium mb-1">Trace ID (optional)</label>
            <input
              type="text"
              value={traceId}
              onChange={(e) => setTraceId(e.target.value)}
              placeholder="Paste a trace ID to use as baseline..."
              className="w-full px-3 py-2 bg-surface-elevated border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-tracex-500/50"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">
              Iterations: <span className="text-tracex-400">{iterations}</span>
            </label>
            <input
              type="range"
              min={5}
              max={50}
              step={5}
              value={iterations}
              onChange={(e) => setIterations(Number(e.target.value))}
              className="w-full accent-tracex-500"
            />
          </div>
        </div>

        <button
          onClick={handleRun}
          disabled={simulate.isPending}
          className="w-full flex items-center justify-center gap-2 py-3 rounded-xl bg-tracex-500/20 hover:bg-tracex-500/30 text-tracex-300 border border-tracex-500/40 font-medium transition-all disabled:opacity-50"
        >
          {simulate.isPending ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Play className="w-4 h-4" />
          )}
          {simulate.isPending ? "Running simulation..." : "Run Simulation"}
        </button>
      </div>

      {/* Results */}
      <div className="space-y-4">
        {simulate.isPending && (
          <div className="glass-card p-8 rounded-xl text-center">
            <Loader2 className="w-8 h-8 animate-spin text-tracex-400 mx-auto mb-3" />
            <p className="text-muted-foreground text-sm">Running {iterations} iterations...</p>
          </div>
        )}

        {result && !simulate.isPending && (
          <>
            {/* Risk assessment */}
            <div className={`glass-card p-4 rounded-xl border ${
              result.risk_assessment === "critical" || result.risk_assessment === "high"
                ? "border-danger/40"
                : result.risk_assessment === "medium"
                ? "border-warning/40"
                : "border-success/40"
            }`}>
              <div className="flex items-center gap-2 mb-2">
                {result.risk_assessment === "low" ? (
                  <CheckCircle className="w-5 h-5 text-success" />
                ) : (
                  <AlertTriangle className={`w-5 h-5 ${result.risk_assessment === "critical" ? "text-danger" : "text-warning"}`} />
                )}
                <h3 className="font-semibold">
                  Risk: <span className="capitalize">{result.risk_assessment}</span>
                </h3>
              </div>
            </div>

            {/* Metrics comparison */}
            <div className="glass-card p-5 rounded-xl">
              <h3 className="font-semibold mb-4">Metrics Comparison</h3>
              <div className="space-y-3">
                {result.baseline_metrics && result.what_if_metrics && [
                  {
                    label: "Success Rate",
                    baseline: `${(result.baseline_metrics.success_rate * 100).toFixed(1)}%`,
                    whatif: `${(result.what_if_metrics.success_rate * 100).toFixed(1)}%`,
                    delta: result.comparison?.success_rate_pct_change,
                    lowerIsBetter: false,
                  },
                  {
                    label: "Avg Latency",
                    baseline: `${result.baseline_metrics.avg_latency_ms?.toFixed(0)}ms`,
                    whatif: `${result.what_if_metrics.avg_latency_ms?.toFixed(0)}ms`,
                    delta: result.comparison?.latency_pct_change,
                    lowerIsBetter: true,
                  },
                  {
                    label: "Error Rate",
                    baseline: `${(result.baseline_metrics.error_rate * 100).toFixed(1)}%`,
                    whatif: `${(result.what_if_metrics.error_rate * 100).toFixed(1)}%`,
                    delta: (result.comparison?.error_rate_delta ?? 0) * 100,
                    lowerIsBetter: true,
                  },
                  {
                    label: "Hallucination Prob.",
                    baseline: `${(result.baseline_metrics.hallucination_probability * 100).toFixed(1)}%`,
                    whatif: `${(result.what_if_metrics.hallucination_probability * 100).toFixed(1)}%`,
                    delta: (result.what_if_metrics.hallucination_probability - result.baseline_metrics.hallucination_probability) * 100,
                    lowerIsBetter: true,
                  },
                ].map(({ label, baseline, whatif, delta, lowerIsBetter }) => {
                  const isWorse = lowerIsBetter ? (delta ?? 0) > 0 : (delta ?? 0) < 0;
                  return (
                    <div key={label} className="flex items-center gap-2">
                      <span className="text-sm text-muted-foreground w-40">{label}</span>
                      <span className="font-mono text-xs text-muted-foreground">{baseline}</span>
                      <span className="text-muted-foreground">→</span>
                      <span className={`font-mono text-xs font-medium ${isWorse ? "text-danger" : "text-success"}`}>{whatif}</span>
                      {delta != null && (
                        <span className={`text-xs ml-auto ${isWorse ? "text-danger" : "text-success"}`}>
                          {isWorse ? <TrendingDown className="w-3 h-3 inline" /> : <TrendingUp className="w-3 h-3 inline" />}
                          {" "}{formatDelta(delta, "%")}
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Insights */}
            {result.insights?.length > 0 && (
              <div className="glass-card p-5 rounded-xl">
                <h3 className="font-semibold mb-3">Insights</h3>
                <ul className="space-y-2">
                  {result.insights.map((insight: string, i: number) => (
                    <li key={i} className="text-sm flex items-start gap-2">
                      <span className="text-tracex-400 mt-0.5">›</span>
                      {insight}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Recommendations */}
            {result.recommended_actions?.length > 0 && (
              <div className="glass-card p-5 rounded-xl border border-tracex-500/20">
                <h3 className="font-semibold mb-3">Recommended Actions</h3>
                <ol className="space-y-2">
                  {result.recommended_actions.map((action: string, i: number) => (
                    <li key={i} className="text-sm flex items-start gap-2">
                      <span className="w-5 h-5 rounded-full bg-tracex-500/20 text-tracex-400 flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5">
                        {i + 1}
                      </span>
                      {action}
                    </li>
                  ))}
                </ol>
              </div>
            )}
          </>
        )}

        {!result && !simulate.isPending && (
          <div className="glass-card p-12 rounded-xl text-center text-muted-foreground">
            <Play className="w-8 h-8 mx-auto mb-3 text-muted-foreground/30" />
            <p>Select a scenario and run simulation to see results</p>
          </div>
        )}
      </div>
    </div>
  );
}
