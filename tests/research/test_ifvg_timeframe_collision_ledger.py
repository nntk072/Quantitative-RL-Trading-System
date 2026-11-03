"""Contracts for source-timeframe IFVG collision reporting."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest
import scripts.research.analysis.features.ifvg_timeframe_collision_ledger as ledger_module
from omegaconf import OmegaConf
from scripts.research.analysis.features.ifvg_timeframe_collision_ledger import (
    _collision_table,
    _input_identity,
    _mark_merged_scalar_selection,
)


def _events() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "source_timeframe": "M1",
                "confirmation_bar": 12,
                "effective_availability_time_ns": 120,
                "effective_availability_m1_bar": 12,
                "side": "bullish",
                "selected_by_source_scalar": True,
                "selected_by_merged_scalar": False,
            },
            {
                "source_timeframe": "M5",
                "confirmation_bar": 3,
                "effective_availability_time_ns": 120,
                "effective_availability_m1_bar": 12,
                "side": "bullish",
                "selected_by_source_scalar": True,
                "selected_by_merged_scalar": False,
            },
            {
                "source_timeframe": "M15",
                "confirmation_bar": 1,
                "effective_availability_time_ns": 120,
                "effective_availability_m1_bar": 12,
                "side": "bullish",
                "selected_by_source_scalar": True,
                "selected_by_merged_scalar": False,
            },
            {
                "source_timeframe": "M5",
                "confirmation_bar": 3,
                "effective_availability_time_ns": 120,
                "effective_availability_m1_bar": 12,
                "side": "bearish",
                "selected_by_source_scalar": False,
                "selected_by_merged_scalar": False,
            },
            {
                "source_timeframe": "M5",
                "confirmation_bar": 3,
                "effective_availability_time_ns": 120,
                "effective_availability_m1_bar": 12,
                "side": "bearish",
                "selected_by_source_scalar": True,
                "selected_by_merged_scalar": False,
            },
        ]
    )


def test_merge_selection_matches_m1_then_configured_timeframe_precedence() -> None:
    selected = _mark_merged_scalar_selection(_events(), ["M1", "M5", "M15"])

    chosen = selected.loc[selected["selected_by_merged_scalar"]]
    assert chosen[["side", "source_timeframe"]].values.tolist() == [
        ["bullish", "M1"],
        ["bearish", "M5"],
    ]


def test_collision_summary_counts_zone_events_and_scalar_suppression() -> None:
    selected = _mark_merged_scalar_selection(_events(), ["M1", "M5", "M15"])

    collisions = _collision_table(selected)
    bullish = collisions.loc[collisions["side"].eq("bullish")].iloc[0]
    bearish = collisions.loc[collisions["side"].eq("bearish")].iloc[0]

    assert bullish["per_zone_event_count"] == 3
    assert bullish["source_scalar_event_count"] == 3
    assert bullish["source_timeframe_count"] == 3
    assert bullish["selected_source_timeframe"] == "M1"
    assert bullish["suppressed_zone_event_count"] == 2
    assert bearish["per_zone_event_count"] == 2
    assert bearish["source_scalar_event_count"] == 1
    assert bearish["source_timeframe_count"] == 1
    assert bearish["selected_source_timeframe"] == "M5"
    assert bearish["suppressed_zone_event_count"] == 1


def test_input_identity_includes_native_timeframes_for_dotted_symbol_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    training_dir = tmp_path / "data/training"
    training_dir.mkdir(parents=True)
    entries = []
    expected = {}
    for timeframe, filename in (("M1", "primary_m1.csv"), ("M3", "primary_m3.csv")):
        path = training_dir / filename
        path.write_text(f"bars for {timeframe}\n", encoding="utf-8")
        stat = path.stat()
        relative = f"data/training/{filename}"
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        entries.append(
            {
                "path": relative,
                "size_bytes": stat.st_size,
                "mtime_utc": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
                "sha256": digest,
            }
        )
        expected[relative] = digest
    manifest_path = tmp_path / "raw_manifest.json"
    manifest_path.write_text(json.dumps({"files": entries}), encoding="utf-8")
    cfg = OmegaConf.create(
        {
            "data": {
                "datasets": {
                    "training": {
                        "raw_dir": "data/training",
                        "m1_files": {"US100.cash": "primary_m1.csv"},
                        "timeframe_files": {
                            "M3": {"US100.cash": "primary_m3.csv"},
                        },
                    }
                }
            }
        }
    )
    monkeypatch.setattr(ledger_module, "ROOT", tmp_path)
    monkeypatch.setattr(ledger_module, "RAW_MANIFEST", manifest_path)

    assert _input_identity(cfg, "US100.cash", ["M1", "M3"]) == expected
