from __future__ import annotations

import subprocess
from pathlib import Path

import gymnasium as gym
import numpy as np
import pytest
from omegaconf import OmegaConf
from scripts.research.benchmarks.measure_ppo_throughput import (
    _apply_profile_overrides,
    _json_default,
    _prepare_bundle,
    _process_tree_cpu_seconds,
    _StepTimingWrapper,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FPS_PROBE_SCRIPT = REPO_ROOT / "scripts" / "research" / "benchmarks" / "run_fps_probe.sh"


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


def test_numpy_scalars_are_json_serializable() -> None:
    assert _json_default(np.int64(7)) == 7
    assert _json_default(np.float32(1.5)) == 1.5


def test_process_tree_cpu_measurement_is_nonnegative() -> None:
    assert _process_tree_cpu_seconds() >= 0.0


def test_environment_step_timer_records_wrapped_steps() -> None:
    env = _StepTimingWrapper(gym.make("CartPole-v1"))
    env.reset(seed=1)

    env.step(0)

    metrics = env.get_step_timing()
    assert metrics["steps"] == 1
    assert metrics["seconds"] >= 0.0
    env.close()


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
