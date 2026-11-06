#!/usr/bin/env python3
"""Audit exact candidate-event overlap with available decision traces.

The current inputs are matched development baselines, not historical PPO
rollouts. This audit can establish source-identified selection overlap only;
it cannot establish that a trained policy selected a proposal or realized its
conditional replay outcome.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from configuration.paths import repository_root

ROOT = repository_root(__file__)
BASELINE = (
    ROOT / "evidence/research/matched_setup_baselines/matched_setup_baselines_19770241b07b5b5e"
)
PROPOSALS = ROOT / "evidence/research/candidate_proposals"
DEFAULT_OUTPUT = ROOT / "evidence/research/candidate_action_linkage"
DECISION_COLUMNS = (
    "trade_setup_candidate_id",
    "trade_setup_source_event_id",
    "trade_setup_event_identity_version",
    "trade_setup_source_event_identity_status",
    "trade_setup_eligible",
    "selection_valid",
    "decision_id",
    "decision_time",
    "selected_idea",
    "selected_timeframe",
    "selected_direction",
    "entry_rejection_reason",
    "entry_state",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_candidate_packet() -> None:
    for line in (PROPOSALS / "OUTPUT_SHA256SUMS").read_text(encoding="utf-8").splitlines():
        expected, name = line.split(maxsplit=1)
        if _sha256(PROPOSALS / name.strip()) != expected:
            raise ValueError(f"candidate proposal packet checksum mismatch: {name}")


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1"}


def build_action_linkage(output_dir: Path) -> dict[str, Any]:
    _verify_candidate_packet()
    result_manifest_path = BASELINE / "result_manifest.json"
    result_manifest = json.loads(result_manifest_path.read_text(encoding="utf-8"))
    proposals = pd.read_parquet(PROPOSALS / "candidate_proposals.parquet")
    if not proposals["policy_eligibility"].eq("eligible").all():
        raise ValueError("candidate proposal input must be statically eligible")
    proposal_pairs = proposals[
        [
            "candidate_id",
            "source_event_id",
            "proposal_id",
            "entry_type",
            "idea_family",
            "source_timeframe",
            "direction",
            "valid_from",
            "expires_at",
        ]
    ].copy()
    if proposal_pairs["proposal_id"].isna().any() or not proposal_pairs["proposal_id"].is_unique:
        raise ValueError("candidate proposal IDs must be present and unique")
    proposal_pairs["candidate_id"] = pd.to_numeric(
        proposal_pairs["candidate_id"], errors="raise"
    ).astype("int64")
    pair_identity_fields = ["idea_family", "source_timeframe", "direction"]
    pair_identity_counts = proposal_pairs.groupby(["candidate_id", "source_event_id"], sort=False)[
        pair_identity_fields
    ].nunique(dropna=False)
    if pair_identity_counts.gt(1).any().any():
        raise ValueError("one candidate event key maps to conflicting catalog identities")
    proposal_window_counts = proposal_pairs.groupby(
        ["candidate_id", "source_event_id"], sort=False
    )[["valid_from", "expires_at"]].nunique(dropna=False)
    if proposal_window_counts.gt(1).any().any():
        raise ValueError("one candidate event key maps to conflicting proposal windows")
    event_pairs = (
        proposal_pairs.groupby(["candidate_id", "source_event_id"], sort=False)
        .agg(
            idea_family=("idea_family", "first"),
            source_timeframe=("source_timeframe", "first"),
            direction=("direction", "first"),
            valid_from=("valid_from", "first"),
            expires_at=("expires_at", "first"),
            proposal_count=("proposal_id", "nunique"),
            proposal_entry_types=(
                "entry_type",
                lambda values: json.dumps(sorted({str(value) for value in values})),
            ),
        )
        .reset_index()
    )

    arm_reports: dict[str, Any] = {}
    linked_records: list[pd.DataFrame] = []
    for run in result_manifest["runs"]:
        run_id = str(run["run_id"])
        decision_artifact = next(
            (item for item in run["artifacts"] if item.get("role") == "decision_trace"), None
        )
        if decision_artifact is None:
            continue
        relative = str(decision_artifact["path"])
        decision_path = BASELINE.parent / relative
        actual_hash = _sha256(decision_path)
        if actual_hash != decision_artifact["sha256"]:
            raise ValueError(f"decision-trace checksum mismatch for {relative}")
        decisions = pd.read_csv(decision_path, usecols=list(DECISION_COLUMNS))
        decisions["trade_setup_candidate_id"] = pd.to_numeric(
            decisions["trade_setup_candidate_id"], errors="coerce"
        )
        identified = decisions[
            decisions["trade_setup_candidate_id"].gt(0)
            & decisions["trade_setup_eligible"].map(_truthy)
            & decisions["selection_valid"].map(_truthy)
            & decisions["trade_setup_source_event_identity_status"].eq("identified")
            & decisions["trade_setup_source_event_id"].notna()
            & decisions["trade_setup_source_event_id"].astype(str).ne("")
        ].copy()
        identified["candidate_id"] = identified["trade_setup_candidate_id"].astype("int64")
        linked = identified.merge(
            event_pairs,
            how="left",
            left_on=["candidate_id", "trade_setup_source_event_id"],
            right_on=["candidate_id", "source_event_id"],
            indicator=True,
            validate="many_to_one",
        )
        decision_times = pd.to_datetime(linked["decision_time"], utc=True, errors="raise")
        valid_from = pd.to_datetime(linked["valid_from"], utc=True, errors="coerce")
        expires_at = pd.to_datetime(linked["expires_at"], utc=True, errors="coerce")
        within_window = (
            linked["_merge"].eq("both")
            & decision_times.ge(valid_from)
            & decision_times.lt(expires_at)
        )
        linked["proposal_window_status"] = "no_proposal_event"
        linked.loc[linked["_merge"].eq("both"), "proposal_window_status"] = "outside_window"
        linked.loc[within_window, "proposal_window_status"] = "within_window"
        matched = linked[linked["_merge"].eq("both")].copy()
        inconsistent_catalog = (
            matched["selected_idea"].astype(str).ne(matched["idea_family"].astype(str))
            | matched["selected_timeframe"].astype(str).ne(matched["source_timeframe"].astype(str))
            | pd.to_numeric(matched["selected_direction"], errors="coerce").ne(
                pd.to_numeric(matched["direction"], errors="coerce")
            )
        )
        if inconsistent_catalog.any():
            raise ValueError("exactly linked decision identity disagrees with proposal catalog")
        linked.insert(0, "baseline_arm", run_id.rsplit("/", maxsplit=1)[-1])
        linked_records.append(linked)
        identity_counts = (
            decisions["trade_setup_source_event_identity_status"]
            .fillna("missing")
            .astype(str)
            .value_counts()
        )
        arm_reports[run_id] = {
            "decision_rows": int(len(decisions)),
            "selected_non_no_trade_rows": int(
                pd.to_numeric(decisions["trade_setup_candidate_id"], errors="coerce")
                .fillna(0)
                .gt(0)
                .sum()
            ),
            "identified_selected_candidate_rows": int(len(identified)),
            "unmatched_identified_rows": int(linked["_merge"].eq("left_only").sum()),
            "matched_identified_rows": int(len(matched)),
            "within_proposal_window_rows": int(within_window.sum()),
            "outside_proposal_window_rows": int(
                (matched["proposal_window_status"] != "within_window").sum()
            ),
            "matched_unique_candidate_events": int(
                matched[["candidate_id", "source_event_id"]].drop_duplicates().shape[0]
            ),
            "within_window_unique_candidate_events": int(
                matched.loc[within_window, ["candidate_id", "source_event_id"]]
                .drop_duplicates()
                .shape[0]
            ),
            "identity_status_counts": {
                str(key): int(value) for key, value in identity_counts.items()
            },
            "identity_version_counts": {
                str(key): int(value)
                for key, value in decisions["trade_setup_event_identity_version"]
                .fillna("missing")
                .astype(str)
                .value_counts()
                .items()
            },
            "decision_trace_sha256": actual_hash,
        }

    linked_frame = (
        pd.concat(linked_records, ignore_index=True)
        if linked_records
        else pd.DataFrame(
            columns=["baseline_arm", *DECISION_COLUMNS, "candidate_id", "source_event_id", "_merge"]
        )
    )
    matched_frame = linked_frame[linked_frame["_merge"].eq("both")].copy()
    unmatched_frame = linked_frame[linked_frame["_merge"].eq("left_only")].copy()
    window_frame = linked_frame[linked_frame["proposal_window_status"].eq("within_window")].copy()
    output_dir.mkdir(parents=True, exist_ok=False)
    links_path = output_dir / "matched_baseline_candidate_actions.csv"
    unmatched_path = output_dir / "unmatched_baseline_candidate_actions.csv"
    window_path = output_dir / "within_proposal_window_actions.csv"
    matched_frame.to_csv(links_path, index=False)
    unmatched_frame.to_csv(unmatched_path, index=False)
    window_frame.to_csv(window_path, index=False)
    matched_events = (
        matched_frame[["candidate_id", "source_event_id"]].drop_duplicates()
        if not matched_frame.empty
        else pd.DataFrame(columns=["candidate_id", "source_event_id"])
    )
    proposal_events = event_pairs[["candidate_id", "source_event_id"]].drop_duplicates()
    matched_proposal_events = proposal_events.merge(
        matched_events,
        how="inner",
        on=["candidate_id", "source_event_id"],
        validate="one_to_one",
    )
    within_window_events = window_frame[["candidate_id", "source_event_id"]].drop_duplicates()
    within_window_proposal_events = proposal_events.merge(
        within_window_events,
        how="inner",
        on=["candidate_id", "source_event_id"],
        validate="one_to_one",
    )
    summary: dict[str, Any] = {
        "schema_version": "candidate-action-event-linkage-v1",
        "status": "matched_development_baseline_traces_only",
        "claim_scope": "exact source-event overlap with selected matched-baseline setup actions",
        "does_not_establish": [
            "historical trained-PPO action linkage",
            "selection of a specific market/limit proposal or bracket by the policy",
            "account-state eligibility or portfolio contention",
            "realized economic value from the conditional outcomes",
        ],
        "candidate_proposal_manifest_sha256": _sha256(PROPOSALS / "proposal_ledger_manifest.json"),
        "candidate_proposal_parquet_sha256": _sha256(PROPOSALS / "candidate_proposals.parquet"),
        "matched_baseline_result_manifest_sha256": _sha256(result_manifest_path),
        "audit_source_sha256": {
            "scripts/research/analysis/evaluation/audit_candidate_action_linkage.py": _sha256(
                ROOT / "scripts/research/analysis/evaluation/audit_candidate_action_linkage.py"
            )
        },
        "proposal_rows": int(len(proposals)),
        "unique_proposal_candidate_events": int(len(proposal_events)),
        "unique_proposal_candidate_events_selected_in_any_baseline_arm": int(
            len(matched_proposal_events)
        ),
        "action_rows_within_proposal_validity_window": int(len(window_frame)),
        "unique_proposal_candidate_events_selected_within_validity_window": int(
            len(within_window_proposal_events)
        ),
        "baseline_arms": arm_reports,
        "matched_rows_csv_sha256": _sha256(links_path),
        "unmatched_action_rows": int(len(unmatched_frame)),
        "unmatched_rows_csv_sha256": _sha256(unmatched_path),
        "within_window_rows_csv_sha256": _sha256(window_path),
    }
    manifest_path = output_dir / "linkage_manifest.json"
    manifest_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    readme_path = output_dir / "README.md"
    readme_path.write_text(
        "# Candidate action linkage\n\n"
        "This audit joins statically eligible candidate proposal events to exact candidate ID and source-event IDs recorded in the matched development baseline decision traces. It also reports whether each decision timestamp falls inside the proposal event's recorded validity window. This is a temporal-overlap audit only: it does not identify a market/limit proposal chosen by the baseline action, link proposals to historical trained PPO rollouts, reconstruct account-state eligibility, or convert conditional outcomes into policy value.\n\n"
        "See `linkage_manifest.json` for input identities, per-arm counts, and claim limits. Event overlaps, unmatched decision rows, and within-window rows are in `matched_baseline_candidate_actions.csv`, `unmatched_baseline_candidate_actions.csv`, and `within_proposal_window_actions.csv`.\n",
        encoding="utf-8",
    )
    outputs = (links_path, unmatched_path, window_path, manifest_path, readme_path)
    (output_dir / "OUTPUT_SHA256SUMS").write_text(
        "".join(f"{_sha256(path)}  {path.name}\n" for path in outputs), encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output_dir = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir
    print(json.dumps(build_action_linkage(output_dir), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
