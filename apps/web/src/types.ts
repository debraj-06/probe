/** Shared types — mirrors the FastAPI schemas. */

export type Depth = "quick" | "balanced" | "deep" | "extreme";

export type FocusArea =
  | "technical"
  | "ux"
  | "chaos"
  | "user"
  | "functional"
  | "reliability"
  | "performance"
  | "accessibility"
  | "edge-cases";

export type InspectionStatus = "queued" | "running" | "completed" | "failed" | "stopped";

export type Severity = "critical" | "high" | "medium" | "low" | "info";

export type Classification = "confirmed_defect" | "ux_issue" | "improvement";

export type AgentRole = "technical" | "ux" | "chaos" | "user" | "review";

export interface Inspection {
  id: string;
  url: string;
  depth: Depth;
  focus: string[];
  goals: string[];
  status: InspectionStatus;
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  duration_s: number | null;
  report: Report | null;
  finding_count: number;
  agent_count: number;
}

export interface AgentRun {
  id: string;
  inspection_id: string;
  role: AgentRole;
  status: string;
  steps: number;
  discoveries: number;
  started_at: string | null;
  finished_at: string | null;
  summary: string | null;
}

export interface ProbeEvent {
  id: number;
  inspection_id: string;
  ts: string;
  agent: string | null;
  type: string;
  message: string;
  data: Record<string, unknown>;
}

export interface Evidence {
  id: string;
  kind: string;
  url: string | null;
  path: string | null;
  meta: Record<string, unknown>;
  created_at: string;
}

export interface Finding {
  id: string;
  inspection_id: string;
  title: string;
  category: string;
  classification: Classification;
  severity: Severity;
  confidence: number;
  description: string;
  expected: string | null;
  actual: string | null;
  steps: string[];
  recommendation: string | null;
  agents: string[];
  reproduced: string | null;
  url: string | null;
  correlated: boolean;
  created_at: string;
}

export interface FindingDetail extends Finding {
  correlation_note: string | null;
  contributing_factors: string[];
  source: {
    discoveries?: Array<Record<string, unknown>>;
    evidence?: Array<Record<string, unknown>>;
    target?: string;
    report_summary?: string;
  };
  evidence: Evidence[];
}

export interface ReportFindingSummary {
  id: string;
  title: string;
  severity: Severity;
  category: string;
  classification: Classification;
  confidence: number;
  correlated: boolean;
  agents: string[];
}

export interface Report {
  application: string;
  url: string;
  inspection: string;
  duration: string;
  /** Numeric twin of `duration` — present on ReportOut, mirrored here. */
  duration_s: number | null;
  agents: Array<{ role: string; label: string; goal: string; discoveries: number }>;
  agent_count: number;
  findings: number;
  critical: number;
  high: number;
  medium: number;
  low: number;
  info: number;
  by_category: Record<string, number>;
  groups: Record<string, string[]>;
  top_findings: ReportFindingSummary[];
  correlated: number;
  browser: string;
  generated_at?: string;
}

export interface ReportResponse extends Report {
  summary: string | null;
  items: Finding[];
}

export interface InspectionDetail extends Inspection {
  agents: AgentRun[];
  findings: Finding[];
  events: ProbeEvent[];
}

export interface Health {
  status: string;
  app: string;
  llm_provider: string;
  llm_model: string;
  browser_mode: string;
  active_inspections: number;
}

export interface InspectionCreate {
  url: string;
  depth: Depth;
  focus: FocusArea[];
  goals: string[];
  autostart?: boolean;
}
