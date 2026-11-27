"""Public decision-diversity contracts for sparse and malformed trade histories."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from evaluation.metrics.decision_diversity import (
    DiversityThresholds,
    active_prior_names,
    candidate_rank,
    diversity_report,
    format_diversity_text,
    risk_mean_collapsed,
    thresholds_from_mapping,
)


def _open(**values: object) -> dict[str, object]:
    row: dict[str, object] = {
        "type": "open",
        "exit_mode": "structural",
        "planned_rr": 2.0,
        "sl_index": 1,
        "n_sl": 3,
        "tp_index": 1,
        "n_tp": 3,
        "stop_u": 0.5,
        "target_u": 0.5,
        "direction": 1,
        "sl_ref": "last_swing_low",
        "tp_ref": "prev_day_high",
    }
    row.update(values)
    return row


def test_threshold_mapping_uses_defaults_and_only_declared_fields() -> None:
    defaults = thresholds_from_mapping(None)
    configured = thresholds_from_mapping({"action_std": 0.12, "unrecognized": 99})

    assert defaults == DiversityThresholds()
    assert configured.action_std == pytest.approx(0.12)
    assert configured.sl_top_share == defaults.sl_top_share
    assert not hasattr(configured, "unrecognized")


@pytest.mark.parametrize(
    ("index", "count"),
    [
        ("not-an-index", 3),
        (1, "not-a-count"),
        (np.nan, 3),
        (1, np.inf),
        (0, 0),
    ],
)
def test_candidate_rank_returns_nan_for_malformed_or_nonfinite_menu(
    index: object, count: object
) -> None:
    assert np.isnan(candidate_rank(index, count))


def test_active_prior_names_requires_real_multi_choice_evidence() -> None:
    limits = DiversityThresholds(
        min_prior_trades=4,
        min_prior_sl_choices=4,
        min_prior_tp_choices=4,
        min_prior_direction_choices=4,
        rank_edge=0.05,
    )
    parked = pd.DataFrame(
        [
            _open(sl_index=0, stop_u=value, tp_index=1, target_u=value)
            for value in (0.49, 0.50, 0.51, 0.50)
        ]
    )

    assert active_prior_names(parked, limits) == {"stop", "target", "exit", "direction"}
    assert active_prior_names(pd.DataFrame(), limits) == set()


def test_ema_only_target_choices_do_not_create_structural_target_collapse() -> None:
    limits = DiversityThresholds(
        min_prior_trades=100,
        min_prior_tp_choices=4,
        rank_edge=0.05,
        action_std=0.05,
    )
    structural = [
        _open(tp_index=rank, target_u=value)
        for rank, value in zip((0, 2, 0, 2), (0.1, 0.3, 0.7, 0.9), strict=True)
    ]
    ema = [_open(exit_mode="ema_21", tp_index=0, tp_ref="ema_21", target_u=0.5) for _ in range(4)]

    assert "target" not in active_prior_names(pd.DataFrame([*structural, *ema]), limits)


def test_report_with_no_open_rows_and_missing_labels_is_explicit() -> None:
    no_opens = diversity_report(pd.DataFrame([{"type": "close", "pnl": 1.0}]))
    missing_labels = diversity_report(
        pd.DataFrame([_open(sl_ref=None, tp_ref=None, exit_mode=np.nan, planned_rr=np.nan)])
    )

    assert no_opens.text == "TRADE DECISION DIVERSITY\nno strategy opens\n"
    assert no_opens.opens.empty
    assert missing_labels.sl_shares.empty
    assert missing_labels.tp_shares.empty
    assert missing_labels.exit_shares.empty
    assert missing_labels.joint.empty
    assert "Exit:  n/a" in format_diversity_text(
        pd.DataFrame([_open(sl_ref=None, tp_ref=None, exit_mode=np.nan, planned_rr=np.nan)])
    )


def test_risk_collapse_uses_training_step_count_and_rejects_invalid_mean() -> None:
    limits = DiversityThresholds(min_prior_risk_steps=10, risk_u_max=0.08)

    assert not risk_mean_collapsed(0.01, 9, limits)
    assert not risk_mean_collapsed(float("nan"), 10, limits)
    assert risk_mean_collapsed(0.08, 10, limits)
    assert not risk_mean_collapsed(0.5, 10, limits)
