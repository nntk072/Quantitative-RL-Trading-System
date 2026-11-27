"""Remaining input and CLI contracts for experiment variant resolution."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

import training.configuration.variant_resolution as resolution
from training.configuration.variant_resolution import (
    VariantError,
    _data_price_grid_overrides,
    _fmt,
    _main,
    load_experiments,
    resolve_variant,
    train_args,
)


def _registry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    variant: dict[str, object] | None = None,
    *,
    defaults: dict[str, object] | None = None,
) -> Path:
    root = tmp_path / "repo"
    (root / "config" / "base").mkdir(parents=True, exist_ok=True)
    (root / "config" / "features").mkdir(parents=True, exist_ok=True)
    (root / "config" / "base" / "default.yaml").touch()
    (root / "config" / "features" / "full_po3_mtf.yaml").touch()
    monkeypatch.setattr(resolution, "PROJECT_ROOT", root)
    path = tmp_path / "experiments.yaml"
    data: dict[str, object] = {"variants": [variant or {"name": "probe", "reward_mode": "pnl"}]}
    if defaults is not None:
        data["defaults"] = defaults
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def test_experiment_catalog_rejects_missing_or_wrong_variant_list(tmp_path: Path) -> None:
    for contents in ("", "null\n", "variants: {}\n", "- one\n"):
        path = tmp_path / "experiments.yaml"
        path.write_text(contents, encoding="utf-8")
        with pytest.raises(VariantError, match="variants.*list"):
            load_experiments(path)


def test_resolution_formats_booleans_and_applies_data_grid_and_run_overrides(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _registry(
        tmp_path,
        monkeypatch,
        {
            "name": "probe",
            "reward_mode": "pnl",
            "strategy": "baseline",
            "include_pd_context": True,
            "use_vae": 1,
            "price_grid_increment": 0.25,
            "price_grid_cache_dir": "/tmp/probe-cache",
            "candidate_max_age_bars": 15,
            "config_overrides": ["ppo.gamma=0.99"],
        },
        defaults={"steps": 50, "seeds": [5, 7]},
    )

    resolved = resolve_variant(
        "probe",
        experiments_path=path,
        vae_path="/tmp/model.pth",
        config_overrides=[" env.seed = 9 "],
    )
    args = train_args(resolved, 7)

    assert _fmt(True) == "true"
    assert _fmt(False) == "false"
    assert resolved["steps"] == 50
    assert resolved["seeds"] == [5, 7]
    assert resolved["use_vae"] is True
    assert resolved["vae_path"] == "/tmp/model.pth"
    assert resolved["include_pd_context"] is True
    assert resolved["feature_profile"] == "default"
    assert "--use-vae" in args
    assert args[args.index("--vae-path") + 1] == "/tmp/model.pth"
    assert "data.price_discretization.increment=0.25" in resolved["overrides"]
    assert "data.cache_dir=/tmp/probe-cache" in resolved["overrides"]
    assert "env.candidate_max_age_bars=15" in resolved["overrides"]
    assert "ppo.gamma=0.99" in resolved["overrides"]
    assert "env.seed=9" in resolved["overrides"]


@pytest.mark.parametrize(
    ("variant", "overrides", "message"),
    [
        (
            {
                "name": "probe",
                "reward_mode": "pnl",
                "price_grid_increment": 0,
                "price_grid_cache_dir": "/tmp/isolated",
            },
            [],
            "price-grid",
        ),
        (
            {"name": "probe", "reward_mode": "pnl", "price_grid_increment": 0.1},
            [],
            "price-grid",
        ),
        ({"name": "probe", "reward_mode": "pnl"}, ["missing_separator"], "key=value"),
        ({"name": "probe", "reward_mode": "pnl"}, ["env.x="], "key=value"),
    ],
)
def test_resolution_rejects_bad_price_grid_and_run_override_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    variant: dict[str, object],
    overrides: list[str],
    message: str,
) -> None:
    path = _registry(tmp_path, monkeypatch, variant)
    with pytest.raises(VariantError, match=message):
        resolve_variant("probe", experiments_path=path, config_overrides=overrides)


def test_resolution_rejects_malformed_declared_overrides_and_missing_base(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    malformed = _registry(
        tmp_path,
        monkeypatch,
        {"name": "probe", "reward_mode": "pnl", "config_overrides": ["bad"]},
    )
    with pytest.raises(VariantError, match="invalid config override"):
        resolve_variant("probe", experiments_path=malformed)

    wrong_type = _registry(
        tmp_path,
        monkeypatch,
        {"name": "probe", "reward_mode": "pnl", "config_overrides": "ppo.gamma=1"},
    )
    with pytest.raises(VariantError, match="must be a list"):
        resolve_variant("probe", experiments_path=wrong_type)

    missing_base = _registry(tmp_path, monkeypatch)
    (resolution.PROJECT_ROOT / "config" / "base" / "default.yaml").unlink()
    with pytest.raises(VariantError, match="base config missing"):
        resolve_variant("probe", experiments_path=missing_base)


def test_price_grid_override_helper_rejects_nonfinite_and_missing_cache() -> None:
    assert _data_price_grid_overrides({}) == []
    assert (
        _data_price_grid_overrides(
            {"price_grid_increment": 0.125, "price_grid_cache_dir": " cache "}
        )[-1]
        == "data.cache_dir=cache"
    )
    for variant in (
        {"price_grid_increment": float("nan"), "price_grid_cache_dir": "cache"},
        {"price_grid_increment": float("inf"), "price_grid_cache_dir": "cache"},
        {"price_grid_increment": 0.25, "price_grid_cache_dir": " "},
    ):
        with pytest.raises(VariantError, match="positive increment"):
            _data_price_grid_overrides(variant)


def test_variant_cli_args_and_manifest_write_resolved_arguments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _registry(tmp_path, monkeypatch)
    monkeypatch.setattr(resolution, "EXPERIMENTS_PATH", path)
    monkeypatch.setattr(resolution, "variant_ftmo_overrides", lambda _name, **_kwargs: [])

    assert _main(["meta", "probe", "--steps", "12", "--seeds", "2,3"]) == 0
    metadata = capsys.readouterr().out
    assert "ALGO=ppo" in metadata
    assert "STEPS=12" in metadata
    assert "SEEDS=2 3" in metadata

    with pytest.raises(SystemExit, match="args requires --seed"):
        _main(["args", "probe"])
    assert _main(["args", "probe", "--seed", "3"]) == 0
    assert "--seed\n3" in capsys.readouterr().out

    with pytest.raises(SystemExit, match="manifest requires --seed and --out"):
        _main(["manifest", "probe", "--seed", "3"])
    output = tmp_path / "manifest.json"
    assert _main(["manifest", "probe", "--seed", "3", "--out", str(output)]) == 0
    manifest = json.loads(output.read_text(encoding="utf-8"))
    assert manifest["variant"] == "probe"
    assert manifest["seed"] == 3
    assert "--seed" in manifest["train_args"]


def test_variant_cli_table_prints_comparison_columns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _registry(tmp_path, monkeypatch)
    monkeypatch.setattr(resolution, "EXPERIMENTS_PATH", path)
    monkeypatch.setattr(resolution, "variant_ftmo_overrides", lambda _name, **_kwargs: [])

    assert _main(["table"]) == 0

    output = capsys.readouterr().out
    assert "variant | strategy | strategy_actions" in output
    assert "probe | baseline" in output
