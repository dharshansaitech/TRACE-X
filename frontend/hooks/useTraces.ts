"use client";
// frontend/hooks/useTraces.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";

// ── Query keys ────────────────────────────────────────────────────────────────
export const traceKeys = {
  all: ["traces"] as const,
  lists: () => [...traceKeys.all, "list"] as const,
  list: (filters: any) => [...traceKeys.lists(), filters] as const,
  detail: (id: string) => [...traceKeys.all, "detail", id] as const,
  diagnosis: (traceId: string) => ["diagnoses", traceId] as const,
  replay: (traceId: string) => ["replay", traceId] as const,
  repairs: (filters?: any) => ["repairs", filters] as const,
  simulation: (id: string) => ["simulation", id] as const,
};

// ── Traces ────────────────────────────────────────────────────────────────────

export function useTraces(filters?: {
  agent_id?: string;
  status?: string;
  failure_type?: string;
  page?: number;
  page_size?: number;
}) {
  return useQuery({
    queryKey: traceKeys.list(filters ?? {}),
    queryFn: () => api.traces.list(filters),
    refetchInterval: 15_000,
  });
}

export function useTrace(traceId: string) {
  return useQuery({
    queryKey: traceKeys.detail(traceId),
    queryFn: () => api.traces.get(traceId),
    enabled: !!traceId,
  });
}

export function useTraceDiagnosis(traceId: string) {
  return useQuery({
    queryKey: traceKeys.diagnosis(traceId),
    queryFn: () => api.diagnoses.get(traceId),
    enabled: !!traceId,
    retry: 1,
  });
}

export function useReplay(traceId: string) {
  return useQuery({
    queryKey: traceKeys.replay(traceId),
    queryFn: () => api.replay.get(traceId),
    enabled: !!traceId,
    staleTime: 60_000,
  });
}

// ── Repairs ───────────────────────────────────────────────────────────────────

export function useRepairs(filters?: { status?: string; agent_id?: string }) {
  return useQuery({
    queryKey: traceKeys.repairs(filters ?? {}),
    queryFn: () => api.repairs.list(filters),
    refetchInterval: 10_000,
  });
}

export function useApproveRepair() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ repairId, approvedBy }: { repairId: string; approvedBy: string }) =>
      api.repairs.approve(repairId, { approved_by: approvedBy }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["repairs"] });
    },
  });
}

export function useApplyRepair() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ repairId, appliedBy }: { repairId: string; appliedBy: string }) =>
      api.repairs.apply(repairId, { applied_by: appliedBy }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["repairs"] });
    },
  });
}

export function useRollbackRepair() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      repairId,
      rolledBackBy,
      reason,
    }: {
      repairId: string;
      rolledBackBy: string;
      reason: string;
    }) => api.repairs.rollback(repairId, { rolled_back_by: rolledBackBy, reason }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["repairs"] });
    },
  });
}

// ── Simulation ────────────────────────────────────────────────────────────────

export function useRunSimulation() {
  return useMutation({
    mutationFn: (payload: {
      trace_id?: string;
      agent_id?: string;
      preset: string;
      iterations?: number;
    }) => api.simulator.run(payload),
  });
}

export function useTriggerDiagnosis() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { trace_id: string; force_rediagnose?: boolean }) =>
      api.diagnoses.trigger(payload),
    onSuccess: (_, variables) => {
      setTimeout(() => {
        queryClient.invalidateQueries({
          queryKey: traceKeys.diagnosis(variables.trace_id),
        });
      }, 15_000);
    },
  });
}

// ── Demo ──────────────────────────────────────────────────────────────────────

export function useInjectFailure() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload?: { failure_type?: string; agent_id?: string }) =>
      api.demo.injectFailure(payload),
    onSuccess: () => {
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: traceKeys.lists() });
        queryClient.invalidateQueries({ queryKey: ["dashboard", "overview"] });
      }, 1_000);
    },
  });
}

// ── Diagnosis insights & reports ─────────────────────────────────────────────

export function useDiagnosisInsights(traceId: string) {
  return useQuery({
    queryKey: ["diagnoses", traceId, "insights"],
    queryFn: () => api.diagnoses.insights(traceId),
    enabled: !!traceId,
    retry: 1,
    staleTime: 60_000,
  });
}

export function useIncidentReport(traceId: string) {
  return useQuery({
    queryKey: ["diagnoses", traceId, "report"],
    queryFn: () => api.diagnoses.report(traceId),
    enabled: false,
    retry: 1,
    staleTime: Infinity,
  });
}
