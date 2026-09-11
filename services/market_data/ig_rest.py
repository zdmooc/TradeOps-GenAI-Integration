from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import httpx

from .clock import SystemClock
from .model import MarketEvent, parse_utc


@dataclass(frozen=True)
class IGSession:
    account_id: str
    cst: str
    security_token: str
    lightstreamer_endpoint: str


class IGRestClient:
    DEMO_BASE_URL = "https://demo-api.ig.com/gateway/deal"
    LIVE_BASE_URL = "https://api.ig.com/gateway/deal"

    def __init__(
        self,
        *,
        api_key: str,
        identifier: str,
        password: str,
        base_url: str = DEMO_BASE_URL,
        client: httpx.Client | None = None,
        clock: Any | None = None,
    ) -> None:
        self.api_key = api_key
        self.identifier = identifier
        self.password = password
        self.base_url = base_url.rstrip("/")
        self.client = client or httpx.Client(timeout=15.0)
        self.clock = clock or SystemClock()
        self.session: IGSession | None = None

    def _base_headers(self, version: str) -> dict[str, str]:
        return {
            "X-IG-API-KEY": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json; charset=UTF-8",
            "Version": version,
        }

    def authenticate_v2(self) -> IGSession:
        response = self.client.post(
            f"{self.base_url}/session",
            headers=self._base_headers("2"),
            json={
                "identifier": self.identifier,
                "password": self.password,
                "encryptedPassword": False,
            },
        )
        response.raise_for_status()
        payload = response.json()
        cst = response.headers.get("CST")
        xst = response.headers.get("X-SECURITY-TOKEN")
        if not cst or not xst:
            raise RuntimeError("IG authentication response missing CST/X-SECURITY-TOKEN")
        account_id = payload.get("currentAccountId") or payload.get("accountId")
        endpoint = payload.get("lightstreamerEndpoint")
        if not account_id or not endpoint:
            raise RuntimeError("IG authentication response missing account or Lightstreamer endpoint")
        self.session = IGSession(account_id, cst, xst, endpoint)
        return self.session

    def _auth_headers(self, version: str) -> dict[str, str]:
        if self.session is None:
            raise RuntimeError("authenticate_v2() must be called first")
        headers = self._base_headers(version)
        headers.update(
            {
                "CST": self.session.cst,
                "X-SECURITY-TOKEN": self.session.security_token,
            }
        )
        return headers

    def historical_prices(
        self,
        epic: str,
        *,
        resolution: str = "MINUTE",
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        max_points: int = 100,
        page_size: int = 100,
    ) -> list[MarketEvent]:
        params: dict[str, Any] = {
            "resolution": resolution,
            "pageSize": page_size,
            "pageNumber": 1,
        }
        if from_time is not None:
            params["from"] = from_time.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        if to_time is not None:
            params["to"] = to_time.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        if from_time is None and to_time is None:
            params["max"] = max_points

        events: list[MarketEvent] = []
        safe_epic = quote(epic, safe="")
        while True:
            response = self.client.get(
                f"{self.base_url}/prices/{safe_epic}",
                headers=self._auth_headers("3"),
                params=params,
            )
            response.raise_for_status()
            payload = response.json()
            instrument_type = payload.get("instrumentType")
            for raw in payload.get("prices", []):
                events.append(self._normalise_historical(epic, resolution, instrument_type, raw))
            page = payload.get("metadata", {}).get("pageData", {})
            current = int(page.get("pageNumber", params["pageNumber"]))
            total = int(page.get("totalPages", current))
            if current >= total:
                break
            params["pageNumber"] = current + 1
        return events

    def _normalise_historical(
        self,
        epic: str,
        resolution: str,
        instrument_type: str | None,
        raw: dict[str, Any],
    ) -> MarketEvent:
        close = raw.get("closePrice") or {}
        event_time = parse_utc(raw.get("snapshotTimeUTC") or raw.get("snapshotTime"))
        ingest_time = self.clock.now()
        bid = close.get("bid")
        ask = close.get("ask")
        last = close.get("lastTraded")
        return MarketEvent(
            instrument=epic,
            event_time=event_time,
            ingest_time=ingest_time,
            source="IG_REST",
            bid=float(bid) if bid is not None else None,
            ask=float(ask) if ask is not None else None,
            last=float(last) if last is not None else None,
            market_status="HISTORICAL",
            event_type="BAR",
            resolution=resolution,
            latency_ms=None,
            metadata={
                "instrument_type": instrument_type,
                "open": raw.get("openPrice"),
                "high": raw.get("highPrice"),
                "low": raw.get("lowPrice"),
                "close": raw.get("closePrice"),
                "last_traded_volume": raw.get("lastTradedVolume"),
            },
        )
