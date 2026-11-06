from __future__ import annotations

from pathlib import Path

import pytest

import learning.rl.checkpoint as checkpoint


class _FakePPO:
    loaded: tuple[Path, object, object] | None = None

    @classmethod
    def load(cls, path, *, env=None, device):
        cls.loaded = (path, env, device)
        return cls()


class _FakeSAC(_FakePPO):
    loaded: tuple[Path, object, object] | None = None


@pytest.mark.unit
@pytest.mark.parametrize(("algo", "algorithm"), [("ppo", _FakePPO), ("sac", _FakeSAC)])
def test_training_checkpoint_loader_resumes_selected_sb3_algorithm(
    monkeypatch, tmp_path: Path, algo: str, algorithm: type[_FakePPO]
) -> None:
    monkeypatch.setattr(checkpoint, "_install_pre_reorganization_checkpoint_modules", lambda: None)
    monkeypatch.setattr(checkpoint, "PPO", _FakePPO)
    monkeypatch.setattr(checkpoint, "SAC", _FakeSAC)
    env = object()
    device = object()

    result = checkpoint.load_sb3_training_checkpoint(
        tmp_path / "model.zip", env=env, device=device, algo=algo
    )

    assert isinstance(result, algorithm)
    assert algorithm.loaded == (tmp_path / "model.zip", env, device)


@pytest.mark.unit
def test_training_checkpoint_loader_rejects_unknown_algorithm(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(checkpoint, "_install_pre_reorganization_checkpoint_modules", lambda: None)
    with pytest.raises(ValueError, match="unsupported SB3 training checkpoint algorithm"):
        checkpoint.load_sb3_training_checkpoint(
            tmp_path / "model.zip", env=object(), device="cpu", algo="a2c"
        )


@pytest.mark.unit
@pytest.mark.parametrize(("algo", "algorithm"), [("ppo", _FakePPO), ("sac", _FakeSAC)])
def test_inference_checkpoint_loader_resolves_manifest_algorithm(
    monkeypatch, tmp_path: Path, algo: str, algorithm: type[_FakePPO]
) -> None:
    monkeypatch.setattr(checkpoint, "_install_pre_reorganization_checkpoint_modules", lambda: None)
    monkeypatch.setattr(checkpoint, "PPO", _FakePPO)
    monkeypatch.setattr(checkpoint, "SAC", _FakeSAC)

    result = checkpoint.load_sb3_checkpoint(tmp_path / "model.zip", algo=algo, device="cpu")

    assert isinstance(result, algorithm)
    assert algorithm.loaded == (tmp_path / "model.zip", None, "cpu")
