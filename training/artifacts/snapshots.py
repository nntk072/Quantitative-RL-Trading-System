"""Training compatibility export for shared resolved-config snapshots."""

from pathlib import Path
from typing import Any

from artifacts.config_snapshot import write_config_snapshot


def write_run_config_snapshot(run_dir: str | Path, config: Any) -> Path:
    """Retain the training artifact API while sharing one snapshot writer."""
    return write_config_snapshot(run_dir, config)


__all__ = ["write_run_config_snapshot"]
