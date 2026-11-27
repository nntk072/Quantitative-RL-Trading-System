"""Behavior contracts for isolated experiment workers and artifact admission."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from experiments.runs import artifact_validation, variant_worker


def test_worker_value_parsers_keep_order_and_discard_empty_entries() -> None:
    assert variant_worker._values(" 1, 2\n3 ,,  ") == ["1", "2", "3"]
    assert variant_worker._config_overrides(" alpha=1\n\n beta=2  ") == ["alpha=1", "beta=2"]


def test_worker_command_combines_resume_report_data_and_selection_options(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PYTHON", "/opt/venv/bin/python")
    monkeypatch.setenv("RESUME_CHECKPOINT", str(tmp_path / "checkpoint.zip"))
    monkeypatch.setenv("QUANT_RL_FULL_REPORTS", "1")
    monkeypatch.setenv("QUANT_RL_FAST_REPORTS", "1")
    monkeypatch.setenv("QUANT_RL_DATA_SOURCE", "bundle")
    monkeypatch.setenv("QUANT_RL_ALLOW_OOS_SELECTION", "1")
    resolved: dict[str, Any] = {"seed": 5}
    monkeypatch.setattr(variant_worker, "train_args", lambda config, seed: ["--seed", str(seed)])

    command = variant_worker._worker_command(5, tmp_path / "output", resolved)

    assert command[:5] == [
        "/opt/venv/bin/python",
        "-u",
        "-m",
        "training.runner.training",
        "--resume-checkpoint",
    ]
    assert command[5] == str(tmp_path / "checkpoint.zip")
    assert "output.report_profile=full" in command
    assert "output.max_order_charts=200" in command
    assert "output.save_html=true" in command
    assert "output.report_profile=experiment_run_fast" not in command
    assert "env.data_source=bundle" in command
    assert "--allow-locked-oos-for-selection" in command
    assert command[command.index("--out") + 1] == str(tmp_path / "output")


def test_worker_command_supports_fast_report_profile_and_frames_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("QUANT_RL_FULL_REPORTS", raising=False)
    monkeypatch.setenv("QUANT_RL_FAST_REPORTS", "1")
    monkeypatch.setenv("QUANT_RL_DATA_SOURCE", "frames")
    monkeypatch.setenv("QUANT_RL_ALLOW_OOS_SELECTION", "0")
    monkeypatch.setattr(variant_worker, "train_args", lambda _config, _seed: [])

    command = variant_worker._worker_command(1, Path("output"), {})

    assert "output.report_profile=experiment_run_fast" in command
    assert "output.max_order_charts=0" in command
    assert "output.save_html=false" in command
    assert "env.data_source=frames" in command
    assert "--allow-locked-oos-for-selection" not in command


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("QUANT_RL_DATA_SOURCE", "ticks", "invalid QUANT_RL_DATA_SOURCE"),
        ("QUANT_RL_ALLOW_OOS_SELECTION", "true", "must be 0 or 1"),
    ],
)
def test_worker_command_rejects_unsupported_data_and_selection_values(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str, message: str
) -> None:
    monkeypatch.setenv(name, value)
    if name != "QUANT_RL_DATA_SOURCE":
        monkeypatch.delenv("QUANT_RL_DATA_SOURCE", raising=False)
    if name != "QUANT_RL_ALLOW_OOS_SELECTION":
        monkeypatch.delenv("QUANT_RL_ALLOW_OOS_SELECTION", raising=False)
    monkeypatch.setattr(variant_worker, "train_args", lambda _config, _seed: [])

    with pytest.raises(ValueError, match=message):
        variant_worker._worker_command(1, Path("output"), {})


def _configure_worker(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    seeds: list[int] | None = None,
    dry_run: str = "0",
) -> dict[str, Any]:
    resolved = {
        "variant": "demo",
        "algo": "ppo",
        "arch": "mlp",
        "strategy": "baseline",
        "reward_mode": "pnl",
        "feature_profile": "core",
        "steps": 100,
        "seeds": [3, 4] if seeds is None else seeds,
    }
    monkeypatch.setenv("VARIANT", "demo")
    monkeypatch.setenv("STEPS", "100")
    monkeypatch.setenv("SEEDS", "3, 4" if seeds is None else ",".join(map(str, seeds)))
    monkeypatch.setenv("OUT_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("DRY_RUN", dry_run)
    monkeypatch.delenv("SEED", raising=False)
    monkeypatch.delenv("VAE_PATH", raising=False)
    monkeypatch.delenv("EXPERIMENT_RUN_WORKER_PID_FILE", raising=False)
    for name in (
        "PYTHON",
        "RESUME_CHECKPOINT",
        "QUANT_RL_FULL_REPORTS",
        "QUANT_RL_FAST_REPORTS",
        "QUANT_RL_DATA_SOURCE",
        "QUANT_RL_ALLOW_OOS_SELECTION",
        "QUANT_RL_CONFIG_OVERRIDES",
        "GPU_ID",
        "QUANT_RL_MAX_N_ENVS",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(variant_worker, "resolve_variant", lambda *args, **kwargs: resolved)
    monkeypatch.setattr(
        variant_worker,
        "train_args",
        lambda config, seed: ["--steps", str(config["steps"]), "--seed", str(seed)],
    )
    return resolved


def test_worker_dry_run_resolves_overrides_writes_metadata_and_never_launches(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    resolved = _configure_worker(monkeypatch, tmp_path, dry_run="1")
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def resolve(*args: Any, **kwargs: Any) -> Any:
        calls.append((args, kwargs))
        return resolved

    monkeypatch.setattr(
        variant_worker,
        "resolve_variant",
        resolve,
    )
    monkeypatch.setenv("VAE_PATH", "vae.zip")
    monkeypatch.setenv("QUANT_RL_CONFIG_OVERRIDES", "env.normalize=false\n\noutput.save_html=false")
    monkeypatch.setenv("EXPERIMENT_RUN_WORKER_PID_FILE", str(tmp_path / "pid" / "worker.json"))
    monkeypatch.setattr(
        cast(Any, variant_worker).subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("dry-run must not launch a worker"),
    )

    assert variant_worker.main() == 0

    assert calls[0][0] == ("demo",)
    assert calls[0][1] == {
        "steps": 100,
        "seeds": [3, 4],
        "vae_path": "vae.zip",
        "config_overrides": ["env.normalize=false", "output.save_html=false"],
    }
    output = tmp_path / "runs"
    assert json.loads((output / "demo__seed3" / "resolved_config.json").read_text())["seed"] == 3
    assert json.loads((output / "demo__seed4" / "resolved_config.json").read_text())[
        "train_args"
    ] == ["--steps", "100", "--seed", "4"]
    assert json.loads((tmp_path / "pid" / "worker.json").read_text())["pid"] > 0
    assert "DRY_RUN demo__seed3" in capsys.readouterr().out


@pytest.mark.parametrize(("returncode", "expected_marker"), [(0, "done"), (7, "failed")])
def test_worker_records_success_and_failure_markers_without_real_training(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    returncode: int,
    expected_marker: str,
) -> None:
    _configure_worker(monkeypatch, tmp_path, seeds=[9])
    calls: list[dict[str, Any]] = []

    def fake_run(command, **kwargs):
        calls.append({"command": command, **kwargs})
        return SimpleNamespace(returncode=returncode)

    monkeypatch.setattr(cast(Any, variant_worker).subprocess, "run", fake_run)

    result = variant_worker.main()

    assert result == (0 if returncode == 0 else returncode)
    assert calls[0]["cwd"] == variant_worker.ROOT
    assert calls[0]["env"]["CUDA_VISIBLE_DEVICES"] == "0"
    assert calls[0]["env"]["QUANT_RL_MAX_N_ENVS"] == "64"
    run_output = tmp_path / "runs" / "demo__seed9"
    assert (tmp_path / "runs" / f"demo__seed9.{expected_marker}").exists()
    assert not (
        tmp_path / "runs" / f"demo__seed9.{'failed' if expected_marker == 'done' else 'done'}"
    ).exists()
    assert (run_output / "resolved_config.json").is_file()


def test_worker_skips_completed_runs_and_removes_stale_failure_marker(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _configure_worker(monkeypatch, tmp_path, seeds=[9])
    output = tmp_path / "runs"
    output.mkdir()
    done = output / "demo__seed9.done"
    failed = output / "demo__seed9.failed"
    done.touch()
    failed.touch()
    monkeypatch.setattr(
        cast(Any, variant_worker).subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("completed run must be skipped"),
    )

    assert variant_worker.main() == 0

    assert done.is_file()
    assert not failed.exists()
    assert "SKIP demo__seed9" in capsys.readouterr().out


def test_worker_seed_override_runs_only_the_requested_seed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _configure_worker(monkeypatch, tmp_path, seeds=[3, 4])
    monkeypatch.setenv("SEED", "8")
    commands: list[list[str]] = []

    def run_worker(command: list[str], **_kwargs: Any) -> SimpleNamespace:
        commands.append(command)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(cast(Any, variant_worker).subprocess, "run", run_worker)

    assert variant_worker.main() == 0

    assert len(commands) == 1
    assert commands[0][commands[0].index("--seed") + 1] == "8"
    assert (tmp_path / "runs" / "demo__seed8.done").is_file()


def test_worker_requires_a_registered_variant_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VARIANT", raising=False)
    with pytest.raises(ValueError, match="VARIANT is required"):
        variant_worker.main()


@pytest.mark.parametrize(
    "value",
    [
        None,
        [],
        {"deterministic": 1, "locked_oos_role": "final_report_only"},
        {"deterministic": True, "locked_oos_role": "final_report_only", "unknown": False},
        {
            "deterministic": True,
            "locked_oos_role": "final_report_only",
            "locked_oos_exposure": "unknown",
        },
        {
            "deterministic": True,
            "locked_oos_role": "final_report_only",
            "selection_allowed": 1,
        },
        {
            "deterministic": True,
            "locked_oos_role": "final_report_only",
            "selection_allowed": True,
        },
        {"deterministic": True, "locked_oos_role": "selection"},
    ],
)
def test_report_only_evaluation_metadata_rejects_invalid_contracts(value: object) -> None:
    with pytest.raises(ValueError):
        artifact_validation.validate_experiment_run_evaluation(value)


def test_report_only_evaluation_metadata_accepts_frozen_report_configuration() -> None:
    evaluation = {
        "locked_oos_role": "final_report_only",
        "locked_oos_exposure": "previously_inspected_holdout",
        "selection_allowed": False,
        "deterministic": False,
    }

    assert artifact_validation.validate_experiment_run_evaluation(evaluation) == evaluation


def test_hash_run_artifacts_records_only_completed_run_inputs_and_outputs(tmp_path: Path) -> None:
    run = tmp_path / "variant__seed7"
    (run / "nested").mkdir(parents=True)
    selected = {
        "attempt_provenance.json": b"{}",
        "config.yaml": b"env: {}\n",
        "model/ppo_final.zip": b"model",
        "nested/training_log.json": b"{}",
        "resolved_config.json": b"{}",
    }
    ignored = {"notes.txt": b"note", "model/ppo_100_steps.zip": b"intermediate"}
    for name, content in {**selected, **ignored}.items():
        path = run / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    result = artifact_validation.hash_run_artifacts(run)

    assert set(result) == set(selected)
    assert result["config.yaml"] == hashlib.sha256(selected["config.yaml"]).hexdigest()
    assert (
        result["model/ppo_final.zip"] == hashlib.sha256(selected["model/ppo_final.zip"]).hexdigest()
    )
