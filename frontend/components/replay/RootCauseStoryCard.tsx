"use client";
// frontend/components/replay/RootCauseStoryCard.tsx
import { motion } from "framer-motion";
import { Sparkles, Search, Activity, Target, Wrench, Loader2 } from "lucide-react";
import { useTraceDiagnosis } from "@/hooks/useTraces";
import { SeverityBadge } from "@/components/shared/SeverityBadge";
import { ConfidenceBar } from "@/components/shared/ConfidenceBar";

interface Props {
  traceId: string;
}

export function RootCauseStoryCard({ traceId }: Props) {
  const { data: diagnosis, isLoading, error } = useTraceDiagnosis(traceId);

  if (isLoading) {
    return (
      <div className="command-card p-5 flex items-center justify-center gap-2 text-muted-foreground text-sm">
        <Loader2 className="w-4 h-4 animate-spin" />
        Loading diagnosis...
      </div>
    );
  }

  if (error || !diagnosis) {
    return null;
  }

  const recommendedFixes = [
    ...(diagnosis.immediate_actions ?? []),
    ...(diagnosis.long_term_recommendations ?? []),
  ];

  const blast = diagnosis.blast_radius;
  const impactItems: { label: string; value: string }[] = [];
  if (blast) {
    if (blast.affected_agents?.length) {
      impactItems.push({ label: "Agents affected", value: String(blast.affected_agents.length) });
    }
    if (blast.affected_sessions?.length) {
      impactItems.push({ label: "Sessions affected", value: String(blast.affected_sessions.length) });
    }
    if (blast.affected_users_estimate) {
      impactItems.push({ label: "Users impacted (est.)", value: String(blast.affected_users_estimate) });
    }
    if (blast.financial_impact_estimate) {
      impactItems.push({ label: "Financial impact (est.)", value: blast.financial_impact_estimate });
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
      className="command-card p-5 sm:p-6"
    >
      <div className="flex items-center justify-between flex-wrap gap-2 mb-4">
        <p className="story-label">
          <Sparkles className="w-3 h-3" />
          TRACE-X DISCOVERY
        </p>
        <div className="flex items-center gap-2">
          <SeverityBadge severity={diagnosis.severity} />
          <span className="text-xs text-muted-foreground font-mono">
            via {diagnosis.model_used ?? "Gemini"}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 lg:gap-8">
        {/* Left: root cause + evidence */}
        <div className="space-y-4">
          <div>
            <h3 className="flex items-center gap-2 text-sm font-semibold text-foreground mb-1.5">
              <Search className="w-4 h-4 text-tracex-400" />
              Root Cause
            </h3>
            <p className="text-xs uppercase tracking-wider text-tracex-400 font-medium mb-1">
              {diagnosis.root_cause_category?.replace(/_/g, " ")}
            </p>
            <p className="text-sm text-foreground/90 leading-relaxed">
              {diagnosis.root_cause_description}
            </p>
          </div>

          <div>
            <h3 className="flex items-center gap-2 text-sm font-semibold text-foreground mb-1.5">
              <Activity className="w-4 h-4 text-tracex-400" />
              Evidence
            </h3>
            <p className="text-sm text-muted-foreground leading-relaxed">{diagnosis.evidence_summary}</p>
            <div className="mt-3">
              <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
                <span>Diagnosis confidence</span>
                <span className="font-mono text-foreground">{(diagnosis.confidence * 100).toFixed(0)}%</span>
              </div>
              <ConfidenceBar value={diagnosis.confidence} />
            </div>
          </div>
        </div>

        {/* Right: impact + recommended fix */}
        <div className="space-y-4">
          {impactItems.length > 0 && (
            <div>
              <h3 className="flex items-center gap-2 text-sm font-semibold text-foreground mb-2">
                <Target className="w-4 h-4 text-warning" />
                Impact
              </h3>
              <div className="grid grid-cols-2 gap-3">
                {impactItems.map((item) => (
                  <div key={item.label} className="rounded-lg border border-border/40 bg-surface-elevated/30 px-3 py-2">
                    <p className="text-base font-bold text-foreground">{item.value}</p>
                    <p className="text-[11px] text-muted-foreground uppercase tracking-wide mt-0.5">{item.label}</p>
                  </div>
                ))}
              </div>
              {blast?.containment_possible === false && (
                <p className="text-xs text-danger mt-2">⚠ Containment not currently possible — escalation recommended</p>
              )}
            </div>
          )}

          {recommendedFixes.length > 0 && (
            <div>
              <h3 className="flex items-center gap-2 text-sm font-semibold text-foreground mb-2">
                <Wrench className="w-4 h-4 text-success" />
                Recommended Fix
              </h3>
              <ul className="space-y-1.5">
                {recommendedFixes.slice(0, 4).map((action, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-foreground/90">
                    <span className="w-1.5 h-1.5 rounded-full bg-success mt-1.5 flex-shrink-0" />
                    {action}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
}
