"""Exact structural comparison and explicit per-field numerical tolerances."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from tools.quality.local_checks.run_evidence import read_quality_json


def compare_quality_traces(
    reference: Any,
    candidate: Any,
    tolerances: dict[str, dict[str, float]],
    path: str = "$",
) -> list[dict[str, Any]]:
    """Compare nested values without treating booleans as numeric or NaN as equality."""
    if isinstance(reference, bool) or isinstance(candidate, bool):
        equal = type(reference) is type(candidate) and reference == candidate
    elif isinstance(reference, (float, int)) and isinstance(candidate, (float, int)):
        rule = tolerances.get(path, tolerances.get("$", {}))
        atol, rtol = rule.get("atol", 0.0), rule.get("rtol", 0.0)
        if not all(math.isfinite(v) and v >= 0 for v in (atol, rtol)):
            raise ValueError(f"Invalid tolerance at {path}")
        equal = (
            math.isfinite(reference)
            and math.isfinite(candidate)
            and math.isclose(reference, candidate, abs_tol=atol, rel_tol=rtol)
        )
    elif isinstance(reference, dict) and isinstance(candidate, dict):
        if reference.keys() != candidate.keys():
            return [{"path": path, "reason": "different field inventory"}]
        return [
            row
            for k in sorted(reference)
            for row in compare_quality_traces(reference[k], candidate[k], tolerances, f"{path}.{k}")
        ]
    elif isinstance(reference, list) and isinstance(candidate, list):
        if len(reference) != len(candidate):
            return [{"path": path, "reason": "different sequence length"}]
        return [
            row
            for i, (a, b) in enumerate(zip(reference, candidate, strict=True))
            for row in compare_quality_traces(a, b, tolerances, f"{path}[{i}]")
        ]
    else:
        equal = type(reference) is type(candidate) and reference == candidate
    return (
        []
        if equal
        else [{"path": path, "reference": repr(reference), "candidate": repr(candidate)}]
    )


def compare_trace_files(left: Path, right: Path, tolerance_file: Path | None) -> dict[str, Any]:
    """Compare saved trace evidence; do not call a match scientific validation by itself."""
    rules = read_quality_json(tolerance_file) if tolerance_file else {}
    mismatches = compare_quality_traces(read_quality_json(left), read_quality_json(right), rules)
    return {
        "status": "findings" if mismatches else "ok",
        "mismatches": mismatches,
        "qualification": "Imported trace comparison; source/backend identity must be verified separately.",
    }
