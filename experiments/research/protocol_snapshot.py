"""Prospective protocol snapshot without model outcomes."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from omegaconf import OmegaConf

from artifacts.atomic import write_json_atomic
from configuration import load_config
from configuration.paths import repository_root
from training.configuration.research_protocol import (
    load_research_protocol,
    research_protocol_sha256,
)

ROOT = repository_root(__file__)
DEFAULT_PROTOCOL = ROOT / "config/research/prospective_research_protocol.yaml"


def _sha256(path: Path) -> str:
    """Return the SHA-256 digest of a file.

    Args:
        path: Path to the input or output artifact.

    Returns:
        Result produced by _sha256.
    """
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolved_config_sha256(path: Path) -> str:
    """Return a semantic digest of a resolved configuration.

    Args:
        path: Path to the input or output artifact.

    Returns:
        Result produced by _resolved_config_sha256.
    """
    cfg = load_config(config_path=path)
    payload = OmegaConf.to_container(cfg, resolve=True)
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def build_protocol_snapshot(protocol_path: Path = DEFAULT_PROTOCOL) -> dict[str, Any]:
    """Build a source-bound protocol record containing no execution outcomes.

    Args:
        protocol_path: Value used for protocol path.

    Returns:
        Result produced by build_protocol_snapshot.
    """
    protocol = load_research_protocol(protocol_path)
    policy = protocol["policy"]
    config_keys = {
        "control": "control_config",
        "canonical": "canonical_survival_config",
        "candidate_geometry": "price_geometry_config",
    }
    configs: dict[str, dict[str, str]] = {}
    for role, key in config_keys.items():
        relative = Path(str(policy[key]))
        path = ROOT / relative
        if not path.is_file():
            raise FileNotFoundError(path)
        configs[role] = {
            "path": relative.as_posix(),
            "file_sha256": _sha256(path),
            "resolved_config_sha256": _resolved_config_sha256(path),
        }
    source_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=ROOT, text=True
    ).splitlines()
    return {
        "schema_version": 1,
        "artifact_role": "prospective_protocol_snapshot",
        "source_commit": source_commit,
        "source_dirty": bool(dirty),
        "dirty_paths": dirty,
        "protocol_path": protocol_path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "protocol_file_sha256": _sha256(protocol_path),
        "protocol_semantic_sha256": research_protocol_sha256(protocol),
        "configs": configs,
        "forbidden_inputs": [
            "exposed_report_period_outcomes",
            "candidate_realized_returns",
            "future_market_values",
            "post_selection_metric_threshold_changes",
        ],
        "protocol": protocol,
    }


def main(argv: list[str] | None = None) -> int:
    """Build and write a prospective protocol snapshot.

    Args:
        argv: Command-line arguments for this operation.

    Returns:
        Result produced by main.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    protocol = args.protocol if args.protocol.is_absolute() else ROOT / args.protocol
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = build_protocol_snapshot(protocol)
    write_json_atomic(output, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
