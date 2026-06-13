"use client";
// frontend/components/dashboard/IncidentAlertOverlay.tsx
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import {
  AlertOctagon,
  Stethoscope,
  Wrench,
  FlaskConical,
  CheckCircle2,
  XCircle,
  X,
  Play,
} from "lucide-react";
import { useWebSocket } from "@/hooks/useWebSocket";
import { SeverityBadge } from "@/components/shared/SeverityBadge";

type Phase = "detected" | "diagnosing" | "repairing" | "validating" | "recovered" | "failed";

interface AlertState {
  traceId: string;
  agentName: string;
  failureType?: string;
  severity?: string;
  rootCause?: string;
  repairType?: string;
  phase: Phase;
}

const PHASE_META: Record<
  Phase,
  { label: string; icon: any; tone: "critical" | "warning" | "success" | "danger" }
> = {
  detected: { label: "Root Cause Investigation Running", icon: AlertOctagon, tone: "critical" },
  diagnosing: { label: "Root Cause Investigation Running", icon: Stethoscope, tone: "critical" },
  repairing: { label: "Generating Self-Repair", icon: Wrench, tone: "warning" },
  validating: { label: "Validating Repair", icon: FlaskConical, tone: "warning" },
  recovered: { label: "Recovered — Repair Validated", icon: CheckCircle2, tone: "success" },
  failed: { label: "Validation Failed — Manual Review Needed", icon: XCircle, tone: "danger" },
};

const TONE_CLASSES: Record<string, { border: string; bg: string; text: string; iconWrap: string }> = {
  critical: {
    border: "border-danger/40",
    bg: "bg-danger/10",
    text: "text-danger",
    iconWrap: "bg-danger/15 border-danger/40 pulse-critical",
  },
  warning: {
    border: "border-warning/40",
    bg: "bg-warning/10",
    text: "text-warning",
    iconWrap: "bg-warning/15 border-warning/40",
  },
  success: {
    border: "border-success/40",
    bg: "bg-success/10",
    text: "text-success",
    iconWrap: "bg-success/15 border-success/40",
  },
  danger: {
    border: "border-danger/40",
    bg: "bg-danger/10",
    text: "text-danger",
    iconWrap: "bg-danger/15 border-danger/40",
  },
};

function AnimatedEllipsis() {
  const [dots, setDots] = useState(1);
  useEffect(() => {
    const id = setInterval(() => setDots((d) => (d % 3) + 1), 450);
    return () => clearInterval(id);
  }, []);
  return <span className="inline-block w-4 text-left">{".".repeat(dots)}</span>;
}

export function IncidentAlertOverlay() {
  const { lastMessage } = useWebSocket();
  const [alert, setAlert] = useState<AlertState | null>(null);
  const dismissTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!lastMessage?.type) return;
    const { type, trace_id } = lastMessage;
    if (!trace_id) return;

    const clearDismiss = () => {
      if (dismissTimer.current) clearTimeout(dismissTimer.current);
    };

    if (type === "failure_injected") {
      clearDismiss();
      setAlert({
        traceId: trace_id,
        agentName: lastMessage.agent_name ?? "Unknown agent",
        failureType: lastMessage.failure_type,
        phase: "detected",
      });
      return;
    }

    if (type === "failure_detected") {
      clearDismiss();
      setAlert((prev) => ({
        traceId: trace_id,
        agentName: lastMessage.agent_name ?? prev?.agentName ?? "Unknown agent",
        failureType: lastMessage.failure_type ?? prev?.failureType,
        severity: lastMessage.severity,
        phase: "diagnosing",
      }));
      return;
    }

    if (type === "diagnosis_complete") {
      setAlert((prev) =>
        prev
          ? {
              ...prev,
              traceId: trace_id,
              severity: lastMessage.severity ?? prev.severity,
              rootCause: lastMessage.root_cause,
              phase: "repairing",
            }
          : prev
      );
      return;
    }

    if (type === "repair_generated") {
      setAlert((prev) =>
        prev
          ? { ...prev, traceId: trace_id, repairType: lastMessage.repair_type, phase: "validating" }
          : prev
      );
      return;
    }

    if (type === "validation_complete") {
      const passed = lastMessage.passed !== false;
      setAlert((prev) => (prev ? { ...prev, traceId: trace_id, phase: passed ? "recovered" : "failed" } : prev));
      dismissTimer.current = setTimeout(() => setAlert(null), 6_000);
      return;
    }
  }, [lastMessage]);

  return (
    <div className="pointer-events-none fixed inset-x-0 top-0 z-[60] flex justify-center px-4 pt-3 sm:pt-4">
      <AnimatePresence>
        {alert && (
          <motion.div
            key={alert.traceId + alert.phase}
            initial={{ y: -60, opacity: 0, scale: 0.96 }}
            animate={{ y: 0, opacity: 1, scale: 1 }}
            exit={{ y: -40, opacity: 0, scale: 0.98 }}
            transition={{ type: "spring", stiffness: 260, damping: 24 }}
            className={`pointer-events-auto command-card w-full max-w-xl border ${
              TONE_CLASSES[PHASE_META[alert.phase].tone].border
            } ${TONE_CLASSES[PHASE_META[alert.phase].tone].bg}`}
          >
            <div className="flex items-start gap-3 px-4 py-3 sm:px-5 sm:py-4">
              <div
                className={`w-10 h-10 rounded-xl border flex items-center justify-center flex-shrink-0 ${
                  TONE_CLASSES[PHASE_META[alert.phase].tone].iconWrap
                }`}
              >
                {(() => {
                  const Icon = PHASE_META[alert.phase].icon;
                  return <Icon className={`w-5 h-5 ${TONE_CLASSES[PHASE_META[alert.phase].tone].text}`} />;
                })()}
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <p className="text-sm font-semibold">
                    {alert.phase === "recovered" || alert.phase === "failed" ? "INCIDENT RESOLVED" : "INCIDENT DETECTED"}
                  </p>
                  {alert.severity && <SeverityBadge severity={alert.severity} />}
                </div>
                <p className="text-sm font-medium mt-0.5 truncate">
                  {alert.agentName}
                  {alert.failureType && (
                    <span className="text-muted-foreground font-normal">
                      {" "}
                      · {alert.failureType.replace(/_/g, " ")}
                    </span>
                  )}
                </p>

                <AnimatePresence mode="wait">
                  <motion.p
                    key={alert.phase}
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -4 }}
                    className={`text-xs mt-1.5 font-medium ${TONE_CLASSES[PHASE_META[alert.phase].tone].text}`}
                  >
                    {alert.phase === "diagnosing" && (
                      <>
                        Root cause investigation running
                        <AnimatedEllipsis />
                      </>
                    )}
                    {alert.phase === "detected" && (
                      <>
                        Pipeline triggered — analyzing trace
                        <AnimatedEllipsis />
                      </>
                    )}
                    {alert.phase === "repairing" && (
                      <>
                        Root cause: {(alert.rootCause ?? "unknown").replace(/_/g, " ")} — generating fix
                        <AnimatedEllipsis />
                      </>
                    )}
                    {alert.phase === "validating" && (
                      <>
                        Repair ready ({(alert.repairType ?? "").replace(/_/g, " ")}) — running validation tests
                        <AnimatedEllipsis />
                      </>
                    )}
                    {alert.phase === "recovered" && "Repair validated — agent reliability restored"}
                    {alert.phase === "failed" && "Validation failed — repair queued for manual review"}
                  </motion.p>
                </AnimatePresence>
              </div>

              <div className="flex items-center gap-1 flex-shrink-0">
                <Link
                  href={`/replay/${alert.traceId}`}
                  className="p-1.5 rounded-lg hover:bg-surface-elevated/60 text-muted-foreground hover:text-tracex-300 transition-colors"
                  title="Open Replay Center"
                >
                  <Play className="w-3.5 h-3.5" />
                </Link>
                <button
                  onClick={() => setAlert(null)}
                  className="p-1.5 rounded-lg hover:bg-surface-elevated/60 text-muted-foreground transition-colors"
                  title="Dismiss"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>

            {/* Progress bar across the bottom */}
            <div className="h-0.5 bg-border/30 overflow-hidden">
              <motion.div
                initial={{ width: "0%" }}
                animate={{
                  width:
                    alert.phase === "detected"
                      ? "15%"
                      : alert.phase === "diagnosing"
                      ? "40%"
                      : alert.phase === "repairing"
                      ? "65%"
                      : alert.phase === "validating"
                      ? "85%"
                      : "100%",
                }}
                transition={{ duration: 0.6, ease: "easeOut" }}
                className={`h-full ${
                  alert.phase === "recovered"
                    ? "bg-success"
                    : alert.phase === "failed"
                    ? "bg-danger"
                    : "bg-tracex-400"
                }`}
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
