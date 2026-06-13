"use client";
// frontend/components/layout/Sidebar.tsx
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Bot,
  Activity,
  Play,
  Wrench,
  FlaskConical,
  Settings,
  ChevronRight,
  Zap,
} from "lucide-react";
import { motion } from "framer-motion";

const navItems = [
  {
    label: "Flight Deck",
    href: "/dashboard",
    icon: LayoutDashboard,
    description: "System overview",
  },
  {
    label: "Agents",
    href: "/agents",
    icon: Bot,
    description: "Agent health",
  },
  {
    label: "Traces",
    href: "/traces",
    icon: Activity,
    description: "Execution traces",
  },
  {
    label: "Replay",
    href: "/replay",
    icon: Play,
    description: "Failure replay",
    disabled: true,
  },
  {
    label: "Repairs",
    href: "/repairs",
    icon: Wrench,
    description: "Auto-generated repairs",
  },
  {
    label: "Simulator",
    href: "/simulator",
    icon: FlaskConical,
    description: "What-If scenarios",
  },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <div className="w-64 flex-shrink-0 bg-card/50 border-r border-border/50 flex flex-col h-full">
      {/* Logo */}
      <div className="p-5 border-b border-border/50">
        <Link href="/dashboard" className="flex items-center gap-3 group">
          <div className="w-8 h-8 rounded-lg bg-tracex-500/20 border border-tracex-500/40 flex items-center justify-center group-hover:glow-primary transition-all">
            <Zap className="w-4 h-4 text-tracex-400" />
          </div>
          <div>
            <span className="font-bold text-lg text-gradient">TRACE-X</span>
            <p className="text-xs text-muted-foreground leading-none">Flight Recorder</p>
          </div>
        </Link>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-3 space-y-0.5 overflow-y-auto">
        {navItems.map((item) => {
          const isActive = pathname.startsWith(item.href) && item.href !== "/replay";
          const Icon = item.icon;

          if (item.disabled) {
            return (
              <div
                key={item.href}
                className="flex items-center gap-3 px-3 py-2 rounded-lg text-muted-foreground/40 cursor-not-allowed"
              >
                <Icon className="w-4 h-4 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium leading-none">{item.label}</div>
                  <div className="text-xs leading-none mt-0.5 opacity-60">Select from trace</div>
                </div>
              </div>
            );
          }

          return (
            <Link
              key={item.href}
              href={item.href}
              className={`relative flex items-center gap-3 px-3 py-2 rounded-lg transition-all group ${
                isActive
                  ? "bg-tracex-500/15 text-tracex-300 border border-tracex-500/30"
                  : "text-muted-foreground hover:text-foreground hover:bg-surface-elevated"
              }`}
            >
              {isActive && (
                <motion.div
                  layoutId="activeNav"
                  className="absolute inset-0 bg-tracex-500/10 rounded-lg"
                  transition={{ type: "spring", duration: 0.3 }}
                />
              )}
              <Icon className={`w-4 h-4 flex-shrink-0 relative z-10 ${isActive ? "text-tracex-400" : ""}`} />
              <div className="flex-1 min-w-0 relative z-10">
                <div className="text-sm font-medium leading-none">{item.label}</div>
                <div className="text-xs leading-none mt-0.5 opacity-60">{item.description}</div>
              </div>
              {isActive && (
                <ChevronRight className="w-3 h-3 text-tracex-500 relative z-10" />
              )}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-border/50">
        <div className="flex items-center gap-2">
          <div className="live-indicator">
            <div className="live-dot" />
            <span className="text-xs text-muted-foreground">Live Monitoring</span>
          </div>
        </div>
        <p className="text-xs text-muted-foreground/50 mt-1">v1.0.0 · Hackathon Demo</p>
      </div>
    </div>
  );
}
