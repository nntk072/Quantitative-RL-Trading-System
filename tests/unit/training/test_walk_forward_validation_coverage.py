from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from configuration import load_config
from configuration.paths import repository_root
from evaluation.reporting.run_manifest import source_state
from training.runner.walk_forward_validation import run_walk_forward_validation


class _Config(dict[str, object]):
    def __getattr__(self, name: str) -> object:
        return self[name]


def test_walk_forward_validation_rejects_a_fold_outside_the_configured_split_set(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "seed-run"
    run_dir.mkdir()
    (run_dir / "run_manifest.json").write_text(
        json.dumps({"source": source_state(repository_root(__file__))}),
        encoding="utf-8",
    )
    args = Namespace(
        walk_forward=True,
        wf_splits=2,
        wf_steps=1,
        purge_bars=0,
        embargo_bars=0,
    )

    with pytest.raises(ValueError, match="outside the configured split set"):
        run_walk_forward_validation(
            args=args,
            timesteps=1,
            train_bars=pd.DataFrame({"close": range(40)}),
            train_sec=None,
            cfg=load_config(),
            cache_dir=tmp_path / "cache",
            primary_sym="US100",
            primary_ticks=None,
            schedule_path=tmp_path / "schedule.csv",
            feature_columns=[],
            run_dir=run_dir,
            env_vae=None,
            pre_ny_by_date=None,
            device="cpu",
            vae_model=None,
            seed=42,
            only_fold=999,
        )


def test_walk_forward_validation_is_a_noop_when_disabled(tmp_path: Path) -> None:
    run_walk_forward_validation(
        args=Namespace(walk_forward=False),
        timesteps=1,
        train_bars=pd.DataFrame(),
        train_sec=None,
        cfg=None,
        cache_dir=tmp_path,
        primary_sym="US100",
        primary_ticks=None,
        schedule_path=tmp_path / "schedule.csv",
        feature_columns=[],
        run_dir=tmp_path,
        env_vae=None,
        pre_ny_by_date=None,
        device="cpu",
        vae_model=None,
        seed=42,
    )


def test_walk_forward_validation_trains_evaluates_and_persists_one_fold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import training.runner.walk_forward_validation as module

    run_dir = tmp_path / "seed-run"
    run_dir.mkdir()
    (run_dir / "run_manifest.json").write_text('{"source": "source"}', encoding="utf-8")
    bars = pd.DataFrame({"close": [10.0, 11.0, 12.0, 13.0]})
    features = pd.DataFrame({"feature": [0.1, 0.2, 0.3, 0.4]})
    train_idx = np.array([0, 1])
    test_idx = np.array([2, 3])
    cfg = _Config(
        session=SimpleNamespace(start="09:30", end="16:00", tz="America/New_York"),
        data=_Config(timestamp_clock="native"),
        env=_Config(
            obs_window=2,
            reward_dsr_eta=0.1,
            block_overnight=True,
        ),
        account=SimpleNamespace(initial_balance=1000.0, contract_size=1.0),
        risk=SimpleNamespace(
            swing_buffer_pts=1.0,
            get=lambda key, default=None: default,
        ),
    )
    fold_receipts: list[dict[str, object]] = []

    class Model:
        def learn(self, **kwargs: object) -> None:
            assert kwargs["total_timesteps"] == 3

    monkeypatch.setattr(module, "final_evaluation_deterministic", lambda _cfg: True)
    monkeypatch.setattr(module, "source_state", lambda _root: "source")
    monkeypatch.setattr(
        module, "build_walk_forward_identity", lambda **_kwargs: {"identity": "folds"}
    )
    monkeypatch.setattr(
        module,
        "purged_walk_forward",
        lambda *_args, **_kwargs: [SimpleNamespace(fold=0, train_idx=train_idx, test_idx=test_idx)],
    )
    monkeypatch.setattr(module, "fold_split_sha256", lambda *_args: "split-hash")
    monkeypatch.setattr(module, "fold_identity_sha256", lambda *_args: "fold-hash")
    monkeypatch.setattr(module, "load_walk_forward_progress", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        module,
        "build_walk_forward_progress",
        lambda **kwargs: {
            "status": "complete",
            "folds": list(kwargs["folds"].values()),
            "splits": len(kwargs["expected_fold_ids"]),
            "mean_sharpe": 0.5,
            "std_sharpe": 0.0,
        },
    )
    monkeypatch.setattr(
        module,
        "build_walkforward_fold_features",
        lambda *_args: (features.copy(), features.copy(), tmp_path / "fold-cache"),
    )
    monkeypatch.setattr(
        module, "attach_policy_market_context", lambda _bars, feat, *_args, **_kwargs: feat
    )
    monkeypatch.setattr(module, "publish_observation_memmap", lambda *_args: tmp_path / "obs.npy")
    monkeypatch.setattr(module, "ticks_covering", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module, "make_env", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(module, "build_agent", lambda *_args, **_kwargs: Model())
    monkeypatch.setattr(module, "build_eval_provider", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(module, "_setup_rngs", lambda _seed: None)
    monkeypatch.setattr(module, "eval_guardrail_kwargs", lambda _cfg: {})
    monkeypatch.setattr(module, "strategy_risk_ranges", lambda _cfg: ((0.01, 0.02), (1.0, 2.0)))
    monkeypatch.setattr(module, "max_loss_per_trade", lambda _cfg: 25.0)
    monkeypatch.setattr(module, "max_episode_steps", lambda _cfg: 100)
    monkeypatch.setattr(module, "strategy_from_cfg", lambda _cfg: ("strategy", None))
    monkeypatch.setattr(module, "fill_delay_ms", lambda _cfg: 0)
    monkeypatch.setattr(
        module,
        "_evaluate_final_split",
        lambda *_args, **kwargs: {
            "equity": [1000.0, 1010.0],
            "trades": [],
            "n_sessions": 1,
            "n_breach_sessions": 0,
            "completed_data_split": True,
            "survived_full_year": False,
        },
    )
    monkeypatch.setattr(
        module,
        "calculate_metrics",
        lambda *_args, **_kwargs: SimpleNamespace(
            sharpe=0.5, max_drawdown=0.0, total_return_pct=1.0, n_trades=0
        ),
    )
    monkeypatch.setattr(module, "evaluation_periods_per_year", lambda _cfg: 252.0)
    monkeypatch.setattr(module, "account_path_metric_inputs", lambda _result: {})
    monkeypatch.setattr(module, "strict_nonnegative_int", lambda value: max(0, int(value or 0)))
    monkeypatch.setattr(
        module,
        "_write_walk_forward_fold_receipt",
        lambda _path, **kwargs: fold_receipts.append(kwargs["record"]),
    )

    run_walk_forward_validation(
        args=Namespace(
            walk_forward=True,
            wf_splits=1,
            wf_steps=3,
            purge_bars=0,
            embargo_bars=0,
            algo="ppo",
            reward="default",
            use_vae=False,
            arch="mlp",
        ),
        timesteps=5,
        train_bars=bars,
        train_sec=None,
        cfg=cfg,
        cache_dir=tmp_path / "cache",
        primary_sym="US100",
        primary_ticks=None,
        schedule_path=tmp_path / "schedule.csv",
        feature_columns=["feature"],
        run_dir=run_dir,
        env_vae=None,
        pre_ny_by_date=None,
        device="cpu",
        vae_model=None,
        seed=42,
        only_fold=0,
    )

    saved_progress = json.loads((run_dir / "walk_forward.json").read_text(encoding="utf-8"))
    assert saved_progress["status"] == "complete"
    assert len(saved_progress["folds"]) == 1

    assert len(fold_receipts) == 1
    assert fold_receipts[0]["fold_identity_sha256"] == "fold-hash"
    assert fold_receipts[0]["policy_action_mode"] == "deterministic"
