from __future__ import annotations

import json
import sys
from argparse import Namespace
from pathlib import Path

import pytest
from omegaconf import OmegaConf

from training.artifacts.walk_forward import (
    _write_walk_forward_fold_receipt,
    build_walk_forward_identity,
    build_walk_forward_progress,
    fold_identity_sha256,
    fold_split_sha256,
    load_walk_forward_progress,
)
from training.configuration.cli import parse_train_args
from training.runner.survival_campaign import validate_survival_campaign


def _args() -> Namespace:
    return Namespace(
        seeds=[42, 43, 44, 45, 46, 47],
        seed=42,
        algo="ppo",
        arch="mtf_reasoning",
        strategy="baseline",
        reward="dsr",
        wf_splits=5,
        purge_bars=60,
        embargo_bars=20,
        wf_steps=None,
    )


def test_walk_forward_identities_bind_seed_run_protocol_and_fold_positions(tmp_path: Path) -> None:
    manifest = tmp_path / "run_manifest.json"
    manifest.write_text('{"seed":42}', encoding="utf-8")
    identity = build_walk_forward_identity(
        run_manifest_path=manifest,
        seed=42,
        wf_splits=5,
        purge_bars=60,
        embargo_bars=20,
        wf_steps=2000,
    )
    split = fold_split_sha256([0, 1, 2], [5, 6])
    fold_identity = fold_identity_sha256(identity, 0, split)

    assert len(split) == len(fold_identity) == 64
    assert fold_identity != fold_identity_sha256(identity, 1, split)
    manifest.write_text('{"seed":43}', encoding="utf-8")
    changed = build_walk_forward_identity(
        run_manifest_path=manifest,
        seed=42,
        wf_splits=5,
        purge_bars=60,
        embargo_bars=20,
        wf_steps=2000,
    )
    assert changed != identity


def test_walk_forward_progress_resumes_exact_completed_folds(tmp_path: Path) -> None:
    identity = {
        "schema_version": "walk-forward-progress-v1",
        "seed": 42,
        "run_manifest_sha256": "a" * 64,
        "wf_splits": 2,
        "purge_bars": 60,
        "embargo_bars": 20,
        "wf_steps": 2000,
    }
    split_sha = fold_split_sha256([0, 1], [2])
    first = {
        "fold": 0,
        "split_sha256": split_sha,
        "fold_identity_sha256": fold_identity_sha256(identity, 0, split_sha),
        "sharpe": 0.0,
    }
    path = tmp_path / "walk_forward.json"
    path.write_text(
        json.dumps(
            build_walk_forward_progress(
                identity=identity,
                expected_fold_ids={0, 1},
                purge_bars=60,
                embargo_bars=20,
                folds={0: first},
            )
        ),
        encoding="utf-8",
    )

    resumed = load_walk_forward_progress(path, identity=identity, expected_fold_ids={0, 1})
    assert resumed == {0: first}
    with pytest.raises(ValueError, match="identity differs"):
        load_walk_forward_progress(
            path, identity={**identity, "seed": 43}, expected_fold_ids={0, 1}
        )

    second_sha = fold_split_sha256([0, 1, 2], [3])
    second = {
        "fold": 1,
        "split_sha256": second_sha,
        "fold_identity_sha256": fold_identity_sha256(identity, 1, second_sha),
        "sharpe": 1.0,
    }
    complete = build_walk_forward_progress(
        identity=identity,
        expected_fold_ids={0, 1},
        purge_bars=60,
        embargo_bars=20,
        folds={**resumed, 1: second},
    )
    assert complete["status"] == "complete"


def test_walk_forward_receipts_validate_and_recover_aggregate_write_gap(tmp_path: Path) -> None:
    identity = {
        "schema_version": "walk-forward-progress-v1",
        "seed": 42,
        "run_manifest_sha256": "a" * 64,
        "wf_splits": 2,
        "purge_bars": 60,
        "embargo_bars": 20,
        "wf_steps": 2000,
    }
    split_sha = fold_split_sha256([0, 1], [2])
    record = {
        "fold": 0,
        "split_sha256": split_sha,
        "fold_identity_sha256": fold_identity_sha256(identity, 0, split_sha),
        "sharpe": 0.0,
    }
    progress_path = tmp_path / "walk_forward.json"
    receipts_dir = tmp_path / "walk_forward_folds"

    _write_walk_forward_fold_receipt(receipts_dir, identity=identity, record=record)
    recovered = load_walk_forward_progress(
        progress_path,
        identity=identity,
        expected_fold_ids={0, 1},
        receipts_dir=receipts_dir,
    )
    assert recovered == {0: record}

    progress_path.write_text(
        json.dumps(
            build_walk_forward_progress(
                identity=identity,
                expected_fold_ids={0, 1},
                purge_bars=60,
                embargo_bars=20,
                folds=recovered,
            )
        ),
        encoding="utf-8",
    )
    assert load_walk_forward_progress(
        progress_path,
        identity=identity,
        expected_fold_ids={0, 1},
        receipts_dir=receipts_dir,
    ) == {0: record}

    receipts_dir.joinpath("fold_0.json").unlink()
    with pytest.raises(ValueError, match="receipt is missing or changed"):
        load_walk_forward_progress(
            progress_path,
            identity=identity,
            expected_fold_ids={0, 1},
            receipts_dir=receipts_dir,
        )


def test_survival_campaign_rejects_source_or_protocol_changes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import training.runner.survival_campaign as campaign

    source = {"available": True, "head": "a" * 40, "dirty_files": []}
    monkeypatch.setattr(campaign, "source_state", lambda _root: source)
    cfg = OmegaConf.create(
        {"env": {"reward_mode": "survival"}, "training": {}, "ppo": {"total_timesteps": 2000}}
    )
    identity = validate_survival_campaign(run_dir=tmp_path, cfg=cfg, args=_args(), create=True)
    saved = json.loads((tmp_path / "survival_campaign.json").read_text(encoding="utf-8"))
    assert saved["identity"] == identity

    changed_source = {**source, "head": "b" * 40}
    monkeypatch.setattr(campaign, "source_state", lambda _root: changed_source)
    with pytest.raises(ValueError, match="source or protocol identity changed"):
        validate_survival_campaign(run_dir=tmp_path, cfg=cfg, args=_args(), create=False)


def test_campaign_identity_requires_clean_source(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import training.runner.survival_campaign as campaign

    monkeypatch.setattr(
        campaign,
        "source_state",
        lambda _root: {"available": True, "head": "a" * 40, "dirty_files": [{"path": "x.py"}]},
    )
    cfg = OmegaConf.create(
        {"env": {"reward_mode": "survival"}, "training": {}, "ppo": {"total_timesteps": 2000}}
    )
    with pytest.raises(ValueError, match="clean, identifiable source tree"):
        validate_survival_campaign(run_dir=tmp_path, cfg=cfg, args=_args(), create=True)


def test_campaign_cli_selects_one_walk_forward_fold(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "training",
            "--seeds",
            "42",
            "43",
            "44",
            "45",
            "46",
            "47",
            "--walk-forward",
            "--survival-campaign-dir",
            "/tmp/survival-campaign",
            "--survival-campaign-phase",
            "walk_forward_fold",
            "--survival-campaign-seed",
            "42",
            "--survival-campaign-fold",
            "0",
        ],
    )

    args = parse_train_args()

    assert args.survival_campaign_phase == "walk_forward_fold"
    assert args.survival_campaign_seed == 42
    assert args.survival_campaign_fold == 0
