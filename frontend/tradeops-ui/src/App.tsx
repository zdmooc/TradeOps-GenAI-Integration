import { useEffect, useMemo, useState } from "react";
import {
  executeDecision,
  getAgentHealth,
  getAudit,
  getPrice,
  getWorkflowHealth,
  proposeDecision,
  reviewDecision,
} from "./api";
import { demoEvidence, demoOutcomes, demoSignal } from "./demo";
import type { AuditItem, Health, MarketQuote } from "./types";

type Tab = "cockpit" | "outcomes" | "audit" | "platform";
type UiMode = "SHADOW" | "PAPER";

type HitlState = {
  proposalId?: string;
  state: "READY" | "PROPOSING" | "REVIEW_REQUIRED" | "APPROVED" | "REJECTED" | "EXECUTED" | "ERROR";
  message: string;
};

const instruments = [
  { symbol: "CAC40", label: "CAC 40", regime: "RANGE" },
  { symbol: "DAX", label: "DAX", regime: "TREND_UP" },
  { symbol: "NASDAQ", label: "Nasdaq 100", regime: "TREND_UP" },
  { symbol: "SP500", label: "S&P 500", regime: "RISK_ON" },
  { symbol: "BTCUSD", label: "BTC/USD", regime: "HIGH_VOLATILITY" },
];

const fallbackPrices: Record<string, number> = {
  CAC40: 8240.4,
  DAX: 23810.2,
  NASDAQ: 24850,
  SP500: 6602.1,
  BTCUSD: 115420,
};

function extractProposalId(payload: { case: Record<string, unknown> }): string | undefined {
  const proposal = payload.case.proposal;
  if (!proposal || typeof proposal !== "object") return undefined;
  const value = (proposal as Record<string, unknown>).proposal_id;
  return typeof value === "string" ? value : undefined;
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 2 }).format(value);
}

function pct(value: number): string {
  return new Intl.NumberFormat("fr-FR", { style: "percent", maximumFractionDigits: 1 }).format(value);
}

function Badge({ children, tone = "neutral" }: { children: React.ReactNode; tone?: "good" | "bad" | "warn" | "neutral" | "info" }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="stat-card">
      <span className="muted">{label}</span>
      <strong>{value}</strong>
      {sub && <small>{sub}</small>}
    </div>
  );
}

export default function App() {
  const [tab, setTab] = useState<Tab>("cockpit");
  const [uiMode, setUiMode] = useState<UiMode>("SHADOW");
  const [quotes, setQuotes] = useState<MarketQuote[]>([]);
  const [agentHealth, setAgentHealth] = useState<Health | null>(null);
  const [workflowHealth, setWorkflowHealth] = useState<Health | null>(null);
  const [audit, setAudit] = useState<AuditItem[]>([]);
  const [agentToken, setAgentToken] = useState("");
  const [reviewerToken, setReviewerToken] = useState("");
  const [showCredentials, setShowCredentials] = useState(false);
  const [hitl, setHitl] = useState<HitlState>({ state: "READY", message: "Prêt à créer une proposition de démonstration." });

  async function refresh() {
    const quoteResults = await Promise.all(
      instruments.map(async (item, index) => {
        try {
          const live = await getPrice(item.symbol);
          return {
            ...item,
            last: live.last,
            ts: live.ts,
            direction: index % 3 === 0 ? "FLAT" : index % 2 === 0 ? "DOWN" : "UP",
            freshness: "API SYNTHETIC",
          } satisfies MarketQuote;
        } catch {
          return {
            ...item,
            last: fallbackPrices[item.symbol],
            ts: new Date().toISOString(),
            direction: index % 2 === 0 ? "UP" : "DOWN",
            freshness: "DEMO FALLBACK",
          } satisfies MarketQuote;
        }
      }),
    );
    setQuotes(quoteResults);

    const [agent, workflow, auditResult] = await Promise.allSettled([
      getAgentHealth(),
      getWorkflowHealth(),
      getAudit(12),
    ]);
    setAgentHealth(agent.status === "fulfilled" ? agent.value : null);
    setWorkflowHealth(workflow.status === "fulfilled" ? workflow.value : null);
    setAudit(auditResult.status === "fulfilled" ? auditResult.value.items : []);
  }

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 15000);
    return () => window.clearInterval(timer);
  }, []);

  const outcomeStats = useMemo(() => {
    const resolved = demoOutcomes.filter((item) => item.result !== "PENDING");
    const wins = resolved.filter((item) => item.result === "TARGET").length;
    const pnl = resolved.reduce((sum, item) => sum + (item.pnlPct ?? 0), 0);
    return { winRate: resolved.length ? wins / resolved.length : 0, pnl };
  }, []);

  async function createProposal() {
    if (!agentToken) {
      setShowCredentials(true);
      setHitl({ state: "ERROR", message: "Renseigne le token Agent pour créer la proposition. Il reste uniquement en mémoire du navigateur." });
      return;
    }
    try {
      setHitl({ state: "PROPOSING", message: "Fusion et gates déterministes en cours…" });
      const result = await proposeDecision(demoSignal, agentToken, uiMode);
      const proposalId = extractProposalId(result);
      if (!proposalId) throw new Error("proposal_id absent de la réponse");
      setHitl({ proposalId, state: "REVIEW_REQUIRED", message: `Proposition ${proposalId.slice(0, 8)} prête pour revue humaine.` });
    } catch (error) {
      setHitl({ state: "ERROR", message: error instanceof Error ? error.message : "Erreur inconnue" });
    }
  }

  async function review(decision: "APPROVE" | "REJECT") {
    if (!hitl.proposalId) return;
    if (!reviewerToken) {
      setShowCredentials(true);
      setHitl({ ...hitl, state: "ERROR", message: "Renseigne le token Reviewer pour effectuer la revue." });
      return;
    }
    try {
      await reviewDecision(hitl.proposalId, reviewerToken, decision);
      setHitl({
        ...hitl,
        state: decision === "APPROVE" ? "APPROVED" : "REJECTED",
        message: decision === "APPROVE" ? "Revue humaine approuvée. L'exécution SHADOW/PAPER reste une action séparée." : "Proposition rejetée par le reviewer.",
      });
      void refresh();
    } catch (error) {
      setHitl({ ...hitl, state: "ERROR", message: error instanceof Error ? error.message : "Erreur inconnue" });
    }
  }

  async function executeApproved() {
    if (!hitl.proposalId || !reviewerToken) return;
    try {
      await executeDecision(hitl.proposalId, reviewerToken);
      setHitl({ ...hitl, state: "EXECUTED", message: `${uiMode} exécuté via la frontière gouvernée. Aucun ordre réel n'est autorisé.` });
      void refresh();
    } catch (error) {
      setHitl({ ...hitl, state: "ERROR", message: error instanceof Error ? error.message : "Erreur inconnue" });
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <div className="eyebrow">Maya AI · Agentic Trading Reference</div>
          <h1>TradeOps Cockpit</h1>
        </div>
        <div className="topbar-status">
          <Badge tone="info">CRC</Badge>
          <button className={`mode-toggle ${uiMode === "PAPER" ? "paper" : "shadow"}`} onClick={() => setUiMode(uiMode === "SHADOW" ? "PAPER" : "SHADOW")}>{uiMode}</button>
          <Badge tone={agentHealth ? "good" : "bad"}>Agent {agentHealth ? "UP" : "DOWN"}</Badge>
          <Badge tone={workflowHealth ? "good" : "bad"}>Workflow {workflowHealth ? "UP" : "DOWN"}</Badge>
        </div>
      </header>

      <nav className="tabs" aria-label="Navigation principale">
        {(["cockpit", "outcomes", "audit", "platform"] as Tab[]).map((item) => (
          <button key={item} className={tab === item ? "active" : ""} onClick={() => setTab(item)}>{item === "cockpit" ? "Cockpit" : item === "outcomes" ? "Performance" : item === "audit" ? "Audit" : "Plateforme"}</button>
        ))}
      </nav>

      {tab === "cockpit" && (
        <main>
          <section className="market-strip">
            {quotes.map((quote) => (
              <article className="market-card" key={quote.symbol}>
                <div className="market-card-head"><strong>{quote.label}</strong><Badge tone={quote.direction === "UP" ? "good" : quote.direction === "DOWN" ? "bad" : "neutral"}>{quote.direction}</Badge></div>
                <div className="market-price">{formatNumber(quote.last)}</div>
                <div className="market-meta"><span>{quote.regime}</span><span>{quote.freshness}</span></div>
              </article>
            ))}
          </section>

          <section className="grid-two">
            <article className="panel chart-panel">
              <div className="panel-head"><div><span className="eyebrow">Market context</span><h2>{demoSignal.symbol} · {demoSignal.timeframe}</h2></div><Badge tone="warn">DEMO / API SYNTHETIC</Badge></div>
              <div className="price-chart" aria-label="Graphique de démonstration">
                <svg viewBox="0 0 720 260" role="img" aria-label="Courbe de prix illustrative">
                  <defs><linearGradient id="fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="currentColor" stopOpacity="0.22"/><stop offset="100%" stopColor="currentColor" stopOpacity="0"/></linearGradient></defs>
                  <path className="chart-grid" d="M0 50H720 M0 100H720 M0 150H720 M0 200H720"/>
                  <path className="chart-fill" d="M0 210 C80 190 110 215 165 170 S260 120 310 145 S410 95 455 120 S535 65 580 90 S665 45 720 58 L720 260 L0 260 Z"/>
                  <path className="chart-line" d="M0 210 C80 190 110 215 165 170 S260 120 310 145 S410 95 455 120 S535 65 580 90 S665 45 720 58"/>
                </svg>
                <div className="chart-tags"><Badge tone="good">EMA aligned</Badge><Badge tone="good">VWAP support</Badge><Badge tone="info">RSI 58</Badge><Badge tone="warn">ATR normal</Badge></div>
              </div>
            </article>

            <article className="panel signal-panel">
              <div className="panel-head"><div><span className="eyebrow">Current signal</span><h2>{demoSignal.direction} {demoSignal.symbol}</h2></div><Badge tone="good">RISK ACCEPT</Badge></div>
              <div className="signal-levels">
                <Stat label="Entry" value={formatNumber(demoSignal.entry)} />
                <Stat label="Stop" value={formatNumber(demoSignal.stop)} />
                <Stat label="Target" value={formatNumber(demoSignal.targets[0])} />
                <Stat label="R/R" value={demoSignal.rr.toFixed(2)} />
              </div>
              <div className="signal-facts"><span>Pattern <strong>{demoSignal.pattern}</strong></span><span>Régime <strong>{demoSignal.regime}</strong></span><span>Evidence <strong>{pct(demoSignal.evidenceQuality)}</strong></span><span>ML <strong>{demoSignal.mlScore.toFixed(2)} · {demoSignal.mlStatus}</strong></span></div>
              <p className="disclaimer">Le score ML reste non décisif tant qu’il n’est pas qualifié sur données réelles hors échantillon. Le Risk Gate déterministe conserve le veto.</p>
            </article>
          </section>

          <section className="grid-two agents-hitl">
            <article className="panel">
              <div className="panel-head"><div><span className="eyebrow">Agent evidence</span><h2>Fusion multi-capacités</h2></div></div>
              <div className="agent-list">
                {demoEvidence.map((item) => <div className="agent-row" key={item.name}><strong>{item.name}</strong><span>{item.detail}</span><Badge tone={item.status === "SUPPORTED" ? "good" : item.status === "VETO" ? "bad" : item.status === "WATCH" ? "warn" : "neutral"}>{item.status}</Badge></div>)}
              </div>
            </article>

            <article className="panel hitl-panel">
              <div className="panel-head"><div><span className="eyebrow">Human-in-the-Loop</span><h2>{hitl.state}</h2></div><Badge tone={hitl.state === "ERROR" ? "bad" : hitl.state === "EXECUTED" ? "good" : "info"}>{uiMode}</Badge></div>
              <p className="hitl-message">{hitl.message}</p>
              {hitl.proposalId && <code className="proposal-id">{hitl.proposalId}</code>}
              <div className="hitl-actions">
                {(hitl.state === "READY" || hitl.state === "ERROR") && <button className="primary" onClick={() => void createProposal()}>Créer proposition</button>}
                {hitl.state === "REVIEW_REQUIRED" && <><button className="danger" onClick={() => void review("REJECT")}>Rejeter</button><button className="primary" onClick={() => void review("APPROVE")}>Approuver {uiMode}</button></>}
                {hitl.state === "APPROVED" && <button className="primary" onClick={() => void executeApproved()}>Exécuter {uiMode}</button>}
                {(hitl.state === "REJECTED" || hitl.state === "EXECUTED") && <button onClick={() => setHitl({ state: "READY", message: "Prêt pour une nouvelle démonstration." })}>Nouvelle démo</button>}
              </div>
              <button className="credentials-link" onClick={() => setShowCredentials(!showCredentials)}>{showCredentials ? "Masquer" : "Configurer"} les credentials de démo</button>
              {showCredentials && <div className="credentials"><label>Agent token<input type="password" autoComplete="off" value={agentToken} onChange={(e: { target: { value: string } }) => setAgentToken(e.target.value)} placeholder="Saisi en mémoire uniquement" /></label><label>Reviewer token<input type="password" autoComplete="off" value={reviewerToken} onChange={(e: { target: { value: string } }) => setReviewerToken(e.target.value)} placeholder="Saisi en mémoire uniquement" /></label><small>Jamais stockés dans localStorage, le dépôt ou l’image frontend.</small></div>}
            </article>
          </section>
        </main>
      )}

      {tab === "outcomes" && <main><section className="stats-row"><Stat label="Win rate démo" value={pct(outcomeStats.winRate)} sub="DEMO_SYNTHETIC"/><Stat label="PnL cumulé démo" value={`${outcomeStats.pnl.toFixed(2)} %`} sub="Illustratif, non performance réelle"/><Stat label="Scope" value="SHADOW / PAPER" sub="Aucun ordre réel"/></section><section className="panel"><div className="panel-head"><div><span className="eyebrow">Outcomes</span><h2>Historique démonstrateur</h2></div><Badge tone="warn">PROVENANCE LABELLED</Badge></div><div className="table-wrap"><table><thead><tr><th>ID</th><th>Instrument</th><th>Mode</th><th>Résultat</th><th>PnL</th><th>R</th><th>Provenance</th></tr></thead><tbody>{demoOutcomes.map((item) => <tr key={item.id}><td>{item.id}</td><td>{item.symbol}</td><td>{item.mode}</td><td><Badge tone={item.result === "TARGET" ? "good" : item.result === "STOP" ? "bad" : "warn"}>{item.result}</Badge></td><td>{item.pnlPct === null ? "—" : `${item.pnlPct.toFixed(2)} %`}</td><td>{item.rMultiple ?? "—"}</td><td>{item.provenance}</td></tr>)}</tbody></table></div></section></main>}

      {tab === "audit" && <main><section className="panel"><div className="panel-head"><div><span className="eyebrow">Audit trail</span><h2>Derniers événements backend</h2></div><button onClick={() => void refresh()}>Rafraîchir</button></div>{audit.length ? <div className="table-wrap"><table><thead><tr><th>ID</th><th>Kind</th><th>Ref</th><th>Correlation</th><th>Date</th></tr></thead><tbody>{audit.map((item) => <tr key={item.audit_id}><td>{item.audit_id}</td><td>{item.kind}</td><td>{item.ref_id.slice(0, 12)}</td><td>{item.correlation_id.slice(0, 12)}</td><td>{new Date(item.created_at).toLocaleString("fr-FR")}</td></tr>)}</tbody></table></div> : <div className="empty">Aucun audit récupéré. Vérifie la santé du Workflow API.</div>}</section></main>}

      {tab === "platform" && <main><section className="grid-two"><article className="panel"><div className="panel-head"><div><span className="eyebrow">Runtime</span><h2>Services de démonstration</h2></div></div><div className="service-grid"><a href="/api/agent/health" target="_blank" rel="noreferrer">Agent Controller health</a><a href="/api/workflow/health" target="_blank" rel="noreferrer">Workflow API health</a><a href="https://agent-controller-tradeops.apps-crc.testing/docs" target="_blank" rel="noreferrer">Agent Swagger</a><a href="https://workflow-api-tradeops.apps-crc.testing/docs" target="_blank" rel="noreferrer">Workflow Swagger</a><a href="https://grafana-tradeops.apps-crc.testing" target="_blank" rel="noreferrer">Grafana</a><a href="https://console-openshift-console.apps-crc.testing" target="_blank" rel="noreferrer">OpenShift Console</a></div></article><article className="panel"><div className="panel-head"><div><span className="eyebrow">Safety</span><h2>Garde-fous visibles</h2></div></div><ul className="guardrails"><li>Risk Gate déterministe = veto autoritaire.</li><li>Human-in-the-Loop obligatoire avant SHADOW/PAPER.</li><li>Aucune exécution real-money dans l’IHM.</li><li>MCP, PostgreSQL, Kafka et Qdrant restent internes.</li><li>Tokens de démo saisis en mémoire, jamais persistés.</li><li>Données synthétiques/estimées clairement étiquetées.</li></ul></article></section></main>}

      <footer><span>TradeOps Web Cockpit · business/demo UI</span><span>Grafana reste l’interface SRE/observabilité</span></footer>
    </div>
  );
}
