from __future__ import annotations

from argparse import Namespace

import torch

from configuration.loader import load_config
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
