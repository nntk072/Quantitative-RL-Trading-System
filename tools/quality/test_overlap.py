#!/usr/bin/env python3
"""Rank test modules by overlap in production lines covered by each module."""

from __future__ import annotations

import argparse
import itertools
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

from coverage import CoverageData

ROOT = Path(__file__).resolve().parents[2]


def _test_module(context: str) -> str | None:
    """Extract the test-file owner from a pytest-cov test context."""
    if "::" not in context:
        return None
    path = context.split("::", maxsplit=1)[0]
    return path if path.startswith("tests/") else None


def coverage_by_test(data: CoverageData) -> dict[str, set[tuple[str, int]]]:
    """Collect production file/line pairs exercised by each test module."""
    result: dict[str, set[tuple[str, int]]] = defaultdict(set)
    for source in data.measured_files():
        normalized = Path(source).resolve()
        try:
            relative = normalized.relative_to(ROOT).as_posix()
        except ValueError:
            continue
        if relative.startswith("tests/") or not relative.endswith(".py"):
            continue
        for line, contexts in data.contexts_by_lineno(source).items():
            for context in contexts:
                module = _test_module(context)
                if module is not None:
                    result[module].add((relative, line))
    return dict(result)


def rank_overlaps(
    coverage: dict[str, set[tuple[str, int]]], minimum_shared_lines: int = 12
) -> list[dict[str, Any]]:
    """Return module pairs with enough shared production coverage to review."""
    rows: list[dict[str, Any]] = []
    for left_name, right_name in itertools.combinations(sorted(coverage), 2):
        left = coverage[left_name]
        right = coverage[right_name]
        shared = left & right
        if len(shared) < minimum_shared_lines:
            continue
        union = left | right
        rows.append(
            {
                "left": left_name,
                "right": right_name,
                "left_lines": len(left),
                "right_lines": len(right),
                "shared_lines": len(shared),
                "jaccard": len(shared) / len(union) if union else 0.0,
                "shared_files": len({path for path, _ in shared}),
            }
        )
    return sorted(rows, key=lambda row: (-row["jaccard"], -row["shared_lines"]))


def _source_identity() -> tuple[str, str]:
    """Return the current branch and commit used for the overlap report."""
    result = subprocess.run(
        ["git", "branch", "--show-current"], cwd=ROOT, capture_output=True, text=True
    )
    branch = result.stdout.strip() or "detached"
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    return branch, result.stdout.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-file", type=Path, default=ROOT / ".coverage")
    parser.add_argument("--minimum-shared-lines", type=int, default=12)
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args(argv)
    data = CoverageData(basename=str(args.data_file))
    data.read()
    coverage = coverage_by_test(data)
    rows = rank_overlaps(coverage, args.minimum_shared_lines)
    branch, commit = _source_identity()
    print(
        f"Coverage overlap for {branch} at {commit[:12]}: {len(coverage)} test modules, "
        f"{len(rows)} candidate pairs (minimum {args.minimum_shared_lines} shared lines)."
    )
    print("Similarity is a review lead; shared coverage alone does not establish duplicate tests.")
    for row in rows[: args.limit]:
        print(
            f"{row['jaccard']:.3f} shared={row['shared_lines']} files={row['shared_files']} "
            f"({row['left']} <> {row['right']})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
