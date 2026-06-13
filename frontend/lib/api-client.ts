// frontend/lib/api-client.ts
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY ?? "demo-api-key-tracex-hackathon";

interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined | null>;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { params, ...fetchOptions } = options;

  let url = `${API_BASE}${path}`;
  if (params) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v != null) searchParams.append(k, String(v));
    });
    const qs = searchParams.toString();
    if (qs) url += `?${qs}`;
  }

  const response = await fetch(url, {
    ...fetchOptions,
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": API_KEY,
      ...fetchOptions.headers,
    },
  });

  if (!response.ok) {
    const error = await response.text().catch(() => "Unknown error");
    throw new Error(`API error ${response.status}: ${error}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

// ── Traces ────────────────────────────────────────────────────────────────────

export const api = {
  traces: {
    list: (params?: {
      agent_id?: string;
      status?: string;
      failure_type?: string;
      page?: number;
      page_size?: number;
    }) => request<any>("/traces", { params }),

    get: (traceId: string) => request<any>(`/traces/${traceId}`),

    ingest: (payload: any) =>
      request<any>("/traces/ingest", {
        method: "POST",
        body: JSON.stringify(payload),
      }),

    delete: (traceId: string) =>
      request<void>(`/traces/${traceId}`, { method: "DELETE" }),
  },

  // ── Agents ──────────────────────────────────────────────────────────────────
  agents: {
    list: (params?: { status?: string; page?: number; page_size?: number }) =>
      request<any>("/agents", { params }),

    get: (agentId: string) => request<any>(`/agents/${agentId}`),

    health: (agentId: string) => request<any>(`/agents/${agentId}/health`),

    register: (payload: any) =>
      request<any>("/agents", { method: "POST", body: JSON.stringify(payload) }),

    delete: (agentId: string) =>
      request<void>(`/agents/${agentId}`, { method: "DELETE" }),
  },

  // ── Diagnoses ────────────────────────────────────────────────────────────────
  diagnoses: {
    get: (traceId: string) => request<any>(`/diagnoses/${traceId}`),

    trigger: (payload: { trace_id: string; force_rediagnose?: boolean }) =>
      request<any>("/diagnoses/trigger", {
        method: "POST",
        body: JSON.stringify(payload),
      }),

    list: (params?: { agent_id?: string; limit?: number }) =>
      request<any>("/diagnoses", { params }),

    insights: (traceId: string) => request<any>(`/diagnoses/${traceId}/insights`),

    report: (traceId: string) => request<any>(`/diagnoses/${traceId}/report`),
  },

  // ── Repairs ──────────────────────────────────────────────────────────────────
  repairs: {
    list: (params?: { status?: string; agent_id?: string; page?: number }) =>
      request<any>("/repairs", { params }),

    get: (repairId: string) => request<any>(`/repairs/${repairId}`),

    approve: (repairId: string, payload: { approved_by: string; notes?: string }) =>
      request<any>(`/repairs/${repairId}/approve`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),

    apply: (repairId: string, payload: { applied_by: string; dry_run?: boolean }) =>
      request<any>(`/repairs/${repairId}/apply`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),

    rollback: (repairId: string, payload: { rolled_back_by: string; reason: string }) =>
      request<any>(`/repairs/${repairId}/rollback`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  },

  // ── Replay ───────────────────────────────────────────────────────────────────
  replay: {
    get: (traceId: string) => request<any>(`/replay/${traceId}`),
  },

  // ── Simulator ────────────────────────────────────────────────────────────────
  simulator: {
    run: (payload: {
      trace_id?: string;
      agent_id?: string;
      preset: string;
      iterations?: number;
      what_if_variables?: any[];
    }) =>
      request<any>("/simulate", {
        method: "POST",
        body: JSON.stringify(payload),
      }),

    get: (simulationId: string) => request<any>(`/simulate/${simulationId}`),
  },

  // ── System ────────────────────────────────────────────────────────────────────
  system: {
    status: () => request<{ demo_mode: boolean; environment: string; version: string }>("/system/status"),
  },

  // ── Demo ─────────────────────────────────────────────────────────────────────
  demo: {
    injectFailure: (payload?: { failure_type?: string; agent_id?: string }) =>
      request<{
        trace_id: string;
        agent_id: string;
        agent_name: string;
        failure_type: string;
        message: string;
      }>("/demo/inject-failure", {
        method: "POST",
        body: JSON.stringify(payload ?? {}),
      }),
  },

  // ── Dashboard ─────────────────────────────────────────────────────────────────
  dashboard: {
    overview: () => request<any>("/dashboard/overview"),

    incidents: (params?: {
      status?: string;
      severity?: string;
      agent_id?: string;
      page?: number;
      page_size?: number;
    }) => request<any>("/dashboard/incidents", { params }),
  },
};

export type ApiClient = typeof api;
