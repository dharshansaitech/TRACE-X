// frontend/app/(dashboard)/agents/[agentId]/page.tsx
"use client";

import { useParams, useRouter } from "next/navigation";
import { useAgentHealth } from "@/hooks/useAgents";
import type { AgentStatus } from "@/types";
import { SeverityBadge } from "@/components/shared/SeverityBadge";
import { ConfidenceBar } from "@/components/shared/ConfidenceBar";
import { ArrowLeft, Loader2, Activity, AlertTriangle, CheckCircle2, Clock } from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

export default function AgentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const agentId = params.agentId as string;
  const { data: health, isLoading } = useAgentHealth(agentId);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-tracex-400" />
      </div>
    );
  }

  if (!health) {
    return (
      <div className="text-center py-20 text-muted-foreground">
        <AlertTriangle className="w-12 h-12 mx-auto mb-4 text-warning" />
        <p>No health data available for agent {agentId}</p>
      </div>
    );
  }

  const sparklineData = (health.sparkline ?? []).map((v: number, i: number) => ({
    hour: `-${24 - i}h`,
    errorRate: v,
  }));

  const statusColorMap: Record<AgentStatus, string> = {
    healthy: "text-success",
    degraded: "text-warning",
    critical: "text-danger",
    offline: "text-muted-foreground",
    unknown: "text-muted-foreground",
  };
  const status = (health.status ?? "unknown") as AgentStatus;
  const statusColor = statusColorMap[status];

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => router.back()}
          className="p-2 rounded-lg hover:bg-surface-elevated transition-colors text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div>
          <h1 className="text-2xl font-bold">{health.agent_name}</h1>
          <p className="text-muted-foreground text-sm">{health.agent_id}</p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <div className={`status-dot status-dot-${health.status}`} />
          <span className={`font-medium ${statusColor}`}>
            {health.status?.toUpperCase()}
          </span>
        </div>
      </div>

      {/* Health Score */}
      <div className="glass-card p-6 rounded-xl">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Health Score</h2>
          <span className="text-4xl font-bold text-gradient">
            {health.health_score?.toFixed(0)}
          </span>
        </div>
        <ConfidenceBar value={(health.health_score ?? 0) / 100} />
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Error Rate", value: `${((health.metrics?.error_rate ?? 0) * 100).toFixed(2)}%`, icon: AlertTriangle, danger: (health.metrics?.error_rate ?? 0) > 0.05 },
          { label: "Success Rate", value: `${((health.metrics?.success_rate ?? 0) * 100).toFixed(1)}%`, icon: CheckCircle2, danger: false },
          { label: "P99 Latency", value: `${health.metrics?.latency_p99_ms?.toFixed(0) ?? 0}ms`, icon: Clock, danger: (health.metrics?.latency_p99_ms ?? 0) > 5000 },
          { label: "Traces (24h)", value: health.traces_24h?.toString() ?? "0", icon: Activity, danger: false },
        ].map((metric) => (
          <div key={metric.label} className="glass-card p-4 rounded-xl">
            <metric.icon
              className={`w-5 h-5 mb-2 ${metric.danger ? "text-danger" : "text-tracex-400"}`}
            />
            <div className="text-2xl font-bold">{metric.value}</div>
            <div className="text-xs text-muted-foreground mt-1">{metric.label}</div>
          </div>
        ))}
      </div>

      {/* Error Rate Chart */}
      {sparklineData.length > 0 && (
        <div className="glass-card p-6 rounded-xl">
          <h2 className="text-lg font-semibold mb-4">Error Rate (24h)</h2>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={sparklineData}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis dataKey="hour" tick={{ fontSize: 11, fill: "#6b7280" }} />
              <YAxis tick={{ fontSize: 11, fill: "#6b7280" }} tickFormatter={(v) => `${v}%`} />
              <Tooltip
                contentStyle={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: "8px" }}
                labelStyle={{ color: "#94a3b8" }}
              />
              <Line
                type="monotone"
                dataKey="errorRate"
                stroke="#0ea5e9"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Detailed Metrics */}
      <div className="glass-card p-6 rounded-xl">
        <h2 className="text-lg font-semibold mb-4">Detailed Metrics</h2>
        <div className="space-y-3">
          {[
            ["Tool Failure Rate", `${((health.metrics?.tool_failure_rate ?? 0) * 100).toFixed(2)}%`],
            ["Hallucination Rate", `${((health.metrics?.hallucination_rate ?? 0) * 100).toFixed(2)}%`],
            ["P50 Latency", `${health.metrics?.latency_p50_ms?.toFixed(0) ?? 0}ms`],
            ["P95 Latency", `${health.metrics?.latency_p95_ms?.toFixed(0) ?? 0}ms`],
            ["Throughput (RPH)", health.metrics?.throughput_rph?.toFixed(0) ?? "0"],
            ["Open Incidents", health.open_incidents?.toString() ?? "0"],
          ].map(([label, value]) => (
            <div key={label} className="flex justify-between items-center py-2 border-b border-border/30 last:border-0">
              <span className="text-muted-foreground text-sm">{label}</span>
              <span className="font-mono text-sm">{value}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
