"use client";
// frontend/components/layout/DemoModeBanner.tsx
import { FlaskConical } from "lucide-react";
import { useSystemStatus } from "@/hooks/useAgents";

export function DemoModeBanner() {
  const { data } = useSystemStatus();

  if (!data?.demo_mode) return null;

  return (
    <div className="flex items-center justify-center gap-2 px-4 py-1.5 bg-warning/10 border-b border-warning/20 text-xs text-warning flex-shrink-0">
      <FlaskConical className="w-3.5 h-3.5 shrink-0" />
      <span>
        <strong className="font-semibold">Demo Mode</strong> — running on simulated agents,
        traces, and repairs (no GCP credentials configured). Connect Firestore + Vertex AI for
        live telemetry.
      </span>
    </div>
  );
}
