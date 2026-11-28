"""Normalize mutation evidence without treating timeouts or skipped tests as kills."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

STATES = (
    "killed",
    "survived",
    "timeout",
    "no_tests",
    "invalid",
    "suspicious",
    "unexecuted",
    "equivalent",
    "unknown",
)

ALIASES = {
    "killed": "killed",
    "caught": "killed",
    "survived": "survived",
    "missed": "survived",
    "timeout": "timeout",
    "timed out": "timeout",
    "no tests": "no_tests",
    "no_tests": "no_tests",
    "unviable": "invalid",
    "invalid": "invalid",
    "suspicious": "suspicious",
    "skipped": "unexecuted",
    "not checked": "unexecuted",
    "not run": "unexecuted",
    "not_run": "unexecuted",
    "unchecked": "unexecuted",
    "unexecuted": "unexecuted",
    "type check error": "invalid",
    "caught by type checker": "invalid",
}


def _count(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("Mutation counts must be nonnegative integers")
    return value


def _counts(raw: dict[str, Any], tool: str) -> dict[str, int | None]:
    keys = {
        "killed": "caught" if tool == "cargo-mutants" else "killed",
        "survived": "missed" if tool == "cargo-mutants" else "survived",
        "timeout": "timeout",
        "no_tests": "no_tests",
        "invalid": "unviable" if tool == "cargo-mutants" else "invalid",
        "suspicious": "suspicious",
        "unexecuted": "skipped",
    }
    if not all(keys[k] in raw for k in ("killed", "survived", "timeout")):
        raise ValueError(f"Unsupported {tool} mutation summary")
    return {state: _count(raw[key]) if key in raw else None for state, key in keys.items()}


def parse_mutmut_results(text: str) -> dict[str, str]:
    """Parse per-mutant status lines, refusing duplicate or unknown records."""
    rows: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        match = re.fullmatch(r"\s*(\S+):\s*(.+?)\s*", line)
        if match is None or match[2].lower() not in ALIASES:
            raise ValueError(f"Unrecognized mutmut result line: {line[:120]}")
        if match[1] in rows:
            raise ValueError("Duplicate mutant identifier")
        rows[match[1]] = ALIASES[match[2].lower()]
    return rows


def summarize(
    raw: dict[str, Any],
    *,
    tool: str,
    scope: dict[str, Any],
    complete: bool,
    mutants: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Keep raw counts, verified status counts and denominator qualifications separate."""
    if tool not in {"mutmut", "cargo-mutants"}:
        raise ValueError("Unsupported mutation tool")
    counts = _counts(raw, tool)
    total = _count(raw["total_mutants"] if "total_mutants" in raw else raw["total"])
    known = sum(value for value in counts.values() if value is not None)
    if known > total:
        raise ValueError("Reported statuses exceed total mutants")
    residual = total - known
    if mutants is not None:
        if len(mutants) != total or any(state not in STATES for state in mutants.values()):
            raise ValueError("Per-mutant inventory does not reconcile with the summary")
        observed = {state: list(mutants.values()).count(state) for state in STATES}
        for state, value in counts.items():
            if value is not None and observed[state] != value:
                raise ValueError(f"Mutation status mismatch: {state}")
        counts = observed
        residual = 0
    killed = counts["killed"] or 0
    survived = counts["survived"] or 0
    denominator = killed + survived
    return {
        "schema_version": 1,
        "tool": tool,
        "scope": scope,
        "status": "complete" if complete and residual == 0 else "incomplete",
        "generated": total,
        "counts": counts,
        "unclassified_count": residual,
        "per_mutant": mutants,
        "score_killed_over_killed_plus_survived": killed / denominator if denominator else None,
        "score_denominator": denominator,
        "score_is_partial": not complete or residual != 0,
        "killed_fraction_of_generated": killed / total if total else None,
        "equivalent_reviewed": None,
        "qualification": "Timeouts, unviable, untested, skipped and unknown are not kills.",
    }


def import_report(
    report: Path, tool: str, scope: dict[str, Any], complete: bool, details: Path | None = None
) -> dict[str, Any]:
    """Import a report; never infer execution completeness from a JSON file alone."""
    raw = json.loads(report.read_text())
    mutants = parse_mutmut_results(details.read_text()) if details and tool == "mutmut" else None
    if details and tool != "mutmut":
        raise ValueError("Per-mutant import requires a supported mutmut results text report")
    return summarize(raw, tool=tool, scope=scope, complete=complete, mutants=mutants)
