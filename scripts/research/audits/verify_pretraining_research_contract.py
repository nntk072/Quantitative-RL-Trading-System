#!/usr/bin/env python3
"""Fail-closed static gate before expensive survival qualification runs.

This gate validates only code/config/protocol contracts. It does not claim that
feature causality, market-data quality, candidate acceptance, CI, or execution
parity evidence has passed; those result-producing gates remain separate and
must be supplied by the terminal execution report.
"""

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
    cfg = load_config(config_path=ROOT / relative)
    value = OmegaConf.to_container(cfg, resolve=True)
    if not isinstance(value, dict):
        raise ValueError(f"resolved config is not a mapping: {relative}")
    return cast(dict[str, Any], value)


def _survival_errors(config: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    env = config["env"]
    ftmo = config["ftmo"]
    ppo = config["ppo"]
    features = config["features"]
    training = config["training"]
    checks = {
        "initial balance": config["account"]["initial_balance"] == 100000.0,
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
        "all setup timeframes": tuple(features["entry_ideas"]["timeframes"])
        == TRADE_SETUP_TIMEFRAMES,
    }
    errors.extend(name for name, passed in checks.items() if not passed)
    return errors


def _without_policy_intervention(config: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(config)
    result["ppo"].pop("policy_distribution", None)
    result["ppo"].pop("trade_setup_conditioned", None)
    return result


def verify(protocol_path: Path) -> dict[str, Any]:
    protocol = load_research_protocol(protocol_path)
    policy = protocol["policy"]
    configs = {
        "control": _resolved(str(policy["control_config"])),
        "canonical": _resolved(str(policy["canonical_survival_config"])),
        "price_geometry": _resolved(str(policy["price_geometry_config"])),
    }
    failures: list[str] = []
    for role, config in configs.items():
        for error in _survival_errors(config):
            failures.append(f"{role}: {error}")

    if _without_policy_intervention(configs["control"]) != _without_policy_intervention(
        configs["canonical"]
    ):
        failures.append("control/canonical configs differ outside the declared policy intervention")
    if configs["control"]["ppo"]["policy_distribution"] != "trade_setup_hybrid_v1":
        failures.append("control distribution is not trade_setup_hybrid_v1")
    if configs["canonical"]["ppo"]["policy_distribution"] != "trade_setup_conditioned_v1":
        failures.append("canonical distribution is not trade_setup_conditioned_v1")

    price = configs["price_geometry"]
    if price["ppo"]["policy_distribution"] != "trade_setup_candidate_geometry_v1":
        failures.append("PRICE distribution is not trade_setup_candidate_geometry_v1")
    if price["env"]["candidate_geometry_actions"] is not True:
        failures.append("PRICE candidate_geometry_actions is not enabled")
    if price["env"]["agent_entry_execution"] is not True:
        failures.append("PRICE agent_entry_execution is not enabled")

    return {
        "schema_version": "pretraining-static-contract-gate-v1",
        "status": "pass" if not failures else "fail",
        "scope": "static protocol/config implementation only",
        "does_not_establish": [
            "feature_causality_pass",
            "data_quality_pass",
            "candidate_geometry_empirical_acceptance",
            "simulator_execution_parity",
            "full_tree_ci",
            "survival_qualification",
            "economic_superiority",
        ],
        "failures": failures,
        "protocol": str(protocol_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    protocol = args.protocol if args.protocol.is_absolute() else ROOT / args.protocol
    report = verify(protocol)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        output = args.output if args.output.is_absolute() else ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    print(text, end="")
    if report["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
