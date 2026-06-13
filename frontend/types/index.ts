// frontend/types/index.ts
// All TypeScript types matching the backend Pydantic schemas

// ── Trace types ───────────────────────────────────────────────────────────────

export type SpanStatus = "ok" | "error" | "timeout" | "cancelled" | "unknown";
export type SpanKind = "agent" | "tool" | "llm" | "retrieval" | "embedding" | "chain" | "internal";
export type TraceStatus = "running" | "success" | "failure" | "partial" | "unknown";
export type FailureType =
  | "tool_error"
  | "hallucination"
  | "staleness"
  | "loop"
  | "timeout"
  | "context_overflow"
  | "safety_violation"
  | "planning_failure"
  | "retrieval_failure"
  | "none";

export interface ToolCallRecord {
  tool_call_id: string;
  tool_name: string;
  tool_version?: string;
  input_args: Record<string, any>;
  output?: any;
  error?: string;
  started_at: string;
  ended_at?: string;
  duration_ms?: number;
  status: SpanStatus;
  retry_count: number;
  metadata: Record<string, any>;
}

export interface AgentSpan {
  span_id: string;
  trace_id: string;
  parent_span_id?: string;
  agent_id: string;
  agent_name: string;
  span_name: string;
  kind: SpanKind;
  started_at: string;
  ended_at?: string;
  duration_ms?: number;
  status: SpanStatus;
  error_message?: string;
  error_type?: string;
  model?: string;
  prompt_tokens?: number;
  completion_tokens?: number;
  total_tokens?: number;
  temperature?: number;
  input_messages: any[];
  output_content?: string;
  finish_reason?: string;
  tool_calls: ToolCallRecord[];
  metadata: Record<string, any>;
  tags: string[];
  attributes: Record<string, any>;
}

export interface AgentTrace {
  trace_id: string;
  agent_id: string;
  agent_name: string;
  agent_version?: string;
  started_at: string;
  ended_at?: string;
  duration_ms?: number;
  status: TraceStatus;
  failure_type: FailureType;
  failure_reason?: string;
  spans: AgentSpan[];
  input_payload: Record<string, any>;
  output_payload: Record<string, any>;
  total_tokens: number;
  total_tool_calls: number;
  error_count: number;
  llm_calls: number;
  session_id?: string;
  user_id?: string;
  environment: string;
  tags: string[];
  metadata: Record<string, any>;
}

export interface TracePreview {
  trace_id: string;
  agent_id: string;
  agent_name: string;
  started_at: string;
  ended_at?: string;
  duration_ms?: number;
  status: TraceStatus;
  failure_type: FailureType;
  span_count: number;
  tool_call_count: number;
  total_tokens: number;
  has_diagnosis: boolean;
  has_repair: boolean;
  tags: string[];
}

export interface TraceListResponse {
  traces: TracePreview[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
}

// ── Diagnosis types ───────────────────────────────────────────────────────────

export type RootCauseCategory =
  | "prompt_design"
  | "tool_configuration"
  | "data_quality"
  | "context_management"
  | "model_limitation"
  | "orchestration_logic"
  | "external_service"
  | "resource_constraint"
  | "security_policy"
  | "unknown";

export type SeverityLevel = "critical" | "high" | "medium" | "low" | "info";

export interface ReasoningStep {
  step_number: number;
  hypothesis: string;
  evidence: string[];
  evidence_spans: string[];
  confidence: number;
  conclusion: string;
  eliminated_alternatives: string[];
}

export interface BlastRadius {
  affected_agents: string[];
  affected_sessions: string[];
  affected_users_estimate: number;
  downstream_services: string[];
  data_integrity_risk: boolean;
  financial_impact_estimate?: string;
  propagation_path: string[];
  containment_possible: boolean;
}

export interface AnomalySignal {
  signal_type: string;
  span_id: string;
  description: string;
  observed_value?: any;
  expected_range?: string;
  anomaly_score: number;
  timestamp?: string;
}

export interface DiagnosisResult {
  diagnosis_id: string;
  trace_id: string;
  agent_id: string;
  diagnosed_at: string;
  diagnosis_duration_ms?: number;
  root_cause_category: RootCauseCategory;
  root_cause_description: string;
  severity: SeverityLevel;
  confidence: number;
  reasoning_chain: ReasoningStep[];
  anomaly_signals: AnomalySignal[];
  blast_radius: BlastRadius;
  failing_span_id?: string;
  divergence_point_span_id?: string;
  contributing_spans: string[];
  evidence_summary: string;
  immediate_actions: string[];
  long_term_recommendations: string[];
  repair_feasibility: number;
  arize_insights: Record<string, any>;
  similar_traces: string[];
  model_used: string;
}

// ── Repair types ──────────────────────────────────────────────────────────────

export type RepairType =
  | "prompt_edit"
  | "tool_config_change"
  | "retry_policy_change"
  | "context_injection"
  | "orchestration_fix"
  | "parameter_tuning"
  | "data_validation"
  | "fallback_addition"
  | "timeout_adjustment"
  | "model_swap";

export type RepairStatus =
  | "pending"
  | "approved"
  | "applied"
  | "validated"
  | "rejected"
  | "rolled_back"
  | "failed";

export interface DiffLine {
  line_number: number;
  content: string;
  change_type: "added" | "removed" | "context";
}

export interface RepairDiff {
  file_path?: string;
  target_type: string;
  before: string;
  after: string;
  diff_lines: DiffLine[];
  description: string;
}

export interface TestCase {
  test_id: string;
  name: string;
  description: string;
  input_payload: Record<string, any>;
  expected_output_pattern?: string;
  expected_behavior: string;
  failure_scenario: string;
  timeout_seconds: number;
  passed?: boolean;
  actual_output?: any;
  error?: string;
  run_duration_ms?: number;
}

export interface RepairArtifact {
  repair_id: string;
  trace_id: string;
  diagnosis_id: string;
  agent_id: string;
  repair_type: RepairType;
  title: string;
  description: string;
  rationale: string;
  diff: RepairDiff;
  implementation_instructions: string[];
  test_cases: TestCase[];
  confidence: number;
  risk_level: "low" | "medium" | "high";
  side_effects: string[];
  rollback_instructions?: string;
  status: RepairStatus;
  created_at: string;
  approved_at?: string;
  applied_at?: string;
  applied_by?: string;
  rolled_back_at?: string;
  validation_passed?: boolean;
  validation_score?: number;
  validation_notes?: string;
  tests_passed: number;
  tests_failed: number;
  tests_total: number;
  model_used: string;
}

export interface RepairListResponse {
  repairs: RepairArtifact[];
  total: number;
  pending_count: number;
  approved_count: number;
  applied_count: number;
}

// ── Replay types ──────────────────────────────────────────────────────────────

export type FrameType =
  | "span_start"
  | "span_end"
  | "llm_prompt"
  | "llm_response"
  | "tool_call"
  | "tool_result"
  | "tool_error"
  | "agent_decision"
  | "context_window"
  | "error_event"
  | "anomaly_detected"
  | "divergence_point"
  | "state_snapshot";

export interface ReplayAnnotation {
  annotation_id: string;
  annotation_type: string;
  title: string;
  body: string;
  severity: string;
  auto_generated: boolean;
  linked_diagnosis_id?: string;
  linked_repair_id?: string;
}

export interface ReplayFrame {
  frame_id: string;
  frame_index: number;
  frame_type: FrameType;
  timestamp: string;
  relative_time_ms: number;
  span_id?: string;
  tool_call_id?: string;
  agent_id: string;
  content: Record<string, any>;
  active_spans: string[];
  context_tokens_used?: number;
  context_tokens_max?: number;
  memory_state: Record<string, any>;
  annotations: ReplayAnnotation[];
  is_failure_frame: boolean;
  is_divergence_point: boolean;
}

export interface ReplaySession {
  session_id: string;
  trace_id: string;
  agent_id: string;
  agent_name: string;
  trace_started_at: string;
  trace_ended_at?: string;
  total_duration_ms: number;
  frames: ReplayFrame[];
  total_frames: number;
  failure_frame_indices: number[];
  divergence_frame_index?: number;
  key_event_indices: number[];
  span_count: number;
  tool_call_count: number;
  llm_call_count: number;
  error_count: number;
  diagnosis_id?: string;
  repair_id?: string;
  created_at: string;
  replay_fps: number;
}

export interface ReplayResponse {
  session: ReplaySession;
  playback: {
    session_id: string;
    current_frame: number;
    is_playing: boolean;
    fps: number;
    loop: boolean;
    speed_multiplier: number;
  };
}

// ── Dashboard types ───────────────────────────────────────────────────────────

export type AgentStatus = "healthy" | "degraded" | "critical" | "offline" | "unknown";

export interface AgentHealthMetrics {
  error_rate: number;
  latency_p50_ms: number;
  latency_p95_ms: number;
  latency_p99_ms: number;
  success_rate: number;
  throughput_rph: number;
  tool_failure_rate: number;
  hallucination_rate: number;
  staleness_events: number;
  context_overflow_events: number;
}

export interface AgentHealth {
  agent_id: string;
  agent_name: string;
  agent_version?: string;
  status: AgentStatus;
  status_reason?: string;
  metrics: AgentHealthMetrics;
  last_seen?: string;
  last_failure?: string;
  uptime_hours: number;
  open_incidents: number;
  resolved_incidents_24h: number;
  traces_24h: number;
  health_score: number;
  trend: "up" | "down" | "stable";
  sparkline: number[];
}

export interface IncidentSummary {
  incident_id: string;
  trace_id: string;
  diagnosis_id?: string;
  repair_id?: string;
  agent_id: string;
  agent_name: string;
  title: string;
  description: string;
  severity: SeverityLevel;
  status: string;
  failure_type: string;
  root_cause_category?: string;
  started_at: string;
  resolved_at?: string;
  duration_open_minutes?: number;
  affected_users: number;
  confidence?: number;
}

export interface DashboardOverview {
  generated_at: string;
  system: {
    total_agents: number;
    healthy_agents: number;
    degraded_agents: number;
    critical_agents: number;
    offline_agents: number;
    total_traces_24h: number;
    failed_traces_24h: number;
    success_rate_24h: number;
    avg_latency_ms: number;
    open_incidents: number;
    resolved_incidents_24h: number;
    pending_repairs: number;
    applied_repairs_24h: number;
    traces_per_hour: Array<{ timestamp: string; value: number }>;
    error_rate_trend: Array<{ timestamp: string; value: number }>;
  };
  agent_health: AgentHealth[];
  recent_incidents: IncidentSummary[];
  top_failure_types: Array<{ type: string; count: number }>;
  repair_stats: Record<string, number>;
  mttr_minutes?: number;
  mtbf_hours?: number;
}
