from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from experiments.runs.execution import (
    experiment_run_config_override_lines,
    normalize_experiment_run_config_overrides,
)

ROOT = Path(__file__).resolve().parents[3]


def test_experiment_run_policy_overrides_are_sorted_and_shell_safe() -> None:
    values = normalize_experiment_run_config_overrides(
        {
            "ftmo.trailing_dd_limit": 0.0,
            "ftmo.daily_loss_limit": 5000.0,
            "env.peak_trailing_dd_limit": 0.0,
            "enabled": False,
        }
    )

    assert list(values) == [
        "enabled",
        "env.peak_trailing_dd_limit",
        "ftmo.daily_loss_limit",
        "ftmo.trailing_dd_limit",
    ]
    assert experiment_run_config_override_lines(values).splitlines() == [
        "enabled=false",
        "env.peak_trailing_dd_limit=0.0",
        "ftmo.daily_loss_limit=5000.0",
        "ftmo.trailing_dd_limit=0.0",
    ]


def test_experiment_run_accepts_a_repository_relative_prebuilt_feature_cache() -> None:
    values = normalize_experiment_run_config_overrides(
        {"data.prebuilt_feature_cache": "cache/normal/US100_features.parquet"}
    )
    assert values == {"data.prebuilt_feature_cache": "cache/normal/US100_features.parquet"}
    assert experiment_run_config_override_lines(values) == (
        "data.prebuilt_feature_cache=cache/normal/US100_features.parquet"
    )


def test_experiment_run_serializes_flat_list_overrides_for_config_loader() -> None:
    values = normalize_experiment_run_config_overrides({"features.ema_periods": [9, 21, 50, 200]})

    assert experiment_run_config_override_lines(values) == ("features.ema_periods=[9,21,50,200]")
    from configuration import load_config

    cfg = load_config(experiment_run_config_override_lines(values).splitlines())
    assert cfg.features.ema_periods == [9, 21, 50, 200]


def test_active_mtf_context_list_override_round_trips() -> None:
    from configuration import load_config

    values = normalize_experiment_run_config_overrides({"features.ema_periods": [9, 21, 50, 200]})
    cfg = load_config(experiment_run_config_override_lines(values).splitlines())

    assert cfg.features.ema_periods == [9, 21, 50, 200]


@pytest.mark.parametrize(
    "value",
    [
        ["ftmo.trailing_dd_limit=0"],
        {"bad key": 0},
        {"ftmo.trailing_dd_limit": float("nan")},
        {"ftmo.trailing_dd_limit": "0"},
        {"data.prebuilt_feature_cache": "/tmp/features.parquet"},
        {"data.prebuilt_feature_cache": "cache/../outside.parquet"},
        {"features.ema_periods": [[9, 21], 50]},
        {"features.ema_periods": [9, float("inf")]},
    ],
)
def test_experiment_run_policy_override_validation_rejects_unsupported_values(
    value: object,
) -> None:
    with pytest.raises(ValueError):
        normalize_experiment_run_config_overrides(value)


def test_active_survival_policies_share_declared_risk_limits() -> None:
    from experiments.research.catalog import load_research_catalog

    experiment = load_research_catalog().experiment("survival_policy")
    assert {"setup_conditioned", "hybrid_control"} <= {
        variant.variant_id for variant in experiment.variants
    }
    for variant in experiment.variants:
        assert variant.config is not None
        policy = yaml.safe_load((ROOT / variant.config).read_text(encoding="utf-8"))
        assert policy["ppo"]["total_timesteps"] == 2_000_000
        assert policy["ftmo"]["limit_value_mode"] == "percent_equity"
        assert policy["ftmo"]["daily_loss_limit_pct"] == 0.05
        assert policy["ftmo"]["max_loss_limit_initial_pct"] == 0.10
        assert policy["ftmo"]["risk_sizing_limit_usd"] == 900.0
