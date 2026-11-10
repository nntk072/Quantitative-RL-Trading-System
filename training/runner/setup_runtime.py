"""Prepare data, configuration, and environment assets for an RL training run."""

from __future__ import annotations

import logging
from typing import Any

from .configuration_stage import _prepare_training_configuration
from .data_stage import _prepare_training_data
from .run_assets_stage import _prepare_run_assets
from .stages import TrainingPreparation

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

__all__ = ["TrainingPreparation", "prepare_training_run"]


def prepare_training_run(args: Any | None = None) -> TrainingPreparation:
    """Resolve config, data/features, and run assets before any policy learning starts.

    Args:
        args: Optional parsed training arguments; parse process arguments when omitted.

    Returns:
        Prepared training configuration, data, and run assets.
    """
    config_stage = _prepare_training_configuration(args)
    data_stage = _prepare_training_data(config_stage)
    return _prepare_run_assets(config_stage, data_stage)
