import uuid
from datetime import datetime, timezone
from services.common.logging import setup_logging
from services.common.kafka import consumer, consume_forever, publish
from services.common.audit import publish_audit

log = setup_logging("risk-engine")

MAX_QTY = 10000

async def handler(topic: str, msg: dict):
    if topic != "signals.generated":
        return
    p = msg.get("payload", {})
    qty = 100  # demo sizing
    breach = qty > MAX_QTY
    correlation_id = msg.get("correlation_id") or str(uuid.uuid4())
    if breach:
        data = {"reason": "MAX_QTY", "qty": qty, "max": MAX_QTY, "symbol": p.get("symbol")}
        await publish_audit("risk.breach", p.get("symbol",""), data, correlation_id)
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "risk.breach",
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "correlation_id": correlation_id,
            "payload": data,
        }
        await publish("risk.breach", event, key=p.get("symbol",""))
        log.warning("risk breach %s", data)

async def main():
    cons = consumer(["signals.generated"], group_id="risk-engine")
    await consume_forever(cons, handler)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
