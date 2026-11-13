from __future__ import annotations

from pathlib import Path

import yaml

from experiments.runs.source_snapshot import experiment_run_data_inputs, sha256_file


def test_configured_experiment_run_resolves_its_variants_and_period_roles() -> None:
    root = Path(__file__).resolve().parents[3]
    experiment_run = yaml.safe_load(
        (root / "config/experiment_runs/example.yaml").read_text(encoding="utf-8")
    )
    base = yaml.safe_load((root / "config/base/default.yaml").read_text(encoding="utf-8"))
    variant_file = root / experiment_run["variant_file"]
    variants = [
        line.strip()
        for line in variant_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]

    assert experiment_run["variants"] == variants
    assert len(variants) == len(set(variants)) == 2
    assert experiment_run["split"]["train_end"] == base["data"]["split"]["train_end"]
    assert experiment_run["split"]["test_start"] == base["data"]["split"]["test_start"]
    assert experiment_run["evaluation"]["selection_allowed"] is False


def test_experiment_run_data_identity_uses_split_bars_ticks_and_calendar(tmp_path: Path) -> None:
    training = tmp_path / "data" / "training"
    testing = tmp_path / "data" / "testing"
    training.mkdir(parents=True)
    testing.mkdir(parents=True)
    paths = {
        training / "US100_M1.csv": b"train bars",
        training / "US100_M3.csv": b"train native M3 bars",
        training / "US100_ticks.csv": b"train ticks",
        testing / "US100_M1.csv": b"test bars",
        testing / "US100_M3.csv": b"test native M3 bars",
        testing / "US100_ticks.csv": b"test ticks",
        tmp_path / "config" / "calendar.csv": b"session schedule",
    }
    for path, contents in paths.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)

    records = experiment_run_data_inputs(
        {
            "datasets": {
                "training": {
                    "raw_dir": "data/training",
                    "m1_files": {"US100": "US100_M1.csv"},
                    "timeframe_files": {"M3": {"US100": "US100_M3.csv"}},
                    "tick_files": {"US100": "US100_ticks.csv"},
                },
                "testing": {
                    "raw_dir": "data/testing",
                    "m1_files": {"US100": "US100_M1.csv"},
                    "timeframe_files": {"M3": {"US100": "US100_M3.csv"}},
                    "tick_files": {"US100": "US100_ticks.csv"},
                },
            },
            "session_schedule_file": "config/calendar.csv",
        },
        root=tmp_path,
    )

    assert records["training:data/training/US100_M1.csv"] == sha256_file(training / "US100_M1.csv")
    assert records["training:data/training/US100_ticks.csv"] == sha256_file(
        training / "US100_ticks.csv"
    )
    assert records["testing:data/testing/US100_M1.csv"] == sha256_file(testing / "US100_M1.csv")
    assert records["training:data/training/US100_M3.csv"] == sha256_file(training / "US100_M3.csv")
    assert records["testing:data/testing/US100_M3.csv"] == sha256_file(testing / "US100_M3.csv")
    assert records["testing:data/testing/US100_ticks.csv"] == sha256_file(
        testing / "US100_ticks.csv"
    )
    assert records["calendar:config/calendar.csv"] == sha256_file(
        tmp_path / "config" / "calendar.csv"
    )
