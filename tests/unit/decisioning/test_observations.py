from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from decisioning.observations import (
    _LEGACY_REPEATED_PAYOUT_SCHEMA_ID,
    OBSERVATION_SCHEMA_REPEATED_PAYOUT,
    _canonicalize_saved_observation_schema_id,
    build_observation_schema,
    normalized_account_vector,
    pad_observation_window,
    requires_normalized_account_observation,
    validate_observation_schema,
)


def test_repeated_payout_schema_uses_domain_name_and_accepts_legacy_checkpoint() -> None:
    expected = build_observation_schema(OBSERVATION_SCHEMA_REPEATED_PAYOUT)
    legacy_checkpoint = expected.to_dict()
    legacy_checkpoint["version"] = _LEGACY_REPEATED_PAYOUT_SCHEMA_ID

    assert expected.version == OBSERVATION_SCHEMA_REPEATED_PAYOUT
    assert (
        _canonicalize_saved_observation_schema_id(_LEGACY_REPEATED_PAYOUT_SCHEMA_ID)
        == expected.version
    )
    with pytest.raises(ValueError, match="unknown observation schema version"):
        build_observation_schema(_LEGACY_REPEATED_PAYOUT_SCHEMA_ID)
    assert expected.width == 28
    assert requires_normalized_account_observation(expected.version)
    validate_observation_schema(legacy_checkpoint, expected)

    legacy_checkpoint["observation_coordinates"] = ["equity"]
    with pytest.raises(ValueError, match="differs from requested environment schema"):
        validate_observation_schema(legacy_checkpoint, expected)


def test_normalized_account_vector_preserves_valid_legacy_coordinates() -> None:
    values = normalized_account_vector(
        equity=99_000.0,
        initial_balance=100_000.0,
        pos_dir=-1.0,
        open_pnl=-100.0,
        dist_to_sl=10.0,
        trailing_dd=0.1,
        close=20_000.0,
        entry_state="IN_POSITION",
    )

    assert values.shape == (10,)
    assert values.dtype == np.float32
    np.testing.assert_allclose(
        values[:6], [np.log(0.99), -1.0, -0.001, -100.0 / 99_000 * 100, 0.0005, 0.1]
    )
    np.testing.assert_array_equal(values[6:], [0.0, 0.0, 0.0, 1.0])


@pytest.mark.parametrize(
    "name",
    ["equity", "initial_balance", "pos_dir", "open_pnl", "dist_to_sl", "trailing_dd", "close"],
)
def test_normalized_account_vector_rejects_nonfinite_inputs(name: str) -> None:
    inputs = {
        "equity": 100_000.0,
        "initial_balance": 100_000.0,
        "pos_dir": 0.0,
        "open_pnl": 0.0,
        "dist_to_sl": 0.0,
        "trailing_dd": 0.0,
        "close": 20_000.0,
    }
    inputs[name] = float("nan")

    with pytest.raises(ValueError, match=f"input {name} must be finite"):
        normalized_account_vector(
            equity=inputs["equity"],
            initial_balance=inputs["initial_balance"],
            pos_dir=inputs["pos_dir"],
            open_pnl=inputs["open_pnl"],
            dist_to_sl=inputs["dist_to_sl"],
            trailing_dd=inputs["trailing_dd"],
            close=inputs["close"],
            entry_state=None,
        )


def test_normalized_account_vector_rejects_nonpositive_equity_for_log_coordinate() -> None:
    with pytest.raises(ValueError, match="equity must be positive"):
        normalized_account_vector(
            equity=0.0,
            initial_balance=100_000.0,
            pos_dir=0.0,
            open_pnl=0.0,
            dist_to_sl=0.0,
            trailing_dd=0.0,
            close=20_000.0,
        )


def test_normalized_account_vector_rejects_values_that_overflow_float32() -> None:
    with pytest.raises(ValueError, match="output coordinates must be finite"):
        normalized_account_vector(
            equity=100_000.0,
            initial_balance=100_000.0,
            pos_dir=0.0,
            open_pnl=1e100,
            dist_to_sl=0.0,
            trailing_dd=0.0,
            close=20_000.0,
        )


def test_pad_observation_window_left_pads_two_dimensional_values_and_mask() -> None:
    values, mask = pad_observation_window(np.array([[1.0, 2.0], [3.0, 4.0]]), 4)

    np.testing.assert_array_equal(values, [[0.0, 0.0], [0.0, 0.0], [1.0, 2.0], [3.0, 4.0]])
    np.testing.assert_array_equal(mask, [0.0, 0.0, 1.0, 1.0])
    assert values.dtype == np.float32


def test_pad_observation_window_keeps_only_the_latest_rows_when_sequence_is_long() -> None:
    values, mask = pad_observation_window(np.array([1.0, 2.0, 3.0]), 2)

    np.testing.assert_array_equal(values, [[2.0], [3.0]])
    np.testing.assert_array_equal(mask, [1.0, 1.0])


@pytest.mark.parametrize("window", [0, -1, 2.5, True])
def test_pad_observation_window_requires_a_positive_window(window: int) -> None:
    with pytest.raises(ValueError, match="window must be a positive integer"):
        pad_observation_window(np.array([1.0]), window)


@pytest.mark.parametrize("sequence", [np.array(1.0), np.zeros((2, 3, 4))])
def test_pad_observation_window_rejects_dimensions_other_than_one_or_two(
    sequence: np.ndarray[Any, Any],
) -> None:
    with pytest.raises(ValueError, match="must be 1D or 2D"):
        pad_observation_window(sequence, 2)
