"""Read-only observation-array materialization for vectorized environments."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from training.setup.environments import strategy_from_cfg


def publish_observation_memmap(
    features: pd.DataFrame,
    bars: pd.DataFrame,
    cfg: Any,
    path: Path,
) -> str | None:
    """Write one model-observation array so workers can mmap it read-only.

    Single-environment runs retain the existing private ``to_numpy`` path.
    The pandas frame is still passed to the bundle builder; this removes only
    the additional float32 matrix copy per worker.
    """
    if int(cfg.env.get("n_envs", 1)) <= 1:
        return None
    strategy, _, _ = strategy_from_cfg(cfg)
    from simulation.environment.bundles import observation_features

    array, _ = observation_features(bars, features, strategy.raw_columns)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(path, array)
    return str(path)
