from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class WalkForwardWindow(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    window_id: str
    train_start: int = Field(ge=0)
    train_end: int = Field(ge=0)
    test_start: int = Field(ge=0)
    test_end: int = Field(ge=0)


class WalkForwardSplit(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    window: WalkForwardWindow
    train: list[Any]
    test: list[Any]


def generate_walk_forward_windows(
    total_bars: int,
    *,
    train_size: int,
    test_size: int,
    step_size: int | None = None,
) -> list[WalkForwardWindow]:
    step = test_size if step_size is None else step_size
    for name, value in (
        ("total_bars", total_bars),
        ("train_size", train_size),
        ("test_size", test_size),
        ("step_size", step),
    ):
        if value <= 0:
            raise ValueError(f"{name} must be greater than 0")
    if total_bars < train_size + test_size:
        raise ValueError("total_bars must be at least train_size + test_size")

    windows: list[WalkForwardWindow] = []
    train_start = 0
    while True:
        train_end = train_start + train_size
        test_start = train_end
        test_end = test_start + test_size
        if test_end > total_bars:
            break
        windows.append(
            WalkForwardWindow(
                window_id=f"wf-{len(windows):03d}",
                train_start=train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
            )
        )
        train_start += step
    return windows


def split_sequence(sequence: Sequence[Any], windows: Sequence[WalkForwardWindow]) -> list[WalkForwardSplit]:
    return [
        WalkForwardSplit(
            window=window,
            train=list(sequence[window.train_start : window.train_end]),
            test=list(sequence[window.test_start : window.test_end]),
        )
        for window in windows
    ]
