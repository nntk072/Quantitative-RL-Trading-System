from __future__ import annotations

from pathlib import Path

import pytest

import experiments.runs.execution as execution
from experiments.runs.execution import (
    experiment_run_config_override_lines,
    load_experiment_run_data_profile,
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


def test_missing_config_override_mapping_means_no_overrides() -> None:
    assert normalize_experiment_run_config_overrides(None) == {}


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
        {"data.price_discretization.rounding": "  "},
        {"features.ema_periods": [[9, 21], 50]},
        {"features.ema_periods": [9, float("inf")]},
    ],
)
def test_experiment_run_policy_override_validation_rejects_unsupported_values(
    value: object,
) -> None:
    with pytest.raises(ValueError):
        normalize_experiment_run_config_overrides(value)


def test_missing_data_profile_means_no_profile_overrides() -> None:
    assert load_experiment_run_data_profile(None) == {}


def test_data_profile_flattens_allowed_nested_data_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repo"
    profile_path = repository / "config" / "data_modes" / "normal.yaml"
    profile_path.parent.mkdir(parents=True)
    profile_path.write_text(
        "profile: normal\n"
        "data:\n"
        "  cache_dir: cache/normal\n"
        "  datasets:\n"
        "    training:\n"
        "      raw_dir: data/training\n"
        "    testing:\n"
        "      raw_dir: data/testing\n"
        "  price_discretization:\n"
        "    enabled: true\n"
        "    increment: 0.25\n"
        "    rounding: nearest\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(execution, "ROOT", repository)

    overrides = load_experiment_run_data_profile("config/data_modes/normal.yaml")

    assert overrides == {
        "data.cache_dir": "cache/normal",
        "data.datasets.testing.raw_dir": "data/testing",
        "data.datasets.training.raw_dir": "data/training",
        "data.price_discretization.enabled": True,
        "data.price_discretization.increment": 0.25,
        "data.price_discretization.rounding": "nearest",
    }


@pytest.mark.parametrize("profile", [0, "", "  "])
def test_data_profile_requires_a_nonempty_relative_path(profile: object) -> None:
    with pytest.raises(ValueError, match="data_profile must be a relative YAML path"):
        load_experiment_run_data_profile(profile)


@pytest.mark.parametrize(
    ("profile", "message"),
    [
        ("../../outside.yaml", "must stay inside the repository"),
        ("config/research/profile.yaml", "must be a YAML file under config/data_modes"),
        ("config/data_modes/profile.json", "must be a YAML file under config/data_modes"),
    ],
)
def test_data_profile_rejects_escape_and_non_profile_locations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profile: str, message: str
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    monkeypatch.setattr(execution, "ROOT", repository)

    with pytest.raises(ValueError, match=message):
        load_experiment_run_data_profile(profile)


@pytest.mark.parametrize(
    "contents",
    [
        "profile: other\ndata: {}\n",
        "profile: valid\ndata: []\n",
    ],
)
def test_data_profile_rejects_mismatched_identity_or_nonmapping_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, contents: str
) -> None:
    repository = tmp_path / "repo"
    profile_path = repository / "config" / "data_modes" / "valid.yaml"
    profile_path.parent.mkdir(parents=True)
    profile_path.write_text(contents, encoding="utf-8")
    monkeypatch.setattr(execution, "ROOT", repository)

    with pytest.raises(ValueError, match="must contain a data mapping"):
        load_experiment_run_data_profile("config/data_modes/valid.yaml")


def test_data_profile_rejects_unapproved_flattened_data_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repo"
    profile_path = repository / "config" / "data_modes" / "normal.yaml"
    profile_path.parent.mkdir(parents=True)
    profile_path.write_text(
        "profile: normal\ndata:\n  execution:\n    block_overnight: false\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(execution, "ROOT", repository)

    with pytest.raises(ValueError, match="contains unsupported data settings"):
        load_experiment_run_data_profile("config/data_modes/normal.yaml")


@pytest.mark.parametrize(
    ("filename", "contents"),
    [("missing.yaml", None), ("broken.yaml", "profile: [unterminated\n")],
)
def test_data_profile_reports_missing_or_malformed_yaml(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    filename: str,
    contents: str | None,
) -> None:
    repository = tmp_path / "repo"
    profile_dir = repository / "config" / "data_modes"
    profile_dir.mkdir(parents=True)
    if contents is not None:
        (profile_dir / filename).write_text(contents, encoding="utf-8")
    monkeypatch.setattr(execution, "ROOT", repository)

    with pytest.raises(ValueError, match="cannot load experiment run data profile"):
        load_experiment_run_data_profile(f"config/data_modes/{filename}")
