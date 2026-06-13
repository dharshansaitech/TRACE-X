"use client";
// frontend/components/dashboard/MetricCard.tsx
import { type LucideIcon, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { motion } from "framer-motion";

interface MetricCardProps {
  title: string;
  value: string | number;
  icon: LucideIcon;
  trend?: "up" | "down" | "stable";
  description?: string;
  valueColor?: string;
  onClick?: () => void;
  glow?: boolean;
}

const TrendIcon = {
  up: TrendingUp,
  down: TrendingDown,
  stable: Minus,
};

const TrendColor = {
  up: "text-success",
  down: "text-danger",
  stable: "text-muted-foreground",
};

export function MetricCard({
  title,
  value,
  icon: Icon,
  trend = "stable",
  description,
  valueColor,
  onClick,
  glow = false,
}: MetricCardProps) {
  const Trend = TrendIcon[trend];

  return (
    <motion.div
      whileHover={{ scale: 1.01 }}
      whileTap={{ scale: 0.99 }}
      onClick={onClick}
      className={`glass-card p-4 rounded-xl card-hover ${onClick ? "cursor-pointer" : ""} ${glow ? "pulse-critical" : ""}`}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="w-9 h-9 rounded-lg bg-tracex-500/10 border border-tracex-500/20 flex items-center justify-center">
          <Icon className="w-4 h-4 text-tracex-400" />
        </div>
        <Trend className={`w-4 h-4 ${TrendColor[trend]}`} />
      </div>

      <div className={`text-2xl font-bold mb-0.5 ${valueColor ?? "text-foreground"}`}>
        {value}
      </div>

      <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
        {title}
      </div>

      {description && (
        <p className="text-xs text-muted-foreground/70 mt-1">{description}</p>
      )}
    </motion.div>
  );
}
