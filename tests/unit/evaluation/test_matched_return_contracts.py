"""Matched-return intervals require timestamp and run-provenance parity."""

from __future__ import annotations

import pandas as pd
import pytest

from evaluation.metrics.matched_comparison import MATCH_FIELDS, compare_matched_returns


def _provenance(index: pd.DatetimeIndex, policy: str = "treatment") -> dict[str, object]:
    result: dict[str, object] = {name: f"shared-{name}" for name in MATCH_FIELDS}
    result["evaluation_start"] = index[0]
    result["evaluation_end"] = index[-1]
    result["policy_sha256"] = policy
    return result


def test_matched_return_interval_uses_declared_distinct_policy_intervention() -> None:
    index = pd.date_range("2026-01-02 16:30", periods=4, freq="min", tz="UTC")
    treatment = pd.Series([0.02, -0.01, 0.03, 0.01], index=index)
    control = pd.Series([0.01, 0.00, 0.02, 0.00], index=index)
    control_provenance = _provenance(index, "control")

    interval = compare_matched_returns(
        treatment,
        control,
        _provenance(index),
        control_provenance,
        intervention_field="policy_sha256",
        n_boot=12,
        rng_seed=3,
    )

    assert interval.estimate == pytest.approx((treatment - control).mean())
    assert interval.lower <= interval.estimate <= interval.upper


def test_matched_return_requires_supported_distinct_intervention_and_complete_provenance() -> None:
    index = pd.date_range("2026-01-02 16:30", periods=3, freq="min", tz="UTC")
    returns = pd.Series([0.01, -0.01, 0.02], index=index)
    treatment = _provenance(index)
    control = _provenance(index, "control")

    with pytest.raises(ValueError, match="Unsupported comparison intervention"):
        compare_matched_returns(
            returns,
            returns,
            treatment,
            control,
            intervention_field="seed",
        )
    same_policy = _provenance(index)
    with pytest.raises(ValueError, match="distinct, non-empty"):
        compare_matched_returns(
            returns,
            returns,
            treatment,
            same_policy,
            intervention_field="policy_sha256",
        )
    missing_policy = _provenance(index)
    missing_policy["policy_sha256"] = " "
    with pytest.raises(ValueError, match="distinct, non-empty"):
        compare_matched_returns(
            returns,
            returns,
            treatment,
            missing_policy,
            intervention_field="policy_sha256",
        )

    mismatched_data = _provenance(index, "control")
    mismatched_data["dataset_sha256"] = "different-dataset"
    with pytest.raises(ValueError, match="dataset_sha256"):
        compare_matched_returns(returns, returns, treatment, mismatched_data)


@pytest.mark.parametrize(
    ("left_index", "right_index", "message"),
    [
        (pd.RangeIndex(3), pd.RangeIndex(3), "timestamp indexes"),
        (
            pd.DatetimeIndex(["2026-01-02 16:30", pd.NaT, "2026-01-02 16:32"], tz="UTC"),
            pd.date_range("2026-01-02 16:30", periods=3, freq="min", tz="UTC"),
            "must not be missing",
        ),
        (
            pd.DatetimeIndex(
                ["2026-01-02 16:31", "2026-01-02 16:30", "2026-01-02 16:32"], tz="UTC"
            ),
            pd.date_range("2026-01-02 16:30", periods=3, freq="min", tz="UTC"),
            "chronologically ordered",
        ),
        (
            pd.DatetimeIndex(
                ["2026-01-02 16:30", "2026-01-02 16:30", "2026-01-02 16:32"], tz="UTC"
            ),
            pd.date_range("2026-01-02 16:30", periods=3, freq="min", tz="UTC"),
            "unique timestamps",
        ),
        (
            pd.date_range("2026-01-02 16:30", periods=3, freq="min", tz="UTC"),
            pd.date_range("2026-01-02 16:31", periods=3, freq="min", tz="UTC"),
            "match exactly",
        ),
    ],
)
def test_matched_return_rejects_invalid_or_unaligned_timestamps(
    left_index: pd.Index, right_index: pd.Index, message: str
) -> None:
    left = pd.Series([0.01] * len(left_index), index=left_index)
    right = pd.Series([0.01] * len(right_index), index=right_index)
    provenance = _provenance(pd.date_range("2026-01-02 16:30", periods=3, freq="min", tz="UTC"))

    with pytest.raises(ValueError, match=message):
        compare_matched_returns(left, right, provenance, provenance)


def test_matched_return_validates_period_endpoints_and_bootstrap_controls() -> None:
    index = pd.date_range("2026-01-02 16:30", periods=3, freq="min", tz="UTC")
    returns = pd.Series([0.01, -0.01, 0.02], index=index)
    provenance = _provenance(index)

    bad_period = _provenance(index)
    bad_period["evaluation_start"] = "not-a-timestamp"
    with pytest.raises(ValueError, match="Invalid declared evaluation period"):
        compare_matched_returns(returns, returns, bad_period, bad_period)
    wrong_period = _provenance(index)
    wrong_period["evaluation_end"] = index[-1] + pd.Timedelta(minutes=1)
    with pytest.raises(ValueError, match="must match"):
        compare_matched_returns(returns, returns, wrong_period, wrong_period)
    with pytest.raises(ValueError, match="at least one"):
        compare_matched_returns(returns.iloc[:0], returns.iloc[:0], provenance, provenance)
    single_provenance = _provenance(index[:1])
    with pytest.raises(ValueError, match="at least two"):
        compare_matched_returns(
            returns.iloc[:1], returns.iloc[:1], single_provenance, single_provenance
        )
    with pytest.raises(ValueError, match="n_boot must be positive"):
        compare_matched_returns(returns, returns, provenance, provenance, n_boot=0)
    with pytest.raises(ValueError, match="Confidence level"):
        compare_matched_returns(returns, returns, provenance, provenance, level=1.0)
