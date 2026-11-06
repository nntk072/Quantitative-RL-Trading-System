"""Reusable training and evaluation lifecycle for configured ablations.

Trains each variant on the in-sample slice and scores the held-out OOS slice
through the shared evaluation pipeline (``build_run_report``), including any
``pnl_dist_*`` extras already produced by the main metrics stack.

"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from omegaconf import DictConfig

from evaluation import build_run_report, run_episode
from evaluation.rollout.trained_policy_rollout import make_action_fn
from training.setup.environments import make_env

_AVG_KEYS = (
    "sharpe",
    "sortino",
    "max_drawdown",
    "n_trades",
    "win_rate",
    "total_return_pct",
    "profit_factor",
    "breach_count",
    "breach_rate",
    # Tier 1 entry-state funnel: averaged so a collapsing FSM shows up as
    # zero/near-zero across seeds rather than being hidden in extras.
    "entry_opened",
    "entry_attempts",
    "entry_rejection_rate",
    "candidate_created",
    "candidate_expired",
    "candidate_invalidated",
    "trigger_requested",
    "trigger_refused",
    "entered",
    "closed",
    "armed_bars",
    "arm_to_trigger_rate",
    "trigger_refusal_rate",
)


@dataclass(frozen=True)
class VariantAblationRequest:
    """Inputs for one command-driven ablation run."""

    bars_csv: Path
    experiments: Path = Path("config/experiments.yaml")
    features_csv: Path | None = None
    rl_config: str | None = None
    steps: int | None = None
    seeds: tuple[int, ...] | None = None
    variants: tuple[str, ...] | None = None
    reward: str = "dsr"
    out_dir: Path = Path("outputs/ablations")
    allow_locked_oos_for_selection: bool = False


def evaluate_oos(
    model: Any,
    *,
    algo: str,
    bars: pd.DataFrame,
    features: pd.DataFrame,
    cfg: DictConfig,
    reward: str,
) -> dict[str, Any]:
    """Deterministic OOS episode scored via ``build_run_report``.

    Returns the report plus the raw env artifacts (trade log, entry
    diagnostics, FSM lifecycle) so the caller can write per-seed full
    artifacts for debugging without re-running the episode.

    Args:
        model: Model used for this operation.
        algo: Text or path value identifying the algo.
        bars: Market bars to process.
        features: Feature values supplied to the operation.
        cfg: Run configuration used by this operation.
        reward: Text or path value identifying the reward.

    Returns:
        Mapping from ``str`` keys to ``Any`` values.
    """
    env = make_env(bars, features, cfg, algo=algo, reward=reward, episodic=False)
    metrics = run_episode(
        env,
        action_fn=make_action_fn(model, continuous_actions=algo == "sac"),
    )
    report = build_run_report(metrics, env.trade_log)
    report["_artifacts"] = {
        "trade_log": list(getattr(env, "trade_log", [])),
        "entry_diag": dict(getattr(env, "_entry_diag", {})),
        "entry_state_diagnostics": (
            env.entry_state_diagnostics()
            if callable(getattr(env, "entry_state_diagnostics", None))
            else {}
        ),
    }
    return report


def train_and_score_variant(
    *,
    bars: pd.DataFrame,
    features: pd.DataFrame,
    base_cfg: DictConfig,
    variant: dict[str, Any],
    defaults: dict[str, Any],
    steps: int,
    seed: int,
    reward: str,
    train_end: str,
    test_start: str,
    out_dir: str,
    name: str,
) -> dict[str, Any]:
    """Reject this retired ungated training path.

    The former implementation trained each variant directly with
    ``model.learn`` and could score exposed report-period rows without first
    passing the cross-seed survival gate. Its configuration cannot express the
    full-split and per-seed walk-forward qualification contract.

    Args:
        bars: Market bars accepted by the retired interface.
        features: Feature rows accepted by the retired interface.
        base_cfg: Base run configuration accepted by the retired interface.
        variant: Variant settings accepted by the retired interface.
        defaults: Variant defaults accepted by the retired interface.
        steps: Training-step count accepted by the retired interface.
        seed: Random seed accepted by the retired interface.
        reward: Reward selector accepted by the retired interface.
        train_end: Training boundary accepted by the retired interface.
        test_start: Evaluation boundary accepted by the retired interface.
        out_dir: Output directory accepted by the retired interface.
        name: Variant name accepted by the retired interface.

    Returns:
        This function never returns; it raises ``SystemExit`` with the supported workflow.
    """
    del (
        bars,
        features,
        base_cfg,
        variant,
        defaults,
        steps,
        seed,
        reward,
        train_end,
        test_start,
        out_dir,
        name,
    )
    raise SystemExit(
        "variant ablation training is retired because it bypasses survival-first "
        "qualification; use training.runner.training with the survival reward and "
        "a complete survival gate before portfolio optimization"
    )


def _flatten_report_metrics(report: dict[str, Any]) -> dict[str, Any]:
    """Lift ``extras`` scalar keys (e.g. ``pnl_dist_*``) to the top level.

    Args:
        report: Key-value data used for the report.

    Returns:
        Mapping from ``str`` keys to ``Any`` values.
    """
    flat = dict(report)
    extras = report.get("extras")
    if isinstance(extras, dict):
        for key, val in extras.items():
            if key not in flat:
                flat[key] = val
    return flat


def _average_seed_reports(seed_reports: list[dict[str, Any]]) -> dict[str, Any]:
    """Mean numeric metrics over successful seed reports.

    Args:
        seed_reports: Items supplied for the seed reports, in input order.

    Returns:
        Mapping from ``str`` keys to ``Any`` values.
    """
    ok = [_flatten_report_metrics(r) for r in seed_reports if r.get("status") == "ok"]
    if not ok:
        return {"status": "all_skipped", "n_ok": 0}
    averaged: dict[str, Any] = {"status": "ok", "n_ok": len(ok)}
    for key in _AVG_KEYS:
        vals = [float(r[key]) for r in ok if key in r and r[key] is not None]
        if vals:
            averaged[key] = round(sum(vals) / len(vals), 4)
    # Preserve distributional extras when present on every ok seed.
    dist_keys = sorted(
        {k for r in ok for k in r if isinstance(k, str) and k.startswith("pnl_dist_")}
    )
    for key in dist_keys:
        vals = [float(r[key]) for r in ok if key in r and isinstance(r[key], (int, float))]
        if len(vals) == len(ok):
            averaged[key] = round(sum(vals) / len(vals), 4)
    return averaged


def load_experiments(path: Path) -> dict[str, Any]:
    """Load the experiments YAML as a plain dict.

    Args:
        path: Path to the input file or directory.

    Returns:
        Mapping from ``str`` keys to ``Any`` values.
    """
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict):
        raise ValueError(f"expected mapping in {path}")
    return raw


def run_variant_ablation(request: VariantAblationRequest) -> None:
    """Reject the retired ungated variant-training command.

    Args:
        request: Request used by the operation described above.
    """
    del request
    raise SystemExit(
        "qrl-experiment variants is retired because it bypasses survival-first "
        "qualification and can rank on exposed report data; use the canonical "
        "training and experiment run workflows"
    )
