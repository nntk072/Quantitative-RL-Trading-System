from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import yaml
from omegaconf import OmegaConf

from training.artifacts.manifests import _training_protocol_manifest
from training.configuration.variant_resolution import resolve_variant


def test_equity_log_growth_is_a_resolvable_variant_reward(tmp_path: Path) -> None:
    path = tmp_path / "experiments.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "defaults": {"steps": 32, "seeds": [50]},
                "variants": [
                    {
                        "name": "growth_probe",
                        "reward_mode": "equity_log_growth",
                        "algo": "ppo",
                        "arch": "tcn",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    resolved = resolve_variant("growth_probe", experiments_path=path)
    assert resolved["reward_mode"] == "equity_log_growth"
    assert "env.reward_mode=equity_log_growth" in resolved["overrides"]


def test_registered_growth_screen_has_matched_reward_and_q5_arms() -> None:
    control = resolve_variant("sustainable_growth_ppo_dsr")
    growth = resolve_variant("sustainable_growth_ppo_log")
    constrained = resolve_variant("sustainable_growth_ppo_log_q5")
    eod_dd = resolve_variant("sustainable_growth_ppo_log_eod_dd10k")
    sac = resolve_variant("sustainable_growth_sac_log")

    assert (control["algo"], control["arch"], control["steps"], control["seeds"]) == (
        "ppo",
        "tcn",
        2_000_000,
        [50],
    )
    assert growth["algo"] == constrained["algo"] == "ppo"
    assert growth["arch"] == constrained["arch"] == "tcn"
    assert growth["reward_mode"] == constrained["reward_mode"] == "equity_log_growth"
    assert sac["algo"] == "sac" and sac["reward_mode"] == "equity_log_growth"
    control_overrides = {
        item.split("=", 1)[0]: item.split("=", 1)[1] for item in control["overrides"]
    }
    growth_overrides = {
        item.split("=", 1)[0]: item.split("=", 1)[1] for item in growth["overrides"]
    }
    constrained_overrides = {
        item.split("=", 1)[0]: item.split("=", 1)[1] for item in constrained["overrides"]
    }
    assert control_overrides["env.risk_mode"] == "dollar_band"
    assert control_overrides["env.risk_band_max_usd"] == "900.0"
    assert growth_overrides["env.equity_log_growth_scale"] == "100.0"
    for key in (
        "env.strategy_actions",
        "env.agent_direction_control",
        "env.allow_agent_sl_mode",
        "env.allow_agent_tp_mode",
        "env.allow_multi_tp",
        "env.entry_state_machine",
        "env.entry_state_observation",
        "env.peak_trailing_dd_limit",
        "env.risk_mode",
        "env.risk_band_max_usd",
        "env.risk_band_hold_below_usd",
    ):
        assert control_overrides[key] == growth_overrides[key], f"RQ1 reward arms differ at {key}"
    assert constrained_overrides["constrained_rl.enabled"] == "true"
    assert constrained_overrides["constrained_rl.episode_cost_budget"] == "0.1"
    assert constrained_overrides["constrained_rl.cost_discount_gamma"] == "0.99"
    eod_dd_overrides = {
        item.split("=", 1)[0]: item.split("=", 1)[1] for item in eod_dd["overrides"]
    }
    assert eod_dd["reward_mode"] == growth["reward_mode"]
    assert eod_dd["algo"] == growth["algo"]
    assert eod_dd["arch"] == growth["arch"]
    assert eod_dd_overrides["env.eod_risk.peak_trailing_dd_limit_usd"] == "10000.0"


def test_legacy_equity_delta_reward_is_resolvable(tmp_path: Path) -> None:
    path = Path(__file__).resolve().parents[2] / "config" / "experiments.yaml"
    contents = yaml.safe_load(path.read_text(encoding="utf-8"))
    contents["variants"].append(
        {
            "name": "equity_delta_resolver_probe",
            "reward_mode": "equity_delta_r",
            "arch": "tcn",
            "config_overrides": ["env.risk_mode=fixed", "env.fixed_risk_usd=500"],
        }
    )
    temporary = tmp_path / "experiments.yaml"
    temporary.write_text(yaml.safe_dump(contents), encoding="utf-8")
    resolved = resolve_variant("equity_delta_resolver_probe", experiments_path=temporary)
    assert resolved["reward_mode"] == "equity_delta_r"


def test_training_protocol_records_growth_scale() -> None:
    cfg = OmegaConf.create(
        {
            "env": {
                "reward_mode": "equity_log_growth",
                "equity_log_growth_scale": 25.0,
                "data_source": "bundle",
                "eod_risk": {"peak_trailing_dd_limit_usd": 10_000.0},
            },
            "ppo": {
                "batch_size": 4,
                "n_epochs": 2,
                "learning_rate": 3e-4,
                "gamma": 0.99,
                "gae_lambda": 0.95,
                "clip_range": 0.2,
            },
            "ftmo": {},
            "constrained_rl": {"enabled": False},
        }
    )
    model = SimpleNamespace(n_envs=2, n_steps=4, num_timesteps=8, ent_coef=0.001)
    manifest = _training_protocol_manifest(
        model=model,
        cfg=cfg,
        args=SimpleNamespace(),
        seed=50,
        requested_steps=8,
    )
    assert manifest["reward"]["mode"] == "equity_log_growth"
    assert manifest["reward"]["equity_log_growth_scale"] == 25.0
    assert manifest["risk"]["eod_peak_trailing_dd_limit_usd"] == 10_000.0
