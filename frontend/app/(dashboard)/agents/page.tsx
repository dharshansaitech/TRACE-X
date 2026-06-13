// frontend/app/(dashboard)/agents/page.tsx
"use client";
import { useQueries } from "@tanstack/react-query";
import { AgentHealthGrid } from "@/components/dashboard/AgentHealthGrid";
import { useAgents, agentKeys } from "@/hooks/useAgents";
import { api } from "@/lib/api-client";
import type { AgentHealth } from "@/types";
import { Loader2, Server } from "lucide-react";

export default function AgentsPage() {
  const { data, isLoading, error } = useAgents();
  const records = data?.agents ?? [];

  const healthQueries = useQueries({
    queries: records.map((record: any) => ({
      queryKey: agentKeys.health(record.agent_id),
      queryFn: () => api.agents.health(record.agent_id),
      enabled: records.length > 0,
      retry: false,
      refetchInterval: 60_000,
    })),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-tracex-400" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-muted-foreground gap-3">
        <Server className="w-12 h-12 text-danger" />
        <p className="text-lg">Failed to load agents</p>
        <p className="text-sm">{(error as Error).message}</p>
      </div>
    );
  }

  const agents: AgentHealth[] = records.map((record: any, i: number) => {
    const health = healthQueries[i]?.data as AgentHealth | undefined;
    if (health) return health;

    // No traces in the last 24h yet — show the registry record with empty metrics
    return {
      agent_id: record.agent_id,
      agent_name: record.agent_name,
      agent_version: record.agent_version,
      status: record.status ?? "unknown",
      metrics: {
        error_rate: 0,
        latency_p50_ms: 0,
        latency_p95_ms: 0,
        latency_p99_ms: 0,
        success_rate: 0,
        throughput_rph: 0,
        tool_failure_rate: 0,
        hallucination_rate: 0,
        staleness_events: 0,
        context_overflow_events: 0,
      },
      last_seen: record.last_seen,
      uptime_hours: 0,
      open_incidents: 0,
      resolved_incidents_24h: 0,
      traces_24h: 0,
      health_score: 0,
      trend: "stable",
      sparkline: [],
    } satisfies AgentHealth;
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Agent Fleet</h1>
        <p className="text-muted-foreground mt-1">
          {agents.length} agents registered — monitor health and performance
        </p>
      </div>
      <AgentHealthGrid agents={agents} />
    </div>
  );
}
