"""Configured session calendar loading for causal market-data consumers."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from omegaconf import DictConfig, OmegaConf

from configuration.paths import repository_root


def scheduled_session_close_map(cfg: DictConfig | None) -> dict[str, str]:
    """Load date-specific NY close times from the resolved data configuration."""
    if cfg is None:
        return {}
    schedule_value = OmegaConf.select(cfg, "data.session_schedule_file")
    if not schedule_value:
        return {}
    schedule_path = Path(str(schedule_value)).expanduser()
    if not schedule_path.is_absolute():
        schedule_path = repository_root(__file__) / schedule_path
    if not schedule_path.is_file():
        raise FileNotFoundError(f"configured session schedule is missing: {schedule_path}")
    schedule = pd.read_csv(schedule_path, dtype=str)
    required = {"session_date", "scheduled_ny_close_broker_time"}
    if not required.issubset(schedule.columns):
        raise ValueError(
            f"session schedule missing columns: {sorted(required - set(schedule.columns))}"
        )
    return dict(
        zip(
            schedule["session_date"].astype(str),
            schedule["scheduled_ny_close_broker_time"].astype(str),
            strict=True,
        )
    )
