from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest
from omegaconf import OmegaConf
from scripts.research.analysis.features import build_po3_setup_lifecycle_ledger as packet


def test_training_slice_includes_both_configured_date_boundaries() -> None:
    index = pd.date_range("2025-01-01", periods=4, freq="D", tz="Etc/GMT-3")
    frame = pd.DataFrame({"value": range(4)}, index=index)

    result = packet._training_slice(frame, "2025-01-02", "2025-01-03")

    assert result["value"].tolist() == [1, 2]


def test_training_input_hashes_require_current_local_manifest_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    files = {
        "US100.cash": ("US100.cash_M1.csv", b"primary local bars"),
        "US500.cash": ("US500.cash_M1.csv", b"secondary local bars"),
    }
    manifest_files = []
    expected: dict[str, str] = {}
    for filename, contents in files.values():
        relative = f"data/training/{filename}"
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)
        digest = hashlib.sha256(contents).hexdigest()
        expected[relative] = digest
        manifest_files.append({"path": relative, "size_bytes": len(contents), "sha256": digest})
    manifest_path = tmp_path / "raw_manifest.json"
    manifest_path.write_text(json.dumps({"files": manifest_files}), encoding="utf-8")
    monkeypatch.setattr(packet, "ROOT", tmp_path)
    monkeypatch.setattr(packet, "RAW_MANIFEST", manifest_path)
    cfg = OmegaConf.create(
        {
            "data": {
                "primary": "US100.cash",
                "secondary": "US500.cash",
                "datasets": {
                    "training": {
                        "raw_dir": "data/training",
                        "m1_files": {
                            "US100.cash": "US100.cash_M1.csv",
                            "US500.cash": "US500.cash_M1.csv",
                        },
                    }
                },
            }
        }
    )

    assert packet._training_input_hashes(cfg) == expected


def test_training_input_hashes_reject_content_outside_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    relative = "data/training/US100.cash_M1.csv"
    path = tmp_path / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"changed local bars")
    manifest_path = tmp_path / "raw_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "files": [
                    {
                        "path": relative,
                        "size_bytes": len(b"changed local bars"),
                        "sha256": hashlib.sha256(b"pinned local bars").hexdigest(),
                    },
                    {
                        "path": "data/training/US500.cash_M1.csv",
                        "size_bytes": 0,
                        "sha256": hashlib.sha256(b"").hexdigest(),
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "data/training/US500.cash_M1.csv").write_bytes(b"")
    monkeypatch.setattr(packet, "ROOT", tmp_path)
    monkeypatch.setattr(packet, "RAW_MANIFEST", manifest_path)
    cfg = OmegaConf.create(
        {
            "data": {
                "primary": "US100.cash",
                "secondary": "US500.cash",
                "datasets": {
                    "training": {
                        "raw_dir": "data/training",
                        "m1_files": {
                            "US100.cash": "US100.cash_M1.csv",
                            "US500.cash": "US500.cash_M1.csv",
                        },
                    }
                },
            }
        }
    )

    with pytest.raises(ValueError, match="content differs from the pinned raw manifest"):
        packet._training_input_hashes(cfg)


def test_summary_separates_accepted_setups_from_sweep_conflicts() -> None:
    ledger = pd.DataFrame(
        [
            {
                "event_kind": "po3_setup_sequence",
                "direction": 1,
                "phase_at_end": "distribution",
                "termination_reason": "input_end",
            },
            {
                "event_kind": "po3_setup_sequence",
                "direction": -1,
                "phase_at_end": "waiting_for_ifvg",
                "termination_reason": "replaced_by_next_sweep",
            },
            {
                "event_kind": "conflicting_same_bar_sweeps",
                "direction": None,
                "phase_at_end": "conflict_rejected",
                "termination_reason": "same_bar_direction_conflict",
            },
        ]
    )

    assert packet._summary(ledger) == {
        "accepted_setup_sequence_count": 2,
        "conflicting_same_bar_sweep_count": 1,
        "setup_sequences_by_direction": {"-1": 1, "1": 1},
        "setup_sequences_by_final_phase": {"distribution": 1, "waiting_for_ifvg": 1},
        "setup_sequences_by_termination": {"input_end": 1, "replaced_by_next_sweep": 1},
    }
