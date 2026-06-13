"use client";
// frontend/components/dashboard/SelfHealingPipeline.tsx
import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Radar,
  Stethoscope,
  Wrench,
  FlaskConical,
  Sparkles,
  Loader2,
  Check,
  X,
} from "lucide-react";
import { useWebSocket } from "@/hooks/useWebSocket";

type StageStatus = "idle" | "active" | "done" | "failed";

interface StageDef {
  key: string;
  label: string;
  icon: any;
}

const STAGES: StageDef[] = [
  { key: "detect", label: "Detect", icon: Radar },
  { key: "diagnose", label: "Diagnose", icon: Stethoscope },
  { key: "repair", label: "Repair", icon: Wrench },
  { key: "validate", label: "Validate", icon: FlaskConical },
  { key: "recover", label: "Recover", icon: Sparkles },
];

interface PipelineState {
  traceId: string | null;
  stages: StageStatus[];
  agentName?: string;
  failureType?: string;
  rootCause?: string;
  repairType?: string;
  passed?: boolean;
  startedAt?: number;
}

const IDLE_STATE: PipelineState = {
  traceId: null,
  stages: ["idle", "idle", "idle", "idle", "idle"],
};

export function SelfHealingPipeline() {
  const { lastMessage } = useWebSocket();
  const [state, setState] = useState<PipelineState>(IDLE_STATE);
  const resetTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!lastMessage?.type) return;
    const { type } = lastMessage;

    if (type === "failure_injected") {
      if (resetTimer.current) clearTimeout(resetTimer.current);
      setState({
        traceId: lastMessage.trace_id,
        stages: ["active", "idle", "idle", "idle", "idle"],
        agentName: lastMessage.agent_name,
        failureType: lastMessage.failure_type,
        startedAt: Date.now(),
      });
      return;
    }

    if (type === "failure_detected") {
      setState((prev) => ({
        traceId: lastMessage.trace_id,
        stages: ["done", "active", "idle", "idle", "idle"],
        agentName: lastMessage.agent_name ?? prev.agentName,
        failureType: lastMessage.failure_type ?? prev.failureType,
        startedAt: prev.startedAt ?? Date.now(),
      }));
      return;
    }

    if (type === "diagnosis_complete") {
      setState((prev) => ({
        ...prev,
        traceId: lastMessage.trace_id,
        stages: ["done", "done", "active", "idle", "idle"],
        rootCause: lastMessage.root_cause,
        startedAt: prev.startedAt ?? Date.now(),
      }));
      return;
    }

    if (type === "repair_generated") {
      setState((prev) => ({
        ...prev,
        traceId: lastMessage.trace_id,
        stages: ["done", "done", "done", "active", "idle"],
        repairType: lastMessage.repair_type,
        startedAt: prev.startedAt ?? Date.now(),
      }));
      return;
    }

    if (type === "validation_complete") {
      const passed = lastMessage.passed !== false;
      setState((prev) => ({
        ...prev,
        traceId: lastMessage.trace_id,
        stages: ["done", "done", "done", "done", passed ? "done" : "failed"],
        passed,
        startedAt: prev.startedAt ?? Date.now(),
      }));

      // Auto-return to idle after the recovery moment has been shown
      if (resetTimer.current) clearTimeout(resetTimer.current);
      resetTimer.current = setTimeout(() => setState(IDLE_STATE), 12_000);
      return;
    }
  }, [lastMessage]);

  const isIdle = state.traceId === null;
  const elapsed = state.startedAt ? ((Date.now() - state.startedAt) / 1000).toFixed(1) : null;

  return (
    <div className={`glass-card rounded-xl p-5 ${isIdle ? "fade-healthy" : ""}`}>
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="font-semibold text-sm flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-tracex-400" />
            Self-Healing Pipeline
          </h2>
          <AnimatePresence mode="wait">
            {isIdle ? (
              <motion.p
                key="idle"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="text-xs text-muted-foreground mt-0.5"
              >
                Standing by — waiting for the next failure signal
              </motion.p>
            ) : (
              <motion.p
                key={state.traceId}
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="text-xs text-muted-foreground mt-0.5"
              >
                {state.agentName ?? "Agent"} ·{" "}
                {(state.repairType ?? state.rootCause ?? state.failureType ?? "")
                  .toString()
                  .replace(/_/g, " ") || "analyzing"}
              </motion.p>
            )}
          </AnimatePresence>
        </div>
        {elapsed && !isIdle && (
          <span className="text-xs font-mono text-tracex-400">{elapsed}s</span>
        )}
      </div>

      <div className="flex items-center">
        {STAGES.map((stage, i) => {
          const status = state.stages[i];
          const Icon = stage.icon;
          const isLast = i === STAGES.length - 1;
          const nextActive = state.stages[i + 1] && state.stages[i + 1] !== "idle";

          return (
            <div key={stage.key} className="flex items-center flex-1 last:flex-initial">
              <div className="flex flex-col items-center gap-2">
                <div
                  className={`pipeline-node w-11 h-11 ${
                    status === "active"
                      ? "pipeline-node-active"
                      : status === "done"
                      ? "pipeline-node-done"
                      : status === "failed"
                      ? "pipeline-node-failed"
                      : "pipeline-node-idle"
                  }`}
                >
                  <AnimatePresence mode="wait" initial={false}>
                    {status === "active" ? (
                      <motion.span
                        key="active"
                        initial={{ scale: 0.5, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        exit={{ scale: 0.5, opacity: 0 }}
                      >
                        <Loader2 className="w-5 h-5 animate-spin" />
                      </motion.span>
                    ) : status === "done" ? (
                      <motion.span
                        key="done"
                        initial={{ scale: 0.5, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        exit={{ scale: 0.5, opacity: 0 }}
                      >
                        <Check className="w-5 h-5" />
                      </motion.span>
                    ) : status === "failed" ? (
                      <motion.span
                        key="failed"
                        initial={{ scale: 0.5, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        exit={{ scale: 0.5, opacity: 0 }}
                      >
                        <X className="w-5 h-5" />
                      </motion.span>
                    ) : (
                      <motion.span
                        key="idle"
                        initial={{ scale: 0.5, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        exit={{ scale: 0.5, opacity: 0 }}
                      >
                        <Icon className="w-5 h-5" />
                      </motion.span>
                    )}
                  </AnimatePresence>
                </div>
                <span
                  className={`text-xs font-medium tracking-wide ${
                    status === "idle" ? "text-muted-foreground" : "text-foreground"
                  }`}
                >
                  {stage.label}
                </span>
              </div>

              {!isLast && (
                <div className="pipeline-connector mx-2 sm:mx-3 mb-5">
                  <div
                    className="pipeline-connector-fill"
                    style={{ width: nextActive || status === "done" ? "100%" : "0%" }}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
