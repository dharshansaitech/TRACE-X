"use client";
// frontend/components/dashboard/FleetReliabilityHero.tsx
import { useEffect, useRef, useState } from "react";
import { motion, useMotionValue, useTransform, animate } from "framer-motion";
import { ShieldCheck, ShieldAlert, ShieldX, Radar } from "lucide-react";

interface Props {
  score: number; // 0-100
  totalAgents: number;
  healthyAgents: number;
  degradedAgents: number;
  criticalAgents: number;
  openIncidents: number;
  mttrMinutes?: number;
}

type Tier = "healthy" | "degraded" | "critical";

function tierFor(score: number): Tier {
  if (score >= 95) return "healthy";
  if (score >= 85) return "degraded";
  return "critical";
}

const TIER_META: Record<
  Tier,
  { label: string; text: string; ring: string; icon: any; flash: string }
> = {
  healthy: {
    label: "All Systems Nominal",
    text: "text-hero-gradient-success",
    ring: "hero-ring-glow-success",
    icon: ShieldCheck,
    flash: "score-flash-up",
  },
  degraded: {
    label: "Degraded — Self-Healing Active",
    text: "text-hero-gradient-warning",
    ring: "hero-ring-glow-warning",
    icon: ShieldAlert,
    flash: "score-flash-down",
  },
  critical: {
    label: "Critical — Investigating",
    text: "text-hero-gradient-danger",
    ring: "hero-ring-glow-danger",
    icon: ShieldX,
    flash: "score-flash-down",
  },
};

export function FleetReliabilityHero({
  score,
  totalAgents,
  healthyAgents,
  degradedAgents,
  criticalAgents,
  openIncidents,
  mttrMinutes,
}: Props) {
  const tier = tierFor(score);
  const meta = TIER_META[tier];
  const Icon = meta.icon;

  const motionScore = useMotionValue(score);
  const display = useTransform(motionScore, (v) => v.toFixed(1));
  const prevScore = useRef(score);
  const [flash, setFlash] = useState<string | null>(null);

  useEffect(() => {
    const from = prevScore.current;
    const controls = animate(motionScore, score, {
      duration: 1.4,
      ease: [0.16, 1, 0.3, 1],
    });

    if (Math.abs(score - from) >= 0.05) {
      const flashClass = score < from ? "score-flash-down" : "score-flash-up";
      setFlash(flashClass);
      const t = setTimeout(() => setFlash(null), 1300);
      prevScore.current = score;
      return () => {
        controls.stop();
        clearTimeout(t);
      };
    }

    prevScore.current = score;
    return () => controls.stop();
  }, [score]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className={`command-card overflow-hidden ${flash ?? ""}`}>
      {/* Ambient glow */}
      <div className={`absolute inset-0 ${meta.ring} pointer-events-none`} />

      <div className="relative px-6 py-7 sm:px-10 sm:py-9 flex flex-col lg:flex-row lg:items-center gap-6 lg:gap-10">
        {/* Score */}
        <div className="flex items-center gap-5 sm:gap-7">
          <div className="relative flex-shrink-0">
            <div
              className={`w-16 h-16 sm:w-20 sm:h-20 rounded-2xl border flex items-center justify-center ${
                tier === "healthy"
                  ? "border-success/30 bg-success/10"
                  : tier === "degraded"
                  ? "border-warning/30 bg-warning/10"
                  : "border-danger/30 bg-danger/10 pulse-critical"
              }`}
            >
              <Icon
                className={`w-8 h-8 sm:w-10 sm:h-10 ${
                  tier === "healthy"
                    ? "text-success"
                    : tier === "degraded"
                    ? "text-warning"
                    : "text-danger"
                }`}
              />
            </div>
          </div>

          <div>
            <p className="story-label mb-1">
              <Radar className="w-3 h-3" />
              AI Fleet Reliability
            </p>
            <div className="flex items-baseline gap-2">
              <motion.span
                className={`font-display text-6xl sm:text-7xl font-bold tracking-tight tabular-nums ${meta.text}`}
              >
                {display}
              </motion.span>
              <span className="text-2xl sm:text-3xl font-semibold text-muted-foreground">%</span>
            </div>
            <p
              className={`text-sm font-medium mt-1 ${
                tier === "healthy" ? "text-success" : tier === "degraded" ? "text-warning" : "text-danger"
              }`}
            >
              {meta.label}
            </p>
          </div>
        </div>

        {/* Divider */}
        <div className="hidden lg:block w-px self-stretch bg-border/40" />

        {/* Fleet breakdown */}
        <div className="flex-1 grid grid-cols-2 sm:grid-cols-4 gap-4 sm:gap-6">
          <Stat label="Agents Online" value={totalAgents} accent="text-foreground" />
          <Stat
            label="Healthy"
            value={healthyAgents}
            accent="text-success"
            dot="bg-success"
          />
          <Stat
            label="Degraded"
            value={degradedAgents}
            accent={degradedAgents > 0 ? "text-warning" : "text-muted-foreground"}
            dot={degradedAgents > 0 ? "bg-warning" : undefined}
          />
          <Stat
            label="Critical"
            value={criticalAgents}
            accent={criticalAgents > 0 ? "text-danger" : "text-muted-foreground"}
            dot={criticalAgents > 0 ? "bg-danger animate-pulse" : undefined}
          />
        </div>

        {/* Live status pill */}
        <div className="flex flex-col items-start lg:items-end gap-2 flex-shrink-0">
          <div className="live-indicator text-xs text-muted-foreground">
            <div className="live-dot" />
            Live · auto-healing pipeline armed
          </div>
          {openIncidents > 0 ? (
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-danger/10 border border-danger/30 text-danger text-xs font-medium">
              <span className="w-1.5 h-1.5 rounded-full bg-danger animate-pulse" />
              {openIncidents} open incident{openIncidents === 1 ? "" : "s"}
            </div>
          ) : (
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-success/10 border border-success/30 text-success text-xs font-medium">
              <span className="w-1.5 h-1.5 rounded-full bg-success" />
              No open incidents
            </div>
          )}
          {mttrMinutes != null && (
            <p className="text-xs text-muted-foreground">
              MTTR: <span className="text-foreground font-mono">{mttrMinutes.toFixed(1)}m</span>
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  accent,
  dot,
}: {
  label: string;
  value: number;
  accent: string;
  dot?: string;
}) {
  return (
    <div>
      <div className="flex items-center gap-1.5">
        {dot && <span className={`w-1.5 h-1.5 rounded-full ${dot}`} />}
        <span className={`text-xl sm:text-2xl font-bold tabular-nums ${accent}`}>{value}</span>
      </div>
      <p className="text-xs text-muted-foreground uppercase tracking-wider mt-0.5">{label}</p>
    </div>
  );
}
