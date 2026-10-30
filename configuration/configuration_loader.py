"""Configuration loading via OmegaConf."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from omegaconf import DictConfig, OmegaConf

from configuration.paths import repository_root
from configuration.schema import reject_unknown_keys

_DEFAULT_CFG = repository_root(__file__) / "config" / "base" / "default.yaml"


def load_config(
    overrides: list[str] | None = None,
    config_path: str | Path | None = None,
) -> DictConfig:
    """Load config from ``config_path`` (the root config/base/default.yaml when None), then apply overrides.

    Parameters
    ----------
    overrides : list[str], optional
        ``key=value`` string overrides applied on top of the loaded YAML.
    config_path : str | Path, optional
        YAML config file to load instead of ``config/base/default.yaml``.
        Lets ``training/train/train_rl.py`` load the Chain B variant configs
        (``config/features_*_mtf.yaml``) just like ``scripts/train_rl.py``.
    """
    cfg_path = Path(config_path) if config_path else _DEFAULT_CFG
    base = load_config_overlay(_DEFAULT_CFG)
    extra = load_config_overlay(cfg_path) if config_path else OmegaConf.create()
    # Merge over default.yaml: works both for Chain B/F variant *fragments*
    # (config/features_*_mtf.yaml only override the features.* keys they set,
    # everything else comes from defaults) and for full standalone configs.
    cfg = merge_config_overlay(base, extra)
    return apply_overrides(cfg, overrides)


def load_config_overlay(path: str | Path) -> DictConfig:
    """Load one YAML mapping and reject list/scalar roots before merging."""
    overlay = OmegaConf.load(Path(path))
    if not isinstance(overlay, DictConfig):
        raise ValueError(f"configuration overlay root must be a mapping: {path}")
    return overlay


def merge_config_overlay(base: DictConfig, overlay: Mapping[str, Any] | DictConfig) -> DictConfig:
    """Validate a partial config against ``base`` and merge it once.

    All YAML overlays share this entry point so nested typos and section/type
    mismatches are rejected consistently in training and live configuration.
    """
    overlay_cfg = overlay if isinstance(overlay, DictConfig) else OmegaConf.create(dict(overlay))
    base_container = OmegaConf.to_container(base, resolve=False)
    overlay_container = OmegaConf.to_container(overlay_cfg, resolve=False)
    if not isinstance(base_container, Mapping) or not isinstance(overlay_container, Mapping):
        raise ValueError("configuration base and overlay roots must be mappings")
    base_mapping = cast(Mapping[str, Any], base_container)
    overlay_mapping = cast(Mapping[str, Any], overlay_container)
    reject_unknown_keys(overlay_mapping, base_mapping)
    return cast(DictConfig, OmegaConf.merge(base, overlay_cfg))


def apply_overrides(cfg: DictConfig, overrides: list[str] | None) -> DictConfig:
    """Apply ``key=value`` string overrides on top of an already-merged ``cfg``.

    Split out of :func:`load_config` so callers that merge an extra layer can
    apply CLI overrides *last*. ``train_rl.load_merged_config`` used to call
    ``load_config(overrides)`` and then merge the strategy variant YAML on top,
    which silently reverted every CLI override — that is why
    ``--overrides env.reward_mode=rr`` stopped taking effect for Idea 1/2 runs.

    Parameters
    ----------
    cfg : DictConfig
        Config to mutate in place; returned for convenience.
    overrides : list[str], optional
        ``key=value`` strings applied after the merge.
    """
    if not overrides:
        return cfg
        # Snapshot the *pre-override* config so keys introduced by a variant merge
        # that already happened are not flagged as typos.
    known_paths = _leaf_paths(cfg)
    for ov in overrides:
        key = ov.partition("=")[0].strip()
        if key and key not in known_paths:
            raise ValueError(
                f"override key {key!r} does not exist in default.yaml — check for a typo"
            )
        _, _, val = ov.partition("=")
        # Try to coerce to int/float/bool before storing
        coerced: object = val
        try:
            coerced = int(val)
        except ValueError:
            try:
                coerced = float(val)
            except ValueError:
                if val.lower() in ("true", "false"):
                    coerced = val.lower() == "true"
        OmegaConf.update(cfg, key.strip(), coerced, merge=True)
    return cfg


def _leaf_paths(cfg: DictConfig, prefix: str = "") -> set[str]:
    """Return all dot-paths to *leaf* keys (including explicit ``null`` leaves)."""
    paths: set[str] = set()
    for k in cfg.keys():
        key = str(k)
        path = f"{prefix}.{key}" if prefix else key
        child = cfg[k]
        if isinstance(child, DictConfig):
            paths |= _leaf_paths(child, path)
        else:
            paths.add(path)
    return paths
