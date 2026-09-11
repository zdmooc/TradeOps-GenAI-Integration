from prometheus_client import Counter, Histogram

DECISION_PROPOSALS = Counter(
    "tradeops_decision_proposals_total",
    "Decision fusion proposals by outcome and execution mode",
    ["decision", "execution_mode"],
)
DECISION_GATE_FAILURES = Counter(
    "tradeops_decision_gate_failures_total",
    "Decision fusion hard-gate failures",
    ["gate"],
)
RISK_DECISIONS = Counter(
    "tradeops_risk_decisions_total",
    "Deterministic risk outcomes",
    ["status"],
)
KAFKA_MESSAGES = Counter(
    "tradeops_kafka_messages_total",
    "Kafka-compatible event messages by direction/topic/status",
    ["direction", "topic", "status"],
)
KAFKA_HANDLER_DURATION = Histogram(
    "tradeops_kafka_handler_duration_seconds",
    "Kafka consumer handler latency",
    ["topic"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)
LLM_REQUESTS = Counter(
    "tradeops_llm_requests_total",
    "LLM requests by provider and outcome",
    ["provider", "status"],
)
LLM_DURATION = Histogram(
    "tradeops_llm_request_duration_seconds",
    "LLM request latency",
    ["provider"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60, 120),
)
LLM_TOKENS_ESTIMATED = Counter(
    "tradeops_llm_tokens_estimated_total",
    "Estimated LLM tokens; not provider-billed token counts",
    ["provider", "direction"],
)
LLM_ESTIMATED_COST_USD = Counter(
    "tradeops_llm_estimated_cost_usd_total",
    "Estimated LLM cost based on configured per-1k-token rates",
    ["provider"],
)
SECURITY_DENIALS = Counter(
    "tradeops_security_denials_total",
    "Authentication/authorization/tool-policy denials",
    ["boundary", "reason"],
)
