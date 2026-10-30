#!/usr/bin/env python3
"""Compatibility CLI adapter for campaign cache-failure recovery."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def prepare_campaign_resume(campaign_dir: Path) -> dict[str, object]:
    """Compatibility API forwarding recovery to its campaign-domain owner."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "experiments.campaigns.cache_failure_recovery",
            "--campaign-dir",
            str(campaign_dir),
        ],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("campaign recovery returned invalid JSON") from exc
    if not isinstance(value, dict):
        raise RuntimeError("campaign recovery returned a non-mapping result")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare_campaign_resume(args.campaign_dir), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
