"use client";
// frontend/components/dashboard/InjectFailureButton.tsx
import { useState, useRef, useEffect } from "react";
import { Zap, ChevronDown, Loader2, CheckCircle2 } from "lucide-react";
import { useInjectFailure } from "@/hooks/useTraces";

const FAILURE_TYPES: { value: string; label: string }[] = [
  { value: "", label: "Random failure" },
  { value: "tool_error", label: "Tool error" },
  { value: "hallucination", label: "Hallucination" },
  { value: "staleness", label: "Stale data" },
  { value: "loop", label: "Infinite loop" },
  { value: "timeout", label: "Timeout" },
  { value: "context_overflow", label: "Context overflow" },
  { value: "safety_violation", label: "Safety violation" },
  { value: "planning_failure", label: "Planning failure" },
  { value: "retrieval_failure", label: "Retrieval failure" },
];

export function InjectFailureButton() {
  const [open, setOpen] = useState(false);
  const [lastResult, setLastResult] = useState<string | null>(null);
  const ref = useRef<HTMLDivElement>(null);
  const inject = useInjectFailure();

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  const handleInject = (failureType: string) => {
    setOpen(false);
    setLastResult(null);
    inject.mutate(
      failureType ? { failure_type: failureType } : undefined,
      {
        onSuccess: (data) => {
          setLastResult(`${data.agent_name} · ${data.failure_type.replace(/_/g, " ")}`);
          setTimeout(() => setLastResult(null), 6000);
        },
      }
    );
  };

  return (
    <div ref={ref} className="relative flex items-center gap-2">
      {lastResult && !inject.isPending && (
        <div className="hidden sm:flex items-center gap-1.5 text-xs text-success">
          <CheckCircle2 className="w-3.5 h-3.5" />
          Injected: {lastResult}
        </div>
      )}
      <div className="flex">
        <button
          onClick={() => handleInject("")}
          disabled={inject.isPending}
          className="flex items-center gap-2 px-3 py-2 rounded-l-lg bg-danger/10 hover:bg-danger/20 border border-danger/30 text-danger text-sm font-medium transition-colors disabled:opacity-50"
          title="Inject a random live failure into the pipeline"
        >
          {inject.isPending ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Zap className="w-4 h-4" />
          )}
          Inject Failure
        </button>
        <button
          onClick={() => setOpen((o) => !o)}
          disabled={inject.isPending}
          className="px-2 py-2 rounded-r-lg bg-danger/10 hover:bg-danger/20 border border-l-0 border-danger/30 text-danger transition-colors disabled:opacity-50"
          title="Choose failure type"
        >
          <ChevronDown className="w-3.5 h-3.5" />
        </button>
      </div>

      {open && (
        <div className="absolute top-full right-0 mt-1 w-52 glass-card rounded-lg overflow-hidden z-20 shadow-xl">
          {FAILURE_TYPES.map((ft) => (
            <button
              key={ft.value}
              onClick={() => handleInject(ft.value)}
              className="w-full text-left px-3 py-2 text-xs hover:bg-surface-elevated/60 transition-colors"
            >
              {ft.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
