from datetime import UTC, datetime

import pytest

from crypto_alpha_agent.data.models import FundingRateRecord, MarketCandle, SourceRecord
from crypto_alpha_agent.data.store import ResearchDataStore
from crypto_alpha_agent.validation.funding_price import validate_funding_price_confirmation
from crypto_alpha_agent.validation.gates import (
    WalkForwardGateResult,
    evaluate_walk_forward_gate,
)


def _candle(hour: int, close: float) -> MarketCandle:
    return MarketCandle(
        source="binance_public",
        venue="binance",
        symbol="BTC/USDT",
        timestamp=datetime(2026, 5, 17, hour, tzinfo=UTC),
        timeframe="1h",
        open=close,
        high=close + 1.0,
        low=close - 1.0,
        close=close,
        volume=1000.0,
    )


def _funding(hour: int, rate: float) -> FundingRateRecord:
    return FundingRateRecord(
        source="ccxt",
        venue="binance",
        symbol="BTC/USDT:USDT",
        timestamp=datetime(2026, 5, 17, hour, tzinfo=UTC),
        funding_rate=rate,
    )


def _funding_record(funding: FundingRateRecord) -> SourceRecord:
    safe_symbol = funding.symbol.replace("/", "").replace(":", "-")
    return SourceRecord(
        record_id=f"{funding.source}:{safe_symbol}:funding:{funding.timestamp.isoformat()}",
        source=funding.source,
        record_type="funding_rate",
        observed_at=funding.timestamp,
        payload=funding.model_dump(mode="json"),
    )


def test_walk_forward_gate_blocks_missing_splits():
    result = evaluate_walk_forward_gate([], min_splits=3, min_pass_rate=0.67)

    assert result.passed is False
    assert result.split_count == 0
    assert result.pass_rate == 0.0
    assert result.blocked_reasons == ["insufficient_walk_forward_splits"]


def test_walk_forward_gate_blocks_low_pass_rate_and_unstable_expectancy():
    result = evaluate_walk_forward_gate(
        [0.01, -0.02, 0.03],
        min_splits=3,
        min_pass_rate=0.67,
    )

    assert result.passed is False
    assert result.split_count == 3
    assert result.pass_rate == 2 / 3
    assert "unstable_walk_forward_performance" in result.blocked_reasons


def test_walk_forward_gate_passes_consistent_positive_splits():
    result = evaluate_walk_forward_gate(
        [0.01, 0.02, 0.03],
        min_splits=3,
        min_pass_rate=0.67,
    )

    assert isinstance(result, WalkForwardGateResult)
    assert result.passed is True
    assert result.blocked_reasons == []


def test_funding_price_validator_requires_walk_forward_splits_for_short_history(tmp_path):
    db_path = tmp_path / "research.sqlite"
    store = ResearchDataStore(db_path)
    store.upsert_records(
        [
            _candle(0, 100.0).to_source_record(),
            _candle(1, 101.0).to_source_record(),
            _candle(2, 99.0).to_source_record(),
        ]
    )
    store.upsert_records([_funding_record(_funding(1, 0.0008))])

    result = validate_funding_price_confirmation(
        db_path,
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
    )

    assert result.approved is False
    assert "insufficient_walk_forward_splits" in result.blocked_reasons


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"min_splits": 0}, "min_splits"),
        ({"min_pass_rate": 0.0}, "min_pass_rate"),
        ({"min_pass_rate": 1.1}, "min_pass_rate"),
    ],
)
def test_walk_forward_gate_rejects_invalid_policy(kwargs, match):
    with pytest.raises(ValueError, match=match):
        evaluate_walk_forward_gate([0.01], **kwargs)
