from __future__ import annotations

from argparse import Namespace
from typing import Any, cast
from unittest.mock import patch

import torch
from omegaconf import OmegaConf

from configuration.loader import load_config
from training.configuration.cli import parse_train_args
from training.runner import configuration_stage


def test_exact_environment_config_preserves_resolved_ppo_geometry(monkeypatch) -> None:
    args = Namespace(
        use_vae=False,
        vae_path=None,
        walk_forward=False,
        arch=None,
        quality_variant=None,
        seed=42,
        resume_checkpoint=None,
        mvp=False,
        algo="ppo",
    )
    scale_call: dict[str, object] = {}
    configure_call: dict[str, object] = {}
    monkeypatch.setattr(configuration_stage, "parse_train_args", lambda: args)
    monkeypatch.setattr(
        configuration_stage,
        "configure_accelerator_for_training",
        lambda device, **kwargs: configure_call.update(device=device, **kwargs),
    )
    monkeypatch.setattr(configuration_stage, "_setup_rngs", lambda _: None)
    monkeypatch.setattr(configuration_stage, "_validate_q5_resume_state", lambda *_, **__: None)
    monkeypatch.setattr(configuration_stage, "get_device", lambda _: torch.device("cpu"))

    def record_scale(_cfg, _device, _arch, *, preserve_ppo_geometry=False):
        scale_call["preserve_ppo_geometry"] = preserve_ppo_geometry

    monkeypatch.setattr(
        configuration_stage,
        "_build_lagrangian_callback",
        lambda *_args, **_kwargs: None,
    )

    for config_path in (
        "config/research/thesis_mtf_reasoning_2m.yaml",
        "config/research/thesis_mtf_reasoning_conditioned_2m.yaml",
        "config/research/thesis_mtf_shared_tcn_2m.yaml",
        "config/research/thesis_mtf_m1_htf_lite_2m.yaml",
        "config/research/thesis_mtf_m1_htf_snapshot_2m.yaml",
    ):
        config = load_config(config_path=config_path)
        monkeypatch.setattr(configuration_stage, "load_merged_config", lambda _: config)
        monkeypatch.setattr(configuration_stage, "scale_training_cfg", record_scale)
        resolved = configuration_stage._prepare_training_configuration().cfg

        assert configure_call["cudnn_benchmark"] is False
        assert scale_call["preserve_ppo_geometry"] is True
        assert resolved.quality_execution.requested_n_envs == 8
        assert resolved.quality_execution.effective_n_envs == 8
        assert resolved.env.n_envs == 8
        assert resolved.ppo.n_steps == 2048
        assert resolved.ppo.batch_size == 512
        assert resolved.ppo.n_epochs == 15


def test_efg_resolved_configs_match_variant_d_outside_encoder_identity() -> None:
    baseline = load_config(config_path="config/research/thesis_mtf_reasoning_conditioned_2m.yaml")
    baseline_fields = OmegaConf.to_container(baseline, resolve=True)
    assert isinstance(baseline_fields, dict)
    baseline_fields["agent"].pop("arch")

    configs = {
        "mtf_shared_tcn_reasoning": "config/research/thesis_mtf_shared_tcn_2m.yaml",
        "mtf_m1_tcn_htf_lite_reasoning": "config/research/thesis_mtf_m1_htf_lite_2m.yaml",
        "mtf_m1_tcn_htf_snapshot_reasoning": ("config/research/thesis_mtf_m1_htf_snapshot_2m.yaml"),
    }
    for expected_arch, config_path in configs.items():
        resolved = load_config(config_path=config_path)
        fields = OmegaConf.to_container(resolved, resolve=True)
        assert isinstance(fields, dict)
        assert fields["agent"]["arch"] == expected_arch
        fields["agent"].pop("arch")
        assert fields == baseline_fields


def test_efg_encoder_ids_are_available_from_training_cli() -> None:
    for arch in (
        "mtf_shared_tcn_reasoning",
        "mtf_m1_tcn_htf_lite_reasoning",
        "mtf_m1_tcn_htf_snapshot_reasoning",
    ):
        with patch("sys.argv", ["train", "--arch", arch]):
            assert parse_train_args().arch == arch


def test_high_throughput_config_is_separate_and_has_measured_geometry() -> None:
    from training.configuration.cli import load_merged_config

    def production_resolve(config_path: str):
        return load_merged_config(
            Namespace(
                config=config_path,
                strategy="baseline",
                variant=None,
                quality_variant=None,
                overrides=[],
            )
        )

    baseline = production_resolve("config/research/thesis_mtf_shared_tcn_2m.yaml")
    high = production_resolve("config/research/thesis_mtf_shared_tcn_2m_high_throughput.yaml")

    baseline_tree = cast(dict[str, Any], OmegaConf.to_container(baseline, resolve=True))
    high_tree = cast(dict[str, Any], OmegaConf.to_container(high, resolve=True))
    assert isinstance(baseline_tree, dict)
    assert isinstance(high_tree, dict)

    def changed_paths(left: dict[str, Any], right: dict[str, Any], prefix: str = "") -> set[str]:
        paths: set[str] = set()
        for key in left.keys() | right.keys():
            path = f"{prefix}.{key}" if prefix else str(key)
            left_value = left.get(key)
            right_value = right.get(key)
            if isinstance(left_value, dict) and isinstance(right_value, dict):
                paths.update(changed_paths(left_value, right_value, path))
            elif left_value != right_value:
                paths.add(path)
        return paths

    assert changed_paths(baseline_tree, high_tree) == {
        "env.data_source",
        "env.n_envs",
        "env.vector_shards",
        "ppo.n_steps",
        "ppo.batch_size",
        "quality_execution.requested_n_envs",
    }

    assert baseline.env.n_envs == 8
    assert baseline.ppo.n_steps == 2048
    assert baseline.ppo.batch_size == 512
    assert high.agent.arch == "mtf_shared_tcn_reasoning"
    assert high.ppo.policy_distribution == "thesis_conditioned_v1"
    assert high.env.thesis_actions is True
    assert high.env.data_source == "bundle"
    assert high.env.n_envs == 64
    assert high.env.vector_backend == "subproc"
    assert high.env.vector_shards == 64
    assert high.ppo.n_steps == 16384
    assert high.ppo.n_steps // high.env.n_envs == 256
    assert high.ppo.batch_size == 4096
    assert high.ppo.n_epochs == 15
    assert high.quality_execution.exact_n_envs is True
