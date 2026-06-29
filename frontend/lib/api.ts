// Typed client for the FastAPI backend. Shapes mirror SessionResponse in
// backend/main.py and the per-agent JSON the orchestrator produces.

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "") || "http://localhost:8000";

export interface Requirements {
  application_type: string;
  users_per_day: number;
  latency_requirement_seconds: number;
  budget_usd_monthly: number;
  document_count: number;
  preferred_llm_provider: string;
  constraints: string[];
  summary: string;
}

export interface Tradeoff {
  decision: string;
  chosen: string;
  alternative: string;
  rationale: string;
}

export interface Infrastructure {
  components: Record<string, string>;
  scaling_strategy: string;
  tradeoffs: Tradeoff[];
  tier: string;
  notes: string;
}

export interface CostLine {
  category: "infra" | "llm" | "external_api";
  item: string;
  monthly_usd: number;
}

export interface Cost {
  breakdown: CostLine[];
  infra_total_usd: number;
  llm_total_usd: number;
  external_api_total_usd: number;
  total_monthly_usd: number;
  budget_usd: number;
  within_budget: boolean;
  notes: string;
}

export interface Deployment {
  artifacts: Record<string, string>;
  notes: string;
}

export interface TimePoint {
  t: number;
  rps: number;
  latency_ms: number;
  cpu_pct: number;
  llm_tokens_per_min: number;
}

export interface Alert {
  type: string;
  token_type?: string;
  severity: "warning" | "critical";
  message: string;
}

export interface Monitoring {
  infrastructure_metrics: Record<string, number>;
  application_metrics: Record<string, number>;
  llm_tokens: Record<string, number>;
  api_tokens: Record<string, number>;
  budget_usd: number;
  projected_monthly_overrun_usd: number;
  timeseries: TimePoint[];
  alerts: Alert[];
}

export interface Recommendation {
  title: string;
  category: string;
  rationale: string;
  projected_savings_usd_monthly: number;
  projected_savings_pct: number;
  effort: "low" | "medium" | "high";
}

export interface Optimization {
  recommendations: Recommendation[];
  total_projected_savings_usd_monthly: number;
  summary: string;
}

export interface Step {
  agent: string;
  output: Record<string, unknown>;
  redesign_pass?: number;
}

export interface SessionResponse {
  session_id: string;
  status: "planned" | "deployed";
  mock_llm: boolean;
  requirements: Requirements | null;
  infrastructure: Infrastructure | null;
  cost: Cost | null;
  deployment: Deployment | null;
  monitoring: Monitoring | null;
  optimization: Optimization | null;
  redesign_count: number;
  steps: Step[];
  errors: string[];
}

async function handle(res: Response): Promise<SessionResponse> {
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json();
}

export async function createSession(requirements: string): Promise<SessionResponse> {
  const res = await fetch(`${API_BASE}/api/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ requirements }),
  });
  return handle(res);
}

export async function approveSession(sessionId: string): Promise<SessionResponse> {
  const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/approve`, {
    method: "POST",
  });
  return handle(res);
}

export async function getHealth(): Promise<{ status: string; mock_llm: boolean }> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error("backend unreachable");
  return res.json();
}
