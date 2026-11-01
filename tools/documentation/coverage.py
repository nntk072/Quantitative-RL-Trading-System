#!/usr/bin/env python3
"""Generate or validate the machine-readable subject coverage audit."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "docs/development/documentation_coverage.md"
OUTPUT = ROOT / "docs/documentation_coverage.json"
OUTPUT = ROOT / "docs/documentation_coverage.json"
DIMENSIONS = (
    "concept",
    "architecture",
    "tutorial",
    "how_to",
    "reference_api",
    "troubleshooting",
    "research",
    "reproduction",
)
CELL_STATES = {"●": "dedicated", "◒": "partial", "—": "missing"}


def build_coverage() -> dict[str, Any]:
    """Parse the reviewed Markdown matrix into a stable JSON representation."""
    rows: list[dict[str, Any]] = []
    in_table = False
    for line in SOURCE.read_text(encoding="utf-8").splitlines():
        if line.startswith("| Subject |"):
            in_table = True
            continue
        if not in_table:
            continue
        if not line.startswith("|"):
            break
        if re.match(r"\|[- :|]+\|$", line):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != len(DIMENSIONS) + 1:
            raise ValueError(f"coverage row has {len(cells)} cells: {line}")
        states = cells[1:]
        if any(state not in CELL_STATES for state in states):
            raise ValueError(f"unknown coverage state in row: {line}")
        rows.append(
            {
                "subject": cells[0],
                "dimensions": dict(zip(DIMENSIONS, (CELL_STATES[state] for state in states))),
            }
        )
    if not rows:
        raise ValueError("coverage matrix table was not found")
    names = [row["subject"] for row in rows]
    if len(names) != len(set(names)):
        raise ValueError("coverage matrix contains duplicate subjects")
    return {
        "schema_version": 1,
        "source": "docs/development/documentation_coverage.md",
        "dimensions": list(DIMENSIONS),
        "state_vocabulary": CELL_STATES,
        "subject_count": len(rows),
        "subjects": rows,
    }


def main() -> int:
    """Write the JSON audit or fail when its committed snapshot is stale."""
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--write", action="store_true")
    actions.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = json.dumps(build_coverage(), indent=2, sort_keys=True) + "\n"
    if args.write:
        OUTPUT.write_text(expected, encoding="utf-8")
        print(f"Wrote {OUTPUT.relative_to(ROOT)}")
        return 0
    actual = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
    if actual != expected:
        print(
            f"{OUTPUT.relative_to(ROOT)} is stale; run python -m tools.documentation.coverage --write"
        )
        return 1
    data = json.loads(actual)
    print(
        f"Coverage matrix is current ({data['subject_count']} subjects, {len(DIMENSIONS)} dimensions)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
