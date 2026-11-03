"""Count the exact rows carried or excluded by the configured TickBook path.

This streams each hash-verified local tick input through ``build_tick_book``
with optional production-path counters. It records raw versus post-transform
rows without bundling quote values.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from omegaconf import OmegaConf

from market_data.loading.ticks import TickBookBuildDiagnostics, build_tick_book
from market_data.transforms.price_grid import configured_price_grid_increment

ROOT = Path(__file__).resolve().parents[4]
PROFILE = Path("evidence/research/market_data_quality/local_market_data_quality.json")
OUTPUT = Path("evidence/research/market_data_quality/tickbook_carry_forward_audit.json")
CONFIG = Path("config/base/default.yaml")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_packet(report: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    checksum_path = output.parent / "SHA256SUMS"
    entries = sorted(
        path for path in output.parent.iterdir() if path.is_file() and path.name != "SHA256SUMS"
    )
    checksum_path.write_text(
        "\n".join(f"{sha256(path)}  {path.name}" for path in entries) + "\n",
        encoding="utf-8",
    )


def run(root: Path, output: Path, chunksize: int) -> None:
    profile_path = root / PROFILE
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    if not profile.get("all_inputs_present") or not profile.get("all_input_hashes_match"):
        raise ValueError("existing quality profile does not verify all local input hashes")
    config_path = root / CONFIG
    config = OmegaConf.load(config_path)
    timezone = str(config.data.tz)
    grid_increment = configured_price_grid_increment(config)
    tick_inputs = [record for record in profile["inputs"] if record.get("kind") == "tick"]
    if len(tick_inputs) != 4:
        raise ValueError(f"expected four role/instrument tick inputs, found {len(tick_inputs)}")

    records: list[dict[str, Any]] = []
    for item in sorted(tick_inputs, key=lambda record: (record["role"], record["instrument"])):
        source = root / str(item["path"])
        stat_before = source.stat()
        source_hash_before = sha256(source)
        if source_hash_before != item.get("observed_sha256"):
            raise ValueError(f"current source hash differs from quality profile: {item['path']}")

        counters = TickBookBuildDiagnostics()
        book = build_tick_book(
            source,
            tz=timezone,
            session_start=None,
            session_end=None,
            cache_path=None,
            force=True,
            chunksize=chunksize,
            price_grid_increment=grid_increment,
            diagnostics=counters,
        )

        stat_after = source.stat()
        source_hash_after = sha256(source)
        stable_identity = (
            stat_before.st_dev,
            stat_before.st_ino,
            stat_before.st_size,
            stat_before.st_mtime_ns,
        ) == (
            stat_after.st_dev,
            stat_after.st_ino,
            stat_after.st_size,
            stat_after.st_mtime_ns,
        )
        if not stable_identity or source_hash_before != source_hash_after:
            raise ValueError(f"source changed during TickBook scan: {item['path']}")
        if counters.source_rows_read != int(item["row_count"]):
            raise ValueError(f"row count mismatch for {item['path']}")
        if counters.rows_retained_after_carry != len(book):
            raise ValueError(f"TickBook output/counter mismatch for {item['path']}")
        if (
            counters.raw_valid_two_sided_quotes
            + counters.raw_rows_with_missing_or_nonpositive_side
            + counters.raw_rows_with_crossed_sides
            != counters.rows_after_session_filter
        ):
            raise ValueError(f"raw row classes do not reconcile for {item['path']}")
        if (
            counters.rows_retained_after_carry
            + counters.rows_dropped_for_unavailable_side_after_carry
            + counters.rows_dropped_for_crossed_pair_after_carry
            != counters.rows_after_session_filter
        ):
            raise ValueError(f"post-carry row classes do not reconcile for {item['path']}")

        record = {
            "path": str(item["path"]),
            "role": str(item["role"]),
            "instrument": str(item["instrument"]),
            "source_sha256": source_hash_before,
            "source_hash_matches_quality_profile": True,
            "source_identity_stable_during_scan": stable_identity,
            "configuration": {
                "path": str(CONFIG),
                "timezone_carrier": timezone,
                "session_start": None,
                "session_end": None,
                "price_grid_increment": grid_increment,
            },
            "counts": asdict(counters),
            "reconciliation": {
                "raw_partition_rows_reconcile": True,
                "post_carry_partition_rows_reconcile": True,
                "reported_tickbook_rows_equal_retained_count": True,
            },
        }
        records.append(record)
        progress = {
            "schema": "qrl.tickbook_carry_forward_audit.progress.v1",
            "status": "in_progress",
            "completed_inputs": records,
            "next_input_index": len(records),
            "expected_input_count": len(tick_inputs),
        }
        write_packet(progress, output.with_name("tickbook_carry_forward_progress.json"))
        print(
            json.dumps(
                {
                    "completed": len(records),
                    "of": len(tick_inputs),
                    "role": record["role"],
                    "instrument": record["instrument"],
                    "rows": counters.source_rows_read,
                    "carried_into_valid": counters.rows_with_any_side_carried_into_valid_quote,
                    "retained": counters.rows_retained_after_carry,
                }
            ),
            flush=True,
        )

    totals = {
        name: sum(int(record["counts"][name]) for record in records)
        for name in asdict(TickBookBuildDiagnostics())
    }
    report = {
        "schema": "qrl.tickbook_carry_forward_audit.v1",
        "status": "complete_source_hash_verified_production_path_counts",
        "generated_from_repository_head": profile.get("repository_head"),
        "profile_path": str(PROFILE),
        "profile_sha256": sha256(profile_path),
        "generator_path": "scripts/research/analysis/market_data/audit_tickbook_carry_forward.py",
        "generator_sha256": sha256(Path(__file__).resolve()),
        "tick_builder_path": "market_data/loading/ticks.py",
        "tick_builder_sha256": sha256(root / "market_data/loading/ticks.py"),
        "configuration_path": str(CONFIG),
        "configuration_sha256": sha256(config_path),
        "method": "Each current source file is hash-checked before and after a sequential raw build. Counters are emitted by build_tick_book itself with no session-hour filter and no cache read.",
        "interpretation": {
            "side_carry_forward_is_a_transform": True,
            "raw_observations_are_not_modified": True,
            "carried_side_counts_are_rows_retained_after_at_least_one_required_side_was_missing_or_nonpositive_in_the_raw_row": True,
            "side_counts_may_overlap": True,
            "drop_reasons_after_carry_are_mutually_exclusive": True,
            "source_order_is_preserved_for_equal_timestamps": True,
            "does_not_establish_simultaneous_quote_availability_or_within_tie_chronology": True,
        },
        "totals": totals,
        "inputs": records,
    }
    write_packet(report, output)
    progress_path = output.with_name("tickbook_carry_forward_progress.json")
    if progress_path.exists():
        progress_path.unlink()
    # Remove the progress entry from the packet checksum after removing the file.
    checksum_path = output.parent / "SHA256SUMS"
    entries = sorted(
        path for path in output.parent.iterdir() if path.is_file() and path.name != "SHA256SUMS"
    )
    checksum_path.write_text(
        "\n".join(f"{sha256(path)}  {path.name}" for path in entries) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": report["status"], "totals": totals}, indent=2), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--chunksize", type=int, default=2_000_000)
    args = parser.parse_args()
    if args.chunksize <= 0:
        raise ValueError("chunksize must be positive")
    root = args.root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    run(root, output, args.chunksize)


if __name__ == "__main__":
    main()
