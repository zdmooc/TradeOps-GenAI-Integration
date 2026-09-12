from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from .clock import SystemClock
from .model import MarketEvent


class KrakenOHLCClient:
    """Public Kraken Spot OHLC adapter normalized to the canonical MarketEvent model."""

    BASE_URL = "https://api.kraken.com/0/public/OHLC"

    def __init__(
        self,
        *,
        base_url: str = BASE_URL,
        client: httpx.Client | None = None,
        clock: Any | None = None,
    ) -> None:
        self.base_url = base_url
        self.client = client or httpx.Client(timeout=15.0)
        self.clock = clock or SystemClock()

    def ohlc(
        self,
        pair: str,
        *,
        interval: int = 1,
        since: int | None = None,
        limit: int | None = 20,
        committed_only: bool = True,
    ) -> list[MarketEvent]:
        params: dict[str, Any] = {
            "pair": pair,
            "interval": interval,
            "assetVersion": 1,
        }
        if since is not None:
            params["since"] = int(since)

        response = self.client.get(self.base_url, params=params)
        response.raise_for_status()
        payload = response.json()

        errors = payload.get("error") or []
        if errors:
            raise RuntimeError(f"Kraken OHLC returned API errors: {errors!r}")

        result = payload.get("result")
        if not isinstance(result, dict):
            raise RuntimeError("Kraken OHLC response missing result object")

        pair_keys = [key for key in result if key != "last"]
        if len(pair_keys) != 1:
            raise RuntimeError(f"Kraken OHLC expected one pair result, got {pair_keys!r}")

        response_pair = pair_keys[0]
        rows = result.get(response_pair)
        if not isinstance(rows, list):
            raise RuntimeError("Kraken OHLC pair result must be a list")

        selected = rows[:-1] if committed_only and rows else rows
        if limit is not None:
            if limit <= 0:
                raise ValueError("limit must be positive when provided")
            selected = selected[-limit:]

        ingest_time = self.clock.now()
        events: list[MarketEvent] = []
        for index, row in enumerate(selected):
            if not isinstance(row, list) or len(row) < 8:
                raise RuntimeError(f"Kraken OHLC row {index} is malformed")

            event_time = datetime.fromtimestamp(int(row[0]), tz=timezone.utc)
            resolution = "MINUTE" if interval == 1 else f"MINUTE_{interval}"
            events.append(
                MarketEvent(
                    instrument=response_pair,
                    event_time=event_time,
                    ingest_time=ingest_time,
                    source="KRAKEN_REST",
                    last=float(row[4]),
                    market_status="HISTORICAL_COMMITTED" if committed_only else "LIVE_OR_COMMITTED",
                    event_type="BAR",
                    resolution=resolution,
                    metadata={
                        "requested_pair": pair,
                        "response_pair": response_pair,
                        "open": float(row[1]),
                        "high": float(row[2]),
                        "low": float(row[3]),
                        "close": float(row[4]),
                        "vwap": float(row[5]),
                        "volume": float(row[6]),
                        "trade_count": int(row[7]),
                        "committed": committed_only,
                    },
                )
            )
        return events
