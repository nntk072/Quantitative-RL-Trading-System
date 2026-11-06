from __future__ import annotations

from types import SimpleNamespace

import pytest

from training.configuration import vae_admission
from training.runner import configuration_stage
from training.runner.vae import prepare_data


def test_vae_candidate_is_rejected_until_input_evidence_passes() -> None:
    vae_admission.require_vae_candidate_admissible(False)

    with pytest.raises(ValueError, match="no session dates"):
        vae_admission.require_vae_candidate_admissible(True)


def test_canonical_training_configuration_blocks_vae_before_config_load(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        configuration_stage,
        "parse_train_args",
        lambda: SimpleNamespace(use_vae=True),
    )

    with pytest.raises(SystemExit, match="validity mask"):
        configuration_stage._prepare_training_configuration()


def test_vae_data_preparation_blocks_undated_dataset_before_file_access() -> None:
    with pytest.raises(RuntimeError, match="chronological train-only fitting"):
        prepare_data({"data_path": "/missing/pre_ny_sequences.npy"})
