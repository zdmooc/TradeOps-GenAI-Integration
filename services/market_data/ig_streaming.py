from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from .clock import SystemClock
from .ig_rest import IGSession
from .model import MarketEvent


class IGLightstreamerAdapter:
    """IG PRICE subscription adapter using the official Lightstreamer Python SDK.

    The Lightstreamer import is lazy so replay/tests do not require the streaming SDK.
    """

    FIELDS = ("BIDPRICE1", "ASKPRICE1", "TIMESTAMP", "DLG_FLAG")

    def __init__(
        self,
        session: IGSession,
        on_event: Callable[[MarketEvent], None],
        *,
        client_factory: Callable[..., Any] | None = None,
        subscription_factory: Callable[..., Any] | None = None,
        listener_base: type | None = None,
        clock: Any | None = None,
    ) -> None:
        self.session = session
        self.on_event = on_event
        self.clock = clock or SystemClock()
        self.client_factory = client_factory
        self.subscription_factory = subscription_factory
        self.listener_base = listener_base
        self.client: Any | None = None
        self.subscriptions: list[Any] = []

    def _sdk(self) -> tuple[Callable[..., Any], Callable[..., Any], type]:
        if self.client_factory and self.subscription_factory:
            return self.client_factory, self.subscription_factory, self.listener_base or object
        from lightstreamer.client import LightstreamerClient, Subscription, SubscriptionListener

        return LightstreamerClient, Subscription, SubscriptionListener

    def connect(self) -> None:
        client_factory, _, _ = self._sdk()
        self.client = client_factory(self.session.lightstreamer_endpoint, None)
        self.client.connectionDetails.setUser(self.session.account_id)
        self.client.connectionDetails.setPassword(
            f"CST-{self.session.cst}|XST-{self.session.security_token}"
        )
        self.client.connect()

    def subscribe_prices(self, epics: list[str]) -> Any:
        if self.client is None:
            raise RuntimeError("connect() must be called before subscribe_prices()")
        _, subscription_factory, listener_base = self._sdk()
        items = [f"PRICE:{self.session.account_id}:{epic}" for epic in epics]
        subscription = subscription_factory("MERGE", items, list(self.FIELDS))
        if hasattr(subscription, "setDataAdapter"):
            subscription.setDataAdapter("Pricing")

        outer = self

        class Listener(listener_base):
            def onItemUpdate(self, update: Any) -> None:  # noqa: N802 - SDK callback name
                outer._handle_update(update)

        subscription.addListener(Listener())
        self.client.subscribe(subscription)
        self.subscriptions.append(subscription)
        return subscription

    def disconnect(self) -> None:
        if self.client is None:
            return
        for subscription in list(self.subscriptions):
            self.client.unsubscribe(subscription)
        self.subscriptions.clear()
        self.client.disconnect()
        self.client = None

    def _handle_update(self, update: Any) -> None:
        item = update.getItemName()
        epic = item.split(":", 2)[-1]
        bid_raw = update.getValue("BIDPRICE1")
        ask_raw = update.getValue("ASKPRICE1")
        timestamp_raw = update.getValue("TIMESTAMP")
        status = update.getValue("DLG_FLAG") or "UNKNOWN"
        ingest_time = self.clock.now()
        if timestamp_raw:
            event_time = datetime.fromtimestamp(float(timestamp_raw) / 1000.0, tz=timezone.utc)
            latency_ms = max(0.0, (ingest_time - event_time).total_seconds() * 1000.0)
        else:
            event_time = ingest_time
            latency_ms = None
        event = MarketEvent(
            instrument=epic,
            event_time=event_time,
            ingest_time=ingest_time,
            source="IG_LIGHTSTREAMER",
            bid=float(bid_raw) if bid_raw is not None else None,
            ask=float(ask_raw) if ask_raw is not None else None,
            market_status=str(status).strip(),
            event_type="TICK",
            latency_ms=latency_ms,
            metadata={"lightstreamer_item": item},
        )
        self.on_event(event)
