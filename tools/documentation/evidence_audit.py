#!/usr/bin/env python3
"""Audit tracked research packages for assets required by documented claims."""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "docs/reproduce/evidence_audit.md"
EXIT = "evidence/research/exit_action_semantics"
SETUP = "evidence/research/setup_conditioned_reasoning_replay"
ENTRY_EXIT = "evidence/research/entry_and_exit_attribution"
IDEAS = "evidence/research/entry_idea_opportunity_counts"
AUDITS: dict[str, dict[str, list[str]]] = {
    "Exit-action exact-common-entry cohort (R2 claim scope)": {
        "Tracked identity and provenance": [
            f"{EXIT}/evidence_manifest.json",
            f"{EXIT}/run_identity.json",
            f"{EXIT}/evaluation_configuration.yaml",
        ],
        "Recomputable cohort summary": [
            f"{EXIT}/common_entry_cohort.csv",
            f"{EXIT}/common_entry_cohort_summary.json",
        ],
        "Fixed-entry shadow exports": [
            f"{EXIT}/fixed_entry_shadow_trades.csv",
            f"{EXIT}/fixed_entry_shadow_events.jsonl",
            f"{EXIT}/fixed_entry_shadow_provenance.json",
        ],
        "Interpretation and comparison records": [
            f"{EXIT}/README.md",
            f"{EXIT}/decoder_behavior_comparison.md",
            f"{EXIT}/fixed_entry_shadow_findings.md",
            f"{EXIT}/decision_gates.json",
            f"{EXIT}/counterfactual_decoder_patch.diff",
        ],
        "Complete closed-loop replay inputs": [
            "not-tracked: full per-arm v2 trade ledger",
            "not-tracked: full per-arm v3 trade ledger",
            "not-tracked: original raw tick data",
        ],
    },
    "Monthly entry and exit attribution (R2 aggregate claim scope)": {
        "Tracked semantic packet, reproduction source, paired trade inputs and figure": [
            f"{ENTRY_EXIT}/evidence_manifest.json",
            f"{ENTRY_EXIT}/monthly_entry_exit_summary.json",
            f"{ENTRY_EXIT}/treatment_paired_trades.csv",
            f"{ENTRY_EXIT}/control_paired_trades.csv",
            f"{ENTRY_EXIT}/monthly_entry_exit_attribution.png",
            "docs/reproduce/entry_and_exit_attribution.ipynb",
        ],
        "Replay inputs absent from the tracked packet": [
            "not-tracked: source run manifests and per-arm environment traces",
            "not-tracked: original raw tick data and broker fill inputs",
            "not-tracked: frozen policy checkpoints for both arms",
        ],
    },
    "Entry-idea opportunity counts (R2 aggregate claim scope)": {
        "Tracked aggregate inputs": [
            f"{IDEAS}/annual_summary.csv",
            f"{IDEAS}/by_idea_timeframe.csv",
            f"{IDEAS}/entry_idea_opportunity_counts.md",
        ],
        "Unavailable raw recount inputs": [
            "not-tracked: timestamp-level source feature rows",
            "not-tracked: source feature cache and generation manifest",
        ],
    },
    "Setup-conditioned replay (R1 evidence view)": {
        "Tracked evidence": [
            f"{SETUP}/README.md",
            f"{SETUP}/policy_variant_comparison/arm_c/testing/policy_metrics.json",
            f"{SETUP}/policy_variant_comparison/arm_d/testing/policy_metrics.json",
            f"{SETUP}/policy_variant_comparison/arm_c/testing/equity.png",
            f"{SETUP}/policy_variant_comparison/arm_d/testing/equity.png",
        ],
        "Independent figure regeneration (R2)": [
            "not-tracked: C per-arm equity ledger",
            "not-tracked: D per-arm equity ledger",
            "not-tracked: C trade ledger",
            "not-tracked: D trade ledger",
        ],
    },
    "Model observation and action semantics (source/configuration scope)": {
        "Tracked source, configuration, and evidence": [
            "evidence/research/model_observation_and_action_semantics/README.md",
            "evidence/research/model_observation_and_action_semantics/run_artifact_shape_inventory.json",
            "scripts/research/analysis/models/inspect_observation_action_artifacts.py",
            "docs/research/model_observation_and_action_semantics.md",
            "decisioning/trade_setup.py",
            "simulation/environment/observation_runtime.py",
            "models/encoders/mtf_reasoning.py",
            "learning/rl/hybrid.py",
            "config/research/trade_setup_mtf_reasoning_2m.yaml",
            "config/research/trade_setup_mtf_reasoning_conditioned_2m.yaml",
            "evidence/research/trade_setup_opportunity_census/census.json",
        ],
        "Run-specific or scientific claims not established by this packet": [
            "not-tracked: run-resolved tensor shapes for every compared configuration and checkpoint",
            "not-tracked: per-decision selected-setup and proposed-price geometry traces",
            "not-tracked: authoritative candidate event timestamps and publication delays",
            "not-tracked: candidate-level fill, return, and calibrated outcome evidence",
        ],
    },
    "Real-market feature prefix invariance (resolved profile inventory)": {
        "Tracked analysis and result": [
            "scripts/research/analysis/features/verify_real_market_feature_prefix_invariance.py",
            "scripts/research/analysis/features/merge_real_market_feature_prefix_shards.py",
            "tests/research/test_feature_prefix_invariance.py",
            "tests/research/test_real_market_feature_prefix_shards.py",
            "evidence/research/feature_causality/real_market_feature_prefix_invariance_all_profiles.json",
            "docs/research/feature_causality_and_availability.md",
            "evidence/research/feature_causality/feature_causality_matrix.csv",
        ],
        "Claims deliberately left open": [
            "not-tracked: authoritative source-event publication timestamps",
            "not-tracked: authoritative session-calendar validation",
            "not-tracked: configurations outside the resolved 130-profile inventory",
            "not-tracked: logical event cardinality and historical candidate-to-action linkage",
        ],
    },
    "Fill quote source alignment (selected local fills)": {
        "Tracked analysis and result": [
            "scripts/research/analysis/market_data/analyze_fill_quote_source_alignment.py",
            "tests/research/test_fill_quote_source_alignment.py",
            "evidence/research/fill_quote_source_alignment/README.md",
            "evidence/research/fill_quote_source_alignment/selected_campaign_fill_quote_alignment.json",
            "docs/research/fill_quote_availability.md",
        ],
        "Claims deliberately left open": [
            "not-tracked: authoritative provider clock and daylight-saving history",
            "not-tracked: authoritative market session calendar",
            "not-tracked: within-timestamp quote chronology or broker order-arrival quote",
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
            "The real-market prefix packet resolves 130 registered configurations into 19 feature-builder groups and passes all 57 comparisons across three cutoffs; it is limited to that inventory and local history. Logical event cardinality, authoritative publication timestamps and calendar semantics, and historical candidate-to-action linkage remain open. The exit-action notebook makes an R2 claim only for the tracked cohort CSV and summary. The monthly entry and exit attribution notebook recomputes paired-trade aggregates, seeded bootstrap intervals, a decomposition, and the versioned figure; raw ticks and checkpoints are absent from this tracked packet. This audit does not inventory ignored local scratch assets or independently validate their availability. The entry-idea notebook recomputes family-level totals from tracked aggregate exports, but timestamp-level feature rows are absent. The setup-conditioned package supports an R1 evidence view; its missing ledgers prevent full plot regeneration.",
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
