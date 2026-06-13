// frontend/app/(dashboard)/traces/page.tsx
"use client";

import { useState } from "react";
import Link from "next/link";
import { useTraces } from "@/hooks/useTraces";
import { SeverityBadge } from "@/components/shared/SeverityBadge";
import { Loader2, Search, Filter, Play, RefreshCw, AlertTriangle } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import type { TracePreview } from "@/types";

const STATUS_STYLES: Record<string, string> = {
  success: "text-success",
  failure: "text-danger",
  running: "text-warning animate-pulse",
  partial: "text-warning",
  unknown: "text-muted-foreground",
};

const FAILURE_COLORS: Record<string, string> = {
  tool_error: "badge-high",
  hallucination: "badge-critical",
  staleness: "badge-medium",
  loop: "badge-high",
  timeout: "badge-medium",
  context_overflow: "badge-medium",
  planning_failure: "badge-high",
  none: "badge-info",
};

export default function TracesPage() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  const { data, isLoading, error, refetch } = useTraces({
    status: statusFilter ?? undefined,
    page,
    page_size: 25,
  });

  const traces = data?.traces ?? [];
  const total = data?.total ?? 0;

  const filtered = search
    ? traces.filter(
        (t: TracePreview) =>
          t.trace_id.includes(search) ||
          t.agent_name.toLowerCase().includes(search.toLowerCase()) ||
          t.failure_type.includes(search)
      )
    : traces;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Trace Explorer</h1>
          <p className="text-muted-foreground text-sm mt-1">
            {total.toLocaleString()} traces recorded
          </p>
        </div>
        <button
          onClick={() => refetch()}
          className="flex items-center gap-2 px-3 py-2 rounded-lg bg-surface-elevated hover:bg-muted transition-colors text-sm"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Filters */}
      <div className="flex gap-3 flex-wrap">
        <div className="relative flex-1 min-w-48">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search traces..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-surface-elevated border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-tracex-500"
          />
        </div>
        {["all", "success", "failure", "running"].map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(s === "all" ? null : s)}
            className={`px-3 py-2 rounded-lg text-sm transition-colors ${
              (statusFilter === null && s === "all") || statusFilter === s
                ? "bg-tracex-500/20 text-tracex-400 border border-tracex-500/50"
                : "bg-surface-elevated border border-border hover:border-tracex-500/30"
            }`}
          >
            {s.charAt(0).toUpperCase() + s.slice(1)}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="glass-card rounded-xl overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border/50">
              {["Trace ID", "Agent", "Status", "Failure Type", "Duration", "Tokens", "Time", "Actions"].map((h) => (
                <th key={h} className="text-left px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={8} className="text-center py-20">
                  <Loader2 className="w-6 h-6 animate-spin text-tracex-400 mx-auto" />
                </td>
              </tr>
            ) : filtered.length === 0 ? (
              <tr>
                <td colSpan={8} className="text-center py-20 text-muted-foreground">
                  No traces found
                </td>
              </tr>
            ) : (
              filtered.map((trace: TracePreview) => (
                <tr
                  key={trace.trace_id}
                  className="border-b border-border/20 hover:bg-surface-elevated/50 transition-colors"
                >
                  <td className="px-4 py-3">
                    <Link
                      href={`/traces/${trace.trace_id}`}
                      className="font-mono text-xs text-tracex-400 hover:text-tracex-300"
                    >
                      {trace.trace_id.slice(0, 8)}...
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-sm font-medium">{trace.agent_name}</td>
                  <td className="px-4 py-3">
                    <span className={`text-sm font-medium ${STATUS_STYLES[trace.status] ?? "text-muted-foreground"}`}>
                      {trace.status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {trace.failure_type !== "none" && (
                      <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${FAILURE_COLORS[trace.failure_type] ?? "badge-info"}`}>
                        {trace.failure_type.replace(/_/g, " ")}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
                    {trace.duration_ms ? `${(trace.duration_ms / 1000).toFixed(2)}s` : "—"}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
                    {trace.total_tokens?.toLocaleString() ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">
                    {formatDistanceToNow(new Date(trace.started_at), { addSuffix: true })}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <Link
                        href={`/traces/${trace.trace_id}`}
                        className="text-xs text-tracex-400 hover:text-tracex-300"
                      >
                        View
                      </Link>
                      {trace.status === "failure" && (
                        <Link
                          href={`/replay/${trace.trace_id}`}
                          className="flex items-center gap-1 text-xs text-warning hover:text-yellow-300"
                        >
                          <Play className="w-3 h-3" />
                          Replay
                        </Link>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>

        {/* Pagination */}
        {total > 25 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-border/50">
            <p className="text-sm text-muted-foreground">
              Showing {(page - 1) * 25 + 1}–{Math.min(page * 25, total)} of {total}
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-3 py-1 rounded text-sm bg-surface-elevated disabled:opacity-50 hover:bg-muted transition-colors"
              >
                Prev
              </button>
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={!data?.has_next}
                className="px-3 py-1 rounded text-sm bg-surface-elevated disabled:opacity-50 hover:bg-muted transition-colors"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
