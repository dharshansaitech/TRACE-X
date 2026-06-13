"use client";
// frontend/components/dashboard/LiveFailureFeed.tsx
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  Play,
  Zap,
  Stethoscope,
  Wrench,
  ShieldCheck,
  ShieldX,
} from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useEffect, useState } from "react";
import type { IncidentSummary } from "@/types";

interface Props {
  incidents: IncidentSummary[];
}

const LIVE_EVENT_TYPES = [
  "failure_injected",
  "failure_detected",
  "diagnosis_complete",
  "repair_generated",
  "validation_complete",
];

const LIVE_EVENT_META: Record<
  string,
  { label: string; icon: any; iconColor: string; iconBg: string }
> = {
  failure_injected: { label: "Failure injected", icon: Zap, iconColor: "text-danger", iconBg: "bg-danger/15 border-danger/40" },
  failure_detected: { label: "Failure detected", icon: AlertTriangle, iconColor: "text-danger", iconBg: "bg-danger/15 border-danger/40" },
  diagnosis_complete: { label: "Root cause diagnosed", icon: Stethoscope, iconColor: "text-warning", iconBg: "bg-warning/15 border-warning/40" },
  repair_generated: { label: "Repair generated", icon: Wrench, iconColor: "text-tracex-400", iconBg: "bg-tracex-500/15 border-tracex-400/40" },
  validation_complete: { label: "Recovery complete", icon: ShieldCheck, iconColor: "text-success", iconBg: "bg-success/15 border-success/40" },
};

const SEVERITY_META: Record<string, { icon: any; iconColor: string; iconBg: string }> = {
  critical: { icon: AlertTriangle, iconColor: "text-danger", iconBg: "bg-danger/15 border-danger/40" },
  high: { icon: AlertTriangle, iconColor: "text-orange-400", iconBg: "bg-orange-500/15 border-orange-500/40" },
  medium: { icon: AlertTriangle, iconColor: "text-warning", iconBg: "bg-warning/15 border-warning/40" },
  low: { icon: ShieldCheck, iconColor: "text-success", iconBg: "bg-success/15 border-success/40" },
};

export function LiveFailureFeed({ incidents }: Props) {
  const { lastMessage } = useWebSocket();
  const [liveEvents, setLiveEvents] = useState<any[]>([]);

  useEffect(() => {
    if (lastMessage && LIVE_EVENT_TYPES.includes(lastMessage.type ?? "")) {
      setLiveEvents((prev) => [
        {
          id: `${lastMessage.type}-${lastMessage.trace_id ?? lastMessage.repair_id}-${Date.now()}`,
          type: lastMessage.type,
          trace_id: lastMessage.trace_id,
          agent_id: lastMessage.agent_id,
          agent_name: lastMessage.agent_name,
          failure_type: lastMessage.failure_type,
          root_cause: lastMessage.root_cause,
          repair_type: lastMessage.repair_type,
          passed: lastMessage.passed,
          timestamp: new Date().toISOString(),
        },
        ...prev.slice(0, 7),
      ]);
    }
  }, [lastMessage]);

  const allItems = [...liveEvents, ...incidents.slice(0, 8 - liveEvents.length)];

  return (
    <div className="glass-card rounded-xl overflow-hidden">
      <div className="px-4 py-3 border-b border-border/50 flex items-center gap-2">
        <Activity className="w-4 h-4 text-tracex-400" />
        <h2 className="font-semibold text-sm">Live Operations Timeline</h2>
        <div className="ml-auto live-indicator">
          <div className="live-dot" />
        </div>
      </div>

      <div className="px-4 py-3 max-h-80 overflow-y-auto">
        <AnimatePresence initial={false}>
          {allItems.length === 0 ? (
            <div className="py-8 text-center text-muted-foreground text-sm">
              <ShieldCheck className="w-6 h-6 mx-auto mb-2 text-muted-foreground/30" />
              No activity yet — fleet is nominal
            </div>
          ) : (
            allItems.map((item, i) => {
              const isLive = "type" in item && Boolean(item.type) && LIVE_EVENT_META[item.type as string];
              const isLast = i === allItems.length - 1;

              let meta: { label: string; icon: any; iconColor: string; iconBg: string };
              let detail: string;

              if (isLive) {
                meta = { ...LIVE_EVENT_META[item.type as string] };
                if (item.type === "validation_complete" && item.passed === false) {
                  meta = { label: "Validation failed", icon: ShieldX, iconColor: "text-danger", iconBg: "bg-danger/15 border-danger/40" };
                }
                detail =
                  (item.repair_type ?? item.root_cause ?? item.failure_type ?? "")
                    .toString()
                    .replace(/_/g, " ") || (item.agent_name ?? item.agent_id ?? "Unknown agent");
              } else {
                const severity = (item.severity ?? "medium") as string;
                const sevMeta = SEVERITY_META[severity] ?? SEVERITY_META.medium;
                meta = {
                  label: item.title ?? item.failure_type?.replace(/_/g, " ") ?? "Incident",
                  icon: sevMeta.icon,
                  iconColor: sevMeta.iconColor,
                  iconBg: sevMeta.iconBg,
                };
                detail = item.agent_name ?? item.agent_id ?? "Unknown agent";
              }

              const Icon = meta.icon;
              const isNewest = i === 0 && isLive;

              return (
                <motion.div
                  key={item.id ?? item.incident_id}
                  initial={{ opacity: 0, x: 16 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -16 }}
                  transition={{ type: "spring", stiffness: 300, damping: 28 }}
                  className="relative flex gap-3 group"
                >
                  {/* Connector rail */}
                  {!isLast && (
                    <div className="absolute left-[15px] top-8 bottom-0 w-px bg-gradient-to-b from-border/50 to-border/10" />
                  )}

                  {/* Stage node */}
                  <div
                    className={`relative z-10 w-8 h-8 rounded-full border flex items-center justify-center flex-shrink-0 mt-0.5 transition-all duration-300 ${meta.iconBg} ${
                      isNewest ? "pulse-critical" : ""
                    }`}
                  >
                    <Icon className={`w-3.5 h-3.5 ${meta.iconColor}`} />
                  </div>

                  {/* Content */}
                  <div className={`flex-1 min-w-0 pb-4 ${isLast ? "pb-1" : ""}`}>
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="text-sm font-medium truncate">{meta.label}</p>
                        <p className="text-xs text-muted-foreground mt-0.5 truncate">{detail}</p>
                      </div>
                      {item.trace_id && (
                        <Link
                          href={`/replay/${item.trace_id}`}
                          className="p-1 rounded hover:bg-tracex-400/20 text-muted-foreground hover:text-tracex-300 transition-colors flex-shrink-0 opacity-0 group-hover:opacity-100"
                          title="Open Replay Center"
                        >
                          <Play className="w-3 h-3" />
                        </Link>
                      )}
                    </div>
                    <p className="text-[11px] text-muted-foreground/60 mt-1">
                      {item.started_at
                        ? formatDistanceToNow(new Date(item.started_at), { addSuffix: true })
                        : isLive
                        ? "just now"
                        : "—"}
                    </p>
                  </div>
                </motion.div>
              );
            })
          )}
        </AnimatePresence>
      </div>

      <div className="px-4 py-2 border-t border-border/30">
        <Link
          href="/traces?status=failure"
          className="text-xs text-tracex-400 hover:text-tracex-300 transition-colors"
        >
          View all failures →
        </Link>
      </div>
    </div>
  );
}
