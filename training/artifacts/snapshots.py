"""Immutable, atomic snapshots of the effective training configuration."""

from __future__ import annotations

from pathlib import Path

from omegaconf import DictConfig, OmegaConf

from artifacts.atomic import write_text_atomic


def write_run_config_snapshot(run_dir: str | Path, config: DictConfig) -> Path:
    """Write ``config.yaml`` once, rejecting an attempt to rewrite run identity."""
    path = Path(run_dir) / "config.yaml"
    contents = OmegaConf.to_yaml(config, resolve=True)
    if path.exists():
        if path.read_text(encoding="utf-8") != contents:
            raise FileExistsError(f"resolved configuration snapshot already differs: {path}")
        return path
    return write_text_atomic(path, contents)


__all__ = ["write_run_config_snapshot"]
