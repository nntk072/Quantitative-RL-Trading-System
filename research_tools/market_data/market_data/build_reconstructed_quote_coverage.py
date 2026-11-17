#!/usr/bin/env python3
"""Build two *sensitivity* quote-coverage packets from the production TickBook.

Never modifies the historical strict raw quote-coverage packet or executable
TickBook. The alternative columns are LOCAL-source assumptions, not proof of
MT5 broker fills, tick-tape completeness or true simultaneous quote updates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from configuration.configuration_loader import load_config
from configuration.paths import repository_root
from market_data.loading import build_tick_books
from market_data.loading.ticks import TickBook

ROOT = repository_root(__file__)
MINUTE_NS = 60_000_000_000
DEFAULT_CONFIG = ROOT / "config/research/trade_setup_mtf_reasoning_2m.yaml"
DEFAULT_COVERAGE = ROOT / "evidence/research/tick_quote_coverage"
DEFAULT_PROPOSALS = ROOT / "evidence/research/candidate_proposals"

PROFILES = {
    "reconstructed_count_checked": (
        "A minute has at least one finite, non-crossed production TickBook quote, "
        "all raw source rows in the minute survive production preprocessing, "
        "and the raw tick-row count equals M1 tickvol. This is not proof of a "
        "complete tick tape or a directly observed simultaneous bid/ask pair."
    ),
    "reconstructed_tickbook_only": (
        "A minute has at least one finite, non-crossed production TickBook quote "
        "and all raw source rows in the minute survive preprocessing. M1 tickvol "
        "parity is deliberately NOT required. This is an exploratory local-"
        "TickBook assumption, not a broker-equivalent execution claim."
    ),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fixed_offset_minutes(index: pd.DatetimeIndex, timezone: str) -> int:
    """Avoid assuming GMT offsets or silently mishandling DST."""
    if index.empty or index.tz is not None:
        raise ValueError("source-minute index must be nonempty and timezone-naive")
    offsets = []
    for timestamp in (index[0], index[len(index) // 2], index[-1]):
        offset = timestamp.tz_localize(timezone).utcoffset()
        if offset is None or offset.total_seconds() % 60 != 0:
            raise ValueError("minute-precision timezone offset required")
        offsets.append(int(offset.total_seconds() // 60))
    if len(set(offsets)) != 1:
        raise ValueError("a changing source timezone requires per-event conversion")
    return offsets[0]


def book_minute_counts(
    book: TickBook,
    source_minutes: pd.DatetimeIndex,
    *,
    timezone: str,
    chunk_rows: int = 2_000_000,
) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]]:
    """Count local executable quote rows, in bounded memory, by M1 source minute.

    Out-of-M1 book ticks are ignored but never treated as evidence of an M1 row.
    The same production TickBook instance used by conditional outcome replay is
    the sole source of reconstructed bid/ask observations.
    """
    if chunk_rows <= 0:
        raise ValueError("chunk_rows must be positive")
    if not source_minutes.is_unique or not source_minutes.is_monotonic_increasing:
        raise ValueError("source-minute index must be sorted and unique")
    if not source_minutes.equals(source_minutes.floor("min")):
        raise ValueError("source timestamps must be minute aligned")
    shift = fixed_offset_minutes(source_minutes, timezone)
    keys = np.asarray(source_minutes.astype("int64"), dtype=np.int64) // MINUTE_NS
    counts = np.zeros(len(keys), dtype=np.int64)
    invalid_counts = np.zeros(len(keys), dtype=np.int64)
    for start in range(0, len(book), chunk_rows):
        end = min(len(book), start + chunk_rows)
        local_minutes = np.floor_divide(book._ts[start:end], MINUTE_NS) + shift
        # Group first, then look up only distinct minutes (not every tick).
        distinct, inverse, group_counts = np.unique(
            local_minutes, return_inverse=True, return_counts=True
        )
        positions = np.asarray(np.searchsorted(keys, distinct), dtype=np.intp)
        in_range = positions < len(keys)
        matching = np.zeros(len(distinct), dtype=bool)
        matching[in_range] = keys[positions[in_range]] == distinct[in_range]
        np.add.at(counts, positions[matching], group_counts[matching])

        bid = book._bid[start:end]
        ask = book._ask[start:end]
        bad = ~(np.isfinite(bid) & np.isfinite(ask) & (bid > 0) & (ask > 0) & (ask >= bid))
        if bad.any():
            bad_per_group = np.bincount(inverse[bad], minlength=len(distinct))
            np.add.at(invalid_counts, positions[matching], bad_per_group[matching])
    return counts, invalid_counts


def classify_coverage(
    original: pd.DataFrame,
    book_rows: np.ndarray[Any, Any],
    book_invalid: np.ndarray[Any, Any],
) -> pd.DataFrame:
    """Retain strict raw labels and add two independently named sensitivities."""
    required = {"source_tick_rows", "m1_tickvol", "valid_two_sided_quotes", "quote_complete"}
    if missing := required.difference(original.columns):
        raise ValueError(f"strict coverage file lacks fields: {sorted(missing)}")
    if len(book_rows) != len(original) or len(book_invalid) != len(original):
        raise ValueError("TickBook count vector must match strict minute index")
    if (book_rows < 0).any() or (book_invalid < 0).any():
        raise ValueError("negative tick counts are invalid")
    raw_rows = original["source_tick_rows"].to_numpy(dtype=np.int64)
    bar_rows = original["m1_tickvol"].to_numpy(dtype=np.int64)
    raw_valid = original["valid_two_sided_quotes"].to_numpy(dtype=np.int64)
    original_strict = original["quote_complete"].astype(bool).to_numpy()
    independently_recomputed_strict = (
        (raw_rows > 0) & (raw_rows == bar_rows) & (raw_valid == raw_rows)
    )
    if not np.array_equal(original_strict, independently_recomputed_strict):
        raise ValueError("strict raw labels fail their own documented contract")
    if (book_rows > raw_rows).any():
        raise ValueError("production TickBook has more rows than the source audit in an M1 minute")
    if (book_invalid > book_rows).any():
        raise ValueError("invalid TickBook rows exceed its total row count")
    reconstructed = (book_rows > 0) & (book_rows == raw_rows) & (book_invalid == 0)
    count_checked = reconstructed & (raw_rows == bar_rows)
    result = original.copy()
    result["strict_raw_quote_complete"] = original_strict
    result["production_tickbook_rows"] = book_rows
    result["production_tickbook_invalid_rows"] = book_invalid
    result["production_tickbook_complete"] = reconstructed
    result["production_tickbook_count_checked"] = count_checked
    return result


def _verify_checksums(packet: Path) -> None:
    for line in (packet / "OUTPUT_SHA256SUMS").read_text(encoding="utf-8").splitlines():
        expected, filename = line.split(maxsplit=1)
        if sha256(packet / filename.strip()) != expected:
            raise ValueError(f"input evidence checksum mismatch: {packet / filename.strip()}")


def build_packets(
    *,
    config_path: Path,
    strict_coverage: Path,
    proposal_dir: Path,
    output_root: Path,
    chunk_rows: int = 2_000_000,
) -> dict[str, Any]:
    """Write two immutable-by-convention sensitivity packets to a NEW directory."""
    if output_root.exists():
        raise FileExistsError(f"output root already exists; refusing overwrite: {output_root}")
    _verify_checksums(strict_coverage)
    _verify_checksums(proposal_dir)
    cfg = load_config(config_path=config_path)
    symbol = str(cfg.data.primary)
    timezone = str(cfg.data.tz)
    strict_manifest_path = strict_coverage / "coverage_manifest.json"
    strict_manifest = json.loads(strict_manifest_path.read_text(encoding="utf-8"))
    proposal_manifest_path = proposal_dir / "proposal_ledger_manifest.json"
    proposal_manifest = json.loads(proposal_manifest_path.read_text(encoding="utf-8"))
    if strict_manifest["symbol"] != symbol:
        raise ValueError("symbol differs between strict packet and resolved configuration")
    dataset = cfg.data.datasets.training
    source_root = ROOT / str(dataset.raw_dir)
    for name in (dataset.tick_files[symbol], dataset.m1_files[symbol]):
        path = source_root / str(name)
        relative = str(path.relative_to(ROOT))
        expected = strict_manifest["input_sha256"].get(relative)
        if expected is None or sha256(path) != expected:
            raise ValueError(f"configured raw file differs from strict packet: {relative}")
    strict_frame = pd.read_csv(strict_coverage / "minute_quote_coverage.csv", parse_dates=[0])
    strict_index = pd.DatetimeIndex(strict_frame.iloc[:, 0])
    train_start = pd.Timestamp(str(cfg.data.split.train_start))
    train_end = pd.Timestamp(str(cfg.data.split.train_end)) + pd.Timedelta(days=1)
    if strict_index[0] < train_start or strict_index[-1] >= train_end:
        raise ValueError("strict minute index escapes the configured training interval")
    if strict_manifest["training_window"] != {
        "start_inclusive": train_start.isoformat(),
        "end_exclusive": train_end.isoformat(),
    }:
        raise ValueError("strict packet and configured training interval differ")
    if len(strict_frame) != int(strict_manifest["m1_rows"]):
        raise ValueError("strict coverage row count is inconsistent with its manifest")
    book = build_tick_books(cfg, symbols=[symbol], datasets=["training"]).get(symbol)
    if book is None or len(book) == 0:
        raise ValueError("configured training TickBook is unavailable")
    book_digest = book.content_sha256()
    if book_digest != proposal_manifest["tickbook_sha256"]:
        raise ValueError("TickBook differs from proposal ledger identity; do not compare")
    book_rows, book_invalid = book_minute_counts(
        book, strict_index, timezone=timezone, chunk_rows=chunk_rows
    )
    frame = classify_coverage(strict_frame, book_rows, book_invalid)
    manifest_by_profile: dict[str, Any] = {}
    for profile, rule in PROFILES.items():
        out = output_root / profile
        out.mkdir(parents=True, exist_ok=False)
        sensitivity_frame = frame.copy()
        sensitivity_frame["quote_complete"] = sensitivity_frame[
            "production_tickbook_count_checked"
            if profile == "reconstructed_count_checked"
            else "production_tickbook_complete"
        ]
        csv_path = out / "minute_quote_coverage.csv"
        sensitivity_frame.to_csv(csv_path, index=False)
        summary: dict[str, Any] = {
            "schema_version": "candidate-quote-coverage-sensitivity-v1",
            "status": "local_tickbook_sensitivity_not_authoritative_tape",
            "profile": profile,
            "coverage_rule": rule,
            "reference_strict_coverage_manifest_sha256": sha256(strict_manifest_path),
            "reference_strict_coverage_csv_sha256": sha256(
                strict_coverage / "minute_quote_coverage.csv"
            ),
            "proposal_manifest_sha256": sha256(proposal_manifest_path),
            "tickbook_sha256": book_digest,
            "source_commit": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            "source_sha256": {
                str(Path(__file__).resolve().relative_to(ROOT)): sha256(Path(__file__))
            },
            "minute_rows": int(len(frame)),
            "strict_complete_minutes": int(frame["strict_raw_quote_complete"].sum()),
            "reconstructed_count_checked_minutes": int(
                frame["production_tickbook_count_checked"].sum()
            ),
            "reconstructed_tickbook_only_minutes": int(frame["production_tickbook_complete"].sum()),
            "count_mismatched_minutes": int(
                (frame["source_tick_rows"] != frame["m1_tickvol"]).sum()
            ),
            "raw_reconstructed_count_mismatch_minutes": int(
                (frame["source_tick_rows"] != frame["production_tickbook_rows"]).sum()
            ),
            "quote_complete_minutes": int(sensitivity_frame["quote_complete"].sum()),
            "coverage_csv_sha256": sha256(csv_path),
        }
        manifest_path = out / "coverage_manifest.json"
        manifest_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
        readme_path = out / "README.md"
        readme_path.write_text(
            f"# {profile} (sensitivity only)\n\n{rule}\n\n"
            "Original strict results remain unchanged. This packet substitutes "
            "only minute-level censoring assumptions; outcomes must be labeled "
            "conditional and are not MT5 broker execution evidence.\n",
            encoding="utf-8",
        )
        artifacts = (csv_path, manifest_path, readme_path)
        (out / "OUTPUT_SHA256SUMS").write_text(
            "".join(f"{sha256(item)}  {item.name}\n" for item in artifacts)
        )
        manifest_by_profile[profile] = summary
    return manifest_by_profile


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--strict-coverage-dir", type=Path, default=DEFAULT_COVERAGE)
    parser.add_argument("--proposal-dir", type=Path, default=DEFAULT_PROPOSALS)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--chunk-rows", type=int, default=2_000_000)
    args = parser.parse_args()

    def resolve(path: Path) -> Path:
        return path if path.is_absolute() else ROOT / path

    print(
        json.dumps(
            build_packets(
                config_path=resolve(args.config),
                strict_coverage=resolve(args.strict_coverage_dir),
                proposal_dir=resolve(args.proposal_dir),
                output_root=resolve(args.output_root),
                chunk_rows=args.chunk_rows,
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
