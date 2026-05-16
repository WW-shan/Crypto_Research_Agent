import pytest

from crypto_alpha_agent.validation.walk_forward import generate_walk_forward_windows, split_sequence


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


@pytest.mark.parametrize("total_bars, train_size, test_size", [(7, 5, 3), (10, 0, 3), (10, 5, 0)])
def test_walk_forward_rejects_invalid_or_short_inputs(total_bars, train_size, test_size):
    with pytest.raises(ValueError):
        generate_walk_forward_windows(total_bars=total_bars, train_size=train_size, test_size=test_size)


def test_walk_forward_rejects_non_positive_step_size():
    with pytest.raises(ValueError):
        generate_walk_forward_windows(total_bars=10, train_size=5, test_size=3, step_size=0)
