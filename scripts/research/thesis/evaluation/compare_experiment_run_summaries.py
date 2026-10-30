#!/usr/bin/env python3
"""Generate a matched comparison from two experiment run summary JSON files."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def _load_summary(path: Path, *, variant: str) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected an experiment run summary object in {path}")
    jobs = value.get("jobs", [])
    matches = [job for job in jobs if job.get("variant") == variant]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one {variant!r} job in {path}")
    value["jobs"] = matches
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _metrics(
    summary: dict[str, Any], split: str
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    job = summary["jobs"][0]
    if split == "train":
        return job["train_metrics"], job["train_replay"], job.get("train_equity_gate", {})
    return job["test_metrics_report_only"], job["test_replay_report_only"], {}


def _check_match(control: dict[str, Any], treatment: dict[str, Any]) -> None:
    fields = (
        "requested_steps_per_variant",
        "seed",
        "n_envs",
        "data_source",
        "evaluation_protocol",
    )
    mismatches = [field for field in fields if control.get(field) != treatment.get(field)]
    if mismatches:
        raise ValueError("experiment runs are not matched for: " + ", ".join(mismatches))


def _fmt(value: Any, *, kind: str) -> str:
    if kind == "percent":
        return f"{float(value):.2f}%"
    if kind == "money":
        number = float(value)
        return f"-${abs(number):,.2f}" if number < 0 else f"${number:,.2f}"
    if kind == "ratio":
        return f"{float(value):.3f}"
    if kind == "count":
        return f"{int(value):,}"
    return str(value)


def _fmt_delta(value: float, *, kind: str) -> str:
    if kind == "percent":
        return f"{value:.3f} pp"
    return _fmt(value, kind=kind)


def render_comparison(control_path: Path, treatment_path: Path) -> str:
    """Return a compact train/test comparison with treatment-minus-control deltas."""
    variant = "sustainable_growth_ppo_dsr"
    control = _load_summary(control_path, variant=variant)
    treatment = _load_summary(treatment_path, variant=variant)
    _check_match(control, treatment)
    labels = (
        ("R0 control", control),
        ("R1 treatment", treatment),
    )
    lines = [
        "# Matched R0/R1 D1 normalization screen",
        "",
        "This is a one-seed development comparison. The 2026 split is report-only and had been inspected before this experiment; it is not confirmatory evidence.",
        "",
        "## Experiment run identity",
        "",
        "| Arm | Experiment run | Git revision | Fingerprint | Summary SHA-256 |",
        "|---|---|---|---|---|",
    ]
    for label, summary in labels:
        path = control_path if label == "R0 control" else treatment_path
        lines.append(
            "| {} | `{}` | `{}` | `{}` | `{}` |".format(
                label,
                summary["experiment_run_dir"].rstrip("/").split("/")[-1],
                summary.get("experiment_run_git_sha", "unavailable"),
                summary.get("experiment_run_fingerprint", "unavailable"),
                _sha256(path),
            )
        )
    lines.extend(
        [
            "",
            f"Matched settings: {control['requested_steps_per_variant']:,} steps per variant, seed {control['seed']}, {control['n_envs']} environments, data source `{control['data_source']}`, stochastic evaluation (`deterministic=false`).",
            "",
            "The only intended intervention is recorded in `matched_pair.json`: source-index normalization of selected D1 technical features before causal alignment. PPO, TCN, action schema, risk policy, dataset, split, seed, and training budget are otherwise matched.",
            "",
            "## Metrics",
            "",
            "Each delta is R1 minus R0. Training metrics are in-sample. Testing metrics come from the previously exposed report-only split.",
            "",
            "| Split | Metric | R0 | R1 | Delta |",
            "|---|---|---:|---:|---:|",
        ]
    )
    specs = (
        ("total_return_pct", "Net return", "percent"),
        ("total_pnl", "Net PnL", "money"),
        ("max_drawdown", "Maximum drawdown", "percent", 100.0),
        ("sharpe", "Sharpe", "ratio"),
        ("profit_factor", "Profit factor", "ratio"),
        ("win_rate", "Win rate", "percent", 100.0),
        ("expectancy", "Expectancy per trade", "money"),
        ("n_trades", "Trades", "count"),
    )
    for split in ("train", "test"):
        control_job = control["jobs"][0]
        treatment_job = treatment["jobs"][0]
        control_metrics, control_replay, control_gate = _metrics(control, split)
        treatment_metrics, treatment_replay, treatment_gate = _metrics(treatment, split)
        for spec in specs:
            key, label, kind, *scale = spec
            factor = scale[0] if scale else 1.0
            left = float(control_metrics[key]) * factor
            right = float(treatment_metrics[key]) * factor
            lines.append(
                f"| {split.capitalize()} | {label} | {_fmt(left, kind=kind)} | "
                f"{_fmt(right, kind=kind)} | {_fmt_delta(right - left, kind=kind)} |"
            )
        left_days = f"{control_replay['days_traded']}/{control_replay['days_total']}"
        right_days = f"{treatment_replay['days_traded']}/{treatment_replay['days_total']}"
        lines.append(
            f"| {split.capitalize()} | Days traded / available | {left_days} | {right_days} | — |"
        )
        lines.append(
            f"| {split.capitalize()} | Full-period survival | "
            f"{'Yes' if control_replay['survived_full_period'] else 'No'} | "
            f"{'Yes' if treatment_replay['survived_full_period'] else 'No'} | — |"
        )
        if split == "train":
            lines.append(
                f"| Train | Risk gate | {control_gate.get('reason', 'unknown')} | "
                f"{treatment_gate.get('reason', 'unknown')} | — |"
            )
    lines.extend(
        [
            "",
            "## Coverage and interpretation limits",
            "",
            "| Measure | R0 | R1 |",
            "|---|---:|---:|",
            f"| Full training-split episodes | {control_job['training_episode_coverage']['full_split_episode_count']} | {treatment_job['training_episode_coverage']['full_split_episode_count']} |",
            f"| Environments with a full-split episode | {control_job['training_episode_coverage']['environments_with_full_split_episode']} | {treatment_job['training_episode_coverage']['environments_with_full_split_episode']} |",
            "",
            "This single-seed screen can show whether restoring D1 feature availability changed this run. It cannot establish statistical superiority or prove that feature availability caused any metric difference. See the full generated R1 report and the R1 causal regime attribution for trade-level evidence.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control", type=Path, required=True)
    parser.add_argument("--treatment", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = render_comparison(args.control, args.treatment)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
