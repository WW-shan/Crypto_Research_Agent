from __future__ import annotations

import importlib
from datetime import UTC, datetime

import pytest

import crypto_alpha_agent.data.models as data_models
from crypto_alpha_agent.data.store import ResearchDataStore


class FakeResponse:
    def __init__(self, payload, *, status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code < 200 or self.status_code >= 300:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, payload) -> None:
        self.payload = payload
        self.calls: list[tuple[str, dict]] = []

    def get(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse(self.payload)


def _model(name: str):
    assert hasattr(data_models, name), f"missing data model: {name}"
    return getattr(data_models, name)


def _client_class():
    module = importlib.import_module("crypto_alpha_agent.data.binance_usdm_derivatives")
    assert hasattr(module, "BinanceUsdmDerivativesClient")
    return module.BinanceUsdmDerivativesClient


def _ingestion_function(name: str):
    module = importlib.import_module("crypto_alpha_agent.data.ingestion")
    assert hasattr(module, name), f"missing ingestion function: {name}"
    return getattr(module, name)


class FakeBinanceUsdmDerivativesClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def fetch_premium_index_klines(
        self,
        *,
        symbol: str,
        interval: str,
        limit: int | None = None,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
    ):
        self.calls.append(
            (
                "premium_index_klines",
                {
                    "symbol": symbol,
                    "interval": interval,
                    "limit": limit,
                    "start_time_ms": start_time_ms,
                    "end_time_ms": end_time_ms,
                },
            )
        )
        return [
            data_models.PremiumIndexKlineRecord(
                source="binance_usdm",
                venue="binance",
                symbol=symbol,
                timestamp=datetime(2026, 6, 8, 1, 0, tzinfo=UTC),
                interval=interval,
                open=-0.0004,
                high=0.0002,
                low=-0.0006,
                close=-0.0001,
                raw={"feed": "premium_index_klines"},
            )
        ]

    def fetch_basis(
        self,
        *,
        pair: str,
        contract_type: str,
        period: str,
        limit: int | None = None,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
    ):
        self.calls.append(
            (
                "basis",
                {
                    "pair": pair,
                    "contract_type": contract_type,
                    "period": period,
                    "limit": limit,
                    "start_time_ms": start_time_ms,
                    "end_time_ms": end_time_ms,
                },
            )
        )
        return [
            data_models.BasisRecord(
                source="binance_usdm",
                venue="binance",
                pair=pair,
                contract_type=contract_type,
                period=period,
                timestamp=datetime(2026, 6, 8, 1, 0, tzinfo=UTC),
                index_price=100000.0,
                futures_price=100025.0,
                basis=25.0,
                basis_rate=0.00025,
                annualized_basis_rate=None,
                raw={"feed": "basis"},
            )
        ]

    def fetch_global_long_short_account_ratio(
        self,
        *,
        symbol: str,
        period: str,
        limit: int | None = None,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
    ):
        self.calls.append(
            (
                "global_long_short_account_ratio",
                {
                    "symbol": symbol,
                    "period": period,
                    "limit": limit,
                    "start_time_ms": start_time_ms,
                    "end_time_ms": end_time_ms,
                },
            )
        )
        return [
            data_models.LongShortRatioRecord(
                source="binance_usdm",
                venue="binance",
                symbol=symbol,
                period=period,
                timestamp=datetime(2026, 6, 8, 1, 0, tzinfo=UTC),
                long_short_ratio=1.25,
                long_account=0.5556,
                short_account=0.4444,
                raw={"feed": "global_long_short_account_ratio"},
            )
        ]

    def fetch_taker_buy_sell_volume(
        self,
        *,
        symbol: str,
        period: str,
        limit: int | None = None,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
    ):
        self.calls.append(
            (
                "taker_buy_sell_volume",
                {
                    "symbol": symbol,
                    "period": period,
                    "limit": limit,
                    "start_time_ms": start_time_ms,
                    "end_time_ms": end_time_ms,
                },
            )
        )
        return [
            data_models.TakerBuySellVolumeRecord(
                source="binance_usdm",
                venue="binance",
                symbol=symbol,
                period=period,
                timestamp=datetime(2026, 6, 8, 1, 0, tzinfo=UTC),
                buy_sell_ratio=1.5,
                buy_volume=150.0,
                sell_volume=100.0,
                raw={"feed": "taker_buy_sell_volume"},
            )
        ]

    def fetch_funding_rate_history(
        self,
        *,
        symbol: str,
        limit: int | None = None,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
    ):
        self.calls.append(
            (
                "funding_rate_history",
                {
                    "symbol": symbol,
                    "limit": limit,
                    "start_time_ms": start_time_ms,
                    "end_time_ms": end_time_ms,
                },
            )
        )
        return [
            data_models.FundingRateRecord(
                source="binance_usdm",
                venue="binance",
                symbol=symbol,
                timestamp=datetime(2026, 6, 8, 0, 0, tzinfo=UTC),
                funding_rate=0.0001,
                raw={"feed": "funding_rate_history", "row": 0},
            ),
            data_models.FundingRateRecord(
                source="binance_usdm",
                venue="binance",
                symbol=symbol,
                timestamp=datetime(2026, 6, 8, 8, 0, tzinfo=UTC),
                funding_rate=-0.0002,
                raw={"feed": "funding_rate_history", "row": 1},
            ),
        ]

    def fetch_open_interest_history(
        self,
        *,
        symbol: str,
        period: str,
        limit: int | None = None,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
    ):
        self.calls.append(
            (
                "open_interest_history",
                {
                    "symbol": symbol,
                    "period": period,
                    "limit": limit,
                    "start_time_ms": start_time_ms,
                    "end_time_ms": end_time_ms,
                },
            )
        )
        return [
            data_models.OpenInterestRecord(
                source="binance_usdm",
                venue="binance",
                symbol=symbol,
                timestamp=datetime(2026, 6, 8, 0, 0, tzinfo=UTC),
                timeframe=period,
                open_interest=12345.0,
                open_interest_value=123450000.0,
                raw={"feed": "open_interest_history", "row": 0},
            ),
            data_models.OpenInterestRecord(
                source="binance_usdm",
                venue="binance",
                symbol=symbol,
                timestamp=datetime(2026, 6, 8, 1, 0, tzinfo=UTC),
                timeframe=period,
                open_interest=12350.0,
                open_interest_value=123500000.0,
                raw={"feed": "open_interest_history", "row": 1},
            ),
        ]


def test_premium_index_kline_record_round_trips_to_source_record():
    PremiumIndexKlineRecord = _model("PremiumIndexKlineRecord")
    observed_at = datetime(2026, 6, 8, 1, 0, tzinfo=UTC)
    record = PremiumIndexKlineRecord(
        source="binance_usdm",
        venue="binance",
        symbol="BTCUSDT",
        timestamp=observed_at,
        interval="1h",
        open=-0.0004,
        high=0.0002,
        low=-0.0006,
        close=-0.0001,
        raw={"row": [1780870800000, "-0.0004", "0.0002", "-0.0006", "-0.0001"]},
    )

    source_record = record.to_source_record()

    assert source_record.source == "binance_usdm"
    assert source_record.record_type == "premium_index_kline"
    assert source_record.observed_at == observed_at
    assert source_record.payload["symbol"] == "BTCUSDT"
    assert source_record.payload["close"] == -0.0001
    assert source_record.payload["suitability"]["execution_role"] == "research_and_paper"
    assert source_record.payload["suitability"]["rpc_dependency"] == "none"
    assert "BTCUSDT" in source_record.record_id


def test_basis_record_round_trips_to_source_record():
    BasisRecord = _model("BasisRecord")
    observed_at = datetime(2026, 6, 8, 1, 0, tzinfo=UTC)
    record = BasisRecord(
        source="binance_usdm",
        venue="binance",
        pair="BTCUSDT",
        contract_type="PERPETUAL",
        period="1h",
        timestamp=observed_at,
        index_price=100000.0,
        futures_price=100025.0,
        basis=25.0,
        basis_rate=0.00025,
        annualized_basis_rate=None,
        raw={"basis": "25.0"},
    )

    source_record = record.to_source_record()

    assert source_record.source == "binance_usdm"
    assert source_record.record_type == "basis"
    assert source_record.payload["pair"] == "BTCUSDT"
    assert source_record.payload["contract_type"] == "PERPETUAL"
    assert source_record.payload["basis_rate"] == 0.00025
    assert "perpetual" in source_record.record_id


def test_long_short_ratio_record_round_trips_to_source_record():
    LongShortRatioRecord = _model("LongShortRatioRecord")
    observed_at = datetime(2026, 6, 8, 1, 0, tzinfo=UTC)
    record = LongShortRatioRecord(
        source="binance_usdm",
        venue="binance",
        symbol="BTCUSDT",
        period="1h",
        timestamp=observed_at,
        long_short_ratio=1.25,
        long_account=0.5556,
        short_account=0.4444,
        raw={"longShortRatio": "1.25"},
    )

    source_record = record.to_source_record()

    assert source_record.source == "binance_usdm"
    assert source_record.record_type == "long_short_account_ratio"
    assert source_record.payload["long_short_ratio"] == 1.25
    assert source_record.payload["long_account"] == 0.5556
    assert source_record.payload["short_account"] == 0.4444
    assert "BTCUSDT" in source_record.record_id


def test_taker_buy_sell_volume_record_round_trips_to_source_record():
    TakerBuySellVolumeRecord = _model("TakerBuySellVolumeRecord")
    observed_at = datetime(2026, 6, 8, 1, 0, tzinfo=UTC)
    record = TakerBuySellVolumeRecord(
        source="binance_usdm",
        venue="binance",
        symbol="BTCUSDT",
        period="1h",
        timestamp=observed_at,
        buy_sell_ratio=1.5,
        buy_volume=150.0,
        sell_volume=100.0,
        raw={"buySellRatio": "1.5"},
    )

    source_record = record.to_source_record()

    assert source_record.source == "binance_usdm"
    assert source_record.record_type == "taker_buy_sell_volume"
    assert source_record.payload["buy_sell_ratio"] == 1.5
    assert source_record.payload["buy_volume"] == 150.0
    assert source_record.payload["sell_volume"] == 100.0
    assert source_record.payload["live_order_routing"] is False


def test_funding_rate_record_round_trips_to_source_record():
    FundingRateRecord = _model("FundingRateRecord")
    observed_at = datetime(2026, 6, 8, 0, 0, tzinfo=UTC)
    record = FundingRateRecord(
        source="binance_usdm",
        venue="binance",
        symbol="BTCUSDT",
        timestamp=observed_at,
        funding_rate=-0.0002,
        raw={"fundingRate": "-0.0002"},
    )

    source_record = record.to_source_record()

    assert source_record.source == "binance_usdm"
    assert source_record.record_type == "funding_rate"
    assert source_record.observed_at == observed_at
    assert source_record.payload["symbol"] == "BTCUSDT"
    assert source_record.payload["funding_rate"] == -0.0002
    assert ":funding_rate:" in source_record.record_id


def test_client_parses_premium_index_klines():
    Client = _client_class()
    session = FakeSession(
        [
            [
                1780870800000,
                "-0.0004",
                "0.0002",
                "-0.0006",
                "-0.0001",
                "0",
                1780874399999,
                "0",
                12,
                "0",
                "0",
                "0",
            ]
        ]
    )
    client = Client(session=session)

    records = client.fetch_premium_index_klines(
        symbol="BTCUSDT",
        interval="1h",
        limit=1,
    )

    assert len(records) == 1
    assert records[0].source == "binance_usdm"
    assert records[0].venue == "binance"
    assert records[0].symbol == "BTCUSDT"
    assert records[0].timestamp == datetime.fromtimestamp(1780870800, tz=UTC)
    assert records[0].close == -0.0001
    assert session.calls[0][1]["params"]["symbol"] == "BTCUSDT"
    assert session.calls[0][1]["params"]["interval"] == "1h"


def test_client_parses_basis_records():
    Client = _client_class()
    session = FakeSession(
        [
            {
                "indexPrice": "100000.0",
                "contractType": "PERPETUAL",
                "basisRate": "0.00025",
                "futuresPrice": "100025.0",
                "annualizedBasisRate": "",
                "basis": "25.0",
                "pair": "BTCUSDT",
                "timestamp": 1780870800000,
            }
        ]
    )
    client = Client(session=session)

    records = client.fetch_basis(
        pair="BTCUSDT",
        contract_type="PERPETUAL",
        period="1h",
        limit=1,
    )

    assert len(records) == 1
    assert records[0].pair == "BTCUSDT"
    assert records[0].contract_type == "PERPETUAL"
    assert records[0].period == "1h"
    assert records[0].basis == 25.0
    assert records[0].annualized_basis_rate is None
    assert session.calls[0][1]["params"]["contractType"] == "PERPETUAL"


def test_client_parses_global_long_short_account_ratio_records():
    Client = _client_class()
    session = FakeSession(
        [
            {
                "symbol": "BTCUSDT",
                "longShortRatio": "1.2500",
                "longAccount": "0.5556",
                "shortAccount": "0.4444",
                "timestamp": "1780870800000",
            }
        ]
    )
    client = Client(session=session)

    records = client.fetch_global_long_short_account_ratio(
        symbol="BTCUSDT",
        period="1h",
        limit=1,
    )

    assert len(records) == 1
    assert records[0].symbol == "BTCUSDT"
    assert records[0].period == "1h"
    assert records[0].long_short_ratio == 1.25
    assert records[0].long_account == 0.5556
    assert records[0].short_account == 0.4444


def test_client_parses_taker_buy_sell_volume_records():
    Client = _client_class()
    session = FakeSession(
        [
            {
                "buySellRatio": "1.5000",
                "buyVol": "150.0",
                "sellVol": "100.0",
                "timestamp": "1780870800000",
            }
        ]
    )
    client = Client(session=session)

    records = client.fetch_taker_buy_sell_volume(
        symbol="BTCUSDT",
        period="1h",
        limit=1,
    )

    assert len(records) == 1
    assert records[0].symbol == "BTCUSDT"
    assert records[0].period == "1h"
    assert records[0].buy_sell_ratio == 1.5
    assert records[0].buy_volume == 150.0
    assert records[0].sell_volume == 100.0


def test_client_parses_funding_rate_history_records():
    Client = _client_class()
    session = FakeSession(
        [
            {
                "symbol": "BTCUSDT",
                "fundingRate": "-0.00020000",
                "fundingTime": 1780876800000,
            }
        ]
    )
    client = Client(session=session)

    records = client.fetch_funding_rate_history(
        symbol="BTCUSDT",
        limit=1,
        start_time_ms=1780870000000,
        end_time_ms=1780880000000,
    )

    assert len(records) == 1
    assert records[0].source == "binance_usdm"
    assert records[0].venue == "binance"
    assert records[0].symbol == "BTCUSDT"
    assert records[0].timestamp == datetime.fromtimestamp(1780876800, tz=UTC)
    assert records[0].funding_rate == -0.0002
    assert session.calls[0][0].endswith("/fapi/v1/fundingRate")
    assert session.calls[0][1]["params"]["startTime"] == 1780870000000


def test_client_parses_open_interest_history_records():
    Client = _client_class()
    session = FakeSession(
        [
            {
                "sumOpenInterest": "12345.67",
                "sumOpenInterestValue": "123456789.01",
                "timestamp": "1780870800000",
            }
        ]
    )
    client = Client(session=session)

    records = client.fetch_open_interest_history(
        symbol="BTCUSDT",
        period="1h",
        limit=1,
    )

    assert len(records) == 1
    assert records[0].source == "binance_usdm"
    assert records[0].venue == "binance"
    assert records[0].symbol == "BTCUSDT"
    assert records[0].timeframe == "1h"
    assert records[0].timestamp == datetime.fromtimestamp(1780870800, tz=UTC)
    assert records[0].open_interest == 12345.67
    assert records[0].open_interest_value == 123456789.01
    assert session.calls[0][0].endswith("/futures/data/openInterestHist")
    assert session.calls[0][1]["params"]["period"] == "1h"


@pytest.mark.parametrize(
    ("function_name", "kwargs", "feed", "record_type", "call_name"),
    [
        (
            "ingest_binance_usdm_premium_index_klines",
            {"symbol": "BTCUSDT", "interval": "1h", "limit": 1},
            "premium_index_klines",
            "premium_index_kline",
            "premium_index_klines",
        ),
        (
            "ingest_binance_usdm_basis",
            {"pair": "BTCUSDT", "contract_type": "PERPETUAL", "period": "1h", "limit": 1},
            "basis",
            "basis",
            "basis",
        ),
        (
            "ingest_binance_usdm_global_long_short_account_ratio",
            {"symbol": "BTCUSDT", "period": "1h", "limit": 1},
            "global_long_short_account_ratio",
            "long_short_account_ratio",
            "global_long_short_account_ratio",
        ),
        (
            "ingest_binance_usdm_taker_buy_sell_volume",
            {"symbol": "BTCUSDT", "period": "1h", "limit": 1},
            "taker_buy_sell_volume",
            "taker_buy_sell_volume",
            "taker_buy_sell_volume",
        ),
    ],
)
def test_ingest_binance_usdm_derivatives_writes_records_and_source_health(
    tmp_path,
    function_name: str,
    kwargs: dict,
    feed: str,
    record_type: str,
    call_name: str,
):
    db_path = tmp_path / "research.sqlite"
    client = FakeBinanceUsdmDerivativesClient()
    function = _ingestion_function(function_name)

    summary = function(db_path, allow_network=True, client=client, **kwargs)

    store = ResearchDataStore(db_path)
    records = store.load_records(record_type=record_type, source="binance_usdm")
    health = store.load_records(record_type="source_health", source="binance_usdm")
    assert summary.source == "binance_usdm"
    assert summary.feed == feed
    assert summary.records_fetched == 1
    assert summary.records_written == 1
    assert summary.network_allowed is True
    assert summary.uses_real_capital is False
    assert summary.live_order_routing is False
    assert len(records) == 1
    assert records[0].record_type == record_type
    assert health[-1].payload["feed"] == feed
    assert health[-1].payload["success"] is True
    assert client.calls[0][0] == call_name


@pytest.mark.parametrize(
    ("function_name", "kwargs"),
    [
        (
            "ingest_binance_usdm_premium_index_klines",
            {"symbol": "BTCUSDT", "interval": "1h"},
        ),
        (
            "ingest_binance_usdm_basis",
            {"pair": "BTCUSDT", "contract_type": "PERPETUAL", "period": "1h"},
        ),
        (
            "ingest_binance_usdm_global_long_short_account_ratio",
            {"symbol": "BTCUSDT", "period": "1h"},
        ),
        (
            "ingest_binance_usdm_taker_buy_sell_volume",
            {"symbol": "BTCUSDT", "period": "1h"},
        ),
        (
            "ingest_binance_usdm_funding_rate_history",
            {"symbol": "BTCUSDT"},
        ),
        (
            "ingest_binance_usdm_open_interest_history",
            {"symbol": "BTCUSDT", "period": "1h"},
        ),
    ],
)
def test_ingest_binance_usdm_derivatives_requires_network_gate(
    tmp_path,
    function_name: str,
    kwargs: dict,
):
    function = _ingestion_function(function_name)

    with pytest.raises(ValueError, match="allow_network"):
        function(
            tmp_path / "research.sqlite",
            allow_network=False,
            client=FakeBinanceUsdmDerivativesClient(),
            **kwargs,
        )


def test_ingest_binance_usdm_funding_rate_history_writes_records_and_source_health(tmp_path):
    db_path = tmp_path / "research.sqlite"
    client = FakeBinanceUsdmDerivativesClient()
    function = _ingestion_function("ingest_binance_usdm_funding_rate_history")

    summary = function(
        db_path,
        symbol="BTCUSDT",
        limit=2,
        allow_network=True,
        client=client,
    )

    store = ResearchDataStore(db_path)
    records = store.load_records(record_type="funding_rate", source="binance_usdm")
    health = store.load_records(record_type="source_health", source="binance_usdm")
    assert summary.feed == "funding_rate_history"
    assert summary.records_written == 2
    assert len(records) == 2
    assert records[0].record_type == "funding_rate"
    assert health[-1].payload["feed"] == "funding_rate_history"
    assert health[-1].payload["success"] is True
    assert client.calls[0][0] == "funding_rate_history"


def test_ingest_binance_usdm_open_interest_history_writes_records_and_source_health(tmp_path):
    db_path = tmp_path / "research.sqlite"
    client = FakeBinanceUsdmDerivativesClient()
    function = _ingestion_function("ingest_binance_usdm_open_interest_history")

    summary = function(
        db_path,
        symbol="BTCUSDT",
        period="1h",
        limit=2,
        allow_network=True,
        client=client,
    )

    store = ResearchDataStore(db_path)
    records = store.load_records(record_type="open_interest", source="binance_usdm")
    health = store.load_records(record_type="source_health", source="binance_usdm")
    assert summary.feed == "open_interest_history"
    assert summary.records_written == 2
    assert len(records) == 2
    assert records[0].record_type == "open_interest"
    assert health[-1].payload["feed"] == "open_interest_history"
    assert health[-1].payload["success"] is True
    assert client.calls[0][0] == "open_interest_history"
