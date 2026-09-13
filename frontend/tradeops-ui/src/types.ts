export type Health = { status: string; service?: string; mode?: string; execution?: string };

export type MarketQuote = {
  symbol: string;
  label: string;
  last: number;
  ts: string;
  direction: "UP" | "DOWN" | "FLAT";
  regime: string;
  freshness: string;
};

export type DemoSignal = {
  symbol: string;
  direction: "LONG" | "SHORT";
  entry: number;
  stop: number;
  targets: number[];
  rr: number;
  timeframe: string;
  regime: string;
  pattern: string;
  evidenceQuality: number;
  mlScore: number;
  mlStatus: string;
};

export type AgentEvidence = {
  name: string;
  status: "SUPPORTED" | "NEUTRAL" | "WATCH" | "VETO";
  detail: string;
};

export type Outcome = {
  id: string;
  symbol: string;
  mode: "SHADOW" | "PAPER";
  result: "TARGET" | "STOP" | "EXPIRED" | "PENDING";
  pnlPct: number | null;
  rMultiple: number | null;
  provenance: "DEMO_SYNTHETIC" | "LIVE_API";
};

export type AuditItem = {
  audit_id: number;
  kind: string;
  ref_id: string;
  hash: string;
  correlation_id: string;
  created_at: string;
};
