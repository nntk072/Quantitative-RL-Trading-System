"""Check that current local M1 bars reproduce saved A4 bar-input identities.

This is a fail-closed preflight for any reanalysis that needs to pair a saved
equity series with current local prices. Matching row counts and date bounds
alone are not enough to establish that the price values are identical.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd
from omegaconf import OmegaConf

from configuration.paths import repository_root
from evaluation.reporting.run_manifest import dataframe_sha256
from market_data.loading.bars import load_bars
from market_data.splits.definitions import split_bars
from market_data.transforms.cleaning import clean
from market_data.transforms.price_grid import configured_price_grid_increment, quantize_bar_prices
from market_data.transforms.sessions import add_session_id, add_session_labels

ROOT = repository_root(__file__)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _partition_report(
    *,
    arm: str,
    partition: str,
    packet_root: Path,
    cache_root: Path,
    symbol: str,
) -> dict[str, Any]:
    evidence_manifest_path = packet_root / f"{arm}_{partition}" / "evidence_manifest.json"
    evidence_manifest = json.loads(evidence_manifest_path.read_text(encoding="utf-8"))
    trades_path = Path(evidence_manifest["input_files"]["trades.csv"]["path"])
    run_dir = trades_path.parent
    reanalysis_path = run_dir.parent / "reanalysis_manifest.json"
    reanalysis = json.loads(reanalysis_path.read_text(encoding="utf-8"))
    dataset_name = "train" if partition == "training" else "test"
    expected = reanalysis["evaluated_datasets"][f"{dataset_name}_bars"]

    source_run = reanalysis.get("source_run")
    run_manifest_path = (
        Path(source_run) / "run_manifest.json" if source_run else run_dir / "run_manifest.json"
    )
    run_manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))
    run_expected = run_manifest["datasets"][f"{dataset_name}_bars"]
    run_frame_identity_matches_reanalysis = all(
        run_expected.get(key) == expected.get(key)
        for key in ("sha256", "rows", "columns", "start", "end")
    )

    bars_path = cache_root / partition / f"{symbol}_M1_v4-semantic-manifest.parquet"
    cache_manifest_path = bars_path.with_suffix(bars_path.suffix + ".manifest.json")
    cache_manifest = json.loads(cache_manifest_path.read_text(encoding="utf-8"))
    bars = pd.read_parquet(bars_path)
    current_hash = dataframe_sha256(bars)
    current_columns = [str(column) for column in bars.columns]
    current_start = str(bars.index.min()) if len(bars) else None
    current_end = str(bars.index.max()) if len(bars) else None

    source_identity = cache_manifest.get("identity", {}).get("inputs", {}).get("source_identity")
    raw_data_sha256 = None
    raw_data_path = None
    source_config_sha256 = reanalysis.get("source_config_sha256")
    source_config_path = Path(source_run) / "config.yaml" if source_run else None
    raw_data_sha256 = None
    raw_data_path = None
    reconstructed: dict[str, Any] = {
        "status": "not_reconstructed",
        "matches_saved_run_frame": False,
    }
    if source_config_path is not None and source_config_path.is_file():
        source_config_sha256_current = _sha256(source_config_path)
        if source_config_sha256_current == source_config_sha256:
            cfg = OmegaConf.load(source_config_path)
            dataset = cfg.data.datasets.get(partition)
            primary = str(cfg.data.primary)
            filename = dataset.m1_files.get(primary) if dataset is not None else None
            raw_dir = Path(str(dataset.raw_dir)) if dataset is not None else None
            if filename and raw_dir is not None:
                candidate = raw_dir / str(filename)
                if not candidate.is_absolute():
                    candidate = ROOT / candidate
                if candidate.is_file():
                    raw_data_path = candidate.resolve().as_posix()
                    raw_data_sha256 = _sha256(candidate)
                    try:
                        source_bars = load_bars(candidate)
                        source_bars = quantize_bar_prices(
                            source_bars, configured_price_grid_increment(cfg)
                        )
                        source_bars = clean(source_bars, tz=str(cfg.data.tz))
                        source_bars = add_session_labels(
                            source_bars,
                            tz=str(cfg.data.tz),
                            ny_end=str(cfg.session.end),
                        )
                        source_bars = add_session_id(source_bars)
                        train_bars, test_bars = split_bars(
                            source_bars,
                            str(cfg.data.split.train_end),
                            str(cfg.data.split.test_start),
                            str(cfg.data.split.train_start),
                        )
                        frame = train_bars if partition == "training" else test_bars
                        reconstructed_hash = dataframe_sha256(frame)
                        reconstructed_match = (
                            reconstructed_hash == expected["sha256"]
                            and len(frame) == int(expected["rows"])
                            and [str(column) for column in frame.columns]
                            == list(expected["columns"])
                            and str(frame.index.min()) == expected["start"]
                            and str(frame.index.max()) == expected["end"]
                        )
                        reconstructed = {
                            "status": (
                                "exact_match" if reconstructed_match else "input_identity_mismatch"
                            ),
                            "path": candidate.resolve().as_posix(),
                            "raw_sha256": raw_data_sha256,
                            "sha256": reconstructed_hash,
                            "rows": len(frame),
                            "columns": [str(column) for column in frame.columns],
                            "start": str(frame.index.min()) if len(frame) else None,
                            "end": str(frame.index.max()) if len(frame) else None,
                            "matches_saved_run_frame": reconstructed_match,
                        }
                    except Exception as error:
                        reconstructed = {
                            "status": "reconstruction_error",
                            "path": candidate.resolve().as_posix(),
                            "raw_sha256": raw_data_sha256,
                            "matches_saved_run_frame": False,
                            "error": f"{type(error).__name__}: {error}",
                        }

    layout_matches = (
        len(bars) == int(expected["rows"])
        and current_columns == list(expected["columns"])
        and current_start == expected["start"]
        and current_end == expected["end"]
    )
    raw_source_matches_cache = bool(
        source_identity and source_identity == f"native:{raw_data_sha256}"
    )
    exact_frame_match = current_hash == expected["sha256"]
    exact_reconstruction_match = bool(reconstructed["matches_saved_run_frame"])
    return {
        "arm": arm.upper(),
        "partition": partition,
        "status": "exact_source_rebuild_match"
        if exact_reconstruction_match and run_frame_identity_matches_reanalysis
        else "input_identity_mismatch",
        "historical_run_manifest": {
            "path": run_manifest_path.resolve().as_posix(),
            "sha256": _sha256(run_manifest_path),
            "source_head": run_manifest.get("source", {}).get("head"),
            "runtime_versions": run_manifest.get("runtime", {}).get("versions", {}),
            "saved_frame_matches_reanalysis_manifest": run_frame_identity_matches_reanalysis,
        },
        "expected_run_frame": expected,
        "current_local_frame": {
            "path": bars_path.resolve().as_posix(),
            "sha256": current_hash,
            "rows": len(bars),
            "columns": current_columns,
            "start": current_start,
            "end": current_end,
            "parquet_sha256": _sha256(bars_path),
            "cache_manifest_sha256": _sha256(cache_manifest_path),
        },
        "source_raw_input": {
            "path": raw_data_path,
            "sha256": raw_data_sha256,
            "sha256_matches_current_cache_source_identity": raw_source_matches_cache,
            "current_cache_source_identity": source_identity,
        },
        "source_config": {
            "path": source_config_path.as_posix() if source_config_path else None,
            "expected_sha256": source_config_sha256,
            "current_sha256": (
                _sha256(source_config_path)
                if source_config_path is not None and source_config_path.is_file()
                else None
            ),
        },
        "layout_matches_expected": layout_matches,
        "exact_frame_hash_matches_expected": exact_frame_match,
        "raw_source_reconstructed_frame": reconstructed,
        "interpretation": (
            "The current Parquet-loaded frame hash differs, but rebuilding the configured raw M1 "
            "source with the saved run config reproduces the exact saved in-memory frame hash. "
            "Use that verified source reconstruction for saved-run equity reconciliation."
            if exact_reconstruction_match and run_frame_identity_matches_reanalysis
            else "Matching row counts, columns, and time bounds do not establish value identity; "
            "do not use these bars to claim exact saved-run mark-to-market reconciliation."
        ),
    }


def audit_saved_equity_bar_identity(
    packet_root: Path,
    cache_root: Path,
    output: Path,
    *,
    symbol: str = "US100.cash",
) -> dict[str, Any]:
    """Write exact frame-hash comparisons for all four selected A4 partitions."""
    partitions = [
        _partition_report(
            arm=arm,
            partition=partition,
            packet_root=packet_root,
            cache_root=cache_root,
            symbol=symbol,
        )
        for arm in ("a4a", "a4b")
        for partition in ("training", "testing")
    ]
    statuses = [partition["status"] for partition in partitions]
    reconstruction_sources = [
        "market_data/loading/bars.py",
        "market_data/transforms/price_grid.py",
        "market_data/transforms/cleaning.py",
        "market_data/transforms/sessions.py",
        "market_data/splits/definitions.py",
        "evaluation/reporting/run_manifest.py",
    ]
    report = {
        "schema_version": 1,
        "status": "exact_source_rebuild_match"
        if all(value == "exact_source_rebuild_match" for value in statuses)
        else "incomplete",
        "scope": "source identity preflight only; no equity or mark-to-market values were reconstructed",
        "hash_algorithm": "evaluation.reporting.run_manifest.dataframe_sha256",
        "analysis_script": {
            "path": Path(__file__)
            .resolve()
            .relative_to(Path(__file__).resolve().parents[4])
            .as_posix(),
            "sha256": _sha256(Path(__file__).resolve()),
        },
        "reconstruction_sources": [
            {"path": path, "sha256": _sha256(ROOT / path)} for path in reconstruction_sources
        ],
        "partitions": partitions,
        "exact_source_rebuild_match_count": statuses.count("exact_source_rebuild_match"),
        "input_identity_mismatch_count": statuses.count("input_identity_mismatch"),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--packet-root",
        type=Path,
        default=Path("evidence/research/selected_policy_trade_lifecycle"),
    )
    parser.add_argument("--cache-root", type=Path, default=Path("cache/train_test_2025_2026"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "evidence/research/simulator_execution_parity/equity_series_reconciliation/"
            "saved_equity_bar_identity.json"
        ),
    )
    parser.add_argument("--symbol", default="US100.cash")
    args = parser.parse_args()
    report = audit_saved_equity_bar_identity(
        args.packet_root, args.cache_root, args.output, symbol=args.symbol
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "exact_source_rebuild_match_count": report["exact_source_rebuild_match_count"],
                "input_identity_mismatch_count": report["input_identity_mismatch_count"],
                "output": args.output.as_posix(),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
