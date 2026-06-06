from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math
from numbers import Real
from typing import Any


REQUIRED_OHLCV_COLUMNS: tuple[str, ...] = (
    "timestamp",
    "open",
    "high",
    "low",
    "close",
    "volume",
)
NUMERIC_OHLCV_COLUMNS: tuple[str, ...] = ("open", "high", "low", "close", "volume")


@dataclass(frozen=True)
class OhlcvValidationResult:
    valid: bool
    errors: tuple[str, ...]


def validate_ohlcv_frame(frame: Mapping[str, Sequence[Any]]) -> OhlcvValidationResult:
    """Validate a column-oriented OHLCV frame without requiring pandas."""
    errors: list[str] = []
    missing_columns = [
        column for column in REQUIRED_OHLCV_COLUMNS if column not in frame
    ]
    if missing_columns:
        errors.append(
            f"missing required columns: {', '.join(missing_columns)}"
        )

    if "timestamp" in frame:
        errors.extend(_timestamp_errors(frame["timestamp"]))

    for column in NUMERIC_OHLCV_COLUMNS:
        if column in frame:
            errors.extend(_numeric_column_errors(column, frame[column]))

    return OhlcvValidationResult(valid=not errors, errors=tuple(errors))


def _timestamp_errors(values: Sequence[Any]) -> list[str]:
    errors: list[str] = []
    duplicates = [
        value for value, count in Counter(values).items() if count > 1
    ]
    if duplicates:
        formatted = ", ".join(str(value) for value in sorted(duplicates))
        errors.append(f"timestamp contains duplicate values: {formatted}")
        return errors

    try:
        if any(current <= previous for previous, current in zip(values, values[1:], strict=False)):
            errors.append("timestamp values must be strictly increasing")
    except TypeError:
        errors.append("timestamp values must be comparable and strictly increasing")

    return errors


def _numeric_column_errors(column: str, values: Sequence[Any]) -> list[str]:
    invalid_rows: list[int] = []
    negative_rows: list[int] = []
    for index, value in enumerate(values):
        if not _is_finite_real(value):
            invalid_rows.append(index)
            continue
        if value < 0:
            negative_rows.append(index)

    errors: list[str] = []
    if invalid_rows:
        errors.append(
            f"{column} contains non-numeric values at rows: {_format_rows(invalid_rows)}"
        )
    if negative_rows:
        errors.append(
            f"{column} contains negative values at rows: {_format_rows(negative_rows)}"
        )
    return errors


def _is_finite_real(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, Real):
        return False
    return math.isfinite(float(value))


def _format_rows(rows: Sequence[int]) -> str:
    return ", ".join(str(row) for row in rows)
