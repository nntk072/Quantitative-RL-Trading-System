#!/usr/bin/env python3
"""Build a monthly tick-side completeness table and figure from a quality profile."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from artifacts.atomic import write_json_atomic


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def monthly_tick_quote_rows(profile: dict[str, Any], profile_sha256: str) -> list[dict[str, Any]]:
    """Summarize missing required quote sides per tick file and source-wall month."""
    rows: list[dict[str, Any]] = []
    for record in profile.get("inputs", []):
        if record.get("kind") != "tick":
            continue
        role = str(record["source_role"])
        instrument = str(record["instrument"])
        for month, counts in sorted(
            record.get("quality_counts_by_period", {}).get("month", {}).items()
        ):
            denominator = int(counts.get("rows", 0))
            missing_bid = int(counts.get("missing_or_nonfinite_bid_rows", 0))
            missing_ask = int(counts.get("missing_or_nonfinite_ask_rows", 0))
            missing_both = int(counts.get("missing_or_nonfinite_bid_and_ask_rows", 0))
            missing_any = missing_bid + missing_ask - missing_both
            if (
                denominator <= 0
                or min(missing_bid, missing_ask, missing_both) < 0
                or max(missing_bid, missing_ask, missing_both) > denominator
                or missing_both > min(missing_bid, missing_ask)
                or missing_any < 0
                or missing_any > denominator
            ):
                raise ValueError(
                    f"invalid quote-side counts for {role}/{instrument}/{month}: "
                    f"rows={denominator}, missing_any={missing_any}"
                )
            rows.append(
                {
                    "source_role": role,
                    "instrument": instrument,
                    "source_wall_month": month,
                    "tick_rows": denominator,
                    "missing_bid_rows": missing_bid,
                    "missing_ask_rows": missing_ask,
                    "missing_both_sides_rows": missing_both,
                    "rows_with_any_missing_required_side": missing_any,
                    "missing_required_side_fraction": missing_any / denominator,
                    "profile_sha256": profile_sha256,
                }
            )
    return rows


def _write_csv_exclusive(path: Path, rows: list[dict[str, Any]]) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0]) if rows else []
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
            output.flush()
            os.fsync(output.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError as exc:
            raise FileExistsError(f"Refusing to overwrite {path}") from exc
    finally:
        temporary.unlink(missing_ok=True)


def _plot_monthly_tick_completeness(
    rows: list[dict[str, Any]],
    output: Path,
    *,
    profile_path: Path,
    profile_sha256: str,
) -> None:
    import matplotlib.pyplot as plt

    groups = sorted({(row["source_role"], row["instrument"]) for row in rows})
    if not groups:
        raise ValueError("the profile contains no monthly tick quality records")
    columns = min(2, len(groups))
    lines = (len(groups) + columns - 1) // columns
    figure, axes = plt.subplots(lines, columns, figsize=(13, 3.5 * lines), squeeze=False)
    try:
        for axis, (role, instrument) in zip(axes.flat, groups, strict=False):
            selected = [
                row
                for row in rows
                if row["source_role"] == role and row["instrument"] == instrument
            ]
            labels = [row["source_wall_month"] for row in selected]
            values = [100.0 * float(row["missing_required_side_fraction"]) for row in selected]
            axis.plot(labels, values, marker="o", linewidth=1.4)
            axis.set_title(f"{role} / {instrument} tick export")
            axis.set_xlabel("Parsed source-wall month")
            axis.tick_params(axis="x", rotation=45)
            axis.grid(True, alpha=0.25)
        for axis in axes.flat[len(groups) :]:
            axis.remove()
        figure.suptitle(
            "Local tick quote-side completeness\n"
            f"Profile: {profile_path.name} | SHA-256 prefix: {profile_sha256[:12]}\n"
            "Monthly labels use parsed wall-clock time; no timezone or session conversion."
        )
        figure.supylabel("Rows missing at least one required quote side (%)", x=0.01)
        figure.tight_layout(rect=(0.06, 0, 1, 0.88))
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists():
            raise FileExistsError(f"Refusing to overwrite {output}")
        figure.savefig(output, dpi=160, bbox_inches="tight")
    finally:
        plt.close(figure)


def build_quality_outputs(profile_path: Path, csv_path: Path, figure_path: Path) -> int:
    profile_bytes = profile_path.read_bytes()
    profile = json.loads(profile_bytes)
    if profile.get("schema") != "qrl.market_data_quality_profile.v2":
        raise ValueError(f"unsupported quality profile schema: {profile.get('schema')}")
    profile_hash = hashlib.sha256(profile_bytes).hexdigest()
    rows = monthly_tick_quote_rows(profile, profile_hash)
    if not rows:
        raise ValueError("the profile contains no tick files with monthly quality counts")
    provenance_path = csv_path.with_suffix(".provenance.json")
    for output in (csv_path, figure_path, provenance_path):
        if output.exists():
            raise FileExistsError(f"Refusing to overwrite {output}")
    _write_csv_exclusive(csv_path, rows)
    _plot_monthly_tick_completeness(
        rows,
        figure_path,
        profile_path=profile_path,
        profile_sha256=profile_hash,
    )
    return len(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True, type=Path, help="v2 market quality JSON")
    parser.add_argument("--csv-out", required=True, type=Path, help="new monthly summary CSV")
    parser.add_argument("--figure-out", required=True, type=Path, help="new PNG output")
    args = parser.parse_args()
    count = build_quality_outputs(args.profile, args.csv_out, args.figure_out)
    provenance_path = args.csv_out.with_suffix(".provenance.json")
    write_json_atomic(
        provenance_path,
        {
            "schema": "qrl.monthly_tick_quote_quality_figure.v2",
            "generator_path": str(Path(__file__).resolve()),
            "generator_sha256": _sha256(Path(__file__).resolve()),
            "profile_path": str(args.profile),
            "profile_sha256": _sha256(args.profile),
            "csv_path": str(args.csv_out),
            "csv_sha256": _sha256(args.csv_out),
            "figure_path": str(args.figure_out),
            "figure_sha256": _sha256(args.figure_out),
            "monthly_records": count,
            "period_basis": "parsed source wall-clock month; no timezone/session conversion",
        },
        default=None,
    )
    print(json.dumps({"monthly_records": count, "figure": str(args.figure_out)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
