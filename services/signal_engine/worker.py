import uuid
from datetime import datetime, timezone
from services.common.logging import setup_logging
from services.common.kafka import consumer, consume_forever, publish

log = setup_logging("signal-engine")

async def handler(topic: str, msg: dict):
    if topic != "market.prices":
        return
    p = msg.get("payload", {})
    symbol = p.get("symbol")
    last = float(p.get("last", 0))
    # Demo strategy: simple threshold -> BUY if last ends with .0-.4, SELL if .5-.9 (arbitrary)
    frac = last - int(last)
    side = "BUY" if frac < 0.5 else "SELL"
    correlation_id = msg.get("correlation_id") or str(uuid.uuid4())
    event = {
        "event_id": str(uuid.uuid4()),
        "event_type": "signals.generated",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "correlation_id": correlation_id,
        "payload": {"symbol": symbol, "side": side, "confidence": round(frac, 2), "source_price": last},
    }
    await publish("signals.generated", event, key=symbol)
    log.info("signal generated symbol=%s side=%s price=%s corr=%s", symbol, side, last, correlation_id)

async def main():
    cons = consumer(["market.prices"], group_id="signal-engine")
    await consume_forever(cons, handler)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
