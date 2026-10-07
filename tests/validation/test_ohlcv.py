from __future__ import annotations

from datetime import UTC, datetime, timedelta

from crypto_alpha_agent.validation.ohlcv import validate_ohlcv_frame


def _valid_frame() -> dict[str, list[object]]:
    start = datetime(2026, 6, 1, tzinfo=UTC)
    return {
        "timestamp": [start + timedelta(hours=index) for index in range(3)],
        "open": [100.0, 101.0, 102.0],
        "high": [101.0, 102.0, 103.0],
        "low": [99.0, 100.0, 101.0],
        "close": [100.5, 101.5, 102.5],
        "volume": [10.0, 0.0, 12.0],
    }


def test_valid_ohlcv_frame_passes_with_no_errors():
    result = validate_ohlcv_frame(_valid_frame())

    assert result.valid is True
    assert result.errors == ()


def test_ohlcv_frame_reports_missing_required_columns_stably():
    frame = _valid_frame()
    del frame["volume"]
    del frame["low"]

    result = validate_ohlcv_frame(frame)

    assert result.valid is False
    assert result.errors == ("missing required columns: low, volume",)


def test_ohlcv_frame_rejects_timestamps_that_are_not_increasing():
    frame = _valid_frame()
    frame["timestamp"] = [frame["timestamp"][0], frame["timestamp"][2], frame["timestamp"][1]]

    result = validate_ohlcv_frame(frame)

    assert result.valid is False
    assert result.errors == ("timestamp values must be strictly increasing",)


def test_ohlcv_frame_rejects_duplicate_timestamps():
    frame = _valid_frame()
    duplicate = frame["timestamp"][1]
    frame["timestamp"] = [frame["timestamp"][0], duplicate, duplicate]

    result = validate_ohlcv_frame(frame)

    assert result.valid is False
    assert result.errors == (
        "timestamp contains duplicate values: 2026-06-01 01:00:00+00:00",
    )


def test_ohlcv_frame_rejects_columns_with_different_lengths():
    frame = _valid_frame()
    frame["volume"].pop()

    result = validate_ohlcv_frame(frame)

    assert result.valid is False
    assert result.errors == ("column length mismatch: timestamp=3, volume=2",)


def test_ohlcv_frame_rejects_negative_numeric_fields():
    frame = _valid_frame()
    frame["open"][1] = -1.0
    frame["volume"][2] = -0.5

    result = validate_ohlcv_frame(frame)

    assert result.valid is False
    assert result.errors == (
        "open contains negative values at rows: 1",
        "volume contains negative values at rows: 2",
    )
