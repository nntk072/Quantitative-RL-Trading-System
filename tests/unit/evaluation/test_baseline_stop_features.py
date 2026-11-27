from __future__ import annotations

import pandas as pd
import pytest

from evaluation.rollout.baseline_features import ensure_baseline_stop_features
from features.technical.structure import structure_levels


def _bars(index: pd.DatetimeIndex) -> pd.DataFrame:
    close = pd.Series([10.0, 12.0, 9.0, 13.0, 8.0, 14.0, 7.0][: len(index)], index=index)
    return pd.DataFrame({"high": close + 1.0, "low": close - 1.0, "close": close}, index=index)


def test_missing_baseline_stop_features_match_canonical_causal_structure() -> None:
    index = pd.date_range("2025-01-01", periods=7, freq="min", tz="UTC")
    bars = _bars(index)
    features = pd.DataFrame({"existing": range(len(index))}, index=index)

    result, generated = ensure_baseline_stop_features(bars, features, swing_period=1)

    expected = structure_levels(bars, swing_period=1, atr_mult=0.0)
    assert generated == ("last_swing_low", "last_swing_high")
    pd.testing.assert_frame_equal(
        result.loc[:, ["last_swing_low", "last_swing_high"]],
        expected.loc[:, ["last_swing_low", "last_swing_high"]],
    )
    pd.testing.assert_series_equal(result["existing"], features["existing"])


def test_existing_baseline_stop_features_are_preserved_without_recomputation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index = pd.date_range("2025-01-01", periods=2, freq="min", tz="UTC")
    bars = _bars(index)
    features = pd.DataFrame(
        {"last_swing_low": [3.0, 4.0], "last_swing_high": [15.0, 16.0]}, index=index
    )

    def unexpected_structure_levels(*args: object, **kwargs: object) -> pd.DataFrame:
        pytest.fail("complete stop features should not trigger a structure rebuild")

    monkeypatch.setattr(
        "evaluation.rollout.baseline_features.structure_levels", unexpected_structure_levels
    )

    result, generated = ensure_baseline_stop_features(bars, features, swing_period=1)

    assert result is features
    assert generated == ()


def test_baseline_bars_and_features_must_have_identical_indexes() -> None:
    bars_index = pd.date_range("2025-01-01", periods=2, freq="min", tz="UTC")
    features_index = bars_index + pd.Timedelta(minutes=1)

    with pytest.raises(ValueError, match="identical indexes"):
        ensure_baseline_stop_features(
            _bars(bars_index), pd.DataFrame(index=features_index), swing_period=1
        )
