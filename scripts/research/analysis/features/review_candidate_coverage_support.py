"""Add an explicit descriptive support review to the 108-candidate census.

Support is based on the census's contiguous active-mask identity episodes, not
ground-truth logical events or independent samples. Existing census outputs
remain immutable; this utility writes review tables alongside them.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
PACKET = Path("evidence/research/trade_setup_opportunity_census")
LOW_EPISODE_SUPPORT_CUTOFF = 10


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty review table: {path}")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def support_state(row: dict[str, str]) -> str:
    if row["support_status"] != "supported":
        return "unsupported_by_config"
    episodes = int(row["episode_starts"])
    if episodes < LOW_EPISODE_SUPPORT_CUTOFF:
        return "low_episode_support"
    return "supported_episode_coverage"


def export(root: Path, packet: Path) -> None:
    source_summary = packet / "candidate_summary.csv"
    source_month = packet / "candidate_month_regime.csv"
    source_horizon = packet / "candidate_horizon_coverage.csv"
    summary_fields, summaries = read_csv(source_summary)
    _, monthly = read_csv(source_month)
    _, horizons = read_csv(source_horizon)
    if len(summaries) != 108 or len(monthly) != 5616 or len(horizons) != 648:
        raise ValueError(
            "candidate census table row counts do not match the declared 108-candidate coverage"
        )

    review_by_id: dict[str, str] = {}
    review_rows: list[dict[str, Any]] = []
    for row in summaries:
        state = support_state(row)
        review_by_id[row["candidate_id"]] = state
        review_rows.append(
            {
                **{key: row[key] for key in summary_fields},
                "support_review_status": state,
                "support_review_basis": (
                    "unsupported by selected profile config"
                    if state == "unsupported_by_config"
                    else f"fewer than {LOW_EPISODE_SUPPORT_CUTOFF} contiguous active-mask identity episodes; not a logical-event count"
                    if state == "low_episode_support"
                    else f"at least {LOW_EPISODE_SUPPORT_CUTOFF} contiguous active-mask identity episodes; not a logical-event count"
                ),
            }
        )

    monthly_rows = [
        {
            **row,
            "support_review_status": review_by_id[row["candidate_id"]],
            "support_review_basis": "candidate-level descriptive episode support; see candidate_support_review.csv",
        }
        for row in monthly
    ]
    horizon_rows = [
        {
            **row,
            "support_review_status": review_by_id[row["candidate_id"]],
            "support_review_basis": "candidate-level descriptive episode support; see candidate_support_review.csv",
        }
        for row in horizons
    ]

    outputs = {
        "candidate_support_review.csv": review_rows,
        "candidate_month_regime_support_review.csv": monthly_rows,
        "candidate_horizon_support_review.csv": horizon_rows,
    }
    for name, rows in outputs.items():
        write_csv(packet / name, rows)

    counts: dict[str, int] = {}
    for row in review_rows:
        state = str(row["support_review_status"])
        counts[state] = counts.get(state, 0) + 1
    provenance = {
        "schema": "qrl.candidate_support_review.v1",
        "generator_path": "scripts/research/analysis/features/review_candidate_coverage_support.py",
        "generator_sha256": sha256(Path(__file__).resolve()),
        "input_sha256": {
            str(source_summary.relative_to(root)): sha256(source_summary),
            str(source_month.relative_to(root)): sha256(source_month),
            str(source_horizon.relative_to(root)): sha256(source_horizon),
        },
        "support_rule": {
            "cutoff_episode_starts": LOW_EPISODE_SUPPORT_CUTOFF,
            "low_episode_support": f"supported candidate with fewer than {LOW_EPISODE_SUPPORT_CUTOFF} contiguous active-mask identity episodes",
            "meaning": "descriptive support flag only; episodes are not ground-truth logical events or independent samples",
        },
        "candidate_status_counts": counts,
        "outputs": {
            name: {"sha256": sha256(packet / name), "rows": len(rows)}
            for name, rows in outputs.items()
        },
    }
    provenance_path = packet / "candidate_support_review_provenance.json"
    provenance_path.write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    readme = packet / "README.md"
    base = (
        readme.read_text(encoding="utf-8").split("\n## Descriptive support review\n", 1)[0].rstrip()
    )
    readme.write_text(
        base
        + "\n\n## Descriptive support review\n\n"
        + f"The review tables mark all 108 catalog combinations as `unsupported_by_config`, `low_episode_support`, or `supported_episode_coverage`. `low_episode_support` means fewer than {LOW_EPISODE_SUPPORT_CUTOFF} contiguous active-mask identity episodes in this selected training profile. This is a descriptive review threshold only: these episodes are not ground-truth logical events or independent samples. The month/regime and horizon review tables preserve the original per-cell rows and repeat the candidate-level review status. See `candidate_support_review_provenance.json` for source and output hashes.\n",
        encoding="utf-8",
    )

    checksum_files = sorted(
        path for path in packet.iterdir() if path.is_file() and path.name != "OUTPUT_SHA256SUMS"
    )
    (packet / "OUTPUT_SHA256SUMS").write_text(
        "\n".join(f"{sha256(path)}  {path.name}" for path in checksum_files) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "candidate_status_counts": counts,
                "monthly_rows": len(monthly_rows),
                "horizon_rows": len(horizon_rows),
                "checksummed_files": len(checksum_files),
            },
            indent=2,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--packet", type=Path, default=PACKET)
    args = parser.parse_args()
    root = args.root.resolve()
    packet = args.packet if args.packet.is_absolute() else root / args.packet
    export(root, packet)


if __name__ == "__main__":
    main()
