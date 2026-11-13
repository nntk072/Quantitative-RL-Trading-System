"""Static prospective research contract validation."""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

from omegaconf import OmegaConf

from configuration import load_config
from configuration.paths import repository_root
from decisioning.trade_setup import TRADE_SETUP_TIMEFRAMES
from training.configuration.research_protocol import load_research_protocol

ROOT = repository_root(__file__)
DEFAULT_PROTOCOL = ROOT / "config/research/prospective_research_protocol.yaml"


def _resolved(relative: str) -> dict[str, Any]:
    """Load one fully resolved research configuration.

    Args:
        relative: Value used for relative.

    Returns:
        Result produced by _resolved.
    """
    cfg = load_config(config_path=ROOT / relative)
    value = OmegaConf.to_container(cfg, resolve=True)
    if not isinstance(value, dict):
        raise ValueError(f"resolved config is not a mapping: {relative}")
    return cast(dict[str, Any], value)


def _survival_errors(
    config: dict[str, Any],
    setup_timeframes: tuple[str, ...] = TRADE_SETUP_TIMEFRAMES,
) -> list[str]:
    """Return static survival-contract violations for one configuration.

    Args:
        config: Value used for config.
        setup_timeframes: Value used for setup timeframes.

    Returns:
        Result produced by _survival_errors.
    """
    env = config["env"]
    ftmo = config["ftmo"]
    ppo = config["ppo"]
    features = config["features"]
    training = config["training"]
    evaluation = config["evaluation"]
    checks = {
        "initial balance": config["account"]["initial_balance"] == 100000.0,
        "development-only evaluation": evaluation["development_only"] is True,
        "survival reward": env["reward_mode"] == "survival",
        "account-state-v2": env["observation_schema_version"] == "account-state-v2",
        "validity channels": env["feature_validity_channels"] is True,
        "reachable-r validity": env["reachable_r_validity_mask"] is True,
        "strict research eligibility": env["strict_research_eligibility"] is True,
        "uncapped episode": env["max_episode_steps"] is None,
        "full split": training["episode_mode"] == "full_split" and training["max_days"] is None,
        "static max loss": ftmo["max_drawdown_mode"] == "static",
        "daily loss 5%": ftmo["daily_loss_limit_pct"] == 0.05,
        "max loss 10%": ftmo["max_loss_limit_initial_pct"] == 0.10,
        "$900 sizing ceiling": ftmo["risk_sizing_limit_usd"] == 900.0,
        "undiscounted PPO": ppo["gamma"] == 1.0 and ppo["gae_lambda"] == 1.0,
        "eight env default": env["n_envs"] == 8,
        "setup actions": env["strategy_actions"] is True and env["trade_setup_actions"] is True,
        "setup timeframes": tuple(features["entry_ideas"]["timeframes"]) == setup_timeframes
        and tuple(env["trade_setup_candidate_timeframes"]) == setup_timeframes,
    }
    return [name for name, passed in checks.items() if not passed]


def _without_policy_intervention(config: dict[str, Any]) -> dict[str, Any]:
    """Remove only the declared policy-intervention fields.

    Args:
        config: Value used for config.

    Returns:
        Result produced by _without_policy_intervention.
    """
    result = deepcopy(config)
    result["ppo"].pop("policy_distribution", None)
    result["ppo"].pop("trade_setup_conditioned", None)
    return result


def verify_static_contract(protocol_path: Path = DEFAULT_PROTOCOL) -> dict[str, Any]:
    """Validate the frozen protocol/config relationships without empirical claims.

    Args:
        protocol_path: Value used for protocol path.

    Returns:
        Result produced by verify_static_contract.
    """
    protocol = load_research_protocol(protocol_path)
    policy = protocol["policy"]
    configs = {
        "control": _resolved(str(policy["control_config"])),
        "canonical": _resolved(str(policy["canonical_survival_config"])),
        "candidate_geometry": _resolved(str(policy["price_geometry_config"])),
    }
    failures: list[str] = []
    for role, config in configs.items():
        failures.extend(f"{role}: {error}" for error in _survival_errors(config))

    history_paths = policy["candidate_history_ablation_configs"]
    history = {name: _resolved(str(path)) for name, path in history_paths.items()}
    for name, config in history.items():
        expected = ("M1",) if name == "m1_reference" else TRADE_SETUP_TIMEFRAMES
        failures.extend(
            f"candidate_history/{name}: {error}" for error in _survival_errors(config, expected)
        )

    reference = history["m1_reference"]
    shared = history["shared_opportunities"]
    completed = history["completed_history"]
    if tuple(shared["env"]["trade_setup_candidate_timeframes"]) != tuple(
        completed["env"]["trade_setup_candidate_timeframes"]
    ):
        failures.append("candidate-history opportunity sets differ")
    if shared["env"].get("completed_htf_history_enabled") is not False:
        failures.append("shared-opportunities must disable completed HTF history")
    if completed["env"].get("completed_htf_history_enabled") is not True:
        failures.append("completed-history must enable completed HTF history")
    if shared["agent"]["arch"] != completed["agent"]["arch"]:
        failures.append("candidate-history encoder architectures differ")
    if shared["ppo"]["policy_distribution"] != completed["ppo"]["policy_distribution"]:
        failures.append("candidate-history policy distributions differ")
    left = deepcopy(shared)
    right = deepcopy(completed)
    left["env"].pop("completed_htf_history_enabled", None)
    right["env"].pop("completed_htf_history_enabled", None)
    if left != right:
        failures.append("candidate-history variants differ outside completed HTF history")
    if tuple(reference["env"]["trade_setup_candidate_timeframes"]) != ("M1",):
        failures.append("M1 reference must expose M1-only candidate opportunities")
    if reference["agent"]["arch"] != "tcn":
        failures.append("M1 reference must use the TCN encoder")

    if _without_policy_intervention(configs["control"]) != _without_policy_intervention(
        configs["canonical"]
    ):
        failures.append("control/canonical differ outside the declared policy intervention")
    if configs["control"]["ppo"]["policy_distribution"] != "trade_setup_hybrid_v1":
        failures.append("control distribution must be trade_setup_hybrid_v1")
    if configs["canonical"]["ppo"]["policy_distribution"] != "trade_setup_conditioned_v1":
        failures.append("canonical distribution must be trade_setup_conditioned_v1")

    price = configs["candidate_geometry"]
    if price["ppo"]["policy_distribution"] != "trade_setup_candidate_geometry_v1":
        failures.append("candidate-geometry distribution is invalid")
    if price["env"]["candidate_geometry_actions"] is not True:
        failures.append("candidate-geometry actions must be enabled")
    if price["env"]["agent_entry_execution"] is not True:
        failures.append("candidate-geometry entry execution must be enabled")

    return {
        "schema_version": 1,
        "status": "pass" if not failures else "fail",
        "scope": "static protocol and configuration implementation",
        "failures": failures,
        "protocol": str(protocol_path),
    }


def main(argv: list[str] | None = None) -> int:
    """Validate and optionally write the static research contract.

    Args:
        argv: Command-line arguments for this operation.

    Returns:
        Result produced by main.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    protocol = args.protocol if args.protocol.is_absolute() else ROOT / args.protocol
    report = verify_static_contract(protocol)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        output = args.output if args.output.is_absolute() else ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
