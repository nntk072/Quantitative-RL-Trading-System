"""Final evaluation artifact writers for training runs."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from artifacts.atomic import write_text_atomic
from evaluation.reporting.run_summary import performance_metrics_payload
from training.artifacts.flags import strict_nonnegative_int
from training.callbacks.activity import assess_train_activity, classify_zero_trade_cause


def write_evaluation_artifacts(
    *,
    run_dir: Path,
    seed: int,
    completed_timesteps: int,
    train_result: dict[str, Any],
    test_result: dict[str, Any],
    train_metrics: Any,
    test_metrics: Any,
    train_gate: dict[str, Any],
    train_activity_gate: dict[str, Any],
    account_currency: str,
    survival_objective: bool = False,
    training_completed: bool = True,
    training_incomplete_reason: str | None = None,
) -> None:
    """Write an explicit train/test evaluation report with unambiguous roles.

    Args:
        run_dir: Text or path value identifying the run dir.
        seed: Random seed used to make sampling reproducible.
        completed_timesteps: Numeric value used for the completed timesteps.
        train_result: Key-value data used for the train result.
        test_result: Key-value data used for the test result.
        train_metrics: Train metrics used by the operation described above.
        test_metrics: Test metrics used by the operation described above.
        train_gate: Key-value data used for the train gate.
        train_activity_gate: Key-value data used for the train activity gate.
        account_currency: Text or path value identifying the account currency.
        survival_objective: Whether this evaluation is part of survival qualification.
        training_completed: Whether learner fitting reached its requested endpoint.
        training_incomplete_reason: Reason provided when fitting stopped early.
    """
    evaluation_dir = run_dir / "evaluations"
    evaluation_dir.mkdir(parents=True, exist_ok=True)

    def split_payload(
        role: str,
        result: dict[str, Any],
        metrics: Any,
        *,
        activity_status: str,
    ) -> dict[str, Any]:
        """Build one split's role-tagged metrics and activity record.

        Args:
            role: Text or path value identifying the role.
            result: Key-value data used for the result.
            metrics: Metrics used by the operation described above.
            activity_status: Text or path value identifying the activity status.

        Returns:
            Mapping from ``str`` keys to ``Any`` values.
        """
        return {
            "role": role,
            "policy_action_mode": str(result.get("policy_action_mode", "stochastic")),
            "action_rng_seed": result.get("action_rng_seed"),
            "seed": int(seed),
            "completed_training_timesteps": int(completed_timesteps),
            "account_currency": str(account_currency),
            "metrics": performance_metrics_payload(metrics),
            "activity_status": activity_status,
            "n_sessions": int(result.get("n_sessions", 0)),
            "days_traded": int(result.get("days_traded", 0)),
            "survived_full_year": result.get("survived_full_year") is True,
            "completed_data_split": result.get("completed_data_split") is True,
            "episode_end_reason": result.get("episode_end_reason"),
            "fail_time": (
                str(result["fail_time"]) if result.get("fail_time") is not None else None
            ),
            "max_trailing_dd": float(result.get("max_trailing_dd", metrics.max_drawdown)),
            "peak_eod_trailing_dd_limit_usd": float(
                result.get("peak_eod_trailing_dd_limit_usd", 0.0)
            ),
            "max_peak_eod_trailing_dd_usd": float(result.get("max_peak_eod_trailing_dd_usd", 0.0)),
            "peak_eod_dd_policy_ok": result.get("peak_eod_dd_policy_ok") is True,
            "breach_events": strict_nonnegative_int(result.get("n_breach_sessions")),
            "entry_diagnostics": result.get("entry_diag", {}),
        }

    train_payload = split_payload(
        "in_sample_training_evaluation",
        train_result,
        train_metrics,
        activity_status=str(train_activity_gate["status"]),
    )
    test_activity = assess_train_activity(int(test_metrics.n_trades))
    test_payload = split_payload(
        "report_only_test_evaluation",
        test_result,
        test_metrics,
        activity_status=str(test_activity["status"]),
    )
    test_payload["oos_role"] = (
        "previously_inspected_holdout; report-only; not pristine confirmation"
    )
    train_payload["equity_gate"] = train_gate
    train_payload["activity_gate"] = train_activity_gate
    peak_dd_limit = float(train_gate.get("peak_trailing_dd_limit", 0.0))
    peak_dd_observed = float(train_gate.get("max_peak_trailing_dd", 0.0))
    peak_dd_enabled = peak_dd_limit > 0.0
    peak_dd_policy_ok = not peak_dd_enabled or peak_dd_observed <= peak_dd_limit
    hard_risk_ok = train_gate.get("hard_risk_ok") is True and train_gate.get("breached") is False
    complete_survival_path = (
        hard_risk_ok
        and train_payload["survived_full_year"] is True
        and train_payload["completed_data_split"] is True
        and train_payload["breach_events"] == 0
    )
    if survival_objective:
        training_admissible = training_completed is True and complete_survival_path
    else:
        training_admissible = (
            training_completed is True
            and train_gate.get("ok") is True
            and train_activity_gate.get("ok") is True
        )
    train_payload["training_phase"] = (
        "survival_qualification" if survival_objective else "portfolio_training"
    )
    train_payload["train_split_survival_ok"] = complete_survival_path
    train_payload["training_completed"] = training_completed is True
    train_payload["training_incomplete_reason"] = training_incomplete_reason
    train_payload["training_admissible"] = training_admissible
    train_payload["training_admissibility_scope"] = (
        "single_seed_train_split"
        if survival_objective
        else "single_training_split_equity_and_activity"
    )
    train_payload["training_admissibility_basis"] = (
        "completed_training_and_breach_free_train_split"
        if survival_objective
        else "completed_training_equity_gate_and_activity"
    )
    peak_dd_policy_fit = {
        "enabled": peak_dd_enabled,
        "status": "DISABLED" if not peak_dd_enabled else ("PASS" if peak_dd_policy_ok else "MISS"),
        "limit": peak_dd_limit,
        "observed": peak_dd_observed,
        "retraining_recommended": (
            not survival_objective and peak_dd_enabled and not peak_dd_policy_ok
        ),
    }
    train_payload["peak_dd_policy_fit"] = peak_dd_policy_fit
    eod_dd_limit = float(train_payload["peak_eod_trailing_dd_limit_usd"])
    eod_dd_observed = float(train_payload["max_peak_eod_trailing_dd_usd"])
    eod_dd_enabled = eod_dd_limit > 0.0
    eod_dd_policy_fit = {
        "enabled": eod_dd_enabled,
        "status": "DISABLED"
        if not eod_dd_enabled
        else ("PASS" if train_payload["peak_eod_dd_policy_ok"] else "MISS"),
        "limit_usd": eod_dd_limit,
        "observed_usd": eod_dd_observed,
        "retraining_recommended": (
            not survival_objective and eod_dd_enabled and not train_payload["peak_eod_dd_policy_ok"]
        ),
    }
    train_payload["peak_eod_dd_policy_fit"] = eod_dd_policy_fit
    test_eod_dd_limit = float(test_payload["peak_eod_trailing_dd_limit_usd"])
    test_eod_dd_enabled = test_eod_dd_limit > 0.0
    test_eod_dd_policy_fit = {
        "enabled": test_eod_dd_enabled,
        "status": "DISABLED"
        if not test_eod_dd_enabled
        else ("PASS" if test_payload["peak_eod_dd_policy_ok"] else "MISS"),
        "limit_usd": test_eod_dd_limit,
        "observed_usd": float(test_payload["max_peak_eod_trailing_dd_usd"]),
    }
    test_payload["peak_eod_dd_policy_fit"] = test_eod_dd_policy_fit
    train_payload["zero_trade_diagnosis"] = classify_zero_trade_cause(
        int(train_metrics.n_trades),
        train_result.get("entry_state_diagnostics"),
        train_result.get("entry_diag"),
    )
    test_payload["zero_trade_diagnosis"] = classify_zero_trade_cause(
        int(test_metrics.n_trades),
        test_result.get("entry_state_diagnostics"),
        test_result.get("entry_diag"),
    )
    write_text_atomic(
        evaluation_dir / "train_in_sample.json",
        json.dumps(train_payload, indent=2, default=str, allow_nan=True),
    )
    write_text_atomic(
        evaluation_dir / "test_report_only.json",
        json.dumps(test_payload, indent=2, default=str, allow_nan=True),
    )
    summary = {
        "schema_version": 3,
        "seed": int(seed),
        "completed_training_timesteps": int(completed_timesteps),
        "training_in_sample": train_payload,
        "test_report_only": test_payload,
        "train_equity_gate": train_gate,
        "peak_dd_policy_fit": peak_dd_policy_fit,
        "peak_eod_dd_policy_fit": eod_dd_policy_fit,
        "test_peak_eod_dd_policy_fit": test_eod_dd_policy_fit,
        "hard_risk_ok": hard_risk_ok,
        "training_completed": training_completed is True,
        "training_incomplete_reason": training_incomplete_reason,
        "train_activity_gate": train_activity_gate,
        "training_phase": "survival_qualification" if survival_objective else "portfolio_training",
        "train_split_survival_ok": complete_survival_path,
        "train_activity_ok": train_activity_gate.get("ok") is True,
        "training_admissible": training_admissible,
        "training_admissibility_scope": (
            "single_seed_train_split"
            if survival_objective
            else "single_training_split_equity_and_activity"
        ),
        "training_admissibility_basis": (
            "completed_training_and_breach_free_train_split"
            if survival_objective
            else "completed_training_equity_gate_and_activity"
        ),
        "zero_trade_diagnosis": train_payload["zero_trade_diagnosis"],
    }
    write_text_atomic(
        evaluation_dir / "summary.json", json.dumps(summary, indent=2, default=str, allow_nan=True)
    )

    def line(label: str, payload: dict[str, Any]) -> str:
        """Format one role's return, PnL, and risk metrics as a Markdown row.

        Args:
            label: Text or path value identifying the label.
            payload: Key-value data used for the payload.

        Returns:
            Text returned by ``line``.
        """
        metrics = payload["metrics"]

        def fmt(name: str, spec: str) -> str:
            """Render a finite metric value, using N/A for unavailable values.

            Args:
                name: Metric key in the report payload.
                spec: Python numeric format specification.

            Returns:
                Formatted metric text or ``N/A`` when the value is unavailable.
            """
            value = metrics.get(name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return "N/A"
            if not math.isfinite(float(value)):
                return "N/A"
            return format(float(value), spec)

        return (
            f"| {label} | {fmt('total_return_pct', '+.2f')}% | "
            f"{fmt('total_pnl', '+.2f')} {account_currency} | "
            f"{fmt('max_drawdown', '.2%')} | "
            f"{fmt('sharpe', '.3f')} | {fmt('profit_factor', '.3f')} | "
            f"{fmt('win_rate', '.1%')} | {metrics['n_trades']} |"
        )

    report = [
        "# Evaluation results",
        "",
        f"Seed: {seed}  ",
        f"Training steps completed: {completed_timesteps:,}",
        "",
        "The dashboard's periodic train-prefix monitor is a progress check. These are the two final replays.",
        (
            "Policy action mode: "
            f"train={train_payload['policy_action_mode']}, "
            f"test={test_payload['policy_action_mode']}; "
            f"action RNG seeds: train={train_payload['action_rng_seed']}, "
            f"test={test_payload['action_rng_seed']}."
        ),
        (
            "Peak EOD drawdown rule: "
            f"train limit=${train_payload['peak_eod_trailing_dd_limit_usd']:,.0f}, "
            f"observed=${train_payload['max_peak_eod_trailing_dd_usd']:,.2f} "
            f"({eod_dd_policy_fit['status']}); report-only test limit="
            f"${test_payload['peak_eod_trailing_dd_limit_usd']:,.0f}, observed="
            f"${test_payload['max_peak_eod_trailing_dd_usd']:,.2f} "
            f"({test_eod_dd_policy_fit['status']})."
        ),
        (
            "A peak EOD drawdown breach closes any open position and blocks entries "
            "until a later EOD equity high; it does not terminate the replay. "
            "The separate configured hard-loss guardrail controls replay termination."
        ),
        (
            "Both final replays use stochastic policy actions, matching PPO training."
            if train_payload["policy_action_mode"] == "stochastic"
            and test_payload["policy_action_mode"] == "stochastic"
            else "Final replay action mode is recorded separately for each split."
        ),
        "",
        f"| Evaluation | Return | Net PnL ({account_currency}) | Max drawdown | Sharpe | Profit factor | Win rate | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
        line("Train (in-sample)", train_payload),
        line("Test (report-only; previously inspected)", test_payload),
        "",
        f"Training phase: {'survival qualification' if survival_objective else 'portfolio training'}",
        f"Training complete: {'PASS' if training_completed else 'FAIL'}",
        (
            "Train-split survival: PASS"
            if survival_objective and complete_survival_path
            else "Train-split survival: FAIL"
            if survival_objective
            else "Train-split survival: not applicable"
        ),
        f"Train-split admissible: {'PASS' if training_admissible else 'FAIL'}",
        (
            "This report does not establish cross-seed and walk-forward qualification; "
            "the run-level survival_phase_gate.json is authoritative."
            if survival_objective
            else ""
        ),
        f"Hard-risk survival: {'PASS' if complete_survival_path else 'FAIL'}",
        (
            "Peak-DD training policy: DISABLED"
            if not peak_dd_enabled
            else (
                f"Peak-DD training policy: {'PASS' if peak_dd_policy_ok else 'MISS'} "
                f"(observed {peak_dd_observed:.2%}; limit {peak_dd_limit:.2%}). "
                + (
                    (
                        "This is a diagnostic and does not affect train-split survival."
                        if survival_objective
                        else "Training completed; another training iteration is recommended."
                    )
                    if not peak_dd_policy_ok
                    else ""
                )
            )
        ),
        (
            f"Train activity diagnostic: {train_activity_gate['status']} "
            f"(trades={train_activity_gate['n_trades']})"
            if survival_objective
            else f"Train activity gate: {train_activity_gate['status']} "
            f"(trades={train_activity_gate['n_trades']})"
        ),
        f"Zero-trade diagnosis: {train_payload['zero_trade_diagnosis'] or 'none'}",
        "",
        "The test split is report-only and must not be described as pristine confirmatory evidence.",
        "",
    ]
    write_text_atomic(evaluation_dir / "summary.md", "\n".join(report))
