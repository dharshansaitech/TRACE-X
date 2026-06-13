"use client";
// frontend/components/repair/RepairQueue.tsx
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { useRepairs, useApproveRepair, useApplyRepair } from "@/hooks/useTraces";
import { RepairDiffView } from "./RepairDiff";
import { BeforeAfterImpact } from "./BeforeAfterImpact";
import { ConfidenceBar } from "@/components/shared/ConfidenceBar";
import {
  Loader2, CheckCircle2, XCircle, Wrench, AlertTriangle, Clock, Shield,
  GitPullRequest, GitMerge, GitPullRequestClosed, RotateCcw, CircleDot,
} from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import type { RepairArtifact, RepairStatus } from "@/types";

const STATUS_META: Record<RepairStatus, { label: string; icon: any; className: string }> = {
  pending: { label: "Open", icon: GitPullRequest, className: "text-success bg-success/10 border-success/30" },
  approved: { label: "Approved", icon: GitPullRequest, className: "text-tracex-400 bg-tracex-500/10 border-tracex-500/30" },
  applied: { label: "Merged", icon: GitMerge, className: "text-violet-400 bg-violet-500/10 border-violet-500/30" },
  validated: { label: "Merged · Validated", icon: GitMerge, className: "text-violet-400 bg-violet-500/10 border-violet-500/30" },
  rejected: { label: "Closed", icon: GitPullRequestClosed, className: "text-danger bg-danger/10 border-danger/30" },
  rolled_back: { label: "Reverted", icon: RotateCcw, className: "text-warning bg-warning/10 border-warning/30" },
  failed: { label: "Failed", icon: XCircle, className: "text-danger bg-danger/10 border-danger/30" },
};

const RISK_COLORS: Record<string, string> = {
  low: "text-success",
  medium: "text-warning",
  high: "text-danger",
};

export function RepairQueue() {
  const [selectedRepair, setSelectedRepair] = useState<string | null>(null);

  const { data, isLoading } = useRepairs();
  const approveRepair = useApproveRepair();
  const applyRepair = useApplyRepair();

  const repairs: RepairArtifact[] = data?.repairs ?? [];

  // Deep-link support: /repairs?repair=<id> (e.g. from Replay Center "View Repair")
  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const repairId = params.get("repair");
    if (repairId) setSelectedRepair(repairId);
  }, []);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-tracex-400" />
      </div>
    );
  }

  if (repairs.length === 0) {
    return (
      <div className="glass-card p-12 rounded-xl text-center text-muted-foreground">
        <Wrench className="w-12 h-12 mx-auto mb-4 text-muted-foreground/30" />
        <h3 className="text-lg font-medium mb-2">No repairs in queue</h3>
        <p className="text-sm">Repairs are auto-generated when failures are detected and diagnosed.</p>
      </div>
    );
  }

  const activeRepair = repairs.find((r) => r.repair_id === selectedRepair);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
      {/* Repair list */}
      <div className="lg:col-span-2 space-y-2">
        {repairs.map((repair) => {
          const statusMeta = STATUS_META[repair.status] ?? STATUS_META.pending;
          const StatusIcon = statusMeta.icon;
          const checksPassed = repair.tests_total > 0 && repair.tests_passed === repair.tests_total;
          const checksFailed = repair.tests_failed > 0;

          return (
            <motion.div
              key={repair.repair_id}
              layout
              className={`command-card cursor-pointer transition-all ${
                selectedRepair === repair.repair_id
                  ? "border-tracex-500/60 bg-tracex-500/5"
                  : "hover:border-border"
              }`}
              onClick={() => setSelectedRepair(repair.repair_id)}
            >
              <div className="p-4">
                {/* PR-style header */}
                <div className="flex items-start gap-2 mb-2">
                  <div className={`flex items-center gap-1 px-2 py-0.5 rounded-full border text-[11px] font-medium flex-shrink-0 ${statusMeta.className}`}>
                    <StatusIcon className="w-3 h-3" />
                    {statusMeta.label}
                  </div>
                  <span className="text-xs text-muted-foreground font-mono truncate">
                    #{repair.repair_id.slice(0, 8)}
                  </span>
                </div>

                <p className="text-sm font-semibold leading-snug mb-1">{repair.title}</p>
                <p className="text-xs text-muted-foreground truncate mb-2">
                  {repair.repair_type.replace(/_/g, " ")} · agent <span className="font-mono">{repair.agent_id}</span>
                </p>

                <div className="flex items-center gap-3 text-xs text-muted-foreground mb-2">
                  <span className={RISK_COLORS[repair.risk_level] ?? "text-muted-foreground"}>
                    <Shield className="w-3 h-3 inline mr-0.5 -mt-0.5" />
                    {repair.risk_level} risk
                  </span>
                  <span>
                    <Clock className="w-3 h-3 inline mr-0.5 -mt-0.5" />
                    opened {formatDistanceToNow(new Date(repair.created_at), { addSuffix: true })}
                  </span>
                </div>

                {/* CI-style checks */}
                {repair.tests_total > 0 && (
                  <div className="flex items-center gap-1.5 text-xs mb-2">
                    {checksFailed ? (
                      <XCircle className="w-3.5 h-3.5 text-danger" />
                    ) : checksPassed ? (
                      <CheckCircle2 className="w-3.5 h-3.5 text-success" />
                    ) : (
                      <CircleDot className="w-3.5 h-3.5 text-warning" />
                    )}
                    <span className={checksFailed ? "text-danger" : checksPassed ? "text-success" : "text-warning"}>
                      {repair.tests_passed}/{repair.tests_total} checks passed
                    </span>
                  </div>
                )}

                <ConfidenceBar value={repair.confidence} small showLabel />

                {/* Actions */}
                {repair.status === "pending" && (
                  <div className="flex gap-2 mt-3">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        approveRepair.mutate({ repairId: repair.repair_id, approvedBy: "demo-user" });
                      }}
                      disabled={approveRepair.isPending}
                      className="flex-1 flex items-center justify-center gap-1 py-1.5 rounded-lg text-xs font-medium bg-success/10 text-success border border-success/30 hover:bg-success/20 transition-colors disabled:opacity-50"
                    >
                      <CheckCircle2 className="w-3 h-3" />
                      Approve
                    </button>
                    <button
                      onClick={(e) => e.stopPropagation()}
                      className="px-2 py-1.5 rounded-lg text-xs bg-danger/10 text-danger border border-danger/30 hover:bg-danger/20 transition-colors"
                    >
                      <XCircle className="w-3 h-3" />
                    </button>
                  </div>
                )}

                {repair.status === "approved" && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      applyRepair.mutate({ repairId: repair.repair_id, appliedBy: "demo-user" });
                    }}
                    disabled={applyRepair.isPending}
                    className="w-full mt-3 flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-xs font-medium bg-violet-500/15 text-violet-300 border border-violet-500/30 hover:bg-violet-500/25 transition-colors disabled:opacity-50"
                  >
                    <GitMerge className="w-3.5 h-3.5" />
                    Merge Repair
                  </button>
                )}
              </div>
            </motion.div>
          );
        })}
      </div>

      {/* Repair detail */}
      <div className="lg:col-span-3 space-y-4">
        {activeRepair ? (
          <>
            <div className="command-card p-5">
              <div className="flex items-center gap-2 mb-1">
                {(() => {
                  const meta = STATUS_META[activeRepair.status] ?? STATUS_META.pending;
                  const Icon = meta.icon;
                  return (
                    <div className={`flex items-center gap-1 px-2 py-0.5 rounded-full border text-[11px] font-medium ${meta.className}`}>
                      <Icon className="w-3 h-3" />
                      {meta.label}
                    </div>
                  );
                })()}
                <span className="text-xs text-muted-foreground font-mono">#{activeRepair.repair_id.slice(0, 8)}</span>
              </div>
              <h2 className="font-semibold text-lg mb-1">{activeRepair.title}</h2>
              <p className="text-sm text-muted-foreground mb-4">{activeRepair.description}</p>

              <div className="grid grid-cols-2 gap-3 mb-4">
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Confidence</p>
                  <ConfidenceBar value={activeRepair.confidence} showLabel />
                </div>
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Tests</p>
                  <p className="text-sm">
                    <span className="text-success">{activeRepair.tests_passed}</span>
                    /{activeRepair.tests_total} passed
                  </p>
                </div>
              </div>

              <div className="p-3 bg-muted/20 rounded-lg text-sm">
                <p className="text-xs font-medium text-muted-foreground mb-1">RATIONALE</p>
                <p>{activeRepair.rationale}</p>
              </div>

              {activeRepair.side_effects?.length > 0 && (
                <div className="mt-3 p-3 bg-warning/5 border border-warning/20 rounded-lg">
                  <p className="text-xs font-medium text-warning mb-1 flex items-center gap-1">
                    <AlertTriangle className="w-3 h-3" /> SIDE EFFECTS
                  </p>
                  <ul className="text-xs space-y-0.5">
                    {activeRepair.side_effects.map((se: string, i: number) => (
                      <li key={i}>{se}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            {/* Before vs After impact */}
            <BeforeAfterImpact agentId={activeRepair.agent_id} repair={activeRepair} />

            {/* Diff */}
            <RepairDiffView diff={activeRepair.diff} />
          </>
        ) : (
          <div className="glass-card p-12 rounded-xl text-center text-muted-foreground">
            <Wrench className="w-8 h-8 mx-auto mb-3 text-muted-foreground/30" />
            <p>Select a repair to view details and diff</p>
          </div>
        )}
      </div>
    </div>
  );
}
