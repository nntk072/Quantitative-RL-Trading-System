#!/usr/bin/env python3
"""Build a training-only PO3 setup lifecycle packet from the configured pipeline.

The output projects the existing PO3 producer state into accepted setup
sequences. It does not create a new event detector, count policy proposals, or
change model-facing features.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, cast

import pandas as pd
from omegaconf import DictConfig, OmegaConf

from configuration.configuration_loader import load_config
from configuration.paths import repository_root
from features.pipeline.feature_matrix_builder import build_features
from features.po3.setup_lifecycle import build_po3_setup_lifecycle_ledger
from market_data.loading.market_data_ingestion import run_pipeline

ROOT = repository_root(__file__)
DEFAULT_CONFIG = ROOT / "config/2_po3_ifvg.yaml"
DEFAULT_OUTPUT = ROOT / "evidence/research/po3_setup_lifecycle"
RAW_MANIFEST = (
    ROOT / "evidence/research/releases/negative-evidence-readiness/RAW_DATA_SHA256_MANIFEST.json"
)
STATE_COLUMNS = (
    "po3_setup_id",
    "po3_manipulation_direction",
    "po3_manipulation_active",
    "po3_manipulation_end",
    "po3_waiting_ifvg",
    "po3_ifvg_confirmed",
    "po3_distribution",
    "po3_distribution_after_ifvg",
    "po3_sweep_reference",
    "po3_sweep_reference_tf_code",
    "po3_sweep_pivot_time_ns",
    "po3_sweep_confirmed_at_ns",
    "po3_sweep_time_ns",
    "po3_reclaim_time_ns",
    "po3_ifvg_time_ns",
    "po3_ifvg_fvg_origin_bar",
    "po3_ifvg_fvg_origin_time_ns",
    "po3_sweep_conflict",
)
SOURCE_PATHS = (
    "features/pipeline/feature_matrix_builder.py",
    "features/pipeline/po3_stage.py",
    "features/po3/ifvg_state.py",
    "features/po3/setup_lifecycle.py",
    "market_data/loading/market_data_ingestion.py",
    "scripts/research/analysis/features/build_po3_setup_lifecycle_ledger.py",
)


def _training_slice(frame: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    """Return the inclusive configured training-date slice."""
    index = pd.DatetimeIndex(frame.index)
    lower = pd.Timestamp(start)
    upper = pd.Timestamp(end) + pd.Timedelta(days=1) - pd.Timedelta(nanoseconds=1)
    if index.tz is not None:
        lower = lower.tz_localize(index.tz) if lower.tzinfo is None else lower.tz_convert(index.tz)
        upper = upper.tz_localize(index.tz) if upper.tzinfo is None else upper.tz_convert(index.tz)
    return frame.loc[(index >= lower) & (index <= upper)]


def _source_hashes() -> dict[str, str]:
    """Hash the producer, projection, pipeline, and this reusable entry point."""
    return {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in SOURCE_PATHS}


def _training_input_hashes(cfg: DictConfig) -> dict[str, str]:
    """Require each configured M1 training input to match the local raw manifest."""
    manifest = json.loads(RAW_MANIFEST.read_text(encoding="utf-8"))
    entries = {item["path"]: item for item in manifest["files"]}
    training = cfg.data.datasets.training
    raw_dir = Path(str(training.raw_dir))
    inputs: dict[str, str] = {}
    for symbol in (str(cfg.data.primary), str(cfg.data.secondary)):
        relative = (raw_dir / str(training.m1_files[symbol])).as_posix()
        record = entries.get(relative)
        if record is None:
            raise ValueError(f"training input is absent from the pinned raw manifest: {relative}")
        path = ROOT / relative
        if not path.is_file() or path.stat().st_size != int(record["size_bytes"]):
            raise ValueError(
                f"training input size differs from the pinned raw manifest: {relative}"
            )
        with path.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != str(record["sha256"]):
            raise ValueError(
                f"training input content differs from the pinned raw manifest: {relative}"
            )
        inputs[relative] = actual
    return inputs


def _git_commit() -> str:
    """Return the source checkout's current commit identity."""
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def _summary(ledger: pd.DataFrame) -> dict[str, Any]:
    accepted = ledger.loc[ledger["event_kind"].eq("po3_setup_sequence")]
    conflicts = ledger.loc[ledger["event_kind"].eq("conflicting_same_bar_sweeps")]
    return {
        "accepted_setup_sequence_count": int(len(accepted)),
        "conflicting_same_bar_sweep_count": int(len(conflicts)),
        "setup_sequences_by_direction": {
            str(int(cast(float, direction))): int(count)
            for direction, count in accepted.groupby("direction", dropna=True).size().items()
        },
        "setup_sequences_by_final_phase": {
            str(phase): int(count)
            for phase, count in accepted.groupby("phase_at_end", dropna=True).size().items()
        },
        "setup_sequences_by_termination": {
            str(reason): int(count)
            for reason, count in accepted.groupby("termination_reason", dropna=True).size().items()
        },
    }


def _write_checksums(output_dir: Path) -> None:
    """Hash packet files except the checksum index itself."""
    rows = [
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}"
        for path in sorted(output_dir.iterdir(), key=lambda item: item.name)
        if path.is_file() and path.name != "OUTPUT_SHA256SUMS"
    ]
    (output_dir / "OUTPUT_SHA256SUMS").write_text("\n".join(rows) + "\n", encoding="utf-8")


def build_ledger(
    cfg: DictConfig,
    output_dir: Path,
    *,
    config_path: Path = DEFAULT_CONFIG,
) -> dict[str, Any]:
    """Build and persist a hash-linked M1 PO3 lifecycle packet for training rows."""
    if str(cfg.features.get("po3_phase_mode", "legacy")) != "reclaim_then_ifvg":
        raise ValueError(
            "PO3 setup lifecycle packet requires features.po3_phase_mode=reclaim_then_ifvg"
        )
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite a non-empty evidence directory: {output_dir}")

    source_hashes = _source_hashes()
    training_input_hashes = _training_input_hashes(cfg)
    cfg.data.cache_dir = str(ROOT / "cache/po3_setup_lifecycle")
    datasets = run_pipeline(cfg, datasets=["training"])
    primary_symbol = str(cfg.data.primary)
    secondary_symbol = str(cfg.data.secondary)
    train_start = str(cfg.data.split.train_start)
    train_end = str(cfg.data.split.train_end)
    primary_frames = {
        timeframe: _training_slice(frame, train_start, train_end)
        for timeframe, frame in datasets[primary_symbol].items()
    }
    secondary_frames = {
        timeframe: _training_slice(frame, train_start, train_end)
        for timeframe, frame in datasets[secondary_symbol].items()
    }
    primary = primary_frames["M1"]
    secondary = secondary_frames["M1"]
    if primary.empty or secondary.empty:
        raise ValueError("configured training-only M1 input is empty")
    train_mask = pd.Series(True, index=primary.index, dtype=bool)
    features = build_features(
        primary,
        secondary,
        cfg=cfg,
        train_mask=train_mask,
        timeframe_bars=primary_frames,
        secondary_timeframe_bars=secondary_frames,
    )
    missing = sorted(set(STATE_COLUMNS) - set(map(str, features.columns)))
    if missing:
        raise ValueError(f"configured feature output lacks PO3 lifecycle columns: {missing}")
    state = features.loc[:, list(STATE_COLUMNS)]
    ledger = build_po3_setup_lifecycle_ledger(state)
    expected_setup_count = int(state["po3_setup_id"].max()) if len(state) else 0
    actual_setup_count = int(ledger["event_kind"].eq("po3_setup_sequence").sum())
    if actual_setup_count != expected_setup_count:
        raise AssertionError("lifecycle rows do not reconcile to producer setup IDs")

    output_dir.mkdir(parents=True, exist_ok=True)
    ledger.to_csv(output_dir / "setup_lifecycle_ledger.csv", index=False, lineterminator="\n")
    resolved_config = OmegaConf.to_yaml(cfg, resolve=True)
    (output_dir / "resolved_config.yaml").write_text(resolved_config, encoding="utf-8")
    summary = _summary(ledger)
    (output_dir / "setup_lifecycle_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    readme = [
        "# PO3 setup lifecycle evidence",
        "",
        "This packet projects the configured M1 PO3 producer state into accepted setup-sequence rows and separate same-bar conflict rows.",
        "It is diagnostic implementation evidence. Counts describe the configured producer on the declared local training inputs; they are not ground-truth market events, candidate proposals, policy actions, fills, or trades.",
        "Bar-indexed sweep, reclaim, IFVG-confirmation, and FVG-origin times are exact integers recovered from the M1 index. Higher-timeframe pivot and confirmation timestamps remain source float nanoseconds because their nullable producer columns cannot represent epoch nanoseconds exactly.",
        "The feature tensor and action schema are unchanged.",
        "",
        "## Contents",
        "",
        "- `setup_lifecycle_ledger.csv`: producer-sequence lifecycle rows.",
        "- `setup_lifecycle_summary.json`: counts by event kind, direction, final phase, and termination.",
        "- `resolved_config.yaml`: fully resolved feature and data configuration.",
        "- `event_ledger.json`: source, configuration, input, and limitation metadata.",
        "- `OUTPUT_SHA256SUMS`: packet file checksums.",
        "",
        "## Regeneration",
        "",
        f"`python scripts/research/analysis/features/build_po3_setup_lifecycle_ledger.py --config {config_path.relative_to(ROOT).as_posix()}`",
        "",
    ]
    (output_dir / "README.md").write_text("\n".join(readme), encoding="utf-8")
    metadata = {
        "schema_version": 1,
        "finding_status": "diagnostic_local_training_profile",
        "profile_scope": "configured M1 reclaim_then_ifvg PO3 producer state",
        "training_start": train_start,
        "training_end": train_end,
        "primary_symbol": primary_symbol,
        "secondary_symbol": secondary_symbol,
        "source_commit": _git_commit(),
        "config_path": config_path.relative_to(ROOT).as_posix(),
        "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
        "resolved_config_sha256": hashlib.sha256(resolved_config.encode("utf-8")).hexdigest(),
        "local_data_manifest": str(RAW_MANIFEST.relative_to(ROOT)),
        "local_data_manifest_sha256": hashlib.sha256(RAW_MANIFEST.read_bytes()).hexdigest(),
        "training_input_sha256": training_input_hashes,
        "source_sha256": source_hashes,
        "counts": summary,
        "limitations": [
            "producer setup sequences are not a ground-truth event ontology",
            "the packet does not count policy proposals or actions",
            "only the configured M1 state path is included",
            "no economic performance or thesis holdout claim is made",
        ],
    }
    (output_dir / "event_ledger.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _write_checksums(output_dir)
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    config_path = args.config if args.config.is_absolute() else ROOT / args.config
    cfg = load_config(config_path=config_path)
    result = build_ledger(cfg, args.output_dir, config_path=config_path)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
