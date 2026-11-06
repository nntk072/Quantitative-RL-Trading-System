#!/usr/bin/env python3
"""Inventory archived config snapshots without treating replay configs as training runs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

_FIELDS = (
    "config_role",
    "campaign",
    "variant",
    "seed",
    "algorithm",
    "architecture",
    "timesteps",
    "n_envs",
    "policy_distribution",
    "risk_target_timeframes",
    "env_target_timeframes",
    "max_drawdown_mode",
    "limit_value_mode",
    "daily_loss_limit_pct",
    "max_loss_limit_initial_pct",
    "daily_loss_limit_usd_saved",
    "max_loss_limit_usd_saved",
    "risk_sizing_limit_usd",
    "trading_policy_mode",
    "payout_active",
    "reward_mode",
    "breach_penalty",
    "eval_breach_penalty",
    "entry_state_machine",
    "entry_state_observation",
    "trade_setup_actions",
    "agent_entry_execution",
    "config_sha256",
    "config_path",
    "run_path",
)


def _get(mapping: Any, *path: str) -> Any:
    """Read a nested config value, preserving false and zero values."""
    value = mapping
    for key in path:
        if not isinstance(value, dict) or key not in value:
            return "not_saved"
        value = value[key]
    if value is None:
        return "not_saved"
    if isinstance(value, (list, tuple)):
        return ",".join(str(item) for item in value)
    return value


def _role(relative: Path) -> str:
    parts = relative.parts
    if "runs" in parts and "attempts" in parts:
        return "training_attempt"
    if any(part.startswith("reanalysis_") for part in parts):
        return "reanalysis_snapshot"
    if "reports" in parts:
        return "report_or_replay_snapshot"
    return "other_snapshot"


def _variant_seed(relative: Path, role: str) -> tuple[str, str]:
    parts = relative.parts
    if role != "training_attempt" or "attempts" not in parts:
        return "not_applicable", "not_saved"
    name = parts[parts.index("attempts") + 1]
    match = re.search(r"__seed(\d+)$", name)
    variant = name[: match.start()] if match else name
    return variant, match.group(1) if match else "not_saved"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _debug_value(run_path: Path, key: str) -> Any:
    debug_path = run_path / "debug_wiring.json"
    if not debug_path.is_file():
        return "not_saved"
    import json

    with debug_path.open(encoding="utf-8") as stream:
        payload = json.load(stream)
    value = payload.get(key)
    return "not_saved" if value is None else value


def _record(path: Path, root: Path) -> dict[str, Any]:
    resolved = path.resolve()
    relative = path.relative_to(root)
    role = _role(relative)
    variant, seed = _variant_seed(relative, role)
    with resolved.open(encoding="utf-8") as stream:
        config = yaml.safe_load(stream) or {}
    policy_mode = _get(config, "trading_policy", "mode")
    payout_active: bool | str = (
        policy_mode == "repeated_payout" if policy_mode != "not_saved" else "not_saved"
    )
    timesteps = _get(config, "ppo", "total_timesteps")
    if timesteps == "not_saved":
        timesteps = _get(config, "sac", "total_timesteps")
    return {
        "config_role": role,
        "campaign": relative.parts[0] if relative.parts else "not_saved",
        "variant": variant,
        "seed": seed,
        "algorithm": _get(config, "agent", "type"),
        "architecture": _get(config, "agent", "arch"),
        "timesteps": timesteps,
        "n_envs": _get(config, "env", "n_envs"),
        "policy_distribution": _get(config, "ppo", "policy_distribution"),
        "risk_target_timeframes": _get(config, "risk", "target_timeframes"),
        "env_target_timeframes": _get(config, "env", "target_timeframes"),
        "max_drawdown_mode": _get(config, "ftmo", "max_drawdown_mode"),
        "limit_value_mode": _get(config, "ftmo", "limit_value_mode"),
        "daily_loss_limit_pct": _get(config, "ftmo", "daily_loss_limit_pct"),
        "max_loss_limit_initial_pct": _get(config, "ftmo", "max_loss_limit_initial_pct"),
        "daily_loss_limit_usd_saved": _get(config, "ftmo", "daily_loss_limit"),
        "max_loss_limit_usd_saved": _get(config, "ftmo", "max_loss_limit"),
        "risk_sizing_limit_usd": _get(config, "ftmo", "risk_sizing_limit_usd"),
        "trading_policy_mode": policy_mode,
        "payout_active": payout_active,
        "reward_mode": _get(config, "env", "reward_mode"),
        "breach_penalty": _debug_value(path.parent, "breach_penalty"),
        "eval_breach_penalty": _debug_value(path.parent, "eval_breach_penalty"),
        "entry_state_machine": _get(config, "env", "entry_state_machine"),
        "entry_state_observation": _get(config, "env", "entry_state_observation"),
        "trade_setup_actions": _get(config, "env", "trade_setup_actions"),
        "agent_entry_execution": _get(config, "env", "agent_entry_execution"),
        "config_sha256": _sha256(resolved),
        "config_path": str(path),
        "run_path": str(path.parent),
    }


def build_inventory(root: Path) -> tuple[list[dict[str, Any]], int]:
    """Return one row per unique config file and count redundant symlink aliases."""
    paths = sorted(root.rglob("config.yaml"))
    by_target: dict[Path, Path] = {}
    aliases = 0
    for path in paths:
        target = path.resolve()
        if target in by_target:
            aliases += 1
            continue
        by_target[target] = path
    rows = [_record(path, root) for path in by_target.values()]
    return rows, aliases


def write_inventory(root: Path, output_dir: Path) -> None:
    """Write a categorized CSV and a scope summary for an archive root."""
    rows, aliases = build_inventory(root)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "config_snapshots.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    counts = Counter(row["config_role"] for row in rows)
    lines = [
        "# Archived configuration snapshot inventory",
        "",
        f"Scanned `{root}`. The inventory contains {len(rows)} unique config files and excludes {aliases} redundant symlink aliases.",
        "",
        "| Snapshot role | Files |",
        "|---|---:|",
    ]
    for role in (
        "training_attempt",
        "report_or_replay_snapshot",
        "reanalysis_snapshot",
        "other_snapshot",
    ):
        lines.append(f"| `{role}` | {counts[role]} |")
    lines.extend(
        [
            "",
            "Only `training_attempt` rows describe configs saved with training attempts. Report, replay, and reanalysis configs are context snapshots and must not be counted as additional training runs.",
            "",
            "`not_saved` means the value is absent from that saved config or its run-local `debug_wiring.json`; current defaults are not substituted. `payout_active` is derived only from the saved `trading_policy.mode`. The inventory contains configuration fields, not performance results or model-selection claims.",
            "",
            "The user's requested future risk overlay is a separate target: static maximum-loss drawdown, 5% daily loss, 10% maximum loss from initial equity, $900 per-trade sizing cap, no payout mode, M1 decision stream plus M3/M5/M10/M15/M30/H1/H4/D1 context. It is not applied retroactively to archived runs.",
            "",
            f"CSV: [`{csv_path.name}`]({csv_path.name})",
            "",
        ]
    )
    (output_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if not args.campaign_root.is_dir():
        parser.error(f"campaign root is not a directory: {args.campaign_root}")
    write_inventory(args.campaign_root.resolve(), args.output_dir)


if __name__ == "__main__":
    main()
