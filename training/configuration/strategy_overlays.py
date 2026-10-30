"""Canonical strategy-overlay discovery and merge behavior."""

from __future__ import annotations

from pathlib import Path

from omegaconf import DictConfig

from configuration import load_config_overlay, merge_config_overlay
from configuration.paths import repository_root

_CONFIG_DIR = repository_root(__file__) / "config"
_STRATEGY_CONFIGS = {
    "po3_ifvg": _CONFIG_DIR / "2_po3_ifvg.yaml",
    "distribution": _CONFIG_DIR / "3_distribution.yaml",
}


def strategy_overlay_path(strategy: str) -> Path | None:
    """Return a strategy overlay path, with baseline as the no-overlay case."""
    if strategy == "baseline":
        return None
    try:
        path = _STRATEGY_CONFIGS[strategy]
    except KeyError as exc:
        raise ValueError(f"unknown strategy: {strategy}") from exc
    if not path.is_file():
        raise FileNotFoundError(f"strategy configuration is missing: {path}")
    return path


def merge_strategy_config(base: DictConfig, strategy: str) -> DictConfig:
    """Apply one validated strategy overlay to a complete base configuration."""
    path = strategy_overlay_path(strategy)
    if path is None:
        return base
    return merge_config_overlay(base, load_config_overlay(path))
