from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts.research.analysis.evaluation.compare_experiment_run_summaries import render_comparison


def _summary(
    experiment_run: str, *, steps: int = 2000, returned: float = -2.0
) -> dict[str, object]:
    metrics = {
        "total_return_pct": returned,
        "total_pnl": returned * 1000,
        "max_drawdown": 0.1,
        "sharpe": -0.5,
        "profit_factor": 0.9,
        "win_rate": 0.4,
        "expectancy": -10.0,
        "n_trades": 10,
    }
    return {
        "experiment_run_dir": f"/experiment_runs/{experiment_run}",
        "experiment_run_git_sha": "abc123",
        "experiment_run_fingerprint": experiment_run,
        "requested_steps_per_variant": steps,
        "seed": 50,
        "n_envs": 8,
        "data_source": "bundle",
        "evaluation_protocol": {"deterministic": False, "selection_allowed": False},
        "training_episode_coverage_summary": {
            "full_split_episode_count": 999,
            "environments_with_full_split_episode": 99,
        },
        "jobs": [
            {
                "variant": "sustainable_growth_ppo_dsr",
                "training_episode_coverage": {
                    "full_split_episode_count": 16,
                    "environments_with_full_split_episode": 8,
                },
                "train_metrics": metrics,
                "test_metrics_report_only": metrics,
                "train_replay": {
                    "days_traded": 100,
                    "days_total": 200,
                    "survived_full_period": False,
                },
                "test_replay_report_only": {
                    "days_traded": 80,
                    "days_total": 100,
                    "survived_full_period": False,
                },
                "train_equity_gate": {"reason": "max_loss_stopped_trading"},
            }
        ],
    }


def _write_summary(path: Path, value: dict[str, object]) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_render_comparison_shows_provenance_and_treatment_deltas(tmp_path: Path) -> None:
    control = _write_summary(tmp_path / "control.json", _summary("r0", returned=-2.0))
    treatment = _write_summary(tmp_path / "treatment.json", _summary("r1", returned=-1.0))

    report = render_comparison(control, treatment)

    assert "Matched R0/R1 D1 normalization screen" in report
    assert "| Train | Net return | -2.00% | -1.00% | 1.000 pp |" in report
    assert "| Train | Net PnL | -$2,000.00 | -$1,000.00 | $1,000.00 |" in report
    assert "max_loss_stopped_trading" in report
    assert "Summary SHA-256" in report
    assert "| Full training-split episodes | 16 | 16 |" in report
    assert "| Environments with a full-split episode | 8 | 8 |" in report


def test_render_comparison_rejects_mismatched_training_budgets(tmp_path: Path) -> None:
    control = _write_summary(tmp_path / "control.json", _summary("r0"))
    treatment = _write_summary(tmp_path / "treatment.json", _summary("r1", steps=3000))

    with pytest.raises(ValueError, match="requested_steps_per_variant"):
        render_comparison(control, treatment)
