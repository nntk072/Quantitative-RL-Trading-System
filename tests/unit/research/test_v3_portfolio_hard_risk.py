import json
from pathlib import Path

from scripts.research.audits.verify_v3_portfolio_hard_risk import verify_run


def test_portfolio_hard_risk_requires_complete_zero_breach_path(tmp_path: Path) -> None:
    run = tmp_path / "run"
    eval_dir = run / "evaluations"
    eval_dir.mkdir(parents=True)
    (eval_dir / "summary.json").write_text(
        json.dumps(
            {
                "seed": 42,
                "training_phase": "portfolio_training",
                "training_completed": True,
                "train_equity_gate": {"hard_risk_ok": True, "breached": False},
            }
        ),
        encoding="utf-8",
    )
    (eval_dir / "train_in_sample.json").write_text(
        json.dumps({"completed_data_split": True, "breach_events": 0}),
        encoding="utf-8",
    )
    assert verify_run(run)["status"] == "pass"
