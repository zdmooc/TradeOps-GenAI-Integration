from datetime import datetime, timedelta, timezone

import httpx

from services.market_data.clock import DeterministicClock
from services.market_data.ig_rest import IGRestClient, IGSession
from services.market_data.ig_streaming import IGLightstreamerAdapter
from services.market_data.kraken_rest import KrakenOHLCClient
from services.market_data.model import MarketEvent
from services.market_data.quality import DataQualityEngine, QualityReason
from services.market_data.replay import ReplayEngine

UTC = timezone.utc
BASE = datetime(2026, 9, 11, 12, 0, tzinfo=UTC)


def event(**overrides):
    data = dict(
        instrument="IX.D.DAX.IFM.IP",
        event_time=BASE,
        ingest_time=BASE,
        source="TEST",
        bid=23500.0,
        ask=23501.0,
        event_id="evt-1",
    )
    data.update(overrides)
    return MarketEvent(**data)


def test_market_event_roundtrip_and_spread():
    original = event()
    restored = MarketEvent.from_dict(original.to_dict())
    assert restored.instrument == original.instrument
    assert restored.spread == 1.0
    assert restored.event_time == BASE


def test_quality_rejects_stale_bad_spread_duplicate_and_out_of_order():
    quality = DataQualityEngine(stale_after=timedelta(seconds=5), max_out_of_order=timedelta(0))
    stale = quality.evaluate(
        event(event_time=BASE - timedelta(seconds=6), event_id="stale"), now=BASE
    )
    assert not stale.accepted and QualityReason.STALE in stale.reasons

    bad = quality.evaluate(event(ask=23499.0, event_id="bad"), now=BASE)
    assert not bad.accepted and QualityReason.BAD_SPREAD in bad.reasons

    first = event(event_id="first")
    assert quality.evaluate(first, now=BASE).accepted
    duplicate = quality.evaluate(first, now=BASE)
    assert not duplicate.accepted and QualityReason.DUPLICATE in duplicate.reasons

    older = event(event_time=BASE - timedelta(seconds=1), event_id="older")
    out = quality.evaluate(older, now=BASE)
    assert not out.accepted and QualityReason.OUT_OF_ORDER in out.reasons


def test_replay_is_deterministic_and_sorts_by_event_time(tmp_path):
    events = [
        event(event_time=BASE + timedelta(seconds=2), event_id="b", bid=2, ask=3),
        event(event_time=BASE, event_id="a", bid=1, ask=2),
    ]
    path = tmp_path / "capture.jsonl"
    ReplayEngine.write_jsonl(path, events)
    loaded = ReplayEngine.load_jsonl(path)
    r1 = ReplayEngine().replay(loaded)
    r2 = ReplayEngine().replay(loaded)
    assert [e.event_id for e in r1.accepted] == ["a", "b"]
    assert [e.to_dict() for e in r1.accepted] == [e.to_dict() for e in r2.accepted]


def test_ig_rest_auth_and_historical_normalization():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/session"):
            assert request.headers["Version"] == "2"
            return httpx.Response(
                200,
                headers={"CST": "cst", "X-SECURITY-TOKEN": "xst"},
                json={
                    "currentAccountId": "ABC123",
                    "lightstreamerEndpoint": "https://push.example",
                },
            )
        assert request.url.path.endswith("/prices/IX.D.DAX.IFM.IP")
        assert request.headers["Version"] == "3"
        return httpx.Response(
            200,
            json={
                "instrumentType": "INDICES",
                "prices": [
                    {
                        "snapshotTimeUTC": "2026-09-11T11:59:00Z",
                        "openPrice": {"bid": 23490.0, "ask": 23491.0},
                        "highPrice": {"bid": 23510.0, "ask": 23511.0},
                        "lowPrice": {"bid": 23480.0, "ask": 23481.0},
                        "closePrice": {
                            "bid": 23500.0,
                            "ask": 23501.0,
                            "lastTraded": None,
                        },
                        "lastTradedVolume": None,
                    }
                ],
                "metadata": {"pageData": {"pageNumber": 1, "totalPages": 1}},
            },
        )

    clock = DeterministicClock(BASE)
    client = httpx.Client(transport=httpx.MockTransport(handler))
    ig = IGRestClient(api_key="k", identifier="u", password="p", client=client, clock=clock)
    session = ig.authenticate_v2()
    assert session.account_id == "ABC123"
    events = ig.historical_prices("IX.D.DAX.IFM.IP", max_points=1)
    assert len(events) == 1
    assert events[0].source == "IG_REST"
    assert events[0].spread == 1.0
    assert events[0].resolution == "MINUTE"


def test_kraken_public_ohlc_normalization_uses_committed_bars_only():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/0/public/OHLC"
        assert request.url.params["pair"] == "XBTUSD"
        assert request.url.params["interval"] == "1"
        assert request.url.params["assetVersion"] == "1"
        return httpx.Response(
            200,
            json={
                "error": [],
                "result": {
                    "BTC/USD": [
                        [
                            int(BASE.timestamp()),
                            "60000.0",
                            "60010.0",
                            "59990.0",
                            "60005.0",
                            "60003.0",
                            "12.5",
                            42,
                        ],
                        [
                            int((BASE + timedelta(minutes=1)).timestamp()),
                            "60005.0",
                            "60015.0",
                            "60000.0",
                            "60012.0",
                            "60009.0",
                            "8.1",
                            31,
                        ],
                    ],
                    "last": int((BASE + timedelta(minutes=1)).timestamp()),
                },
            },
        )

    clock = DeterministicClock(BASE + timedelta(minutes=2))
    client = httpx.Client(transport=httpx.MockTransport(handler))
    kraken = KrakenOHLCClient(client=client, clock=clock)
    events = kraken.ohlc("XBTUSD", interval=1, limit=10, committed_only=True)

    assert len(events) == 1
    assert events[0].source == "KRAKEN_REST"
    assert events[0].instrument == "BTC/USD"
    assert events[0].event_time == BASE
    assert events[0].last == 60005.0
    assert events[0].resolution == "MINUTE"
    assert events[0].metadata["committed"] is True
    assert events[0].metadata["trade_count"] == 42


class FakeConnectionDetails:
    def __init__(self):
        self.user = self.password = None

    def setUser(self, value):
        self.user = value

    def setPassword(self, value):
        self.password = value


class FakeClient:
    def __init__(self, endpoint, adapter_set):
        self.endpoint = endpoint
        self.adapter_set = adapter_set
        self.connectionDetails = FakeConnectionDetails()
        self.subscriptions = []
        self.connected = False

    def connect(self):
        self.connected = True

    def subscribe(self, sub):
        self.subscriptions.append(sub)

    def unsubscribe(self, sub):
        self.subscriptions.remove(sub)

    def disconnect(self):
        self.connected = False


class FakeSubscription:
    def __init__(self, mode, items, fields):
        self.mode, self.items, self.fields = mode, items, fields
        self.listener = None
        self.adapter = None

    def setDataAdapter(self, value):
        self.adapter = value

    def addListener(self, listener):
        self.listener = listener


class FakeUpdate:
    def getItemName(self):
        return "PRICE:ABC123:IX.D.DAX.IFM.IP"

    def getValue(self, field):
        return {
            "BIDPRICE1": "23500.0",
            "ASKPRICE1": "23501.0",
            "TIMESTAMP": str(int(BASE.timestamp() * 1000)),
            "DLG_FLAG": "DEAL",
        }.get(field)


def test_lightstreamer_adapter_maps_price_subscription_to_market_event():
    captured = []
    clock = DeterministicClock(BASE + timedelta(milliseconds=150))
    adapter = IGLightstreamerAdapter(
        IGSession("ABC123", "cst", "xst", "https://push.example"),
        captured.append,
        client_factory=FakeClient,
        subscription_factory=FakeSubscription,
        clock=clock,
    )
    adapter.connect()
    sub = adapter.subscribe_prices(["IX.D.DAX.IFM.IP"])
    assert sub.adapter == "Pricing"
    assert sub.items == ["PRICE:ABC123:IX.D.DAX.IFM.IP"]
    sub.listener.onItemUpdate(FakeUpdate())
    assert len(captured) == 1
    assert captured[0].source == "IG_LIGHTSTREAMER"
    assert captured[0].latency_ms == 150.0
    assert captured[0].market_status == "DEAL"
    adapter.disconnect()
