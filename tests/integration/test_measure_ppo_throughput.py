from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import Mock

import gymnasium as gym
import numpy as np
import pytest
import torch
from omegaconf import OmegaConf
from research_tools.learning.benchmarks import measure_ppo_throughput as probe
from research_tools.learning.benchmarks.measure_ppo_throughput import (
    _apply_profile_overrides,
    _json_default,
    _prepare_bundle,
    _process_tree_cpu_seconds,
    _scale_profile_config,
    _StepTimingWrapper,
    _time_method_calls,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FPS_PROBE_SCRIPT = REPO_ROOT / "scripts" / "research" / "benchmarks" / "run_fps_probe.sh"
FPS_PROBE_IMPLEMENTATION = (
    REPO_ROOT / "research_tools" / "compute" / "benchmarks" / "run_fps_probe.sh"
)


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
        "research_tools.learning.benchmarks.measure_ppo_throughput.scale_training_cfg",
        fake_scale,
    )
    _scale_profile_config(cfg, "cuda", "mtf_reasoning")

    assert observed["preserve_ppo_geometry"] is True
    assert cfg.env.n_envs == 8
    assert cfg.ppo.n_steps == 2048


def test_numpy_scalars_are_json_serializable() -> None:
    assert _json_default(np.int64(7)) == 7
    assert _json_default(np.float32(1.5)) == 1.5


@pytest.mark.parametrize(
    ("overrides", "expected_episodic"),
    [([], False), (["env.reward_mode=dsr", "training.episode_mode=risk_terminated"], True)],
)
def test_probe_constructs_workers_with_configured_episodes_and_seeds_agent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    overrides: list[str],
    expected_episodic: bool,
) -> None:
    class AgentConstructionReached(Exception):
        pass

    make_env = Mock(return_value=Mock(observation_space=gym.spaces.Dict({})))
    build_agent = Mock(side_effect=AgentConstructionReached)
    monkeypatch.setattr(probe, "make_bundle_env", make_env)
    monkeypatch.setattr(probe, "build_agent", build_agent)
    monkeypatch.setattr(probe, "_scale_profile_config", Mock())
    monkeypatch.setattr(probe, "configure_cuda_for_training", Mock())
    monkeypatch.setattr(probe, "_setup_rngs", Mock())
    monkeypatch.setattr(torch, "set_num_threads", Mock())
    for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        monkeypatch.setenv(name, "1")

    with pytest.raises(AgentConstructionReached):
        probe._train_probe(
            None,
            None,
            None,
            "cpu",
            tmp_path / "report.json",
            bundle_dir=tmp_path,
            config_path=Path("config/research/survival_trade_setup_mtf_conditioned.yaml"),
            overrides=overrides,
            seed=47,
        )

    parent_spec = make_env.call_args.args[0]
    build_agent.call_args.kwargs["env_fn"]()
    assert make_env.call_args.args[0] == parent_spec
    assert (parent_spec.episodic, build_agent.call_args.kwargs.get("seed")) == (
        expected_episodic,
        47,
    )


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


def test_environment_step_profiler_profiles_only_requested_policy_steps() -> None:
    env = _StepTimingWrapper(gym.make("CartPole-v1"), profile_steps=2)
    env.reset(seed=1)

    env.step(0)
    env.step(1)
    env.step(0)

    profile = env.get_step_profile()
    assert profile["profiled_steps"] == 2
    assert isinstance(profile["top_cumulative"], str)
    assert "CartPole" in profile["top_cumulative"] or "step" in profile["top_cumulative"]
    env.close()


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
        ("config/research/trade_setup_mtf_reasoning_2m.yaml", "trade_setup_hybrid_v1"),
        (
            "config/research/trade_setup_mtf_reasoning_conditioned_2m.yaml",
            "trade_setup_conditioned_v1",
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
    wrapper_result = subprocess.run(
        ["bash", "-n", str(FPS_PROBE_SCRIPT)],
        check=False,
        capture_output=True,
        text=True,
    )
    implementation_result = subprocess.run(
        ["bash", "-n", str(FPS_PROBE_IMPLEMENTATION)],
        check=False,
        capture_output=True,
        text=True,
    )
    wrapper = FPS_PROBE_SCRIPT.read_text(encoding="utf-8")
    source = FPS_PROBE_IMPLEMENTATION.read_text(encoding="utf-8")

    assert wrapper_result.returncode == 0, wrapper_result.stderr
    assert implementation_result.returncode == 0, implementation_result.stderr
    assert "../../../research_tools/compute/benchmarks/run_fps_probe.sh" in wrapper
    assert 'dirname "${BASH_SOURCE[0]}")/../../..' in source
    assert 'export TRITON_REPO="$REPO_ROOT"' in source
    assert 'source "$REPO_ROOT/scripts/compute/slurm/activate_venv.sh"' in source
    assert '"$VIRTUAL_ENV/bin/python"' in source
    assert '"$REPO_ROOT/research_tools/learning/benchmarks/measure_ppo_throughput.py"' in source
    assert '--config "$CONFIG_PATH"' in source
    assert 'PROFILE_ARGS+=(--n-envs "$N_ENVS")' in source
    assert "--n-envs 64" not in source
    assert ".venv-x86/bin/python" not in source
