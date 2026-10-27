#!/usr/bin/env python3
"""Build the shared bar cache once before concurrent thesis workers start."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import yaml

from configuration import load_config
from market_data.loading.pipeline import BAR_CACHE_VERSION, build_tick_books, run_pipeline
from market_data.loading.ticks import TICK_CACHE_VERSION
from market_data.transforms.price_grid import (
    ROUNDING_MODE,
    configured_price_grid_increment,
    tick_cache_filename,
)

ROOT = Path(__file__).resolve().parents[2]


def _flatten_data(value: Any, prefix: str = "data") -> dict[str, bool | int | float | str]:
    """Flatten only scalar data settings from a campaign profile."""
    if not isinstance(value, dict):
        raise ValueError("campaign data settings must be mappings")
    result: dict[str, bool | int | float | str] = {}
    for key, item in value.items():
        path = f"{prefix}.{key}"
        if isinstance(item, dict):
            result.update(_flatten_data(item, path))
        elif isinstance(item, (bool, int, float, str)):
            result[path] = item
        else:
            raise ValueError(f"unsupported campaign data setting {path}: {item!r}")
    return result


def _campaign_profile_overrides(profile: Any) -> dict[str, bool | int | float | str]:
    if profile is None:
        return {}
    if not isinstance(profile, str) or not profile.strip():
        raise ValueError("campaign data_profile must be a relative YAML path")
    path = (ROOT / profile).resolve()
    try:
        relative = path.relative_to(ROOT)
    except ValueError:
        raise ValueError("campaign data_profile must stay inside this repository") from None
    if relative.parts[:2] != ("config", "data_modes") or path.suffix not in {".yaml", ".yml"}:
        raise ValueError("campaign data_profile must be a YAML file under config/data_modes")
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("campaign data_profile must contain a mapping")
    return _flatten_data(payload.get("data", {}))


def _variant_data_overrides(name: str, experiments: dict[str, Any]) -> dict[str, str]:
    defaults = experiments.get("defaults") or {}
    matches = [item for item in experiments.get("variants", []) if item.get("name") == name]
    if len(matches) != 1:
        raise ValueError(f"variant {name!r} must be declared once in config/experiments.yaml")
    variant = {**defaults, **matches[0]}
    overrides: dict[str, str] = {}
    if "price_grid_increment" in variant:
        increment = float(variant["price_grid_increment"])
        cache_dir = str(variant.get("price_grid_cache_dir", "")).strip()
        relative_cache = Path(cache_dir)
        if (
            increment <= 0
            or not relative_cache.parts
            or relative_cache.is_absolute()
            or ".." in relative_cache.parts
        ):
            raise ValueError("price-grid variant needs a positive increment and relative cache dir")
        overrides.update(
            {
                "data.price_discretization.enabled": "true",
                "data.price_discretization.increment": f"{increment:.12g}",
                "data.price_discretization.rounding": "nearest_half_away_from_zero",
                "data.cache_dir": cache_dir,
            }
        )
    variant_overrides = variant.get("config_overrides", [])
    if not isinstance(variant_overrides, list):
        raise ValueError(f"variant {name!r} config_overrides must be a list")
    for entry in variant_overrides:
        if isinstance(entry, str) and entry.startswith("data."):
            key, separator, value = entry.partition("=")
            if not separator or not value.strip():
                raise ValueError(f"invalid data override in variant {name!r}: {entry!r}")
            overrides[key] = value.strip()
    return overrides


def _campaign_data_overrides() -> list[str]:
    """Use the same data transform and cache policy as every campaign worker."""
    spec_value = os.environ.get("CAMPAIGN_SPEC")
    if not spec_value:
        return []
    spec_path = Path(spec_value)
    if not spec_path.is_file():
        raise FileNotFoundError(f"campaign spec is missing: {spec_path}")
    spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    if not isinstance(spec, dict) or not isinstance(spec.get("variants"), list):
        raise ValueError("campaign spec must contain a variants list")
    data_prefixes = (
        "data.cache_dir=",
        "data.datasets.training.raw_dir=",
        "data.datasets.testing.raw_dir=",
        "data.price_discretization.",
    )
    profile = _campaign_profile_overrides(spec.get("data_profile"))
    raw_explicit = spec.get("config_overrides", {})
    if not isinstance(raw_explicit, dict):
        raise ValueError("campaign config_overrides must be a mapping")
    explicit = {
        str(key): str(value).lower() if isinstance(value, bool) else str(value)
        for key, value in raw_explicit.items()
        if str(key).startswith(data_prefixes)
    }
    experiments = yaml.safe_load((ROOT / "config" / "experiments.yaml").read_text(encoding="utf-8"))
    policies = [
        tuple(
            f"{key}={value}"
            for key, value in sorted(_variant_data_overrides(str(name), experiments).items())
        )
        for name in spec["variants"]
    ]
    if policies and any(policy != policies[0] for policy in policies[1:]):
        raise ValueError("campaign variants must share one data transform and cache policy")
    variant = dict(item.partition("=")[::2] for item in policies[0]) if policies else {}
    values = {**profile, **variant, **explicit}
    return [
        f"{key}={str(value).lower() if isinstance(value, bool) else value}"
        for key, value in sorted(values.items())
    ]


def main() -> None:
    cfg = load_config(overrides=_campaign_data_overrides())
    cache_dir = Path(str(cfg.data.cache_dir))
    if cache_dir.is_symlink():
        raise RuntimeError(f"campaign bar cache must be a real directory: {cache_dir}")
    cache_dir.mkdir(parents=True, exist_ok=True)
    if not cache_dir.is_dir():
        raise RuntimeError(f"campaign bar cache must be a real directory: {cache_dir}")

    data = run_pipeline(cfg, force=True)
    configured_sets = cfg.data.get("datasets")
    cache_sets = list(configured_sets) if configured_sets else [None]
    expected = [
        cache_dir
        / (str(dataset_name) if dataset_name is not None else "")
        / f"{symbol}_{timeframe}_{BAR_CACHE_VERSION}.parquet"
        for dataset_name in cache_sets
        for symbol in cfg.data.symbols
        for timeframe in cfg.data.timeframes
    ]
    missing = [str(path) for path in expected if not path.is_file() or path.stat().st_size == 0]
    if missing:
        raise RuntimeError(f"bar cache build left missing/empty outputs: {missing}")

    tick_books = build_tick_books(cfg, force=True)
    grid_increment = configured_price_grid_increment(cfg)
    tick_cache_paths = [
        cache_dir
        / (str(dataset_name) if dataset_name is not None else "")
        / tick_cache_filename(symbol, grid_increment, TICK_CACHE_VERSION)
        for dataset_name in cache_sets
        for symbol in cfg.data.symbols
    ]
    missing_ticks = [
        str(path) for path in tick_cache_paths if not path.is_file() or path.stat().st_size == 0
    ]
    if missing_ticks:
        raise RuntimeError(f"tick cache build left missing/empty outputs: {missing_ticks}")

    summary = {
        "cache_dir": str(cache_dir.resolve()),
        "price_discretization": {
            "enabled": grid_increment is not None,
            "increment": grid_increment,
            "rounding": ROUNDING_MODE,
        },
        "cache_files": len(expected),
        "tick_cache_files": len(tick_cache_paths),
        "bars": {
            symbol: {timeframe: len(frame) for timeframe, frame in frames.items()}
            for symbol, frames in data.items()
        },
        "ticks": {
            symbol: len(book) if book is not None else 0 for symbol, book in tick_books.items()
        },
    }
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
