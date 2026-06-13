"use client";
// frontend/components/dashboard/AgentHealthGrid.tsx
import Link from "next/link";
import { motion } from "framer-motion";
import type { AgentHealth } from "@/types";
import { ConfidenceBar } from "@/components/shared/ConfidenceBar";

interface Props {
  agents: AgentHealth[];
  compact?: boolean;
}

const STATUS_STYLES = {
  healthy: { dot: "bg-success", text: "text-success", border: "border-success/20" },
  degraded: { dot: "bg-warning", text: "text-warning", border: "border-warning/20" },
  critical: { dot: "bg-danger animate-pulse", text: "text-danger", border: "border-danger/30" },
  offline: { dot: "bg-muted-foreground", text: "text-muted-foreground", border: "border-border/30" },
  unknown: { dot: "bg-muted-foreground", text: "text-muted-foreground", border: "border-border/30" },
};

export function AgentHealthGrid({ agents, compact = false }: Props) {
  if (agents.length === 0) {
    return (
      <div className="glass-card p-8 rounded-xl text-center text-muted-foreground">
        <p>No agents registered yet</p>
        <p className="text-sm mt-1">Instrument your first agent with the TRACE-X SDK</p>
      </div>
    );
  }

  return (
    <div className={`grid gap-3 ${compact ? "grid-cols-1" : "grid-cols-1 md:grid-cols-2 lg:grid-cols-3"}`}>
      {agents.map((agent, i) => {
        const styles = STATUS_STYLES[agent.status as keyof typeof STATUS_STYLES] ?? STATUS_STYLES.unknown;

        return (
          <motion.div
            key={agent.agent_id}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05 }}
          >
            <Link
              href={`/agents/${agent.agent_id}`}
              className={`block glass-card p-4 rounded-xl card-hover border ${styles.border} transition-all ${
                agent.status === "critical" ? "pulse-critical" : agent.status === "healthy" ? "fade-healthy" : ""
              }`}
            >
              <div className="flex items-start gap-3">
                <div className="flex-shrink-0 mt-0.5">
                  <div className={`w-2.5 h-2.5 rounded-full ${styles.dot}`} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <h3 className="font-medium text-sm truncate">{agent.agent_name}</h3>
                    <span className={`text-xs font-medium ${styles.text} flex-shrink-0`}>
                      {agent.status}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5 truncate">
                    {agent.agent_id}
                  </p>

                  {!compact && (
                    <div className="mt-3 space-y-1.5">
                      <div className="flex justify-between text-xs text-muted-foreground">
                        <span>Health Score</span>
                        <span className="font-mono">{agent.health_score?.toFixed(0) ?? 0}/100</span>
                      </div>
                      <ConfidenceBar value={(agent.health_score ?? 0) / 100} small />
                    </div>
                  )}

                  <div className="flex items-center gap-3 mt-2 text-xs text-muted-foreground">
                    <span>
                      Error: <span className={agent.metrics.error_rate > 0.05 ? "text-danger" : "text-success"}>
                        {(agent.metrics.error_rate * 100).toFixed(1)}%
                      </span>
                    </span>
                    <span>
                      P99: <span className="text-foreground">{agent.metrics.latency_p99_ms?.toFixed(0) ?? 0}ms</span>
                    </span>
                    {agent.traces_24h != null && (
                      <span>{agent.traces_24h} traces</span>
                    )}
                  </div>
                </div>
              </div>
            </Link>
          </motion.div>
        );
      })}
    </div>
  );
}
