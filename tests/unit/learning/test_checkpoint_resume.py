from __future__ import annotations

from pathlib import Path
from typing import Any
from zipfile import ZipFile

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


def test_legacy_checkpoint_migration_rebinds_archived_tcn_policy_on_cpu(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from gymnasium import spaces

    from learning.rl import ppo
    from models.encoders import LegacyTCNEncoderV1, TCNEncoder

    archive_path = tmp_path / "legacy.zip"
    with ZipFile(archive_path, "w") as archive:
        archive.writestr("data", "synthetic saved data")
    action_space = spaces.Box(low=-1.0, high=1.0, shape=(4,))
    monkeypatch.setattr(checkpoint, "_install_pre_reorganization_checkpoint_modules", lambda: None)
    monkeypatch.setattr(
        checkpoint,
        "json_to_data",
        lambda _payload: {
            "action_space": action_space,
            "policy_kwargs": {"features_extractor_class": TCNEncoder, "net_arch": [64]},
        },
    )
    loaded: dict[str, Any] = {}

    def load(path: Path, *, device: str, custom_objects: dict[str, Any]) -> object:
        loaded.update(path=path, device=device, custom_objects=custom_objects)
        return object()

    monkeypatch.setattr(checkpoint, "PPO", type("FakePPO", (), {"load": staticmethod(load)}))

    result = checkpoint.load_sb3_checkpoint(
        archive_path,
        legacy_layout_key="legacy4_no_exit_v1",
        device="cuda",
        algo="PPO",
    )

    assert result is not None
    assert loaded["path"] == archive_path
    assert loaded["device"] == "cpu"
    assert loaded["custom_objects"]["policy_class"] is ppo.LegacyClampedStdMultiInputPolicy
    assert loaded["custom_objects"]["policy_kwargs"] == {
        "features_extractor_class": LegacyTCNEncoderV1,
        "net_arch": [64],
    }


@pytest.mark.parametrize(
    ("algo", "legacy_key", "message"),
    [
        ("a2c", None, "unsupported SB3 checkpoint algorithm"),
        ("sac", "legacy4_no_exit_v1", "supported only for PPO"),
    ],
)
def test_checkpoint_loader_rejects_unsupported_algorithms_and_migrations(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    algo: str,
    legacy_key: str | None,
    message: str,
) -> None:
    monkeypatch.setattr(checkpoint, "_install_pre_reorganization_checkpoint_modules", lambda: None)

    with pytest.raises(ValueError, match=message):
        checkpoint.load_sb3_checkpoint(
            tmp_path / "not-needed.zip",
            legacy_layout_key=legacy_key,
            algo=algo,
        )


def test_checkpoint_validation_wrappers_enforce_action_spaces_and_forward_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from gymnasium import spaces

    from learning.rl import agent

    model = type("FakeModel", (), {"action_space": spaces.Box(-1.0, 1.0, shape=(4,))})()
    expected_schema = {"version": "overlay-v2"}
    calls: list[tuple[Any, ...]] = []
    adapter = object()

    def validate_overlay(*args: Any, **kwargs: Any) -> str:
        calls.append((args, kwargs))
        return "legacy4_no_exit_v1_to_overlay-action-v2-5"

    monkeypatch.setattr(
        agent,
        "validate_model_action_schema",
        validate_overlay,
    )
    monkeypatch.setattr(
        agent, "LegacyFourToFiveActionAdapter", lambda candidate: (adapter, candidate)
    )
    monkeypatch.setattr(
        agent,
        "validate_model_observation_schema",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    discrete_calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(
        agent,
        "validate_model_discrete_action_schema",
        lambda *args, **kwargs: discrete_calls.append((args, kwargs)),
    )

    assert checkpoint.validate_sb3_overlay_action_schema(
        model,
        expected_schema,
        allow_legacy=True,
        legacy_layout_key="legacy4_no_exit_v1",
    ) == (adapter, model)
    assert calls[0][0] == (model, expected_schema)
    checkpoint.validate_sb3_observation_schema(
        model, {"version": "observation-v2"}, allow_legacy_v1=True
    )
    assert calls[1][1] == {"allow_legacy_v1": True}

    discrete_model = type("DiscreteModel", (), {"action_space": spaces.Discrete(5)})()
    assert checkpoint.is_sb3_discrete_model(discrete_model) is True
    checkpoint.validate_sb3_discrete_action_schema(
        discrete_model,
        {"width": 5},
        {"width": 5},
        allow_legacy=False,
        legacy_layout_key=None,
    )
    assert discrete_calls[0][0] == (discrete_model, {"width": 5}, {"width": 5})

    with pytest.raises(ValueError, match="must use a Discrete action space"):
        checkpoint.validate_sb3_discrete_action_schema(
            model,
            {"width": 5},
            None,
            allow_legacy=False,
            legacy_layout_key=None,
        )

    with pytest.raises(ValueError, match="must be Box for strategy overlay"):
        checkpoint.validate_sb3_overlay_action_schema(
            discrete_model,
            expected_schema,
            allow_legacy=False,
            legacy_layout_key=None,
        )
