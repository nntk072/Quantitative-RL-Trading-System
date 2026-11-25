"""Focused lifecycle and report-only safety contracts for per-seed training."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from training.runner import seed_runtime


def test_development_only_seed_cannot_evaluate_report_only_split() -> None:
    runner: Any = object.__new__(seed_runtime.SeedRunner)
    runner.development_only = True

    with pytest.raises(
        RuntimeError, match="development-only runs must not evaluate the report-only split"
    ):
        runner.evaluate_test_split()


def test_test_split_evaluation_requires_a_decision_provider() -> None:
    runner: Any = object.__new__(seed_runtime.SeedRunner)
    runner.development_only = False
    runner.context = SimpleNamespace(
        preparation=SimpleNamespace(configuration=SimpleNamespace(cfg=SimpleNamespace()))
    )
    runner.seed = 42
    runner.provider = None

    with pytest.raises(RuntimeError, match="decision provider was not created for evaluation"):
        runner.evaluate_test_split()


def test_test_split_evaluation_requires_a_saved_final_checkpoint() -> None:
    runner: Any = object.__new__(seed_runtime.SeedRunner)
    runner.development_only = False
    runner.context = SimpleNamespace(
        preparation=SimpleNamespace(
            configuration=SimpleNamespace(cfg=SimpleNamespace()),
            run_assets=SimpleNamespace(test_eval_spec=None),
            data=SimpleNamespace(test_bars=None, test_feat=None, primary_ticks=None),
        )
    )
    runner.seed = 42
    runner.provider = object()
    runner.phase_timings_seconds = {}
    runner.eval_common = {}
    runner.model_path = None

    with pytest.raises(RuntimeError, match="learner did not produce a final checkpoint path"):
        runner.evaluate_test_split()


@pytest.mark.parametrize("selected_seeds", [[], [99]])
def test_seed_subset_rejects_empty_or_unconfigured_work_before_training(
    monkeypatch: pytest.MonkeyPatch, selected_seeds: list[int]
) -> None:
    context: Any = SimpleNamespace(
        preparation=SimpleNamespace(run_assets=SimpleNamespace(seeds=[7, 11, 23]))
    )
    constructed_seeds: list[int] = []

    class RecordingSeedRunner:
        def __init__(self, _context: Any, seed: int) -> None:
            constructed_seeds.append(seed)
            self.seed = seed
            self.timesteps = 100

        def run(self) -> dict[str, int]:
            return {"seed": self.seed}

    monkeypatch.setattr(seed_runtime, "SeedRunner", RecordingSeedRunner)

    with pytest.raises(
        ValueError, match="selected seed work must be a non-empty subset of the configured seeds"
    ):
        seed_runtime.run_seed_training(context, selected_seeds=selected_seeds)

    assert constructed_seeds == []


def test_seed_subset_runs_configured_order_and_returns_last_seed_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context: Any = SimpleNamespace(
        preparation=SimpleNamespace(run_assets=SimpleNamespace(seeds=[7, 11, 23]))
    )
    constructed_seeds: list[int] = []

    class RecordingSeedRunner:
        def __init__(self, _context: Any, seed: int) -> None:
            constructed_seeds.append(seed)
            self.seed = seed
            self.timesteps = seed * 1_000

        def run(self) -> dict[str, int]:
            return {"seed": self.seed}

    monkeypatch.setattr(seed_runtime, "SeedRunner", RecordingSeedRunner)

    results, timesteps = seed_runtime.run_seed_training(context, selected_seeds=[23, 7])

    assert constructed_seeds == [7, 23]
    assert results == [{"seed": 7}, {"seed": 23}]
    assert timesteps == 23_000


@pytest.mark.parametrize(
    ("development_only", "allow_selection", "test_result", "expected_role"),
    [
        (True, True, None, "development_only"),
        (
            False,
            False,
            {"entry_diag": {"eligible": 4}, "entry_state_diagnostics": {"valid": True}},
            "final_report_only",
        ),
        (
            False,
            True,
            {"entry_diag": {"eligible": 4}, "entry_state_diagnostics": {"valid": True}},
            "selection_acknowledged",
        ),
    ],
)
def test_build_result_preserves_oos_role_and_per_seed_risk_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    development_only: bool,
    allow_selection: bool,
    test_result: dict[str, Any] | None,
    expected_role: str,
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    cfg = SimpleNamespace(
        env={"strategy_actions": True, "trade_setup_actions": False, "agent_entry_execution": 1}
    )
    runner: Any = object.__new__(seed_runtime.SeedRunner)
    runner.context = SimpleNamespace(
        preparation=SimpleNamespace(
            configuration=SimpleNamespace(
                args=SimpleNamespace(allow_locked_oos_for_selection=allow_selection), cfg=cfg
            ),
            run_assets=SimpleNamespace(run_dir=run_dir),
        )
    )
    runner.seed = 42
    runner.train_env = object()
    runner.model = SimpleNamespace(num_timesteps=1234)
    runner.test_result = test_result
    runner.test_m = None
    runner.train_result = {"survived_full_year": False, "n_breach_sessions": 1}
    runner.train_m = None
    runner.train_gate = {"hard_risk_ok": False, "reason": "daily_loss"}
    runner.train_activity_gate = {"status": "INACTIVE"}
    runner.best_checkpoint_callback = SimpleNamespace(
        best_checkpoint_status="none", best_n_trades=0, viability_eval_history=[]
    )
    runner.abort_reason = "daily_loss"
    runner.sequence_feature_schema = {"columns": ["close"]}
    runner.phase_timings_seconds = {"ppo_learn": 1.25}
    runner.manifest_path = run_dir / "manifest.json"
    runner.development_only = development_only
    monkeypatch.setattr(seed_runtime, "get_action_space_width", lambda _env: 5)
    monkeypatch.setattr(seed_runtime, "action_schema_manifest", lambda _env: {"width": 5})
    monkeypatch.setattr(seed_runtime, "observation_account_dim", lambda _env: 2)
    monkeypatch.setattr(seed_runtime, "observation_space_shapes", lambda _env: {"policy": [7]})
    monkeypatch.setattr(seed_runtime, "observation_schema_manifest", lambda _env: {"width": 7})

    result = runner.build_result()

    assert result["oos_role"] == expected_role
    assert result["train_result"] == {"survived_full_year": False, "n_breach_sessions": 1}
    assert result["train_gate"] == {"hard_risk_ok": False, "reason": "daily_loss"}
    assert result["env_flags"]["strategy_actions"] is True
    assert result["env_flags"]["trade_setup_actions"] is False
    assert result["env_flags"]["agent_entry_execution"] is True
    assert result["model_num_timesteps"] == 1234
    assert result["run_manifest"] == "manifest.json"
    if test_result is None:
        assert result["entry_diag"] == {}
        assert result["entry_state_diagnostics"] == {}
    else:
        assert result["entry_diag"] == {"eligible": 4}
        assert result["entry_state_diagnostics"] == {"valid": True}
