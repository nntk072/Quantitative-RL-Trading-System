"""Tests for training.configuration.variant_resolution and the variant launcher.

Plain Python (PyYAML only). Runs under pytest, or directly: python -m tests.unit.training.test_variant_resolver
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

from training.configuration.variant_resolution import (
    ARCHS,
    PREBUILT_FEATURE_CACHES,
    PROJECT_ROOT,
    VariantError,
    consistency_table,
    load_experiments,
    resolve_variant,
    train_args,
)
from training.configuration.variant_risk_policy import load_variant_ftmo_config


def test_e_f_g_architectures_are_registered_for_variant_resolution() -> None:
    assert {
        "mtf_shared_tcn_reasoning",
        "mtf_m1_tcn_htf_lite_reasoning",
        "mtf_m1_tcn_htf_snapshot_reasoning",
    }.issubset(ARCHS)


def _all_names() -> list[str]:
    return [str(v["name"]) for v in load_experiments()["variants"]]


def _write_experiments(data: dict[str, object]) -> Path:
    tmp = Path(tempfile.mkdtemp()) / "experiments.yaml"
    tmp.write_text(yaml.safe_dump(data), encoding="utf-8")
    return tmp


def _overrides_by_key(resolved: dict[str, list[str]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in resolved["overrides"]:
        key, value = item.split("=", 1)
        assert key not in out, f"duplicate override {key}"
        out[key] = value
    return out


def test_every_variant_resolves_and_declares_reward_mode() -> None:
    names = _all_names()
    assert len(names) == len(set(names))
    for name in names:
        resolved = resolve_variant(
            name, vae_path="placeholder.pth"
        )  # only the VAE variant needs it
        assert resolved["reward_mode"] in (
            "dsr",
            "pnl",
            "rr",
            "equity_delta_r",
            "equity_log_growth",
            "survival",
        )
        assert resolved["steps"] > 0
        assert resolved["seeds"]
        policy_path = PROJECT_ROOT / "config" / "variants" / f"{name}.yaml"
        assert policy_path.is_file(), f"missing per-variant policy YAML: {policy_path}"
        policy = load_variant_ftmo_config(name)
        assert policy["limit_value_mode"] == "percent_equity"
        assert policy["max_drawdown_mode"] == "static"
        assert policy["risk_per_trade_limit_pct"] == pytest.approx(0.01)
        assert policy["daily_loss_limit_pct"] == pytest.approx(0.05)
        assert policy["max_loss_limit_initial_pct"] == pytest.approx(0.10)


def test_variant_row_overrides_registry_defaults() -> None:
    experiments = _write_experiments(
        {
            "defaults": {
                "algo": "ppo",
                "arch": "gru",
                "strategy": "distribution",
                "steps": 2048,
                "seeds": [7, 8],
            },
            "variants": [{"name": "probe", "reward_mode": "dsr", "arch": "tcn", "steps": 4096}],
        }
    )

    resolved = resolve_variant("probe", experiments_path=experiments)

    assert resolved["algo"] == "ppo"
    assert resolved["arch"] == "tcn"
    assert resolved["strategy"] == "distribution"
    assert resolved["steps"] == 4096
    assert resolved["seeds"] == [7, 8]


def test_resolver_exposes_policy_selected_market_or_limit_entry() -> None:
    experiments = _write_experiments(
        {
            "defaults": {
                "algo": "ppo",
                "arch": "tcn",
                "strategy": "baseline",
                "steps": 2048,
                "seeds": [42, 43, 44, 45, 46, 47],
            },
            "variants": [
                {
                    "name": "market_limit_probe",
                    "reward_mode": "dsr",
                    "strategy_actions": True,
                    "trade_setup_actions": True,
                    "agent_entry_execution": True,
                }
            ],
        }
    )

    resolved = resolve_variant("market_limit_probe", experiments_path=experiments)
    overrides = _overrides_by_key(resolved)

    assert resolved["feature_profile"] == "full_po3"
    assert resolved["trade_setup_actions"] is True
    assert resolved["agent_entry_execution"] is True
    assert resolved["policy_distribution"] == "trade_setup_hybrid_v1"
    assert overrides["env.strategy_actions"] == "true"
    assert overrides["env.trade_setup_actions"] == "true"
    assert overrides["env.agent_entry_execution"] == "true"
    assert overrides["ppo.policy_distribution"] == "trade_setup_hybrid_v1"
    assert resolved["seeds"] == [42, 43, 44, 45, 46, 47]


def test_resolver_reports_trade_setup_flags_from_effective_config_overrides() -> None:
    resolved = resolve_variant("rq_mtf_treatment_reasoning")
    overrides = _overrides_by_key(resolved)

    assert resolved["strategy_actions"] is True
    assert resolved["trade_setup_actions"] is True
    assert resolved["agent_entry_execution"] is False
    assert resolved["policy_distribution"] == "trade_setup_hybrid_v1"
    assert overrides["env.trade_setup_actions"] == "true"


def test_resolver_rejects_entry_execution_override_without_trade_setup_schema() -> None:
    experiments = _write_experiments(
        {
            "variants": [
                {
                    "name": "invalid_effective_entry_execution",
                    "reward_mode": "dsr",
                    "strategy_actions": True,
                    "config_overrides": ["env.agent_entry_execution=true"],
                }
            ]
        }
    )

    with pytest.raises(VariantError, match="agent_entry_execution requires trade_setup_actions"):
        resolve_variant("invalid_effective_entry_execution", experiments_path=experiments)


@pytest.mark.parametrize(
    ("strategy_actions", "trade_setup_actions", "agent_entry_execution", "message"),
    [
        (False, True, False, "trade_setup_actions requires strategy_actions=true"),
        (True, False, True, "agent_entry_execution requires trade_setup_actions=true"),
    ],
)
def test_resolver_rejects_invalid_trade_setup_execution_dependencies(
    strategy_actions: bool,
    trade_setup_actions: bool,
    agent_entry_execution: bool,
    message: str,
) -> None:
    variant: dict[str, object] = {
        "name": "invalid_entry_execution",
        "reward_mode": "dsr",
        "strategy_actions": strategy_actions,
        "trade_setup_actions": trade_setup_actions,
        "agent_entry_execution": agent_entry_execution,
    }
    experiments = _write_experiments({"variants": [variant]})

    with pytest.raises(VariantError, match=message):
        resolve_variant("invalid_entry_execution", experiments_path=experiments)


def test_resolver_rejects_gaussian_distribution_for_trade_setup_actions() -> None:
    variant: dict[str, object] = {
        "name": "invalid_setup_distribution",
        "reward_mode": "dsr",
        "strategy_actions": True,
        "trade_setup_actions": True,
        "config_overrides": ["ppo.policy_distribution=clamped_diagonal_gaussian"],
    }
    experiments = _write_experiments({"variants": [variant]})

    with pytest.raises(VariantError, match="trade_setup_actions requires ppo.policy_distribution"):
        resolve_variant("invalid_setup_distribution", experiments_path=experiments)


def test_active_experiment_run_variants_build_features_from_current_split() -> None:
    base_config = yaml.safe_load(
        (PROJECT_ROOT / "config/base/default.yaml").read_text(encoding="utf-8")
    )
    assert base_config["env"]["peak_trailing_dd_limit"] == 0.0
    experiment_run_names = [
        line.strip()
        for line in (PROJECT_ROOT / "config/experiment_runs/variants.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    assert len(experiment_run_names) == len(set(experiment_run_names)) == 2
    assert PREBUILT_FEATURE_CACHES == {}
    for name in experiment_run_names:
        resolved = resolve_variant(name)
        assert not any(
            override.startswith("data.prebuilt_feature_cache=")
            for override in resolved["overrides"]
        )
        assert _overrides_by_key(resolved).get("env.peak_trailing_dd_limit", "0.0") == "0.0"


def test_baseline_ladder_rungs_pin_baseline_strategy_name() -> None:
    # Before the fix these rungs silently ran the default po3_ifvg strategy.
    for name in ("ladder_a0_flat", "ladder_a1_sl", "ladder_a4b_entry_fsm"):
        resolved = resolve_variant(name)
        assert resolved["strategy"] == "baseline"
        assert _overrides_by_key(resolved)["strategy.name"] == "baseline"


def test_strategy_rungs_use_strategy_flag_not_name_override() -> None:
    resolved = resolve_variant("ladder_a0_flat_dist")
    assert resolved["strategy"] == "distribution"
    assert "strategy.name" not in _overrides_by_key(resolved)
    args = train_args(resolved, 42)
    assert args[args.index("--strategy") + 1] == "distribution"


def test_controls_run_declared_algo_and_arch() -> None:
    sac = resolve_variant("ablation_sac_agent")
    assert (sac["algo"], sac["arch"]) == ("sac", "gru")
    transformer = resolve_variant("ablation_transformer_encoder")
    assert transformer["arch"] == "transformer"
    args = train_args(sac, 42)
    assert args[args.index("--algo") + 1] == "sac"
    assert args[args.index("--arch") + 1] == "gru"


def test_mtf_reasoning_arch_resolves_for_a_experiment_run_variant() -> None:
    experiments = _write_experiments(
        {
            "defaults": {"steps": 8, "seeds": [41]},
            "variants": [
                {
                    "name": "mtf_reasoning_probe",
                    "reward_mode": "dsr",
                    "strategy": "baseline",
                    "strategy_actions": True,
                    "arch": "mtf_reasoning",
                }
            ],
        }
    )

    resolved = resolve_variant("mtf_reasoning_probe", experiments_path=experiments)
    args = train_args(resolved, 41)

    assert resolved["arch"] == "mtf_reasoning"
    assert args[args.index("--arch") + 1] == "mtf_reasoning"


def test_vae_variant_requires_vae_path() -> None:
    try:
        resolve_variant("ablation_conditional_narrative")
    except VariantError as exc:
        assert "VAE" in str(exc)
    else:
        raise AssertionError("use_vae=1 without a VAE path must fail")
    resolved = resolve_variant("ablation_conditional_narrative", vae_path="/x/vae.pth")
    args = train_args(resolved, 42)
    assert "--use-vae" in args and args[args.index("--vae-path") + 1] == "/x/vae.pth"


def test_reward_mode_must_be_declared() -> None:
    data = load_experiments()
    data["variants"] = [{"name": "no_reward", "arch": "tcn"}]
    path = _write_experiments(data)
    try:
        resolve_variant("no_reward", experiments_path=path)
    except VariantError as exc:
        assert "reward_mode" in str(exc)
    else:
        raise AssertionError("missing reward_mode must fail")


def test_survival_reward_mode_is_resolvable_for_an_explicit_variant() -> None:
    data = load_experiments()
    data["variants"].append(
        {
            "name": "survival_objective_probe",
            "reward_mode": "survival",
            "arch": "tcn",
            "config_overrides": ["ppo.gamma=1.0", "ppo.gae_lambda=1.0"],
        }
    )
    path = _write_experiments(data)
    resolved = resolve_variant("survival_objective_probe", experiments_path=path)

    assert resolved["reward_mode"] == "survival"
    assert _overrides_by_key(resolved)["ppo.gamma"] == "1.0"
    assert _overrides_by_key(resolved)["ppo.gae_lambda"] == "1.0"


def test_steps_and_seeds_overrides_flow_into_args() -> None:
    resolved = resolve_variant("ladder_a2_tp", steps=8192, seeds=[7])
    assert _overrides_by_key(resolved)["ppo.total_timesteps"] == "8192"
    assert resolved["seeds"] == [7]
    args = train_args(resolved, 7)
    assert args[args.index("--seed") + 1] == "7"
    assert "--seeds" not in args


def test_variant_resolver_leaves_tick_latency_to_yaml_defaults() -> None:
    resolved = resolve_variant("ladder_a0_flat")

    assert not any(
        arg.startswith("execution.randomized_fill_latency_ms=") for arg in train_args(resolved, 42)
    )


def test_overrides_come_after_strategy_and_have_no_duplicates() -> None:
    resolved = resolve_variant("ladder_a4b_po3_ifvg")
    keys = _overrides_by_key(resolved)  # asserts uniqueness
    assert keys["env.reward_mode"] == "pnl"
    assert keys["features.include_pd_context"] == "true"
    assert keys["ftmo.trailing_dd_limit"] == "0.0"


def test_selected_entry_fsm_pair_disables_peak_drawdown_behavior() -> None:
    control = _overrides_by_key(resolve_variant("ladder_a4b_entry_fsm"))
    treatment = _overrides_by_key(resolve_variant("ladder_a4a_entry_fsm_hidden"))

    assert control["env.peak_trailing_dd_limit"] == "0.0"
    assert treatment["env.peak_trailing_dd_limit"] == "0.0"
    assert control["env.risk_floor"] == "0.0005"
    assert treatment["env.risk_floor"] == "0.0005"
    assert control["env.entry_state_observation"] == "true"
    assert treatment["env.entry_state_observation"] == "false"


def test_market_limit_entry_profiles_are_matched_on_all_other_resolved_settings() -> None:
    control = resolve_variant("entry_execution_market_control")
    treatment = resolve_variant("entry_execution_policy_market_limit")
    control_overrides = _overrides_by_key(control)
    treatment_overrides = _overrides_by_key(treatment)

    assert control["seeds"] == treatment["seeds"]
    assert (
        control["policy_distribution"]
        == treatment["policy_distribution"]
        == ("trade_setup_hybrid_v1")
    )
    assert len(control["seeds"]) >= 6
    assert {
        key: value for key, value in control_overrides.items() if key != "env.agent_entry_execution"
    } == {
        key: value
        for key, value in treatment_overrides.items()
        if key != "env.agent_entry_execution"
    }
    assert control_overrides["env.strategy_actions"] == "true"
    assert control_overrides["env.trade_setup_actions"] == "true"
    assert control_overrides["env.agent_entry_execution"] == "false"
    assert control_overrides["ppo.policy_distribution"] == "trade_setup_hybrid_v1"
    assert treatment_overrides["env.agent_entry_execution"] == "true"
    assert treatment_overrides["execution.limit_order_max_offset_atr"] == "1.0"
    assert treatment_overrides["execution.limit_order_max_ttl_bars"] == "60"
    assert treatment_overrides["execution.limit_order_require_trade_through"] == "false"


def test_quarter_grid_pair_preserves_policy_and_shares_data_transform() -> None:
    continuous = {
        name: value
        for name, value in _overrides_by_key(resolve_variant("ladder_a4b_entry_fsm")).items()
        if not name.startswith("data.")
    }
    quantized_control = _overrides_by_key(resolve_variant("ladder_a4b_entry_fsm_qgrid025"))
    quantized_treatment = _overrides_by_key(resolve_variant("ladder_a4a_entry_fsm_hidden_qgrid025"))

    control_policy = {
        key: value for key, value in quantized_control.items() if not key.startswith("data.")
    }
    treatment_policy = {
        key: value for key, value in quantized_treatment.items() if not key.startswith("data.")
    }
    assert control_policy == continuous
    assert treatment_policy == {
        **continuous,
        "env.entry_state_observation": "false",
    }
    assert quantized_control["data.price_discretization.enabled"] == "true"
    assert quantized_treatment["data.price_discretization.increment"] == "0.25"
    assert quantized_control["data.cache_dir"] == quantized_treatment["data.cache_dir"]
    assert quantized_control["data.cache_dir"].endswith("qgrid025_v1")


def test_quarter_grid_comparison_variants_share_the_active_registry() -> None:
    names = {item["name"] for item in load_experiments()["variants"]}
    pair = {"ladder_a4b_entry_fsm_qgrid025", "ladder_a4a_entry_fsm_hidden_qgrid025"}
    assert pair <= names
    for name in pair:
        assert resolve_variant(name)["arch"] == "tcn"


def test_consistency_table_covers_all_variants() -> None:
    names = _all_names()
    rows = consistency_table(names)
    assert len(rows) == len(names)
    by_name = {r["variant"]: r for r in rows}
    # The confound this module makes visible: baseline-named rungs and PO3 rungs
    # differ in reward mode and PD context.
    assert by_name["ladder_a0_flat"]["reward_mode"] == "dsr"
    assert by_name["ladder_a0_flat_po3"]["reward_mode"] == "pnl"
    assert by_name["ladder_a0_flat"]["include_pd_context"] is False
    assert by_name["ladder_a0_flat_po3"]["include_pd_context"] is True
    assert by_name["entry_execution_market_control"]["trade_setup_actions"] is True
    assert by_name["entry_execution_market_control"]["agent_entry_execution"] is False
    assert by_name["entry_execution_policy_market_limit"]["agent_entry_execution"] is True
    assert by_name["entry_execution_policy_market_limit"]["policy_distribution"] == (
        "trade_setup_hybrid_v1"
    )


def test_dollar_band_q5_pair_differs_only_by_q5_objective() -> None:
    q5_off = _overrides_by_key(resolve_variant("ladder_a4a_dollar_band_q5_off"))
    q5_on = _overrides_by_key(resolve_variant("ladder_a4a_dollar_band_q5_on"))
    shared = {
        "env.risk_mode": "dollar_band",
        "env.risk_band_max_usd": "900",
        "env.risk_band_hold_below_usd": "100",
        "env.risk_floor": "0",
    }
    assert {key: q5_off[key] for key in shared} == shared
    assert {key: q5_on[key] for key in shared} == shared
    assert q5_off["env.risk_floor"] == "0"
    assert q5_off["constrained_rl.enabled"] == "false"
    assert q5_on["constrained_rl.enabled"] == "true"
    assert q5_on["constrained_rl.episode_cost_budget"] == "0.1"
    assert q5_on["constrained_rl.cost_discount_gamma"] == "1.0"


def test_training_arguments_cover_every_registered_seed() -> None:
    resolved = resolve_variant("ablation_sac_agent")
    for seed in (42, 43, 44, 45, 46):
        args = train_args(resolved, seed)
        assert args[args.index("--seed") + 1] == str(seed)
        assert args[args.index("--algo") + 1] == "sac"
        assert args[args.index("--arch") + 1] == "gru"


def test_variant_resolution_rejects_missing_vae_checkpoint() -> None:
    with pytest.raises(VariantError, match="VAE"):
        resolve_variant("ablation_conditional_narrative")


def test_manifest_cli_writes_resolved_config() -> None:
    import json
    import os

    out = Path(tempfile.mkdtemp()) / "resolved_config.json"
    env = dict(os.environ, PYTHONPATH=str(PROJECT_ROOT))
    subprocess.run(
        [
            sys.executable,
            "-m",
            "training.configuration.variant_resolution",
            "manifest",
            "ladder_a1_sl_dist",
            "--seed",
            "43",
            "--out",
            str(out),
        ],
        cwd=PROJECT_ROOT,
        env=env,
        check=True,
        capture_output=True,
        timeout=120,
    )
    manifest = json.loads(out.read_text())
    assert manifest["variant"] == "ladder_a1_sl_dist"
    assert manifest["seed"] == 43
    assert manifest["strategy"] == "distribution"
    assert "--seed" in manifest["train_args"] and "43" in manifest["train_args"]


def test_experiment_run_config_overrides_are_last_in_resolved_training_args() -> None:
    resolved = resolve_variant(
        "ladder_a4b_entry_fsm_qgrid025",
        steps=2_000_000,
        seeds=[50],
        config_overrides=[
            "ftmo.risk_sizing_limit_usd=900.0",
            "ftmo.trailing_dd_limit=0.0",
        ],
    )

    assert resolved["overrides"][-2:] == [
        "ftmo.risk_sizing_limit_usd=900.0",
        "ftmo.trailing_dd_limit=0.0",
    ]
    args = train_args(resolved, 50)
    assert args[-2:] == [
        "ftmo.risk_sizing_limit_usd=900.0",
        "ftmo.trailing_dd_limit=0.0",
    ]


if __name__ == "__main__":
    import sys

    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except Exception as exc:  # noqa: BLE001
                failures += 1
                print(f"FAIL {name}: {exc}")
    sys.exit(1 if failures else 0)
