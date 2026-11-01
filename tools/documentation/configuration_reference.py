#!/usr/bin/env python3
"""Generate the exact default-key inventory from the canonical YAML file."""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFAULTS = ROOT / "config/base/default.yaml"
OUTPUT = ROOT / "docs/reference/configuration.md"

SECTION_OWNERS = {
    "account": "trading/account",
    "agent": "learning/rl",
    "auxiliary": "learning/supervised",
    "backtest": "simulation/backtest",
    "compute": "compute",
    "constrained_rl": "learning/rl",
    "costs": "trading/execution",
    "data": "market_data/configuration",
    "device": "compute/environment",
    "encoder": "models/encoders",
    "env": "simulation/environment and decisioning",
    "evaluation": "evaluation",
    "execution": "trading/execution and simulation",
    "features": "features",
    "ftmo": "trading/risk",
    "live_risk_overrides": "live and integrations/mt5",
    "output": "artifacts and evaluation/reporting",
    "ppo": "learning/rl",
    "quality_diagnostics": "training and evaluation",
    "quality_execution": "trading/risk and simulation",
    "risk": "trading/risk",
    "sac": "learning/rl",
    "session": "market_data and features",
    "strategy": "trading/strategies",
    "training": "training",
    "trading_policy": "trading/policy",
}


def _leaves(value: Mapping[str, Any], prefix: str = "") -> Iterator[tuple[str, Any]]:
    """Yield dotted keys for YAML leaves, keeping lists as one configured value."""
    for key, child in value.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(child, Mapping) and child:
            yield from _leaves(child, path)
        else:
            yield path, child


def _inferred_type(value: Any) -> str:
    """Name the YAML value's Python-level type without evaluating interpolations."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, Mapping):
        return "object"
    return type(value).__name__


def render_configuration_reference(config: Mapping[str, Any]) -> str:
    """Render a stable Markdown inventory from parsed configuration defaults."""
    rows = [
        "# Configuration reference",
        "",
        "This inventory is generated from [`config/base/default.yaml`](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/main/config/base/default.yaml).",
        "It lists leaf keys, their YAML defaults, inferred value types, and the owning",
        "domain section. OmegaConf interpolation expressions are shown literally; their",
        "resolved values depend on the referenced keys and run configuration.",
        "",
        "The inventory describes defaults, not every valid override. Schema validation",
        "lives in [`configuration/schema.py`](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/main/configuration/schema.py); key",
        "resolution and merging live in [`configuration/configuration_loader.py`](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/main/configuration/configuration_loader.py).",
        "The owner column groups consumers by domain; it does not imply that every key",
        "is read by every listed package.",
        "",
        "| Key path | Type | Default | Owning domain |",
        "|---|---|---|---|",
    ]
    for path, value in sorted(_leaves(config)):
        section = path.split(".", maxsplit=1)[0]
        owner = SECTION_OWNERS.get(section, section)
        default = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        default = default.replace("|", "\\|")
        rows.append(f"| `{path}` | `{_inferred_type(value)}` | `{default}` | `{owner}` |")
    rows.append("")
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--write", action="store_true", help="write the generated reference")
    action.add_argument("--check", action="store_true", help="fail if the reference is stale")
    args = parser.parse_args(argv)
    parsed = yaml.safe_load(DEFAULTS.read_text(encoding="utf-8"))
    if not isinstance(parsed, Mapping):
        parser.error(f"expected a mapping at the root of {DEFAULTS.relative_to(ROOT)}")
    rendered = render_configuration_reference(parsed)
    if args.write:
        OUTPUT.write_text(rendered, encoding="utf-8")
        return 0
    if args.check:
        if not OUTPUT.is_file() or OUTPUT.read_text(encoding="utf-8") != rendered:
            print(f"generated configuration reference is stale: {OUTPUT.relative_to(ROOT)}")
            return 1
        print(
            f"Configuration keys: {sum(1 for _ in _leaves(parsed))} generated defaults match source."
        )
        return 0
    print(f"Configuration keys: {sum(1 for _ in _leaves(parsed))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
