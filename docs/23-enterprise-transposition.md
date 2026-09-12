# I12 — Enterprise transposition: banking, payments and insurance

The portfolio uses trading because it forces real-time ingestion, noisy/conflicting data, deterministic risk, ML evaluation, agent orchestration, auditability and human control. The architecture is intentionally reusable outside trading.

| Trading reference | Banking / payments | Insurance | Cyber / IT operations |
|---|---|---|---|
| Market event | Payment / account / transaction event | Claim / policy / telematics event | Alert / log / topology event |
| Source identity and freshness | Channel/provider/system-of-record identity | Broker/core/partner provenance | Sensor/tool/source provenance |
| Data-quality gate | Payment-message validation / duplicate control | Claim completeness / consistency | Event normalization / deduplication |
| Technical/pattern engine | Deterministic fraud/velocity rules | Eligibility/rule patterns | Detection/correlation rules |
| Market regime | Customer/payment/risk context | Claim/policy/context state | Incident/threat/operational state |
| ML signal-quality score | Fraud/risk ranking | Triage/severity/propensity ranking | Alert prioritization/anomaly ranking |
| RAG | Regulations, procedures, product rules | Policy wording, procedures, coverage rules | Runbooks, CMDB, security policies |
| Specialized agents | Payment/fraud/risk/compliance agents | Claim/coverage/fraud/risk agents | Incident/change/security agents |
| Governed MCP/tool boundary | Customer/payment/limits/AML tools | Policy/claim/document tools | CMDB/SIEM/ITSM/orchestration tools |
| Deterministic risk veto | Limits, sanctions, eligibility, policy constraints | Coverage/authority/underwriting constraints | Change/security/blast-radius policy |
| HITL | Maker-checker / fraud analyst | Claims adjuster / underwriter | Operator / incident commander |
| Paper/shadow mode | Shadow fraud/payment decision | Shadow claim/underwriting decision | Dry-run remediation |
| Backtest/replay | Historical transaction replay | Historical claim replay | Historical incident/event replay |
| OTel/audit lineage | Decision/audit trace | Regulated decision trace | Incident/change trace |

## Payments and fraud

A payment stream replaces the market stream. ISO/event normalization feeds deterministic validation, fraud features and context. ML ranks risk, agents retrieve policies/context and governed tools, but sanctions/limits/eligibility remain deterministic vetoes. HITL maps naturally to maker-checker or fraud analyst review.

## Insurance

Claim and policy events replace market events. Deterministic eligibility/coverage/authority rules remain outside the LLM. ML can rank triage/fraud propensity, RAG grounds policy/procedure reasoning, and agents orchestrate evidence collection. Human adjuster/underwriter approval remains explicit for consequential decisions.

## Cybersecurity and IT operations

Telemetry replaces market data. Deterministic detection and blast-radius controls stay authoritative. Agents can correlate runbooks, CMDB and incident context and propose remediation; governed tools plus HITL prevent unrestricted autonomous changes.

## Architectural invariants across domains

- preserve source/provenance and event time;
- fail closed on stale/conflicting/insufficient evidence;
- keep deterministic policy/risk separate from generative reasoning;
- measure ML out of sample and calibrate only when probabilistic claims are needed;
- constrain tools with identity, scopes, validation, rate limits, timeouts and audit;
- require human approval for consequential actions;
- preserve end-to-end correlation and evidence lineage;
- use replay/shadow operation before production autonomy;
- distinguish implementation, testing, deployment and verification claims.
