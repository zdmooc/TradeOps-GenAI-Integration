import uuid
from datetime import datetime, timezone

from services.common.audit import publish_audit
from services.common.kafka import consume_forever, consumer, publish
from services.common.logging import setup_logging
from services.risk_engine.adapter import evaluate_payload

log = setup_logging("risk-engine")


async def _publish_breach(data: dict, correlation_id: str, symbol: str) -> None:
    await publish_audit("risk.breach", symbol, data, correlation_id)
    event = {
        "event_id": str(uuid.uuid4()),
        "event_type": "risk.breach",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "correlation_id": correlation_id,
        "payload": data,
    }
    await publish("risk.breach", event, key=symbol)


async def handler(topic: str, msg: dict):
    if topic != "signals.generated":
        return
    payload = msg.get("payload", {})
    symbol = str(payload.get("symbol") or payload.get("risk_intent", {}).get("instrument", ""))
    correlation_id = msg.get("correlation_id") or str(uuid.uuid4())
    try:
        decision = evaluate_payload(payload)
    except (KeyError, TypeError, ValueError) as exc:
        data = {
            "reason": "I3_CONTEXT_INVALID",
            "detail": str(exc),
            "symbol": symbol,
        }
        await _publish_breach(data, correlation_id, symbol)
        log.warning("risk input veto %s", data)
        return

    if decision.approved:
        log.info("risk approved symbol=%s regime=%s", symbol, decision.regime)
        return

    data = {
        "reason": "RISK_POLICY_VETO",
        "reasons": list(decision.veto_reasons),
        "regime": decision.regime,
        "circuit_breaker": decision.circuit_breaker,
        "metrics": decision.metrics,
        "symbol": symbol,
    }
    await _publish_breach(data, correlation_id, symbol)
    log.warning("risk veto %s", data)


async def main():
    cons = consumer(["signals.generated"], group_id="risk-engine")
    await consume_forever(cons, handler)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
