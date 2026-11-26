from __future__ import annotations

import logging
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import numpy as np
import pytest
import torch
import yaml
from torch import nn
from torch.utils.data import DataLoader, Dataset

from training.configuration import vae_admission
from training.runner import configuration_stage
from training.runner import vae as vae_runner
from training.runner.vae import PreNYSequenceDataset, VAELoss, prepare_data


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


def test_pre_ny_dataset_returns_float_tensors_and_weighted_vae_loss() -> None:
    dataset = PreNYSequenceDataset(np.asarray([[[1.0, 2.0]]], dtype=np.float64))
    sample = dataset[0]

    assert len(dataset) == 1
    assert sample.dtype == torch.float32
    torch.testing.assert_close(sample, torch.tensor([[1.0, 2.0]]))

    loss = VAELoss(reconstruction_weight=2.0, kl_weight=3.0)
    total = loss(
        torch.tensor([[1.0, 2.0]]),
        torch.zeros((1, 2)),
        torch.ones((1, 1)),
        torch.zeros((1, 1)),
    )
    torch.testing.assert_close(total, torch.tensor(11.5))


def test_vae_data_preparation_uses_saved_shape_and_partitions_all_samples(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    data = np.arange(20 * 4 * 3, dtype=np.float32).reshape(20, 4, 3)
    data_path = tmp_path / "sequences.npy"
    np.save(data_path, data)
    monkeypatch.setattr(vae_runner, "require_vae_candidate_admissible", lambda _enabled: None)

    with caplog.at_level(logging.WARNING, logger=vae_runner.logger.name):
        train, validation, test = prepare_data(
            {"data_path": str(data_path), "seq_len": 8, "n_features": 5}
        )

    assert (len(train), len(validation), len(test)) == (14, 3, 3)
    assert "Data sequence length 4 does not match config 8" in caplog.text
    assert "Data features 3 does not match config 5" in caplog.text
    assert isinstance(train.dataset, PreNYSequenceDataset)
    assert train.dataset.data.shape == (20, 4, 3)
    partitions = [set(split.indices) for split in (train, validation, test)]
    assert partitions[0].isdisjoint(partitions[1])
    assert partitions[0].isdisjoint(partitions[2])
    assert partitions[1].isdisjoint(partitions[2])
    assert set.union(*partitions) == set(range(20))


def test_vae_data_preparation_rejects_non_sequence_arrays(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_path = tmp_path / "not-sequences.npy"
    np.save(data_path, np.zeros((4, 3), dtype=np.float32))
    monkeypatch.setattr(vae_runner, "require_vae_candidate_admissible", lambda _enabled: None)

    with pytest.raises(ValueError, match="Expected 3D data.*got 2D"):
        prepare_data({"data_path": str(data_path), "seq_len": 3, "n_features": 3})


class _TinyTrainingVAE(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.scale = nn.Parameter(torch.tensor(0.25))

    def forward(self, batch: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        batch_size = batch.shape[0]
        return (
            batch * self.scale,
            torch.zeros((batch_size, 1), device=batch.device),
            torch.zeros((batch_size, 1), device=batch.device),
        )


class _TensorListDataset(Dataset[torch.Tensor]):
    def __init__(self, values: list[torch.Tensor]) -> None:
        self.values = values

    def __len__(self) -> int:
        return len(self.values)

    def __getitem__(self, index: int) -> torch.Tensor:
        return self.values[index]


def test_vae_training_saves_best_weights_and_evaluates_on_cpu(tmp_path: Path) -> None:
    samples = [torch.ones((2, 3)), torch.full((2, 3), 2.0)]
    sample_dataset = _TensorListDataset(samples)
    train_loader = DataLoader(sample_dataset, batch_size=2)
    validation_loader = DataLoader(sample_dataset, batch_size=2)
    model = _TinyTrainingVAE()

    trained = vae_runner.train_vae(
        cast(Any, model),
        train_loader,
        validation_loader,
        {"lr": 0.01, "epochs": 2, "output_dir": str(tmp_path)},
        torch.device("cpu"),
    )
    trained_model = cast(_TinyTrainingVAE, trained)
    test_loss = vae_runner.evaluate_vae(
        cast(Any, trained_model), validation_loader, torch.device("cpu")
    )

    assert trained_model is model
    assert float(trained_model.scale.detach()) > 0.25
    assert np.isfinite(test_loss)
    saved_state = torch.load(tmp_path / "vae_best.pth", map_location="cpu", weights_only=True)
    assert set(saved_state) == {"scale"}
    assert torch.isfinite(saved_state["scale"])


def test_vae_main_writes_final_checkpoint_and_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "vae.yaml"
    output_dir = tmp_path / "run"
    config: dict[str, Any] = {
        "data_path": "unused.npy",
        "seq_len": 2,
        "n_features": 1,
        "latent_dim": 1,
        "batch_size": 1,
        "output_dir": str(output_dir),
        "device": "cpu",
        "epochs": 1,
    }
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    model = _TinyTrainingVAE()
    monkeypatch.setattr(vae_runner, "require_vae_candidate_admissible", lambda _enabled: None)
    monkeypatch.setattr(vae_runner, "get_device", lambda _device: torch.device("cpu"))
    monkeypatch.setattr(vae_runner, "prepare_data", lambda _config: ([torch.ones((2, 1))], [], []))

    def make_model(**_kwargs: Any) -> _TinyTrainingVAE:
        return model

    monkeypatch.setattr(vae_runner, "VAE", make_model)
    monkeypatch.setattr(vae_runner, "train_vae", lambda candidate, *_args: candidate)
    monkeypatch.setattr(vae_runner, "evaluate_vae", lambda *_args: 0.0)
    monkeypatch.setattr(sys, "argv", ["qrl-train-vae", "--config", str(config_path)])

    vae_runner.main()

    assert (output_dir / "vae_final.pth").is_file()
    assert yaml.safe_load((output_dir / "config.yaml").read_text(encoding="utf-8")) == config


def test_vae_main_blocks_before_creating_output_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_dir = tmp_path / "blocked-run"
    config_path = tmp_path / "blocked.yaml"
    config_path.write_text(yaml.safe_dump({"output_dir": str(output_dir)}), encoding="utf-8")

    def reject_candidate(_enabled: bool) -> None:
        raise ValueError("candidate evidence is incomplete")

    monkeypatch.setattr(vae_runner, "require_vae_candidate_admissible", reject_candidate)
    monkeypatch.setattr(sys, "argv", ["qrl-train-vae", "--config", str(config_path)])

    with pytest.raises(SystemExit, match="candidate evidence is incomplete"):
        vae_runner.main()

    assert not output_dir.exists()
