from __future__ import annotations

import math
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict


class WalkForwardGateResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    split_count: int
    pass_count: int
    pass_rate: float
    min_splits: int
    min_pass_rate: float
    passed: bool
    blocked_reasons: list[str]


def evaluate_walk_forward_gate(
    split_expectancies: Sequence[float],
    *,
    min_splits: int = 3,
    min_pass_rate: float = 1.0,
    expectancy_floor: float = 0.0,
) -> WalkForwardGateResult:
    min_splits = _require_positive_int("min_splits", min_splits)
    min_pass_rate = _require_pass_rate("min_pass_rate", min_pass_rate)
    expectancy_floor = _require_finite_float("expectancy_floor", expectancy_floor)
    expectancies = [
        _require_finite_float("split_expectancy", expectancy)
        for expectancy in split_expectancies
    ]

    split_count = len(expectancies)
    pass_count = sum(1 for expectancy in expectancies if expectancy > expectancy_floor)
    pass_rate = pass_count / split_count if split_count else 0.0
    blocked_reasons: list[str] = []

    if split_count < min_splits:
        blocked_reasons.append("insufficient_walk_forward_splits")
    if (
        any(expectancy <= expectancy_floor for expectancy in expectancies)
        or pass_rate < min_pass_rate
    ):
        blocked_reasons.append("unstable_walk_forward_performance")

    return WalkForwardGateResult(
        split_count=split_count,
        pass_count=pass_count,
        pass_rate=float(pass_rate),
        min_splits=min_splits,
        min_pass_rate=min_pass_rate,
        passed=not blocked_reasons,
        blocked_reasons=blocked_reasons,
    )


def _require_positive_int(name: str, value: int) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _require_pass_rate(name: str, value: float) -> float:
    value = _require_finite_float(name, value)
    if value <= 0.0 or value > 1.0:
        raise ValueError(f"{name} must be greater than 0 and less than or equal to 1")
    return value


def _require_finite_float(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value
