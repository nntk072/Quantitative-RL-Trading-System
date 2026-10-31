"""Immutable, atomic snapshots of resolved run configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from omegaconf import OmegaConf

from artifacts.atomic import write_text_atomic


def write_config_snapshot(run_dir: str | Path, config: Any) -> Path:
    """Write a resolved ``config.yaml`` once, rejecting identity rewrites."""
    path = Path(run_dir) / "config.yaml"
    if not OmegaConf.is_config(config):
        config = OmegaConf.create(config)
    contents = OmegaConf.to_yaml(config, resolve=True)
    if path.exists():
        if path.read_text(encoding="utf-8") != contents:
            raise FileExistsError(f"resolved configuration snapshot already differs: {path}")
        return path
    return write_text_atomic(path, contents)


__all__ = ["write_config_snapshot"]
