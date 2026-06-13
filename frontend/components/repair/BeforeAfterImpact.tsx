"use client";
// frontend/components/repair/BeforeAfterImpact.tsx
import { motion } from "framer-motion";
import { ArrowRight, TrendingUp, Loader2 } from "lucide-react";
import { useAgentHealth } from "@/hooks/useAgents";
import type { RepairArtifact } from "@/types";

interface Props {
  agentId: string;
  repair: RepairArtifact;
}

function clamp01(n: number): number {
  return Math.max(0, Math.min(1, n));
}

export function BeforeAfterImpact({ agentId, repair }: Props) {
  const { data: health, isLoading } = useAgentHealth(agentId);

  if (isLoading) {
    return (
      <div className="glass-card p-5 rounded-xl flex items-center justify-center gap-2 text-muted-foreground text-sm">
        <Loader2 className="w-4 h-4 animate-spin" />
        Loading agent health...
      </div>
    );
  }

  if (!health) return null;

  const improvementFactor = repair.validation_score ?? repair.confidence;

  const beforeErrorRate = health.metrics.error_rate;
  const beforeSuccessRate = health.metrics.success_rate;
  const beforeHealthScore = health.health_score;

  const afterErrorRate = beforeErrorRate * (1 - clamp01(improvementFactor));
  const afterSuccessRate = clamp01(beforeSuccessRate + (1 - beforeSuccessRate) * clamp01(improvementFactor));
  const afterHealthScore = clamp01(beforeHealthScore / 100 + (1 - beforeHealthScore / 100) * clamp01(improvementFactor)) * 100;

  const rows = [
    {
      label: "Error Rate",
      before: `${(beforeErrorRate * 100).toFixed(1)}%`,
      after: `${(afterErrorRate * 100).toFixed(1)}%`,
      improved: afterErrorRate < beforeErrorRate,
    },
    {
      label: "Success Rate",
      before: `${(beforeSuccessRate * 100).toFixed(1)}%`,
      after: `${(afterSuccessRate * 100).toFixed(1)}%`,
      improved: afterSuccessRate > beforeSuccessRate,
    },
    {
      label: "Health Score",
      before: beforeHealthScore.toFixed(0),
      after: afterHealthScore.toFixed(0),
      improved: afterHealthScore > beforeHealthScore,
    },
  ];

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="glass-card p-5 rounded-xl"
    >
      <h3 className="flex items-center gap-2 text-sm font-semibold mb-1">
        <TrendingUp className="w-4 h-4 text-success" />
        Before vs. After Impact
      </h3>
      <p className="text-xs text-muted-foreground mb-4">
        Projected from {repair.validation_score != null ? "validation score" : "repair confidence"} (
        {(improvementFactor * 100).toFixed(0)}%) — actual results depend on applying and re-validating the repair.
      </p>

      <div className="space-y-3">
        {rows.map((row) => (
          <div key={row.label} className="flex items-center gap-3">
            <span className="text-xs text-muted-foreground w-28 flex-shrink-0">{row.label}</span>
            <span className="text-sm font-mono text-muted-foreground">{row.before}</span>
            <ArrowRight className="w-3.5 h-3.5 text-muted-foreground/50 flex-shrink-0" />
            <span className={`text-sm font-mono font-semibold ${row.improved ? "text-success" : "text-warning"}`}>
              {row.after}
            </span>
            <div className="flex-1 h-1.5 bg-muted/30 rounded-full overflow-hidden ml-2">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${improvementFactor * 100}%` }}
                transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
                className={`h-full rounded-full ${row.improved ? "bg-success" : "bg-warning"}`}
              />
            </div>
          </div>
        ))}
      </div>
    </motion.div>
  );
}
