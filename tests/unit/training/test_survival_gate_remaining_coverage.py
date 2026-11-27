from __future__ import annotations

import pytest
from omegaconf import OmegaConf

from training.configuration.survival_gate import survival_config_identity


def test_survival_config_identity_rejects_non_mapping_root() -> None:
    config = OmegaConf.create(["not", "a", "configuration mapping"])

    with pytest.raises(ValueError, match="resolved training configuration must be a mapping"):
        survival_config_identity(config)
