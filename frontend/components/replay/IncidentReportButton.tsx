"use client";
// frontend/components/replay/IncidentReportButton.tsx
import { useState } from "react";
import { FileText, Loader2, X, Sparkles } from "lucide-react";
import { useIncidentReport } from "@/hooks/useTraces";

interface Props {
  traceId: string;
}

export function IncidentReportButton({ traceId }: Props) {
  const [open, setOpen] = useState(false);
  const { data, isFetching, isFetched, refetch } = useIncidentReport(traceId);

  const handleGenerate = () => {
    setOpen(true);
    refetch();
  };

  return (
    <>
      <div className="glass-card rounded-xl p-4 h-full flex flex-col justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-tracex-400" />
            AI Incident Report
          </h3>
          <p className="text-xs text-muted-foreground mt-1">
            Generate a human-readable postmortem for this trace using Gemini —
            covering the root cause, blast radius, remediation, and recommendations.
          </p>
        </div>
        <button
          onClick={handleGenerate}
          disabled={isFetching}
          className="flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-tracex-500/15 hover:bg-tracex-500/25 border border-tracex-500/30 text-tracex-300 text-sm font-medium transition-colors disabled:opacity-50"
        >
          {isFetching ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />}
          {isFetched ? "Regenerate Report" : "Generate Incident Report"}
        </button>
      </div>

      {open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          onClick={() => setOpen(false)}
        >
          <div
            className="glass-card rounded-xl max-w-2xl w-full max-h-[80vh] overflow-hidden flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="px-4 py-3 border-b border-border/50 flex items-center justify-between flex-shrink-0">
              <h3 className="text-sm font-semibold flex items-center gap-2">
                <FileText className="w-4 h-4 text-tracex-400" />
                Incident Report
              </h3>
              <button
                onClick={() => setOpen(false)}
                className="p-1 rounded hover:bg-surface-elevated/60 transition-colors text-muted-foreground"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-4">
              {isFetching ? (
                <div className="flex flex-col items-center justify-center h-40 gap-2 text-muted-foreground text-sm">
                  <Loader2 className="w-6 h-6 animate-spin text-tracex-400" />
                  Generating report...
                </div>
              ) : (
                <pre className="whitespace-pre-wrap text-xs font-mono leading-relaxed text-foreground/90">
                  {data?.report ?? "No report generated."}
                </pre>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
