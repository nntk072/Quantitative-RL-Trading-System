"""Contracts for configured source-timeframe FVG event reporting."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest
from omegaconf import OmegaConf
from scripts.research.analysis.features.fvg_timeframe_event_ledger import (
    _collision_table,
    _configured_timeframes,
    _input_identity,
)


def test_timeframes_include_m1_once_and_preserve_configured_order() -> None:
    cfg = OmegaConf.create({"features": {"fvg_timeframes": ["M5", "M3", "M5"]}})
    assert _configured_timeframes(cfg) == ["M1", "M5", "M3"]


def test_collision_table_counts_within_timeframe_zone_suppression() -> None:
    events = pd.DataFrame(
        [
            {
                "source_timeframe": "M5",
                "confirmation_bar": 2,
                "confirmation_time_ns": 120,
                "side": "bullish",
                "zone_start_time_ns": 80,
                "selected_by_scalar": False,
            },
            {
                "source_timeframe": "M5",
                "confirmation_bar": 2,
                "confirmation_time_ns": 120,
                "side": "bullish",
                "zone_start_time_ns": 100,
                "selected_by_scalar": True,
            },
            {
                "source_timeframe": "M15",
                "confirmation_bar": 1,
                "confirmation_time_ns": 120,
                "side": "bullish",
                "zone_start_time_ns": 90,
                "selected_by_scalar": True,
            },
        ]
    )
    bars = {
        "M5": pd.DataFrame(index=pd.date_range("2025-01-01", periods=3, freq="5min")),
        "M15": pd.DataFrame(index=pd.date_range("2025-01-01", periods=2, freq="15min")),
    }

    collisions = _collision_table(events, bars)

    assert collisions[
        ["source_timeframe", "per_zone_retest_count", "suppressed_per_zone_retests"]
    ].values.tolist() == [["M5", 2, 1]]


def test_input_identity_keeps_dotted_symbol_keys_and_validates_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    training_dir = tmp_path / "data/training"
    training_dir.mkdir(parents=True)
    path = training_dir / "m1.csv"
    path.write_text("local training bars\n", encoding="utf-8")
    stat = path.stat()
    relative = "data/training/m1.csv"
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "files": [
                    {
                        "path": relative,
                        "size_bytes": stat.st_size,
                        "mtime_utc": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
                        "sha256": digest,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    cfg = OmegaConf.create(
        {
            "data": {
                "datasets": {
                    "training": {
                        "raw_dir": "data/training",
                        "m1_files": {"US100.cash": "m1.csv"},
                        "timeframe_files": {},
                    }
                }
            }
        }
    )
    module = __import__(
        "scripts.research.analysis.features.fvg_timeframe_event_ledger",
        fromlist=["RAW_MANIFEST", "ROOT"],
    )
    monkeypatch.setattr(module, "RAW_MANIFEST", manifest_path)
    monkeypatch.setattr(module, "ROOT", tmp_path)

    assert _input_identity(cfg, "US100.cash", ["M1"]) == {relative: digest}
