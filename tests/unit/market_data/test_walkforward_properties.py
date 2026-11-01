from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from market_data.splits.walkforward import purged_walk_forward, purged_walk_forward_legacy


def test_default_walkforward_contract_matches_five_explicit_folds() -> None:
    default_splits = list(purged_walk_forward(1000))
    explicit_splits = list(
        purged_walk_forward(
            1000,
            n_splits=5,
            test_size=0.2,
            purge_bars=60,
            embargo_bars=20,
            label_horizon=0,
        )
    )

    assert len(default_splits) == 5
    for default, explicit in zip(default_splits, explicit_splits, strict=True):
        assert default.fold == explicit.fold
        assert (default.train_idx == explicit.train_idx).all()
        assert (default.test_idx == explicit.test_idx).all()


@pytest.mark.parametrize(
    ("n", "n_splits", "test_size"),
    (
        (0, 5, 0.2),
        (1000, 0, 0.2),
        (1000, 5, 0.0),
        (1000, 5, -0.1),
    ),
)
def test_invalid_walkforward_inputs_yield_no_folds(n: int, n_splits: int, test_size: float) -> None:
    assert list(purged_walk_forward(n, n_splits=n_splits, test_size=test_size)) == []


def test_legacy_default_arguments_match_explicit_compatibility_contract() -> None:
    with pytest.warns(DeprecationWarning):
        defaults = list(purged_walk_forward_legacy(1000))
    with pytest.warns(DeprecationWarning):
        explicit = list(
            purged_walk_forward_legacy(
                1000,
                n_splits=5,
                test_size=0.2,
                purge_bars=60,
                embargo_bars=20,
            )
        )

    assert len(defaults) == len(explicit) == 5
    for default, expected in zip(defaults, explicit, strict=True):
        assert default.fold == expected.fold
        assert (default.train_idx == expected.train_idx).all()
        assert (default.test_idx == expected.test_idx).all()


@given(
    n=st.integers(min_value=100, max_value=5000),
    n_splits=st.integers(min_value=1, max_value=10),
    test_size=st.floats(min_value=0.05, max_value=0.8, allow_nan=False, allow_infinity=False),
    purge=st.integers(min_value=0, max_value=80),
    embargo=st.integers(min_value=0, max_value=40),
    label_horizon=st.integers(min_value=0, max_value=80),
)
@settings(max_examples=150, derandomize=True, database=None, deadline=None)
def test_generated_walkforward_folds_preserve_order_and_gap(
    n: int,
    n_splits: int,
    test_size: float,
    purge: int,
    embargo: int,
    label_horizon: int,
) -> None:
    splits = list(
        purged_walk_forward(
            n,
            n_splits=n_splits,
            test_size=test_size,
            purge_bars=purge,
            embargo_bars=embargo,
            label_horizon=label_horizon,
        )
    )
    required_gap = purge + embargo + label_horizon

    for split in splits:
        assert len(split.train_idx) > 0
        assert len(split.test_idx) > 0
        assert split.train_idx[0] == 0
        assert (split.train_idx[1:] > split.train_idx[:-1]).all()
        assert (split.test_idx[1:] > split.test_idx[:-1]).all()
        assert split.test_idx[-1] < n
        assert split.test_idx[0] - split.train_idx[-1] >= required_gap + 1

    for earlier, later in zip(splits, splits[1:], strict=False):
        assert earlier.test_idx[-1] < later.test_idx[0]
        assert earlier.fold < later.fold
