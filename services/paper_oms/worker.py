import random
import uuid
from datetime import datetime, timezone
from services.common.logging import setup_logging
from services.common.kafka import consumer, consume_forever, publish
from services.common.db import execute, fetchone
from services.common.audit import publish_audit

log = setup_logging("paper-oms")

async def handler(topic: str, msg: dict):
    if topic != "workflow.approved":
        return
    p = msg.get("payload", {})
    workflow_id = p["workflow_id"]
    # Retrieve workflow payload for symbol/side/qty
    wf = fetchone("SELECT payload FROM workflows WHERE workflow_id=%s", (workflow_id,))
    if not wf:
        return
    payload = wf["payload"]
    symbol = payload["symbol"]
    side = payload["side"]
    qty = float(payload["qty"])
    fill_price = 100 + (hash(symbol) % 1000) / 10.0 + random.uniform(-0.2, 0.2)

    order_id = str(uuid.uuid4())
    execute(
        "INSERT INTO orders(order_id, workflow_id, status, symbol, side, qty, fill_price) VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (order_id, workflow_id, "FILLED", symbol, side, qty, fill_price),
    )

    correlation_id = msg.get("correlation_id") or str(uuid.uuid4())
    data = {"order_id": order_id, "workflow_id": workflow_id, "symbol": symbol, "side": side, "qty": qty, "fill_price": fill_price}
    await publish_audit("order.filled", order_id, data, correlation_id)

    event = {
        "event_id": str(uuid.uuid4()),
        "event_type": "orders.filled",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "correlation_id": correlation_id,
        "payload": data,
    }
    await publish("orders.filled", event, key=order_id)
    log.info("paper filled order_id=%s workflow_id=%s", order_id, workflow_id)

async def main():
    cons = consumer(["workflow.approved"], group_id="paper-oms")
    await consume_forever(cons, handler)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
