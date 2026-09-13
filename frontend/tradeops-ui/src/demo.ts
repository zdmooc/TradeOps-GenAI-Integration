import type { AgentEvidence, DemoSignal, Outcome } from "./types";

export const demoSignal: DemoSignal = {
  symbol: "NASDAQ",
  direction: "LONG",
  entry: 24850,
  stop: 24770,
  targets: [25040],
  rr: 2.38,
  timeframe: "15m",
  regime: "TREND_UP",
  pattern: "PULLBACK",
  evidenceQuality: 0.88,
  mlScore: 0.74,
  mlStatus: "SCORE_ONLY",
};

export const demoEvidence: AgentEvidence[] = [
  { name: "Market", status: "SUPPORTED", detail: "Structure directionnelle cohérente" },
  { name: "Technical", status: "SUPPORTED", detail: "EMA/VWAP et momentum alignés" },
  { name: "Pattern", status: "SUPPORTED", detail: "Pullback valide, géométrie prix cohérente" },
  { name: "Macro", status: "NEUTRAL", detail: "Aucun veto macro dans le scénario de démo" },
  { name: "RAG", status: "SUPPORTED", detail: "Politique de risque et runbook admissibles" },
  { name: "ML", status: "WATCH", detail: "Score 0,74 non qualifié comme probabilité réelle" },
];

export const demoOutcomes: Outcome[] = [
  { id: "DEMO-104", symbol: "NASDAQ", mode: "SHADOW", result: "TARGET", pnlPct: 0.72, rMultiple: 2.1, provenance: "DEMO_SYNTHETIC" },
  { id: "DEMO-103", symbol: "DAX", mode: "PAPER", result: "STOP", pnlPct: -0.31, rMultiple: -1, provenance: "DEMO_SYNTHETIC" },
  { id: "DEMO-102", symbol: "CAC40", mode: "SHADOW", result: "TARGET", pnlPct: 0.46, rMultiple: 1.8, provenance: "DEMO_SYNTHETIC" },
  { id: "DEMO-101", symbol: "BTCUSD", mode: "PAPER", result: "EXPIRED", pnlPct: 0, rMultiple: 0, provenance: "DEMO_SYNTHETIC" },
];
