#!/usr/bin/env python3
"""Build the prospective six-seed primary treatment-vs-no-trade payload.

The source specification is deliberately explicit and hash-pinned. It may be
assembled only after the portfolio candidate and matched no-trade evidence
exist, but this source tool need not change after results arrive.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from scripts.research.audits.record_pretraining_scientific_gate import file_sha256

from artifacts.atomic import write_json_atomic
from evaluation.metrics.matched_comparison import MATCH_FIELDS

EXPECTED_SEEDS = [42, 43, 44, 45, 46, 47]


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


def _verify_sources(rows: Any, label: str) -> list[dict[str, str]]:
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{label} requires source_artifacts")
    verified: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"{label} source artifact must be an object")
        path = Path(str(row.get("path", ""))).expanduser().resolve()
        digest = row.get("sha256")
        if not path.is_file():
            raise FileNotFoundError(path)
        observed = file_sha256(path)
        if digest != observed:
            raise ValueError(f"{label} source artifact hash mismatch: {path}")
        verified.append({"path": str(path), "sha256": observed})
    return verified


def _arm(
    value: Any,
    *,
    seed: int,
    control: bool,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("pair arm must be an object")
    provenance = value.get("provenance")
    if not isinstance(provenance, dict):
        raise ValueError("pair arm requires provenance")
    missing = [field for field in MATCH_FIELDS if field not in provenance]
    if missing:
        raise ValueError(f"pair arm missing provenance fields: {missing}")
    if provenance.get("seed") != seed:
        raise ValueError("pair arm provenance seed mismatch")
    policy_sha = provenance.get("policy_sha256")
    if not isinstance(policy_sha, str) or len(policy_sha) != 64:
        raise ValueError("pair arm requires policy_sha256")
    initial = _finite(value.get("initial_operating_equity"), "initial_operating_equity")
    retained = _finite(value.get("ending_retained_equity"), "ending_retained_equity")
    payouts = _finite(value.get("cumulative_payouts"), "cumulative_payouts")
    trade_count = value.get("trade_count")
    if isinstance(trade_count, bool) or not isinstance(trade_count, int) or trade_count < 0:
        raise ValueError("trade_count must be a nonnegative integer")
    if (
        value.get("evaluation_complete") is not True
        or value.get("hard_risk_gate_passed") is not True
    ):
        raise ValueError("primary comparison requires complete hard-risk-safe paths")
    if initial <= 0.0 or payouts < 0.0:
        raise ValueError("invalid account values")
    if control:
        if value.get("policy_id") != "always_no_trade_v1":
            raise ValueError("primary control must be always_no_trade_v1")
        if (
            trade_count != 0
            or payouts != 0.0
            or not math.isclose(retained, initial, rel_tol=1e-12, abs_tol=1e-9)
        ):
            raise ValueError("no-trade control must retain capital with zero trades/payout")
    net_return = 100.0 * (retained + payouts - initial) / initial
    declared = _finite(value.get("net_return_initial_equity_pct"), "net_return_initial_equity_pct")
    if not math.isclose(net_return, declared, rel_tol=1e-12, abs_tol=1e-9):
        raise ValueError("declared full-path net return does not reconcile")
    return {
        "run_id": str(value.get("run_id", "")).strip(),
        "status": "succeeded",
        "evidence_role": "matched_exploratory",
        "policy_id": value.get("policy_id"),
        "evaluation_complete": True,
        "hard_risk_gate_passed": True,
        "initial_operating_equity": initial,
        "ending_retained_equity": retained,
        "cumulative_payouts": payouts,
        "trade_count": trade_count,
        "provenance": dict(provenance),
        "metrics": {"net_return_initial_equity_pct": declared},
        "source_artifacts": _verify_sources(value.get("source_artifacts"), f"seed {seed} arm"),
    }


def build_payload(spec: dict[str, Any]) -> dict[str, Any]:
    """Build an analyzer-ready aalto.paired_seed_metrics.v2 payload."""
    if spec.get("schema_version") != "v3-primary-pair-sources-v1":
        raise ValueError("unsupported primary pair source schema")
    if spec.get("evaluation_exposure") != "development":
        raise ValueError("primary selection must use development exposure")
    seeds = spec.get("expected_seeds")
    if seeds != EXPECTED_SEEDS:
        raise ValueError(f"expected_seeds must be exactly {EXPECTED_SEEDS}")
    pairs = spec.get("pairs")
    if not isinstance(pairs, list) or len(pairs) != len(EXPECTED_SEEDS):
        raise ValueError("primary source spec requires exactly six pairs")
    by_seed: dict[int, dict[str, Any]] = {}
    for pair in pairs:
        if not isinstance(pair, dict):
            raise ValueError("pair must be an object")
        seed = pair.get("seed")
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise ValueError("pair seed must be an integer")
        if seed in by_seed:
            raise ValueError("duplicate pair seed")
        by_seed[seed] = pair
    if sorted(by_seed) != EXPECTED_SEEDS:
        raise ValueError("pair seeds do not match the prospective seed set")

    built = []
    for seed in EXPECTED_SEEDS:
        pair = by_seed[seed]
        control = _arm(pair.get("control"), seed=seed, control=True)
        treatment = _arm(pair.get("treatment"), seed=seed, control=False)
        for field in MATCH_FIELDS:
            if control["provenance"][field] != treatment["provenance"][field]:
                raise ValueError(f"seed {seed} unmatched provenance: {field}")
        if control["provenance"]["policy_sha256"] == treatment["provenance"]["policy_sha256"]:
            raise ValueError(f"seed {seed} policy intervention does not differ")
        built.append({"seed": seed, "control": control, "treatment": treatment})

    return {
        "schema": "aalto.paired_seed_metrics.v2",
        "comparison_id": str(spec.get("comparison_id", "v3-primary-treatment-vs-no-trade")),
        "evidence_role": "matched_exploratory",
        "evaluation_exposure": "development",
        "intervention_field": "policy_sha256",
        "metrics": ["net_return_initial_equity_pct"],
        "expected_seeds": EXPECTED_SEEDS,
        "primary_selection": {
            "contrast": "treatment_vs_always_no_trade",
            "metric": "net_return_initial_equity_pct",
            "alternative": "greater",
            "control_policy_id": "always_no_trade_v1",
        },
        "pairs": built,
        "selection_note": (
            "Prospective primary six-seed development comparison. "
            "The exposed 2026 interval is excluded from selection."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    spec = json.loads(args.source_spec.read_text(encoding="utf-8"))
    if not isinstance(spec, dict):
        raise ValueError("source spec must be a JSON object")
    payload = build_payload(spec)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(args.output, payload)
    print(json.dumps({"output": str(args.output), "pairs": len(payload["pairs"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
