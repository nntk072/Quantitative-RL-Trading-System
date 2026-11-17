#!/usr/bin/env python3
"""Join local tick-quote coverage to candidate proposal execution intervals."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from configuration.configuration_loader import load_config
from configuration.paths import repository_root

ROOT = repository_root(__file__)
DEFAULT_CONFIG = ROOT / "config/base/default.yaml"
DEFAULT_PROPOSALS = ROOT / "evidence/research/candidate_proposals"
DEFAULT_COVERAGE = ROOT / "evidence/research/tick_quote_coverage"
DEFAULT_OUTPUT = ROOT / "evidence/research/candidate_outcome_coverage"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _wall_clock(value: str, timezone: str) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tz is None:
        raise ValueError("proposal timestamps must be timezone-aware")
    return timestamp.tz_convert(timezone).tz_localize(None)


def _verify_packet(packet: Path) -> None:
    for line in (packet / "OUTPUT_SHA256SUMS").read_text(encoding="utf-8").splitlines():
        expected, name = line.split(maxsplit=1)
        if _sha256(packet / name.strip()) != expected:
            raise ValueError(f"candidate proposal packet checksum mismatch: {name}")


def build_candidate_quote_coverage(
    *, config_path: Path, proposal_dir: Path, coverage_dir: Path, output_dir: Path
) -> dict[str, Any]:
    _verify_packet(proposal_dir)
    _verify_packet(coverage_dir)
    cfg = load_config(config_path=config_path)
    timezone = str(cfg.data.tz)
    cutoff = pd.Timestamp(str(cfg.data.split.train_end)) + pd.Timedelta(days=1)
    minute = pd.read_csv(coverage_dir / "minute_quote_coverage.csv", parse_dates=[0])
    minute_index = pd.DatetimeIndex(minute.iloc[:, 0])
    if not minute_index.is_unique or not minute_index.is_monotonic_increasing:
        raise ValueError("minute quote coverage must have a sorted unique index")
    coverage_values = minute["quote_complete"].astype(bool).to_numpy()
    coverage_by_minute = pd.Series(coverage_values, index=minute_index)
    proposal_path = proposal_dir / "candidate_proposals.parquet"
    proposals = pd.read_parquet(proposal_path)
    required = {
        "proposal_id",
        "entry_type",
        "eligible_action_fill_time",
        "expires_at",
        "session_close_time",
    }
    missing = required.difference(proposals.columns)
    if missing:
        raise ValueError(f"candidate proposal packet lacks interval fields: {sorted(missing)}")

    records: list[dict[str, Any]] = []
    for row in proposals.itertuples(index=False):
        start = _wall_clock(str(row.eligible_action_fill_time), timezone).floor("min")
        expiry = _wall_clock(str(row.expires_at), timezone)
        close = _wall_clock(str(row.session_close_time), timezone)
        if row.entry_type == "market":
            # A market order does not remain pending through the proposal TTL.
            # Require only its eligible action-fill minute in this conservative
            # minute-level census; the replay still applies exact tick latency.
            end = min(start + pd.Timedelta(minutes=1), close, cutoff)
        else:
            # A passive order's entire observable life must be covered before a
            # no-touch expiry can be distinguished from an unobserved interval.
            end = min(expiry, close, cutoff)
        end_minute = end.ceil("min")
        expected_index = pd.date_range(start, end_minute, freq="min", inclusive="left")
        first_incomplete: pd.Timestamp | None
        if expected_index.empty:
            complete = False
            missing_minutes = 0
            incomplete_minutes = 0
            first_incomplete = start
        else:
            indexer = coverage_by_minute.index.get_indexer(expected_index)
            missing_minutes = int((indexer < 0).sum())
            observed = coverage_by_minute.reindex(expected_index, fill_value=False).to_numpy(
                dtype=bool
            )
            incomplete_minutes = int((~observed).sum())
            complete = incomplete_minutes == 0
            first_incomplete = expected_index[int((~observed).argmax())] if not complete else None
        records.append(
            {
                "proposal_id": row.proposal_id,
                "entry_type": row.entry_type,
                "coverage_start_source_wall_clock": start.isoformat(),
                "coverage_end_source_wall_clock_exclusive": end.isoformat(),
                "expected_quote_minutes": int(len(expected_index)),
                "missing_quote_minutes": missing_minutes,
                "incomplete_quote_minutes": incomplete_minutes,
                "quote_complete_through_order_disposition": complete,
                "first_incomplete_source_wall_clock": (
                    first_incomplete.isoformat() if first_incomplete is not None else ""
                ),
            }
        )
    intervals = pd.DataFrame.from_records(records)
    output_dir.mkdir(parents=True, exist_ok=False)
    interval_path = output_dir / "proposal_interval_coverage.csv"
    intervals.to_csv(interval_path, index=False)
    summary_by_entry: dict[str, dict[str, int]] = {}
    for entry_type, group in intervals.groupby("entry_type", sort=True):
        summary_by_entry[str(entry_type)] = {
            "proposal_count": int(len(group)),
            "quote_complete_through_order_disposition": int(
                group["quote_complete_through_order_disposition"].sum()
            ),
            "incomplete_or_missing_quote_intervals": int(
                (~group["quote_complete_through_order_disposition"]).sum()
            ),
            "total_expected_quote_minutes": int(group["expected_quote_minutes"].sum()),
            "total_missing_quote_minutes": int(group["missing_quote_minutes"].sum()),
            "total_incomplete_quote_minutes": int(group["incomplete_quote_minutes"].sum()),
        }
    summary: dict[str, Any] = {
        "schema_version": "candidate-proposal-quote-coverage-v1",
        "status": "proposal_interval_coverage_audited",
        "timezone_conversion": f"proposal UTC timestamps converted to configured fixed-offset {timezone} to match raw source wall-clock",
        "coverage_rule": "For market proposals, the eligible action-fill minute must be present and quote-complete. For pending limits, every minute from eligible fill through the earlier of expiry, session close, and training cutoff must be present and quote-complete before a no-touch expiry can be labeled. This is a conservative local-source consistency rule, not proof of exchange-tape completeness.",
        "source_sha256": {
            "scripts/research/analysis/evaluation/audit_candidate_quote_coverage.py": _sha256(
                ROOT / "scripts/research/analysis/evaluation/audit_candidate_quote_coverage.py"
            ),
            str(config_path.resolve().relative_to(ROOT)): _sha256(config_path.resolve()),
        },
        "proposal_packet_sha256": _sha256(proposal_path),
        "coverage_packet_manifest_sha256": _sha256(coverage_dir / "coverage_manifest.json"),
        "proposal_count": int(len(proposals)),
        "by_entry_type": summary_by_entry,
        "interval_csv_sha256": _sha256(interval_path),
    }
    manifest_path = output_dir / "coverage_manifest.json"
    manifest_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    readme_path = output_dir / "README.md"
    readme_path.write_text(
        "# Candidate proposal quote coverage\n\n"
        "For market proposals, this packet checks the eligible action-fill minute. For pending limits, it checks every minute through the earlier of proposal expiry, session close, and training cutoff. Incomplete intervals cannot support a local no-touch expiry label. A passing interval remains conditional local-feed evidence and is not proof of venue-complete quotes or policy action.\n\n"
        "Input packet identities and counts are in `coverage_manifest.json`; per-proposal intervals are in `proposal_interval_coverage.csv`.\n",
        encoding="utf-8",
    )
    outputs = (interval_path, manifest_path, readme_path)
    (output_dir / "OUTPUT_SHA256SUMS").write_text(
        "".join(f"{_sha256(path)}  {path.name}\n" for path in outputs), encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--proposal-dir", type=Path, default=DEFAULT_PROPOSALS)
    parser.add_argument("--coverage-dir", type=Path, default=DEFAULT_COVERAGE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    resolved = [
        value if value.is_absolute() else ROOT / value
        for value in (args.config, args.proposal_dir, args.coverage_dir, args.output_dir)
    ]
    print(
        json.dumps(
            build_candidate_quote_coverage(
                config_path=resolved[0],
                proposal_dir=resolved[1],
                coverage_dir=resolved[2],
                output_dir=resolved[3],
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
