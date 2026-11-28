"""Formatting and serialization for descriptive experiment-run reports."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def _fmt_percent(value: Any) -> str:
    """Process percent.

    Args:
        value: Value to process.

    Returns:
        Text returned by ``_fmt_percent``.
    """
    if not isinstance(value, (int, float)):
        return "—"
    return f"{value:+.2f}%"


def _fmt_money(value: Any) -> str:
    """Process money.

    Args:
        value: Value to process.

    Returns:
        Text returned by ``_fmt_money``.
    """
    return f"{value:+,.2f}" if isinstance(value, (int, float)) else "—"


def render_markdown(summary: dict[str, Any]) -> str:
    """Render an experiment-run summary without ranking its variants.

    Args:
        summary: Mapping produced by :func:`build_summary`.

    Returns:
        Markdown tables and provenance notes for the run.
    """
    jobs = summary["jobs"]
    currencies = {job.get("account_currency") for job in jobs if job.get("account_currency")}
    pnl_label = next(iter(currencies)) if len(currencies) == 1 else "account currency"
    families = summary.get("comparison_families") or (
        [summary["variant_family"]] if isinstance(summary.get("variant_family"), dict) else []
    )
    if len(families) == 1:
        study_label = (
            f"**Study:** {families[0].get('title')} "
            f"({families[0].get('domain')}; {families[0].get('id')})"
        )
    elif families:
        study_label = "**Comparisons:** " + "; ".join(
            f"{family.get('title')} ({family.get('domain')}; {family.get('id')})"
            for family in families
        )
    else:
        study_label = "**Study:** ungrouped run"
    lines = [
        "# Experiment run results snapshot",
        "",
        study_label,
        f"**Controller status as of:** {summary.get('controller_status_as_of_utc')}",
        f"**Slurm job:** {summary.get('experiment_run_job_id')}  ",
        f"**Specification:** {summary.get('requested_steps_per_variant')} steps per variant; "
        f"seeds {', '.join(str(seed) for seed in summary.get('seeds', [])) or 'unknown'}"
        f"{'' if summary.get('seed_metadata_complete', False) else ' (incomplete metadata)'}; "
        f"{summary.get('n_envs')} environments; {summary.get('data_source')} backend.",
        f"**Evaluation role:** {summary.get('evaluation_protocol', {}).get('locked_oos_role')} "
        f"({summary.get('evaluation_protocol', {}).get('locked_oos_exposure')}).",
        "",
        "This is a descriptive snapshot, not a ranking. Training values are in-sample. Test values follow the declared evaluation role and do not become confirmatory without a valid holdout protocol and provenance.",
        "",
        "## Outcomes",
        "",
        f"- Controller counts: `{json.dumps(summary.get('controller_status_counts', {}), sort_keys=True)}`",
        f"- Train-equity gate failures with saved gate records: **{summary.get('gate_failure_count')} / {len(jobs)}**",
        "- Gate failure reasons (overlapping): "
        + (
            ", ".join(
                f"`{reason}` {count}/{len(jobs)}"
                for reason, count in summary.get("train_gate_failure_reason_counts", {}).items()
            )
            or "none recorded"
        ),
        f"- Test replays that did not survive the full period: **{summary.get('test_non_survival_count')} / {len(jobs)}**",
        f"- Test replays that survived with at most two trades: **{summary.get('test_survived_low_activity_count')} / {len(jobs)}**",
        f"- Split PnL reconciled against final equity: **{summary.get('pnl_reconciliation_counts', {}).get('verified', 0)} verified**, **{summary.get('pnl_reconciliation_counts', {}).get('mismatch', 0)} mismatched**, **{summary.get('pnl_reconciliation_counts', {}).get('unavailable', 0)} unavailable**",
        f"- Completed full-training-split episodes: **{summary.get('training_episode_coverage_summary', {}).get('full_split_episode_count', 0)}** across **{summary.get('training_episode_coverage_summary', {}).get('environments_with_full_split_episode', 0)} environments**; telemetry available for **{summary.get('training_episode_coverage_summary', {}).get('telemetry_available_runs', 0)} / {len(jobs)} runs**",
        "",
        "## Per-variant metrics",
        "",
        f"PnL is in the account currency ({pnl_label}). `Survived / days` comes from the matching worker log.",
        "",
        f"| Comparison arms | Variant | Controller | Attempt / failure | Train survival | Full-year episodes | Envs reached year end | Train return | Train PnL ({pnl_label}) | Train trades | Test return | Test PnL ({pnl_label}) | Test max DD | Test Sharpe | Test PF | Test trades | Test survived / days | Evidence |",
        "|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for job in jobs:
        train = job.get("train_metrics") or {}
        test = job.get("test_metrics_report_only") or {}
        gate = job.get("train_equity_gate") or {}
        coverage = job.get("training_episode_coverage") or {}
        replay = job.get("test_replay_report_only") or {}
        days = "—"
        if replay.get("days_traded") is not None and replay.get("days_total") is not None:
            days = f"{replay['days_traded']}/{replay['days_total']}"
        survived = replay.get("survived_full_period")
        survived_label = "—" if survived is None else ("yes" if survived else "no")
        failure_reason = job.get("failure_reason")
        if failure_reason:
            failure_detail = str(failure_reason).replace("|", "\\|").replace("\n", " ").strip()
            if len(failure_detail) > 180:
                failure_detail = failure_detail[:177] + "..."
        elif job.get("controller_status") in {"failed", "interrupted"}:
            failure_detail = f"exit {job.get('exit_code')}"
        else:
            failure_detail = "—"
        attempt_failure = f"{job.get('attempt', '—')} — {failure_detail}"
        evidence_links: list[str] = []
        worker_log = job.get("worker_log")
        if worker_log:
            evidence_links.append(f"[worker log](../{worker_log})")
        episode_artifact = coverage.get("artifact")
        if episode_artifact:
            evidence_links.append(f"[episode coverage](../{episode_artifact})")
        run_artifact_dir = job.get("run_artifact_dir")
        if run_artifact_dir:
            evidence_links.append(f"[run files](../{run_artifact_dir})")
            evaluation_summary = (
                Path(summary["experiment_run_dir"])
                / run_artifact_dir
                / "evaluations"
                / "summary.md"
            )
            if evaluation_summary.is_file():
                evidence_links.append(
                    f"[train/test evaluation](../{run_artifact_dir}/evaluations/summary.md)"
                )
        evidence = " · ".join(evidence_links) or "—"
        comparison_arms = (
            ", ".join(
                f"{membership.get('family_id')}:{membership.get('arm_label')}"
                for membership in job.get("family_memberships", [])
            )
            or "—"
        )
        lines.append(
            "| {comparisons} | {variant} | {status} | {attempt_failure} | {gate} | {full_year} | {full_year_envs} | {tr} | {tpnl} | {tn} | {er} | {epnl} | {edd} | {esharpe} | {epf} | {en} | {survived} / {days} | {evidence} |".format(
                comparisons=comparison_arms,
                variant=job.get("variant") or job.get("run_key"),
                status=job.get("controller_status", "—"),
                attempt_failure=attempt_failure,
                gate="PASS"
                if gate.get("ok") is True
                else "FAIL"
                if gate.get("ok") is False
                else "—",
                full_year=coverage.get("full_split_episode_count", "—")
                if coverage.get("status") == "available"
                else "unavailable",
                full_year_envs=coverage.get("environments_with_full_split_episode", "—")
                if coverage.get("status") == "available"
                else "unavailable",
                tr=_fmt_percent(train.get("total_return_pct")),
                tpnl=_fmt_money(train.get("total_pnl")),
                tn=train.get("n_trades", "—"),
                er=_fmt_percent(test.get("total_return_pct")),
                epnl=_fmt_money(test.get("total_pnl")),
                edd=(
                    f"{100 * test['max_drawdown']:.2f}%"
                    if isinstance(test.get("max_drawdown"), (int, float))
                    else "—"
                ),
                esharpe=f"{test['sharpe']:.3f}"
                if isinstance(test.get("sharpe"), (int, float))
                else "—",
                epf=f"{test['profit_factor']:.3f}"
                if isinstance(test.get("profit_factor"), (int, float))
                else "—",
                en=test.get("n_trades", "—"),
                survived=survived_label,
                days=days,
                evidence=evidence,
            )
        )
    lines.extend(
        [
            "",
            "## Resource samples",
            "",
        ]
    )
    for profile in summary.get("resource_profiles", []):
        lines.extend(
            [
                f"- `{profile['resource_csv']}`: {profile['active_sample_count']} active of {profile['sample_count']} samples; process-tree PSS mean {profile['active_process_tree_pss_mean_gib']:.1f} GiB and peak {profile['active_process_tree_pss_peak_gib']:.1f} GiB.",
                "- Per-device GPU utilization and memory are reconstructed from the sampler's raw two-row `nvidia-smi` output; the CSV does not have separate per-device columns. This sampler did not record process-tree CPU time or allocation-wide cgroup memory scope.",
            ]
        )
        for device in profile["gpu_devices"]:
            if device["sample_count"]:
                lines.append(
                    f"- GPU {device['device_index']}: mean utilization {device['mean_utilization_pct']:.1f}%, peak {device['peak_utilization_pct']}%; memory mean {device['mean_memory_used_mib']:.0f} MiB, peak {device['peak_memory_used_mib']} MiB."
                )
    lines.extend(
        [
            "",
            "## Reproducibility and limits",
            "",
            f"- Experiment run manifest SHA-256: `{summary.get('experiment_run_manifest_sha256')}`",
            f"- Controller status SHA-256: `{summary.get('controller_status_sha256')}`",
            f"- Summary script SHA-256: `{summary.get('summary_script_sha256')}`",
            "- Profit and trade counts are reported as metrics. The train survival gate covers risk-limit breach and peak trailing drawdown; evidence hashes are listed in the adjacent JSON file.",
            "- Launch-time source-hash comparison with the current repository is recorded in [the source-fidelity audit](source_fidelity_audit.md).",
            f"- This report covers the declared {summary.get('requested_steps_per_variant')} steps per variant and experiment run data role. It cannot establish statistical significance or strategy viability beyond the evidence and seeds shown above.",
            "- Do not select a variant from this report. Preserve all failed gates and low/no-trade outcomes.",
            "",
        ]
    )
    return "\n".join(lines)


def _write_summary_outputs(summary: dict[str, Any], out_stem: Path) -> tuple[Path, Path, Path]:
    """Write tabular and readable summaries without replacing prior run evidence.

    Args:
        summary: Key-value data used for the summary.
        out_stem: Text or path value identifying the out stem.

    Returns:
        Markdown, JSON, and CSV report paths.
    """
    json_path = out_stem.with_suffix(".json")
    markdown_path = out_stem.with_suffix(".md")
    csv_path = out_stem.with_suffix(".csv")
    existing = [path for path in (json_path, markdown_path, csv_path) if path.exists()]
    if existing:
        raise FileExistsError(
            "refusing to overwrite experiment run summary artifact(s): "
            + ", ".join(str(path) for path in existing)
        )
    out_stem.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(summary), encoding="utf-8")
    columns = (
        "experiment_run_id",
        "experiment_run_git_sha",
        "experiment_run_fingerprint",
        "experiment_run_manifest_sha256",
        "data_identity_sha256",
        "data_source",
        "requested_steps_per_variant",
        "n_envs",
        "evaluation_role",
        "domain",
        "family_id",
        "family_title",
        "comparison_type",
        "variant",
        "arm_label",
        "arm_role",
        "changed_factors",
        "run_key",
        "seed",
        "controller_status",
        "failure_reason",
        "account_currency",
        "train_return_pct",
        "train_pnl",
        "train_trades",
        "test_return_pct",
        "test_pnl",
        "test_max_drawdown",
        "test_sharpe",
        "test_profit_factor",
        "test_trades",
        "test_survived_full_period",
        "test_days_traded",
        "test_days_total",
        "train_pnl_reconciliation",
        "test_pnl_reconciliation",
        "evidence_sha256",
    )
    with csv_path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for job in summary["jobs"]:
            train = job.get("train_metrics") or {}
            test = job.get("test_metrics_report_only") or {}
            replay = job.get("test_replay_report_only") or {}
            memberships = job.get("family_memberships")
            if not isinstance(memberships, list) or not memberships:
                memberships = [_family_metadata(None, None)]
            for membership in memberships:
                writer.writerow(
                    {
                        **job,
                        **membership,
                        "experiment_run_id": summary.get("experiment_run_id"),
                        "experiment_run_git_sha": summary.get("experiment_run_git_sha"),
                        "experiment_run_fingerprint": summary.get("experiment_run_fingerprint"),
                        "experiment_run_manifest_sha256": summary.get(
                            "experiment_run_manifest_sha256"
                        ),
                        "data_identity_sha256": summary.get("data_identity_sha256"),
                        "data_source": summary.get("data_source"),
                        "requested_steps_per_variant": summary.get("requested_steps_per_variant"),
                        "n_envs": summary.get("n_envs"),
                        "evaluation_role": summary.get("evaluation_protocol", {}).get(
                            "locked_oos_role"
                        ),
                        "changed_factors": "; ".join(membership.get("changed_factors", [])),
                        "evidence_sha256": json.dumps(
                            job.get("evidence_sha256", {}), sort_keys=True, separators=(",", ":")
                        ),
                        "train_return_pct": train.get("total_return_pct"),
                        "train_pnl": train.get("total_pnl"),
                        "train_trades": train.get("n_trades"),
                        "test_return_pct": test.get("total_return_pct"),
                        "test_pnl": test.get("total_pnl"),
                        "test_max_drawdown": test.get("max_drawdown"),
                        "test_sharpe": test.get("sharpe"),
                        "test_profit_factor": test.get("profit_factor"),
                        "test_trades": test.get("n_trades"),
                        "test_survived_full_period": replay.get("survived_full_period"),
                        "test_days_traded": replay.get("days_traded"),
                        "test_days_total": replay.get("days_total"),
                        "train_pnl_reconciliation": json.dumps(
                            job.get("train_pnl_reconciliation", {}),
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                        "test_pnl_reconciliation": json.dumps(
                            job.get("test_pnl_reconciliation", {}),
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                    }
                )
    return markdown_path, json_path, csv_path


def _family_metadata(family: Any, arm: Any) -> dict[str, Any]:
    """Attach the declared study domain and treatment factors to a result row.

    Args:
        family: Registered comparison-family record, when available.
        arm: Registered treatment-arm record, when available.

    Returns:
        Stable family, arm, and changed-factor metadata for the row.
    """
    if not isinstance(family, dict) or not isinstance(arm, dict):
        return {
            "family_id": None,
            "domain": None,
            "family_title": None,
            "comparison_type": None,
            "arm_label": None,
            "arm_role": None,
            "changed_factors": [],
        }
    return {
        "family_id": family.get("id"),
        "domain": family.get("domain"),
        "family_title": family.get("title"),
        "comparison_type": family.get("comparison_type"),
        "arm_label": arm.get("label"),
        "arm_role": arm.get("role"),
        "changed_factors": arm.get("changed_factors", []),
    }
