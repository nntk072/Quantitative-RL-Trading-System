#!/usr/bin/env python3
"""Summarize verified candidate-outcome data dispositions by proposal type."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

from configuration.paths import repository_root

ROOT = repository_root(__file__)
DEFAULT_PROPOSALS = ROOT / "evidence/research/candidate_proposals"
DEFAULT_OUTCOMES = ROOT / "evidence/research/candidate_outcomes"

STATUS_LABELS = {
    "filled_resolved": "Filled and resolved",
    "unfilled_expired": "Unfilled and expired",
    "censored_order_horizon": "Censored order horizon",
    "censored_exit_horizon": "Censored exit horizon",
    "unresolved_data": "Unresolved data",
}
STATUS_COLORS = {
    "filled_resolved": "#2a6f97",
    "unfilled_expired": "#7f8c8d",
    "censored_order_horizon": "#e9c46a",
    "censored_exit_horizon": "#f4a261",
    "unresolved_data": "#d1495b",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_inputs(proposal_dir: Path, outcome_dir: Path) -> tuple[Path, Path]:
    independent_report = outcome_dir / "independent_verification.json"
    outcome_manifest_path = outcome_dir / "outcome_manifest.json"
    if not independent_report.is_file() or not outcome_manifest_path.is_file():
        raise ValueError("independent outcome verification must pass before plotting")
    proposal_path = proposal_dir / "candidate_proposals.parquet"
    outcome_path = outcome_dir / "conditional_outcomes.parquet"
    if not proposal_path.is_file() or not outcome_path.is_file():
        raise FileNotFoundError("candidate proposal or outcome parquet is missing")
    verification = json.loads(independent_report.read_text(encoding="utf-8"))
    verifier_source = (
        ROOT / "scripts/research/analysis/evaluation/verify_candidate_proposal_outcomes.py"
    )
    if verification.get("status") != "verified_training_conditional_outcome_packet":
        raise ValueError("candidate outcome packet has no passing independent verification")
    if verification.get("outcome_manifest_sha256") != _sha256(outcome_manifest_path):
        raise ValueError("independent verification references a different outcome manifest")
    if verification.get("outcome_parquet_sha256") != _sha256(outcome_path):
        raise ValueError("independent verification references a different outcome parquet")
    if verification.get("source_sha256", {}).get(
        "scripts/research/analysis/evaluation/verify_candidate_proposal_outcomes.py"
    ) != _sha256(verifier_source):
        raise ValueError("independent verification was produced by a different verifier source")
    return proposal_path, outcome_path


def _update_packet_checksums(outcome_dir: Path, output_paths: tuple[Path, ...]) -> None:
    checksum_path = outcome_dir / "OUTPUT_SHA256SUMS"
    current: dict[str, str] = {}
    replaced_names = {path.name for path in output_paths}
    if checksum_path.is_file():
        for line in checksum_path.read_text(encoding="utf-8").splitlines():
            expected, name = line.split(maxsplit=1)
            name = name.strip()
            if name in replaced_names:
                continue
            if _sha256(outcome_dir / name) != expected:
                raise ValueError(f"existing outcome-packet checksum mismatch: {name}")
            current[name] = expected
    for path in output_paths:
        current[path.name] = _sha256(path)
    checksum_path.write_text(
        "".join(f"{digest}  {name}\n" for name, digest in sorted(current.items())),
        encoding="utf-8",
    )


def build_outcome_coverage_figure(*, proposal_dir: Path, outcome_dir: Path) -> dict[str, Any]:
    proposal_path, outcome_path = _verify_inputs(proposal_dir, outcome_dir)
    outcome_manifest_path = outcome_dir / "outcome_manifest.json"
    outcome_manifest = json.loads(outcome_manifest_path.read_text(encoding="utf-8"))
    if outcome_manifest["status"] != "training_conditional_outcomes_with_coverage_dispositions":
        raise ValueError("outcome packet is not the full training replay")
    if _sha256(proposal_path) != outcome_manifest["proposal_parquet_sha256"]:
        raise ValueError("outcome manifest proposal parquet hash does not verify")
    if _sha256(outcome_path) != outcome_manifest["output_sha256"]["conditional_outcomes.parquet"]:
        raise ValueError("outcome manifest outcome parquet hash does not verify")

    proposal_columns = [
        "proposal_id",
        "candidate_id",
        "idea_family",
        "source_timeframe",
        "direction",
        "signal_confirmed_at",
        "entry_type",
    ]
    proposals = pd.read_parquet(proposal_path, columns=proposal_columns)
    outcomes = pd.read_parquet(outcome_path, columns=["proposal_id", "status", "unresolved_reason"])
    if proposals["proposal_id"].isna().any() or not proposals["proposal_id"].is_unique:
        raise ValueError("proposal IDs must be present and unique")
    joined = outcomes.merge(
        proposals,
        how="left",
        on="proposal_id",
        validate="many_to_one",
        indicator=True,
    )
    if not joined["_merge"].eq("both").all():
        raise ValueError("outcome rows refer to unknown candidate proposals")
    joined["signal_month"] = pd.to_datetime(
        joined["signal_confirmed_at"], format="ISO8601", utc=True, errors="raise"
    ).dt.strftime("%Y-%m")
    joined["direction_label"] = joined["direction"].map({1: "long", -1: "short"})
    if joined["direction_label"].isna().any():
        raise ValueError("proposal directions must be -1 or +1")
    joined["candidate_label"] = (
        joined["idea_family"].astype(str)
        + "/"
        + joined["source_timeframe"].astype(str)
        + "/"
        + joined["direction_label"].astype(str)
    )
    status_order = [status for status in STATUS_LABELS if status in set(joined["status"])]
    status_order.extend(sorted(set(joined["status"]) - set(status_order)))
    entry_types = sorted(joined["entry_type"].astype(str).unique())
    counts = (
        joined.groupby(["entry_type", "status"], observed=True)
        .size()
        .rename("outcome_rows")
        .reset_index()
    )
    proposal_counts = proposals.groupby("entry_type", observed=True).size().rename("proposal_count")
    outcome_counts = (
        joined.groupby("entry_type", observed=True).size().rename("conditional_outcome_rows")
    )
    denominators = pd.concat([proposal_counts, outcome_counts], axis=1)
    table = counts.join(denominators, on="entry_type")
    table["fraction_within_entry_type"] = table["outcome_rows"] / table["conditional_outcome_rows"]
    table["status_label"] = table["status"].map(STATUS_LABELS).fillna(table["status"])
    table = table[
        [
            "entry_type",
            "status",
            "status_label",
            "proposal_count",
            "conditional_outcome_rows",
            "outcome_rows",
            "fraction_within_entry_type",
        ]
    ].sort_values(["entry_type", "status"], kind="stable")

    candidate_dimensions = [
        "candidate_id",
        "candidate_label",
        "idea_family",
        "source_timeframe",
        "direction",
        "signal_month",
        "entry_type",
    ]
    candidate_status_counts = (
        joined.groupby([*candidate_dimensions, "status"], observed=True)
        .size()
        .rename("outcome_rows")
        .reset_index()
    )
    candidate_proposal_counts = (
        proposals.assign(
            signal_month=pd.to_datetime(
                proposals["signal_confirmed_at"], format="ISO8601", utc=True, errors="raise"
            ).dt.strftime("%Y-%m"),
            direction_label=proposals["direction"].map({1: "long", -1: "short"}),
        )
        .assign(
            candidate_label=lambda frame: (
                frame["idea_family"].astype(str)
                + "/"
                + frame["source_timeframe"].astype(str)
                + "/"
                + frame["direction_label"].astype(str)
            )
        )
        .groupby(candidate_dimensions, observed=True)
        .size()
        .rename("proposal_count")
    )
    candidate_outcome_counts = (
        joined.groupby(candidate_dimensions, observed=True)
        .size()
        .rename("conditional_outcome_rows")
    )
    candidate_denominators = pd.concat(
        [candidate_proposal_counts, candidate_outcome_counts], axis=1
    )
    candidate_table = candidate_status_counts.join(candidate_denominators, on=candidate_dimensions)
    candidate_table["fraction_within_candidate_month_entry_type"] = (
        candidate_table["outcome_rows"] / candidate_table["conditional_outcome_rows"]
    )
    candidate_table["status_label"] = (
        candidate_table["status"].map(STATUS_LABELS).fillna(candidate_table["status"])
    )
    candidate_table = candidate_table[
        [
            *candidate_dimensions,
            "status",
            "status_label",
            "proposal_count",
            "conditional_outcome_rows",
            "outcome_rows",
            "fraction_within_candidate_month_entry_type",
        ]
    ].sort_values(["candidate_id", "signal_month", "entry_type", "status"], kind="stable")

    monthly_status_counts = (
        joined.groupby(["signal_month", "status"], observed=True)
        .size()
        .rename("outcome_rows")
        .reset_index()
    )
    monthly_proposal_counts = (
        proposals.assign(
            signal_month=pd.to_datetime(
                proposals["signal_confirmed_at"], format="ISO8601", utc=True, errors="raise"
            ).dt.strftime("%Y-%m")
        )
        .groupby("signal_month", observed=True)
        .size()
        .rename("proposal_count")
    )
    monthly_outcome_counts = (
        joined.groupby("signal_month", observed=True).size().rename("conditional_outcome_rows")
    )
    monthly_denominators = pd.concat([monthly_proposal_counts, monthly_outcome_counts], axis=1)
    monthly_table = monthly_status_counts.join(monthly_denominators, on="signal_month")
    monthly_table["fraction_within_month"] = (
        monthly_table["outcome_rows"] / monthly_table["conditional_outcome_rows"]
    )
    monthly_table["status_label"] = (
        monthly_table["status"].map(STATUS_LABELS).fillna(monthly_table["status"])
    )
    monthly_table = monthly_table[
        [
            "signal_month",
            "status",
            "status_label",
            "proposal_count",
            "conditional_outcome_rows",
            "outcome_rows",
            "fraction_within_month",
        ]
    ].sort_values(["signal_month", "status"], kind="stable")
    unresolved = joined[joined["status"].eq("unresolved_data")].copy()
    if unresolved["unresolved_reason"].isna().any():
        raise ValueError("every unresolved outcome row must have a reason")
    unresolved_reason_counts = (
        unresolved.groupby(["signal_month", "entry_type", "unresolved_reason"], observed=True)
        .size()
        .rename("reason_outcome_rows")
    )
    unresolved_denominators = joined.groupby(["signal_month", "entry_type"], observed=True).agg(
        conditional_outcome_rows=("status", "size"),
        unresolved_outcome_rows=("status", lambda values: int(values.eq("unresolved_data").sum())),
    )
    month_entry_proposals = (
        proposals.assign(
            signal_month=pd.to_datetime(
                proposals["signal_confirmed_at"], format="ISO8601", utc=True, errors="raise"
            ).dt.strftime("%Y-%m")
        )
        .groupby(["signal_month", "entry_type"], observed=True)
        .size()
        .rename("proposal_count")
    )
    reason_table = unresolved_reason_counts.reset_index().join(
        unresolved_denominators, on=["signal_month", "entry_type"]
    )
    reason_table = reason_table.join(month_entry_proposals, on=["signal_month", "entry_type"])
    reason_table["reason_outcome_rows"] = reason_table["reason_outcome_rows"].astype("int64")
    reason_table["fraction_of_unresolved"] = (
        reason_table["reason_outcome_rows"] / reason_table["unresolved_outcome_rows"]
    )
    reason_table["fraction_of_all_conditional_rows"] = (
        reason_table["reason_outcome_rows"] / reason_table["conditional_outcome_rows"]
    )
    reason_table = reason_table.sort_values(
        ["signal_month", "entry_type", "reason_outcome_rows"],
        ascending=[True, True, False],
        kind="stable",
    )

    output_dir = outcome_dir
    csv_path = output_dir / "outcome_disposition_by_entry_type.csv"
    figure_path = output_dir / "outcome_disposition_by_entry_type.png"
    candidate_csv_path = output_dir / "outcome_disposition_by_candidate_month.csv"
    candidate_figure_path = output_dir / "unresolved_fraction_by_candidate_month.png"
    monthly_csv_path = output_dir / "outcome_disposition_by_month.csv"
    monthly_figure_path = output_dir / "outcome_disposition_by_month.png"
    reason_csv_path = output_dir / "outcome_unresolved_reasons_by_month.csv"
    summary_path = output_dir / "outcome_disposition_summary.json"
    table.to_csv(csv_path, index=False)
    candidate_table.to_csv(candidate_csv_path, index=False)
    monthly_table.to_csv(monthly_csv_path, index=False)
    reason_table.to_csv(reason_csv_path, index=False)

    fig, ax = plt.subplots(figsize=(10.5, 5.8), layout="constrained")
    left = [0.0] * len(entry_types)
    for status in status_order:
        values = []
        counts_for_status = []
        for entry_type in entry_types:
            match = table[(table["entry_type"] == entry_type) & (table["status"] == status)]
            fraction = (
                float(match["fraction_within_entry_type"].iloc[0]) if not match.empty else 0.0
            )
            count = int(match["outcome_rows"].iloc[0]) if not match.empty else 0
            values.append(fraction)
            counts_for_status.append(count)
        ax.barh(
            entry_types,
            values,
            left=left,
            color=STATUS_COLORS.get(status, "#6c757d"),
            label=STATUS_LABELS.get(status, status.replace("_", " ").title()),
            edgecolor="white",
            linewidth=0.6,
        )
        for position, (fraction, count, origin) in enumerate(
            zip(values, counts_for_status, left, strict=True)
        ):
            if fraction >= 0.07:
                label_color = (
                    "white" if status in {"filled_resolved", "unresolved_data"} else "#202020"
                )
                ax.text(
                    origin + fraction / 2,
                    position,
                    f"{fraction:.0%}\n{count:,}",
                    ha="center",
                    va="center",
                    color=label_color,
                    fontsize=8,
                )
        left = [origin + value for origin, value in zip(left, values, strict=True)]

    ax.set_xlim(0, 1)
    ax.set_xlabel("Share of conditional bracket rows within proposal type")
    ax.set_ylabel("Proposal type")
    ax.set_title("Candidate outcome data dispositions")
    ax.xaxis.set_major_formatter(lambda value, _position: f"{value:.0%}")
    ax.grid(axis="x", alpha=0.25)
    ax.set_axisbelow(True)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=3, frameon=False)
    fig.text(
        0.01,
        0.005,
        "Training-only conditional bracket combinations; rows are not independent trades or policy outcomes.",
        fontsize=8,
        color="#444444",
    )
    fig.savefig(figure_path, dpi=220, bbox_inches="tight")
    plt.close(fig)

    months = sorted(joined["signal_month"].unique())
    candidates = sorted(joined["candidate_label"].unique())
    candidate_status = (
        joined.groupby(["candidate_label", "signal_month", "status"], observed=True)
        .size()
        .unstack("status", fill_value=0)
    )
    unresolved_fraction = pd.DataFrame(index=candidates, columns=months, dtype=float)
    for candidate in candidates:
        for month in months:
            row = (
                candidate_status.loc[(candidate, month)]
                if (candidate, month) in candidate_status.index
                else None
            )
            if row is None:
                continue
            total = int(row.sum())
            unresolved_fraction.loc[candidate, month] = (
                float(row.get("unresolved_data", 0)) / total if total else float("nan")
            )
    heat_values = unresolved_fraction.to_numpy(dtype=float)
    cmap = plt.get_cmap("YlOrRd").copy()
    cmap.set_bad(color="#eeeeee")
    heat_fig, heat_ax = plt.subplots(
        figsize=(max(11.0, 0.8 * len(months)), max(7.5, 0.35 * len(candidates))),
        layout="constrained",
    )
    image = heat_ax.imshow(heat_values, aspect="auto", cmap=cmap, vmin=0.0, vmax=1.0)
    heat_ax.set_xticks(range(len(months)), labels=months, rotation=45, ha="right")
    heat_ax.set_yticks(range(len(candidates)), labels=candidates)
    heat_ax.set_xlabel("UTC month of signal confirmation")
    heat_ax.set_ylabel("Candidate family / timeframe / direction")
    heat_ax.set_title("Unresolved local-data share by candidate and signal month")
    for row_index, candidate in enumerate(candidates):
        for column_index, month in enumerate(months):
            value = unresolved_fraction.loc[candidate, month]
            if pd.notna(value):
                heat_ax.text(
                    column_index,
                    row_index,
                    f"{value:.0%}",
                    ha="center",
                    va="center",
                    fontsize=6.5,
                    color="#202020" if value < 0.58 else "white",
                )
    colorbar = heat_fig.colorbar(image, ax=heat_ax, fraction=0.025, pad=0.02)
    colorbar.set_label("Share of conditional bracket rows marked unresolved")
    heat_fig.text(
        0.01,
        0.002,
        "Blank cells have no proposals. Rows are conditional bracket combinations, not trades or policy outcomes.",
        fontsize=8,
        color="#444444",
    )
    heat_fig.savefig(candidate_figure_path, dpi=220, bbox_inches="tight")
    plt.close(heat_fig)

    month_order = sorted(joined["signal_month"].unique())
    monthly_left = [0.0] * len(month_order)
    month_fig, month_ax = plt.subplots(figsize=(12, 5.7), layout="constrained")
    for status in status_order:
        monthly_values: list[float] = []
        monthly_counts_for_status: list[int] = []
        for month in month_order:
            match = monthly_table[
                (monthly_table["signal_month"] == month) & (monthly_table["status"] == status)
            ]
            fraction = float(match["fraction_within_month"].iloc[0]) if not match.empty else 0.0
            count = int(match["outcome_rows"].iloc[0]) if not match.empty else 0
            monthly_values.append(fraction)
            monthly_counts_for_status.append(count)
        month_ax.bar(
            month_order,
            monthly_values,
            bottom=monthly_left,
            color=STATUS_COLORS.get(status, "#6c757d"),
            label=STATUS_LABELS.get(status, status.replace("_", " ").title()),
            edgecolor="white",
            linewidth=0.6,
        )
        for position, (fraction, count, origin) in enumerate(
            zip(monthly_values, monthly_counts_for_status, monthly_left, strict=True)
        ):
            if fraction >= 0.09:
                month_ax.text(
                    position,
                    origin + fraction / 2,
                    f"{fraction:.0%}\n{count:,}",
                    ha="center",
                    va="center",
                    color="white"
                    if status in {"filled_resolved", "unresolved_data"}
                    else "#202020",
                    fontsize=7,
                )
        monthly_left = [origin + value for origin, value in zip(monthly_left, values, strict=True)]
    month_ax.set_ylim(0, 1)
    month_ax.set_ylabel("Share of conditional bracket rows")
    month_ax.set_xlabel("UTC month of signal confirmation")
    month_ax.set_title("Candidate outcome data dispositions by signal month")
    month_ax.yaxis.set_major_formatter(lambda value, _position: f"{value:.0%}")
    month_ax.tick_params(axis="x", rotation=45)
    month_ax.grid(axis="y", alpha=0.25)
    month_ax.set_axisbelow(True)
    month_ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.24), ncol=3, frameon=False)
    month_fig.text(
        0.01,
        0.002,
        "Training-only conditional bracket combinations; monthly counts are in the accompanying table.",
        fontsize=8,
        color="#444444",
    )
    month_fig.savefig(monthly_figure_path, dpi=220, bbox_inches="tight")
    plt.close(month_fig)

    plot_outputs = (
        csv_path,
        figure_path,
        candidate_csv_path,
        candidate_figure_path,
        monthly_csv_path,
        monthly_figure_path,
        reason_csv_path,
    )
    report = {
        "schema_version": "candidate-outcome-disposition-summary-v1",
        "proposal_rows": int(len(proposals)),
        "conditional_outcome_rows": int(len(outcomes)),
        "entry_types": entry_types,
        "candidate_month_cells": int(unresolved_fraction.notna().to_numpy().sum()),
        "candidate_count": int(len(candidates)),
        "signal_months": months,
        "monthly_status_counts": {
            str(month): {
                str(row.status): int(row.outcome_rows)
                for row in monthly_table[monthly_table["signal_month"] == month].itertuples(
                    index=False
                )
            }
            for month in month_order
        },
        "unresolved_reason_counts_by_month": {
            str(month): {
                str(reason): int(count)
                for reason, count in unresolved.loc[
                    unresolved["signal_month"].eq(month), "unresolved_reason"
                ]
                .value_counts()
                .items()
            }
            for month in month_order
        },
        "status_counts_by_entry_type": {
            str(entry_type): {
                str(row.status): int(row.outcome_rows)
                for row in table[table["entry_type"] == entry_type].itertuples(index=False)
            }
            for entry_type in entry_types
        },
        "output_sha256": {path.name: _sha256(path) for path in plot_outputs},
        "plot_script_sha256": _sha256(Path(__file__).resolve()),
    }
    summary_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    outputs = (*plot_outputs, summary_path)
    _update_packet_checksums(output_dir, outputs)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proposal-dir", type=Path, default=DEFAULT_PROPOSALS)
    parser.add_argument("--outcome-dir", type=Path, default=DEFAULT_OUTCOMES)
    args = parser.parse_args()
    proposal_dir = (
        args.proposal_dir if args.proposal_dir.is_absolute() else ROOT / args.proposal_dir
    )
    outcome_dir = args.outcome_dir if args.outcome_dir.is_absolute() else ROOT / args.outcome_dir
    print(build_outcome_coverage_figure(proposal_dir=proposal_dir, outcome_dir=outcome_dir))


if __name__ == "__main__":
    main()
