from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import gymnasium as gym
import numpy as np
import pytest
from gymnasium import spaces
from omegaconf import OmegaConf
from scripts.research.benchmarks.measure_ppo_throughput import (
    PROJECT_ROOT,
    _apply_profile_overrides,
    _json_default,
    _NvidiaSmiSampler,
    _prepare_bundle,
    _process_tree_cpu_seconds,
    _ProcessTreeSampler,
    _sample_summary,
    _scale_profile_config,
    _StepTimingWrapper,
    _time_callable,
    _time_method_calls,
    _time_tensor_backward,
    _validate_high_throughput_runtime_identity,
    _working_tree_patch_identity,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FPS_PROBE_SCRIPT = REPO_ROOT / "scripts" / "research" / "benchmarks" / "run_fps_probe.sh"
BATCH_SCRIPT = REPO_ROOT / "scripts" / "research" / "benchmarks" / "run_pipelined_ppo_wp0.sbatch"


def test_benchmark_imports_project_modules_from_its_own_checkout() -> None:
    assert PROJECT_ROOT == REPO_ROOT
    assert str(REPO_ROOT) == sys.path[0]


def test_working_tree_identity_includes_dirty_sources_but_excludes_run_outputs(tmp_path) -> None:
    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True, text=True)

    git("init", "-q")
    git("config", "user.email", "benchmark@example.invalid")
    git("config", "user.name", "Benchmark Test")
    tracked = tmp_path / "tracked.py"
    tracked.write_text("VALUE = 1\n", encoding="utf-8")
    git("add", "tracked.py")
    git("commit", "-q", "-m", "baseline")
    baseline = _working_tree_patch_identity(tmp_path)
    assert baseline["working_tree_dirty"] is False

    tracked.write_text("VALUE = 2\n", encoding="utf-8")
    untracked = tmp_path / "new_source.py"
    untracked.write_text("NEW_VALUE = 3\n", encoding="utf-8")
    output = tmp_path / "measurements" / "case.json"
    output.parent.mkdir()
    output.write_text("{}\n", encoding="utf-8")
    changed = _working_tree_patch_identity(tmp_path)

    assert changed["working_tree_dirty"] is True
    assert changed["patch_identity_sha256"] != baseline["patch_identity_sha256"]
    assert changed["tracked_diff_sha256"] != baseline["tracked_diff_sha256"]
    assert changed["untracked_source_sha256"] == {
        "new_source.py": hashlib.sha256(untracked.read_bytes()).hexdigest()
    }
    stable_identity = changed["patch_identity_sha256"]
    output.write_text('{"updated": true}\n', encoding="utf-8")
    scheduler_output = tmp_path / "slurm-123.out"
    scheduler_output.write_text("measurement progress\n", encoding="utf-8")
    after_outputs = _working_tree_patch_identity(tmp_path)
    assert after_outputs["patch_identity_sha256"] == stable_identity


def test_profile_overrides_are_explicit_and_preserve_production_defaults() -> None:
    cfg = OmegaConf.create(
        {
            "env": {"n_envs": 64},
            "ppo": {"n_steps": 8192, "batch_size": 4096},
        }
    )

    _apply_profile_overrides(cfg, n_envs=None, rollout_steps_per_env=None)

    assert cfg.env.n_envs == 64
    assert cfg.ppo.n_steps == 8192
    assert cfg.ppo.batch_size == 4096


def test_rollout_override_is_global_steps_times_logical_envs() -> None:
    cfg = OmegaConf.create(
        {
            "env": {"n_envs": 32},
            "ppo": {"n_steps": 8192},
        }
    )

    _apply_profile_overrides(cfg, n_envs=None, rollout_steps_per_env=128)

    assert cfg.ppo.n_steps == 4096


def test_batch_size_override_is_applied_after_hardware_scaling() -> None:
    cfg = OmegaConf.create(
        {
            "env": {"n_envs": 64},
            "ppo": {"n_steps": 8192, "batch_size": 4096},
        }
    )

    _apply_profile_overrides(cfg, n_envs=None, rollout_steps_per_env=None, batch_size=8192)

    assert cfg.ppo.batch_size == 8192


def test_exact_quality_geometry_is_preserved_during_probe_scaling(monkeypatch) -> None:
    cfg = OmegaConf.create(
        {
            "env": {"n_envs": 8},
            "ppo": {"n_steps": 2048, "batch_size": 512},
            "quality_execution": {"exact_n_envs": True},
        }
    )
    observed: dict[str, bool] = {}

    def fake_scale(_cfg, _device, _arch, *, preserve_ppo_geometry=False):
        observed["preserve_ppo_geometry"] = preserve_ppo_geometry
        if not preserve_ppo_geometry:
            cfg.env.n_envs = 64
            cfg.ppo.n_steps = 8192

    monkeypatch.setattr(
        "scripts.research.benchmarks.measure_ppo_throughput.scale_training_cfg",
        fake_scale,
    )
    _scale_profile_config(cfg, "cuda", "mtf_reasoning")

    assert observed["preserve_ppo_geometry"] is True
    assert cfg.env.n_envs == 8
    assert cfg.ppo.n_steps == 2048


def test_numpy_scalars_are_json_serializable() -> None:
    assert _json_default(np.int64(7)) == 7
    assert _json_default(np.float32(1.5)) == 1.5


def test_process_tree_cpu_measurement_is_nonnegative() -> None:
    assert _process_tree_cpu_seconds() >= 0.0


def test_environment_step_timer_records_wrapped_steps() -> None:
    env = _StepTimingWrapper(gym.make("CartPole-v1"))
    env.reset(seed=1)

    for _ in range(8):
        env.step(0)

    metrics = env.get_step_timing()
    assert metrics["steps"] == 8
    assert metrics["seconds"] >= 0.0
    assert len(metrics["sampled_step_ms"]) == 1
    env.close()


def test_environment_wrapper_times_observation_construction() -> None:
    class ObservationEnv(gym.Env[Any, Any]):
        observation_space = spaces.Box(low=-1, high=1, shape=(1,), dtype=np.float32)
        action_space = spaces.Discrete(2)

        def _get_observation(self) -> np.ndarray[Any, Any]:
            return np.zeros(1, dtype=np.float32)

        def reset(
            self, *, seed: int | None = None, options: dict[str, Any] | None = None
        ) -> tuple[np.ndarray[Any, Any], dict[str, Any]]:
            del options
            super().reset(seed=seed)
            return self._get_observation(), {}

        def step(
            self, action: int
        ) -> tuple[np.ndarray[Any, Any], float, bool, bool, dict[str, Any]]:
            del action
            return self._get_observation(), 0.0, False, False, {}

    env = _StepTimingWrapper(ObservationEnv())
    env.reset(seed=1)
    for _ in range(2):
        env.step(0)
    metrics = env.get_step_timing()
    assert metrics["observation_construction_calls"] == 3
    assert metrics["observation_construction_seconds"] >= 0.0
    env.close()


def test_sample_summary_reports_bounded_sample_percentiles() -> None:
    assert _sample_summary([]) == {
        "sample_count": 0,
        "total": 0.0,
        "p50": None,
        "p95": None,
    }
    summary = _sample_summary([1.0, 2.0, 3.0], scale=1000.0)

    assert summary["sample_count"] == 3
    assert summary["total"] == 6000.0
    assert summary["p50"] == 2000.0
    assert summary["p95"] == 2900.0


def test_gpu_telemetry_keeps_unsupported_metrics_explicitly_unknown(monkeypatch) -> None:
    sampler = _NvidiaSmiSampler()
    monkeypatch.setattr(sampler, "executable", None)

    report = sampler.stop()

    assert report["available"] is False
    assert report["sm_active_pct"] is None
    assert report["dram_bandwidth"] is None


def test_process_tree_sampler_tracks_profile_phase() -> None:
    sampler = _ProcessTreeSampler(os.getpid(), interval_seconds=0.05)
    assert sampler.current_phase() == "startup"
    with sampler.phase("unit-test-phase"):
        assert sampler.current_phase() == "unit-test-phase"

    report = sampler.stop()

    assert sampler.current_phase() == "startup"
    assert report["available"] is False
    assert report["ipc_bytes"] is None


def test_high_throughput_runtime_identity_fails_closed_on_variant_mismatch() -> None:
    policy_type = type("ThesisConditionedClampedStdMultiInputPolicy", (), {})
    cfg = OmegaConf.create(
        {
            "agent": {"arch": "mtf_shared_tcn_reasoning"},
            "ppo": {"policy_distribution": "thesis_conditioned_v1"},
            "env": {"thesis_actions": True, "vector_backend": "sharded_bundle"},
        }
    )
    model = SimpleNamespace(
        n_envs=64,
        n_steps=256,
        batch_size=4096,
        n_epochs=15,
        policy=policy_type(),
    )
    vec_env = SimpleNamespace(num_envs=64)
    parent_env = SimpleNamespace(
        observation_space=spaces.Dict(
            {"thesis_mask": spaces.Box(low=0, high=1, shape=(109,), dtype=np.float32)}
        )
    )
    config_path = Path("config/research/thesis_mtf_shared_tcn_2m_high_throughput.yaml")

    with pytest.raises(RuntimeError, match="configured_vector_backend"):
        _validate_high_throughput_runtime_identity(cfg, model, vec_env, parent_env, config_path)

    class ShardedBundleVecEnv:
        num_envs = 64

    vec_env_good = ShardedBundleVecEnv()
    result = _validate_high_throughput_runtime_identity(
        cfg, model, vec_env_good, parent_env, config_path
    )

    assert result is not None
    assert result["passed"] is True
    assert result["aggregate_rollout"] == 16384

    cfg.env.vector_backend = "subproc"

    class SubprocVecEnv:
        num_envs = 64

    subproc_env = SubprocVecEnv()
    subproc_result = _validate_high_throughput_runtime_identity(
        cfg, model, subproc_env, parent_env, config_path
    )
    assert subproc_result is not None
    assert subproc_result["vector_backend"] == "SubprocVecEnv"


def test_class_method_timer_restores_class_without_mutating_instance() -> None:
    class Meter:
        def increment(self, value: int) -> int:
            return value + 1

    meter = Meter()
    calls: list[float] = []
    with _time_method_calls(meter, "increment", calls):
        assert meter.increment(4) == 5
        assert "increment" not in vars(meter)

    assert len(calls) == 1
    assert calls[0] >= 0.0
    assert meter.increment(8) == 9


def test_callable_timer_restores_owner_attribute() -> None:
    owner = SimpleNamespace(increment=lambda value: value + 1)
    samples: list[float] = []
    original = owner.increment
    with _time_callable(owner, "increment", samples, range_name="unit-test"):
        assert owner.increment(4) == 5
    assert owner.increment is original
    assert len(samples) == 1
    assert samples[0] >= 0.0


def test_tensor_backward_timer_restores_torch_method() -> None:
    import torch

    original = torch.Tensor.backward
    samples: list[float] = []
    tensor = torch.tensor(2.0, requires_grad=True)
    with _time_tensor_backward(torch, samples, None):
        backward_tensor = cast(Any, tensor * tensor)
        backward_tensor.backward()
    assert tensor.grad is not None
    assert torch.Tensor.backward is original
    assert len(samples) == 1
    assert samples[0] >= 0.0


def test_variant_config_uses_production_strategy_merge_and_cli_override(
    tmp_path: Path,
) -> None:
    cfg, bundle_path, algo, arch = _prepare_bundle(
        tmp_path,
        variant="ladder_a0_flat",
        overrides=[
            "ppo.n_epochs=7",
            "ppo.rollout_buffer_on_device=false",
            "env.vector_backend=sharded_bundle",
            "env.vector_shards=4",
        ],
    )

    assert bundle_path == tmp_path
    assert algo == "ppo"
    assert arch == "tcn"
    assert cfg.strategy.name == "baseline"
    assert cfg.ppo.n_epochs == 7
    assert cfg.ppo.rollout_buffer_on_device is False
    assert cfg.env.vector_backend == "sharded_bundle"
    assert cfg.env.vector_shards == 4
    assert cfg.ppo.total_timesteps > 0


@pytest.mark.parametrize(
    ("config_path", "expected_distribution"),
    [
        ("config/research/thesis_mtf_reasoning_2m.yaml", "thesis_hybrid_v1"),
        (
            "config/research/thesis_mtf_reasoning_conditioned_2m.yaml",
            "thesis_conditioned_v1",
        ),
    ],
)
def test_cd_standalone_configs_resolve_through_production_loader(
    tmp_path: Path,
    config_path: str,
    expected_distribution: str,
) -> None:
    cfg, bundle_path, algo, arch = _prepare_bundle(
        tmp_path,
        config_path=Path(config_path),
    )

    assert bundle_path == tmp_path
    assert algo == "ppo"
    assert arch == "mtf_reasoning"
    assert cfg.ppo.policy_distribution == expected_distribution
    assert cfg.env.n_envs == 8
    assert cfg.ppo.n_steps == 2048


def test_fps_probe_launcher_is_repo_relative_and_architecture_aware() -> None:
    result = subprocess.run(
        ["bash", "-n", str(FPS_PROBE_SCRIPT)],
        check=False,
        capture_output=True,
        text=True,
    )
    source = FPS_PROBE_SCRIPT.read_text(encoding="utf-8")

    assert result.returncode == 0, result.stderr
    assert 'dirname "${BASH_SOURCE[0]}")/../../..' in source
    assert 'export TRITON_REPO="$REPO_ROOT"' in source
    assert 'source "$REPO_ROOT/scripts/compute/slurm/activate_venv.sh"' in source
    assert '"$VIRTUAL_ENV/bin/python"' in source
    assert '--config "$CONFIG_PATH"' in source
    assert 'PROFILE_ARGS+=(--n-envs "$N_ENVS")' in source
    assert "--n-envs 64" not in source
    assert ".venv-x86/bin/python" not in source


def test_pipelined_batch_stages_full_tree_mypy_on_node_local_storage() -> None:
    result = subprocess.run(
        ["bash", "-n", str(BATCH_SCRIPT)],
        check=False,
        capture_output=True,
        text=True,
    )
    source = BATCH_SCRIPT.read_text(encoding="utf-8")

    assert result.returncode == 0, result.stderr
    assert 'mktemp -d "/tmp/triton-mypy-${USER}-wp0-${SLURM_JOB_ID}-XXXXXX"' in source
    assert '"$MYPY_STAGE/pythonbase/bin/python3.12" -m mypy .' in source
    assert '--cache-dir "$MYPY_STAGE/cache" --no-color-output --show-error-codes' in source
    assert '"$VIRTUAL_ENV/bin/mypy" .' not in source
    assert "tests/test_compute_contracts.py" in source
