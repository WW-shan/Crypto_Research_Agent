import pytest
from pydantic import ValidationError

from crypto_alpha_agent.validation.walk_forward import WalkForwardWindow, generate_walk_forward_windows, split_sequence


def test_generate_walk_forward_windows_uses_exclusive_indexes():
    windows = generate_walk_forward_windows(total_bars=12, train_size=5, test_size=3, step_size=3)

    assert [window.model_dump() for window in windows] == [
        {
            "window_id": "wf-000",
            "train_start": 0,
            "train_end": 5,
            "test_start": 5,
            "test_end": 8,
        },
        {
            "window_id": "wf-001",
            "train_start": 3,
            "train_end": 8,
            "test_start": 8,
            "test_end": 11,
        },
    ]


def test_split_sequence_returns_train_test_slices():
    data = list(range(12))
    windows = generate_walk_forward_windows(total_bars=len(data), train_size=5, test_size=3, step_size=3)

    splits = split_sequence(data, windows)

    assert splits[0].train == [0, 1, 2, 3, 4]
    assert splits[0].test == [5, 6, 7]
    assert splits[1].train == [3, 4, 5, 6, 7]
    assert splits[1].test == [8, 9, 10]


@pytest.mark.parametrize(
    "train_start, train_end, test_start, test_end",
    [
        (5, 4, 4, 7),
        (0, 5, 6, 8),
        (0, 5, 5, 4),
    ],
)
def test_walk_forward_window_rejects_invalid_bounds(train_start, train_end, test_start, test_end):
    with pytest.raises((ValidationError, ValueError)):
        WalkForwardWindow(
            window_id="wf-invalid",
            train_start=train_start,
            train_end=train_end,
            test_start=test_start,
            test_end=test_end,
        )


def test_split_sequence_rejects_out_of_range_window():
    data = list(range(8))
    window = WalkForwardWindow(
        window_id="wf-out-of-range",
        train_start=0,
        train_end=5,
        test_start=5,
        test_end=9,
    )

    with pytest.raises(ValueError, match="bounds"):
        split_sequence(data, [window])


@pytest.mark.parametrize("total_bars, train_size, test_size", [(7, 5, 3), (10, 0, 3), (10, 5, 0)])
def test_walk_forward_rejects_invalid_or_short_inputs(total_bars, train_size, test_size):
    with pytest.raises(ValueError):
        generate_walk_forward_windows(total_bars=total_bars, train_size=train_size, test_size=test_size)


def test_walk_forward_rejects_non_positive_step_size():
    with pytest.raises(ValueError):
        generate_walk_forward_windows(total_bars=10, train_size=5, test_size=3, step_size=0)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"total_bars": 10.0, "train_size": 5, "test_size": 3},
        {"total_bars": 10, "train_size": True, "test_size": 3},
        {"total_bars": 10, "train_size": 5, "test_size": True},
        {"total_bars": 10, "train_size": 5, "test_size": 3, "step_size": True},
    ],
)
def test_walk_forward_rejects_non_integer_inputs(kwargs):
    with pytest.raises(ValueError, match="positive integer"):
        generate_walk_forward_windows(**kwargs)
