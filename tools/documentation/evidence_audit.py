#!/usr/bin/env python3
"""Audit tracked research packages for assets required by documented claims."""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "docs/reproduce/evidence_audit.md"
EXIT = "evidence/research/archive_2026/evidence/exit_action_semantics_20261024"
SETUP = "evidence/research/setup_conditioned_reasoning_replay"
AUDITS: dict[str, dict[str, list[str]]] = {
    "Exit-action exact-common-entry cohort (R2 claim scope)": {
        "Tracked identity": [f"{EXIT}/provenance.json", f"{EXIT}/config.yaml"],
        "Recomputable cohort summary": [
            f"{EXIT}/phase2_common_entry_cohort.csv",
            f"{EXIT}/phase2_cohort_summary.json",
        ],
        "Fixed-entry shadow exports": [
            f"{EXIT}/fixed_entry_shadow/paired_trades.csv",
            f"{EXIT}/fixed_entry_shadow/shadow_events.jsonl",
        ],
        "Complete closed-loop replay inputs": [
            "not-tracked: full per-arm v2 trade ledger",
            "not-tracked: full per-arm v3 trade ledger",
            "not-tracked: original raw tick data",
        ],
    },
    "Setup-conditioned replay (R1 evidence view)": {
        "Tracked evidence": [
            f"{SETUP}/README.md",
            f"{SETUP}/benchmark_output_20261028/C/testing/thesis_policy_metrics.json",
            f"{SETUP}/benchmark_output_20261028/D/testing/thesis_policy_metrics.json",
            f"{SETUP}/benchmark_output_20261028/C/testing/equity.png",
            f"{SETUP}/benchmark_output_20261028/D/testing/equity.png",
        ],
        "Independent figure regeneration (R2)": [
            "not-tracked: C per-arm equity ledger",
            "not-tracked: D per-arm equity ledger",
            "not-tracked: C trade ledger",
            "not-tracked: D trade ledger",
        ],
    },
}


def render_audit(root: Path = ROOT) -> str:
    """Render deterministic complete/partial/missing checks for known packages."""
    lines = [
        "# Research evidence sufficiency audit",
        "",
        "This generated audit checks files required for the stated claim scope. It does not upgrade a result beyond the available inputs.",
        "",
    ]
    for result, groups in AUDITS.items():
        lines.extend([f"## {result}", ""])
        for group, assets in groups.items():
            missing = [
                asset
                for asset in assets
                if asset.startswith("not-tracked:") or not (root / asset).is_file()
            ]
            status = (
                "complete"
                if not missing
                else ("missing" if len(missing) == len(assets) else "partial")
            )
            lines.append(
                f"**{group}: {status}** ({len(assets) - len(missing)}/{len(assets)} tracked assets present)"
            )
            lines.extend(
                [
                    f"- {asset.removeprefix('not-tracked: ')} — {'missing' if asset in missing else 'present'}"
                    for asset in assets
                ]
            )
            lines.append("")
    lines.extend(
        [
            "## Interpretation",
            "",
            "The exit-action notebook makes an R2 claim only for the tracked cohort CSV and summary. The fixed-entry shadow exports exist, but the full per-arm ledgers and raw ticks are missing. The setup-conditioned package supports an R1 evidence view; its missing ledgers prevent full plot regeneration.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    """Write the audit report or verify that its committed copy is current."""
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = render_audit()
    if args.write:
        OUTPUT.write_text(expected, encoding="utf-8")
        print(f"Wrote {OUTPUT.relative_to(ROOT)}")
        return 0
    if not OUTPUT.is_file() or OUTPUT.read_text(encoding="utf-8") != expected:
        print(
            f"{OUTPUT.relative_to(ROOT)} is stale; run python -m tools.documentation.evidence_audit --write"
        )
        return 1
    print("Research evidence sufficiency audit is current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
