from __future__ import annotations

from datetime import UTC, datetime

import pytest

from crypto_alpha_agent.data.models import FundingRateRecord, SourceRecord
from crypto_alpha_agent.data.store import ResearchDataStore
from crypto_alpha_agent.validation.funding import validate_funding_extremes


def _funding(symbol: str, hour: int, rate: float, *, venue: str = "binance", source: str = "ccxt") -> SourceRecord:
    record = FundingRateRecord(
        source=source,
        venue=venue,
        symbol=symbol,
        timestamp=datetime(2026, 5, 16, hour, tzinfo=UTC),
        funding_rate=rate,
    )
    return SourceRecord(
        record_id=f"{source}:{venue}:{symbol}:{hour}",
        source=source,
        record_type="funding_rate",
        observed_at=record.timestamp,
        payload=record.model_dump(mode="json"),
    )


def test_funding_validator_detects_positive_and_negative_extremes(tmp_path):
    db_path = tmp_path / "research.sqlite"
    ResearchDataStore(db_path).upsert_records(
        [
            _funding("BTC/USDT:USDT", 0, 0.0001),
            _funding("BTC/USDT:USDT", 8, 0.0007),
            _funding("BTC/USDT:USDT", 16, -0.0008),
            _funding("ETH/USDT:USDT", 16, 0.001),
        ]
    )

    result = validate_funding_extremes(
        db_path,
        symbol="BTC/USDT:USDT",
        venue="binance",
        threshold_abs=0.0005,
        min_samples=3,
        min_extremes=2,
    )

    assert result.strategy_family == "funding_extremity"
    assert result.symbol == "BTC/USDT:USDT"
    assert result.venue == "binance"
    assert result.sample_count == 3
    assert result.extreme_count == 2
    assert result.positive_extreme_count == 1
    assert result.negative_extreme_count == 1
    assert result.mean_funding_rate == pytest.approx(0.0)
    assert result.max_abs_funding_rate == 0.0008
    assert result.threshold_abs == 0.0005
    assert result.approved is True
    assert result.blocked_reasons == []


def test_funding_validator_blocks_insufficient_samples_and_missing_extremes(tmp_path):
    db_path = tmp_path / "research.sqlite"
    ResearchDataStore(db_path).upsert_records([_funding("ETH/USDT:USDT", 0, 0.0001)])

    result = validate_funding_extremes(
        db_path,
        symbol="ETH/USDT:USDT",
        threshold_abs=0.0005,
        min_samples=3,
        min_extremes=1,
    )

    assert result.approved is False
    assert result.sample_count == 1
    assert result.extreme_count == 0
    assert "insufficient_samples" in result.blocked_reasons
    assert "no_extreme_funding" in result.blocked_reasons


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"threshold_abs": 0.0}, "threshold_abs must be finite and greater than 0"),
        ({"threshold_abs": float("nan")}, "threshold_abs must be finite and greater than 0"),
        ({"min_samples": 0}, "min_samples must be greater than 0"),
        ({"min_extremes": 0}, "min_extremes must be greater than 0"),
    ],
)
def test_funding_validator_rejects_invalid_threshold_and_minimums(tmp_path, kwargs, message):
    db_path = tmp_path / "research.sqlite"
    ResearchDataStore(db_path)

    with pytest.raises(ValueError, match=message):
        validate_funding_extremes(db_path, **kwargs)
