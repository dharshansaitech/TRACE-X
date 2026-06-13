"use client";
// frontend/hooks/useAgents.ts
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";

export const agentKeys = {
  all: ["agents"] as const,
  lists: () => [...agentKeys.all, "list"] as const,
  list: (filters: any) => [...agentKeys.lists(), filters] as const,
  detail: (id: string) => [...agentKeys.all, "detail", id] as const,
  health: (id: string) => [...agentKeys.all, "health", id] as const,
  dashboard: () => ["dashboard", "overview"] as const,
};

export function useAgents(filters?: { status?: string }) {
  return useQuery({
    queryKey: agentKeys.list(filters ?? {}),
    queryFn: () => api.agents.list(filters),
    refetchInterval: 30_000,
  });
}

export function useAgent(agentId: string) {
  return useQuery({
    queryKey: agentKeys.detail(agentId),
    queryFn: () => api.agents.get(agentId),
    enabled: !!agentId,
  });
}

export function useAgentHealth(agentId: string) {
  return useQuery({
    queryKey: agentKeys.health(agentId),
    queryFn: () => api.agents.health(agentId),
    enabled: !!agentId,
    refetchInterval: 60_000,
  });
}

export function useDashboardOverview() {
  return useQuery({
    queryKey: agentKeys.dashboard(),
    queryFn: () => api.dashboard.overview(),
    refetchInterval: 30_000,
    staleTime: 10_000,
  });
}

export function useSystemStatus() {
  return useQuery({
    queryKey: ["system", "status"],
    queryFn: () => api.system.status(),
    staleTime: 5 * 60_000,
    refetchInterval: 5 * 60_000,
    retry: false,
  });
}

export function useIncidents(filters?: {
  status?: string;
  severity?: string;
  agent_id?: string;
  page?: number;
}) {
  return useQuery({
    queryKey: ["dashboard", "incidents", filters ?? {}],
    queryFn: () => api.dashboard.incidents(filters),
    refetchInterval: 20_000,
  });
}
