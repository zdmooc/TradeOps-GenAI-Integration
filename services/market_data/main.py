import uuid
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from services.common.logging import setup_logging
from services.common.metrics import install
from services.common.kafka import publish

log = setup_logging("market-data")

app = FastAPI(title="Market Data API", version="0.1")
install(app, "market-data")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/metrics")
def metrics():
    return PlainTextResponse(generate_latest().decode("utf-8"), media_type=CONTENT_TYPE_LATEST)

@app.get("/prices/{symbol}")
def get_prices(symbol: str):
    # Demo: returns synthetic last price
    price = 100 + (hash(symbol) % 1000) / 10.0
    return {"symbol": symbol.upper(), "last": price, "ts": datetime.now(timezone.utc).isoformat()}

@app.post("/publish/{symbol}")
async def publish_price(symbol: str):
    # Publish a market.prices event (synthetic)
    correlation_id = str(uuid.uuid4())
    price = 100 + (hash(symbol) % 1000) / 10.0
    event = {
        "event_id": str(uuid.uuid4()),
        "event_type": "market.prices",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "correlation_id": correlation_id,
        "payload": {"symbol": symbol.upper(), "last": price},
    }
    await publish("market.prices", event, key=symbol.upper())
    log.info("published market.prices symbol=%s price=%s corr=%s", symbol, price, correlation_id)
    return {"published": True, "event": event}
