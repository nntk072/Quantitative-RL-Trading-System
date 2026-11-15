from __future__ import annotations

import pytest

from experiments.runs.execution import (
    experiment_run_config_override_lines,
    normalize_experiment_run_config_overrides,
)


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


def test_list_override_round_trips_through_the_canonical_config_loader() -> None:
    from configuration import load_config

    values = normalize_experiment_run_config_overrides({"features.ema_periods": [9, 21, 50, 200]})
    config_override_lines = experiment_run_config_override_lines(values).splitlines()
    cfg = load_config(config_override_lines)

    assert values["features.ema_periods"] == [9, 21, 50, 200]
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
