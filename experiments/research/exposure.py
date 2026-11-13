"""One-time exposed-period access marker."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from artifacts.atomic import write_json_atomic
from artifacts.identity import file_sha256
from configuration.paths import repository_root

ROOT = repository_root(__file__)


def _object(path: Path) -> dict[str, Any]:
    """Load one JSON object from disk.

    Args:
        path: Path to the input or output artifact.

    Returns:
        Result produced by _object.
    """
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def open_exposed_report(marker: Path, robustness_record: Path) -> dict[str, Any]:
    """Atomically record the only authorized opening of the exposed interval.

    Args:
        marker: Path used to record the one-time exposed-period opening.
        robustness_record: Path to the robustness disposition artifact.

    Returns:
        Result produced by open_exposed_report.
    """
    marker = marker.expanduser().resolve()
    robustness_record = robustness_record.expanduser().resolve()
    if marker.exists():
        raise FileExistsError(f"exposed report interval was already opened: {marker}")
    robustness = _object(robustness_record)
    if robustness.get("status") != "pass":
        raise ValueError("exposed report requires passing robustness evidence")
    source_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    payload = {
        "schema_version": 1,
        "status": "opened",
        "source_commit": source_commit,
        "opened_at_utc": datetime.now(UTC).isoformat(),
        "period": {"start": "2026-01-01", "end_inclusive": "2026-10-16"},
        "selection_allowed": False,
        "robustness_record": str(robustness_record),
        "robustness_sha256": file_sha256(robustness_record),
    }
    marker.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(marker, payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    """Run the one-time exposed-period marker command.

    Args:
        argv: Command-line arguments for this operation.

    Returns:
        Result produced by main.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--marker", type=Path, required=True)
    parser.add_argument("--robustness-record", type=Path, required=True)
    args = parser.parse_args(argv)
    payload = open_exposed_report(args.marker, args.robustness_record)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
