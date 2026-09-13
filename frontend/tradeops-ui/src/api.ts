import type { AuditItem, DemoSignal, Health } from "./types";

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`${response.status} ${response.statusText}${text ? ` — ${text}` : ""}`);
  }
  return (await response.json()) as T;
}

export const getAgentHealth = () => request<Health>("/api/agent/health");
export const getWorkflowHealth = () => request<Health>("/api/workflow/health");
export const getPrice = (symbol: string) => request<{ symbol: string; last: number; ts: string }>(`/api/market/prices/${encodeURIComponent(symbol)}`);
export const getAudit = (limit = 12) => request<{ items: AuditItem[] }>(`/api/workflow/audit?limit=${limit}`);

export async function proposeDecision(signal: DemoSignal, agentToken: string, executionMode: "SHADOW" | "PAPER") {
  return request<{ case: Record<string, unknown> }>("/api/agent/decision/propose", {
    method: "POST",
    headers: { Authorization: `Bearer ${agentToken}` },
    body: JSON.stringify({
      symbol: signal.symbol,
      direction: signal.direction,
      qty: 1,
      entry: signal.entry,
      stop: signal.stop,
      targets: signal.targets,
      timeframe: signal.timeframe,
      regime: signal.regime,
      pattern: signal.pattern,
      assessment_status: "SUPPORTED",
      risk_status: "ACCEPT",
      event_age_ms: 120,
      max_freshness_ms: 5000,
      evidence_quality: signal.evidenceQuality,
      rr: signal.rr,
      historical_expectancy_r: 0.23,
      historical_trade_count: 120,
      ml_score: signal.mlScore,
      ml_probability_status: signal.mlStatus,
      evidence: ["technical", "pattern", "risk", "rag"],
      execution_mode: executionMode,
    }),
  });
}

export async function reviewDecision(proposalId: string, reviewerToken: string, decision: "APPROVE" | "REJECT") {
  return request<{ case: Record<string, unknown> }>(`/api/agent/decision/${proposalId}/review`, {
    method: "POST",
    headers: { Authorization: `Bearer ${reviewerToken}` },
    body: JSON.stringify({ decision, rationale: decision === "APPROVE" ? "Validated from TradeOps Web Cockpit" : "Rejected from TradeOps Web Cockpit" }),
  });
}

export async function executeDecision(proposalId: string, reviewerToken: string) {
  return request<{ case: Record<string, unknown> }>(`/api/agent/decision/${proposalId}/execute`, {
    method: "POST",
    headers: { Authorization: `Bearer ${reviewerToken}` },
  });
}
