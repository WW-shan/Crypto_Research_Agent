from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from crypto_alpha_agent.data.models import DataSuitability, MarketCandle
from crypto_alpha_agent.data.store import ResearchDataStore
from crypto_alpha_agent.pipeline.data_depth_campaign import (
    CampaignMonth,
    DataDepthCampaignSpec,
    build_data_depth_campaign_report,
    expand_campaign_months,
)


START = datetime(2026, 1, 1, tzinfo=UTC)


def test_expand_campaign_months_is_inclusive_and_chronological():
    months = expand_campaign_months(
        CampaignMonth(year=2026, month=1),
        CampaignMonth(year=2026, month=3),
    )

    assert [(month.year, month.month) for month in months] == [
        (2026, 1),
        (2026, 2),
        (2026, 3),
    ]


def test_campaign_spec_normalizes_symbols_and_preserves_safety_flags():
    spec = DataDepthCampaignSpec(
        symbols=["btcusdt", "ETH/USDT", "ethusdt"],
        timeframe="1h",
        market="um-futures",
        start=CampaignMonth(year=2026, month=1),
        end=CampaignMonth(year=2026, month=3),
        min_unique_months=3,
    )

    assert spec.symbols == ("BTC/USDT", "ETH/USDT")
    assert spec.uses_real_capital is False
    assert spec.live_order_routing is False


def test_campaign_spec_rejects_empty_symbols_and_reversed_ranges():
    with pytest.raises(ValueError, match="symbols"):
        DataDepthCampaignSpec(
            symbols=[],
            timeframe="1h",
            market="um-futures",
            start=CampaignMonth(year=2026, month=1),
            end=CampaignMonth(year=2026, month=3),
            min_unique_months=3,
        )

    with pytest.raises(ValueError, match="end.*before.*start"):
        DataDepthCampaignSpec(
            symbols=["BTC/USDT"],
            timeframe="1h",
            market="um-futures",
            start=CampaignMonth(year=2026, month=4),
            end=CampaignMonth(year=2026, month=3),
            min_unique_months=3,
        )


def test_campaign_models_are_strict():
    with pytest.raises(ValidationError):
        CampaignMonth(year="2026", month=1)

    with pytest.raises(ValidationError):
        CampaignMonth(year=2026, month=1, unexpected="field")

    with pytest.raises(ValidationError):
        DataDepthCampaignSpec(
            symbols=["BTC/USDT"],
            timeframe="1h",
            market="spot",
            start=CampaignMonth(year=2026, month=1),
            end=CampaignMonth(year=2026, month=3),
            min_unique_months=3,
        )


def test_campaign_report_audits_local_month_coverage_read_only(tmp_path):
    db_path = tmp_path / "research.sqlite"
    store = ResearchDataStore(db_path)
    store.upsert_records(
        [
            _market_candle("BTC/USDT", datetime(2026, 1, 1, tzinfo=UTC)),
            _market_candle("BTC/USDT", datetime(2026, 3, 1, tzinfo=UTC)),
        ]
    )
    before = _record_snapshot(db_path)
    spec = DataDepthCampaignSpec(
        symbols=["BTCUSDT"],
        timeframe="1h",
        market="um-futures",
        start=CampaignMonth(year=2026, month=1),
        end=CampaignMonth(year=2026, month=3),
        min_unique_months=3,
    )

    report = build_data_depth_campaign_report(db_path, spec=spec, now=START)

    assert report.generated_at == START
    assert report.readiness == "blocked"
    assert report.reason_codes == ("insufficient_month_coverage",)
    assert len(report.coverage) == 1
    row = report.coverage[0]
    assert row.symbol == "BTC/USDT"
    assert row.requested_months == 3
    assert row.unique_months == 2
    assert [(month.year, month.month) for month in row.missing_months] == [(2026, 2)]
    assert row.readiness == "blocked"
    assert row.reason_codes == ("insufficient_month_coverage",)
    assert len(report.missing_collection_jobs) == 1
    job = report.missing_collection_jobs[0]
    assert job.symbol == "BTC/USDT"
    assert job.timeframe == "1h"
    assert job.market == "um-futures"
    assert job.month == CampaignMonth(year=2026, month=2)
    assert job.status == "planned"
    assert job.uses_real_capital is False
    assert job.live_order_routing is False
    assert _record_snapshot(db_path) == before


def _market_candle(symbol: str, timestamp: datetime):
    return MarketCandle(
        source="binance_public",
        venue="binance_usdm",
        symbol=symbol,
        timestamp=timestamp,
        timeframe="1h",
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.5,
        volume=1000.0,
        suitability=DataSuitability(
            min_capital_usd=25.0,
            latency_dependency="low",
            rpc_dependency="none",
            execution_role="research_and_paper",
        ),
    ).to_source_record()


def _record_snapshot(db_path):
    return [
        record.model_dump(mode="json")
        for record in ResearchDataStore(db_path).load_records()
    ]
