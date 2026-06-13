"use client";
// frontend/components/dashboard/FlightDeck.tsx
import { useDashboardOverview } from "@/hooks/useAgents";
import { MetricCard } from "./MetricCard";
import { AgentHealthGrid } from "./AgentHealthGrid";
import { LiveFailureFeed } from "./LiveFailureFeed";
import { InjectFailureButton } from "./InjectFailureButton";
import { FleetReliabilityHero } from "./FleetReliabilityHero";
import { SelfHealingPipeline } from "./SelfHealingPipeline";
import { Loader2, Activity, AlertTriangle, CheckCircle2, Wrench, Bot } from "lucide-react";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { format } from "date-fns";

export function FlightDeck() {
  const { data: overview, isLoading } = useDashboardOverview();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-tracex-400" />
      </div>
    );
  }

  const sys = overview?.system;
  const tracesPerHour = (sys?.traces_per_hour ?? []).map((p: any) => ({
    time: format(new Date(p.timestamp), "HH:mm"),
    traces: p.value,
  }));
  const errorTrend = (sys?.error_rate_trend ?? []).map((p: any) => ({
    time: format(new Date(p.timestamp), "HH:mm"),
    errorRate: p.value,
  }));

  return (
    <div className="space-y-6">
      {/* Title */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Flight Deck</h1>
          <p className="text-muted-foreground text-sm mt-0.5">
            Real-time overview of all AI agent operations
          </p>
        </div>
        <InjectFailureButton />
      </div>

      {/* Fleet Reliability Hero */}
      <FleetReliabilityHero
        score={(sys?.success_rate_24h ?? 0) * 100}
        totalAgents={sys?.total_agents ?? 0}
        healthyAgents={sys?.healthy_agents ?? 0}
        degradedAgents={sys?.degraded_agents ?? 0}
        criticalAgents={sys?.critical_agents ?? 0}
        openIncidents={sys?.open_incidents ?? 0}
      />

      {/* Self-Healing Pipeline */}
      <SelfHealingPipeline />

      {/* Metrics Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4">
        <MetricCard
          title="Total Agents"
          value={sys?.total_agents ?? 0}
          icon={Bot}
          trend="stable"
          description={`${sys?.healthy_agents ?? 0} healthy`}
        />
        <MetricCard
          title="Traces (24h)"
          value={(sys?.total_traces_24h ?? 0).toLocaleString()}
          icon={Activity}
          trend="up"
          description="Total executions"
        />
        <MetricCard
          title="Success Rate"
          value={`${((sys?.success_rate_24h ?? 0) * 100).toFixed(1)}%`}
          icon={CheckCircle2}
          trend={sys?.success_rate_24h && sys.success_rate_24h > 0.95 ? "up" : "down"}
          valueColor={sys?.success_rate_24h && sys.success_rate_24h > 0.95 ? "text-success" : "text-warning"}
          description="24h success rate"
        />
        <MetricCard
          title="Open Incidents"
          value={sys?.open_incidents ?? 0}
          icon={AlertTriangle}
          trend={sys?.open_incidents && sys.open_incidents > 0 ? "down" : "stable"}
          valueColor={sys?.open_incidents && sys.open_incidents > 0 ? "text-danger" : "text-success"}
          description="Requires attention"
          glow={!!sys?.open_incidents && sys.open_incidents > 0}
        />
        <MetricCard
          title="Pending Repairs"
          value={sys?.pending_repairs ?? 0}
          icon={Wrench}
          trend="stable"
          description="Awaiting approval"
          valueColor={sys?.pending_repairs && sys.pending_repairs > 0 ? "text-warning" : "text-success"}
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Traces per hour */}
        <div className="glass-card p-5 rounded-xl">
          <h2 className="font-semibold mb-4 text-sm text-muted-foreground uppercase tracking-wider">
            Traces / Hour (24h)
          </h2>
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart data={tracesPerHour}>
              <defs>
                <linearGradient id="tracesGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#0ea5e9" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#0ea5e9" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
              <XAxis dataKey="time" tick={{ fontSize: 10, fill: "#6b7280" }} interval={4} />
              <YAxis tick={{ fontSize: 10, fill: "#6b7280" }} />
              <Tooltip
                contentStyle={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: "8px", fontSize: "12px" }}
              />
              <Area type="monotone" dataKey="traces" stroke="#0ea5e9" fill="url(#tracesGradient)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Error rate trend */}
        <div className="glass-card p-5 rounded-xl">
          <h2 className="font-semibold mb-4 text-sm text-muted-foreground uppercase tracking-wider">
            Error Rate % (24h)
          </h2>
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart data={errorTrend}>
              <defs>
                <linearGradient id="errorGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
              <XAxis dataKey="time" tick={{ fontSize: 10, fill: "#6b7280" }} interval={4} />
              <YAxis tick={{ fontSize: 10, fill: "#6b7280" }} tickFormatter={(v) => `${v.toFixed(1)}%`} />
              <Tooltip
                contentStyle={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: "8px", fontSize: "12px" }}
                formatter={(v: number) => [`${v.toFixed(2)}%`, "Error Rate"]}
              />
              <Area type="monotone" dataKey="errorRate" stroke="#ef4444" fill="url(#errorGradient)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Bottom Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2">
          <AgentHealthGrid agents={overview?.agent_health ?? []} compact />
        </div>
        <div>
          <LiveFailureFeed incidents={overview?.recent_incidents ?? []} />
        </div>
      </div>
    </div>
  );
}
