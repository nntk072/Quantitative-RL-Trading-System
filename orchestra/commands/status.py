"""Inspection, reporting, and recovery commands for Orchestra tasks."""

from __future__ import annotations

import json
import sys
import time
from typing import Any

import click

from orchestra.backup import list_slots, resolve_slot, restore_snapshot
from orchestra.task_orchestration import WORKSPACE, Pipeline
from orchestra.task_state_store import TaskState, list_tasks

command_group = click.Group()


@command_group.command()
def stats() -> None:
    """Show model usage statistics."""
    pipeline = Pipeline()
    model_stats = pipeline.router.stats()
    click.echo("Model Usage Today")
    click.echo("=" * 60)
    for name, info in model_stats.items():
        quota_str = f"{info['remaining']:,}" if info["remaining"] >= 0 else "unlimited"
        click.echo(
            f"  {name:30s}  used={info['tokens_used']:>10,}  "
            f"calls={info['calls']:>4}  remaining={quota_str}  "
            f"available={'yes' if info['available'] else 'no'}"
        )


@command_group.command()
def roster() -> None:
    """Show available models and their capabilities."""
    pipeline = Pipeline()
    click.echo("Model Roster")
    click.echo("=" * 60)
    for model in sorted(pipeline.router.models, key=lambda m: m.priority):
        status = "available" if model.is_available() else "unavailable"
        esc = " [ESCALATION ONLY]" if model.escalation_only else ""
        # Mirror SessionManager.build_command: 'default' means no --model flag.
        if model.model_flag and model.name and model.name != "default":
            flag = f" {model.model_flag} {model.name}"
        else:
            flag = ""
        extra = f" {' '.join(model.extra_args)}" if model.extra_args else ""
        # 'run' subcommand for one-shot non-interactive execution.
        verb = " run" if model.cli in ("opencode", "kilo") else ""
        click.echo(
            f"  {model.display_name:30s}  cli=`{model.cli}{verb}{flag}{extra}`  "
            f"roles={','.join(model.roles)}  "
            f"priority={model.priority}  {status}{esc}"
        )


@command_group.command()
def tasks() -> None:
    """List all orchestra tasks."""
    state_dir = WORKSPACE / "outputs" / "orchestra" / "state"
    all_tasks = list_tasks(state_dir)
    if not all_tasks:
        click.echo("No tasks found.")
        return
    click.echo("Orchestra Tasks")
    click.echo("=" * 80)
    click.echo(f"  {'ID':20s}  {'Phase':15s}  {'Description':40s}")
    click.echo("-" * 80)
    for t in all_tasks:
        click.echo(f"  {t['task_id']:20s}  {t['phase']:15s}  {t['description']:40s}")


@command_group.command()
@click.argument("task_id")
def show(task_id: str) -> None:
    """Show details of a specific task."""
    state_dir = WORKSPACE / "outputs" / "orchestra" / "state"
    try:
        state = TaskState.load(task_id, state_dir)
    except FileNotFoundError:
        click.echo(f"Task {task_id} not found.", err=True)
        sys.exit(1)

    click.echo(f"Task: {state.task_id}")
    click.echo(f"Description: {state.task_description}")
    click.echo(f"Phase: {state.phase.value}")
    click.echo(f"Complexity: {state.data.get('complexity', 'unknown')}")
    click.echo(f"Created: {time.ctime(state.data.get('created_at', 0))}")
    click.echo(f"Updated: {time.ctime(state.data.get('updated_at', 0))}")
    click.echo(f"Errors: {len(state.data.get('errors', []))}")

    plans = state.data.get("planner_outputs", [])
    if plans:
        click.echo(f"\nPlans ({len(plans)}):")
        for p in plans:
            click.echo(f"  - {p['model']}: {len(p['output'])} chars")

    synthesis = state.data.get("synthesis_output")
    if synthesis:
        click.echo(f"\nSynthesis ({len(synthesis)} chars):")
        click.echo(synthesis[:500] + ("..." if len(synthesis) > 500 else ""))

    review_synth = state.data.get("review_synthesis_output")
    if review_synth:
        verdict = state.data.get("review_verdict", "unknown")
        click.echo(f"\nReview Synthesis (verdict: {verdict}):")
        click.echo(review_synth[:500] + ("..." if len(review_synth) > 500 else ""))

    verification = state.data.get("verification_result")
    if verification:
        click.echo("\nVerification:")
        for k, v in verification.items():
            success = v.get("success", False) if isinstance(v, dict) else False
            click.echo(f"  {k}: {'PASS' if success else 'FAIL'}")

    fix_outputs = state.data.get("fix_outputs", [])
    if fix_outputs:
        click.echo(f"\nFix Iterations: {len(fix_outputs)}")
        for f in fix_outputs:
            click.echo(f"  - Loop {f['loop'] + 1}: {f['model']} ({len(f['output'])} chars)")

    errors = state.data.get("errors", [])
    if errors:
        click.echo(f"\nErrors ({len(errors)}):")
        for e in errors:
            click.echo(f"  - [{e['phase']}] {e['error']}")


@command_group.command()
@click.option("--date", default=None, help="Date to report on (YYYY-MM-DD). Defaults to today.")
@click.option(
    "--month", default=None, help="Month to report on (YYYY-MM). Defaults to current month."
)
def cost(date: str | None, month: str | None) -> None:
    """Show cost and token usage report."""
    state_dir = WORKSPACE / "outputs" / "orchestra" / "state"
    from orchestra.cost import CostTracker

    tracker = CostTracker(state_dir)

    if date:
        summary = tracker.get_daily_summary(date)
        click.echo(f"Cost Report: {summary['date']}")
        click.echo("=" * 60)
        click.echo(f"  Total calls:    {summary['total_calls']}")
        click.echo(f"  Prompt tokens:  {summary['prompt_tokens']:,}")
        click.echo(f"  Output tokens:  {summary['completion_tokens']:,}")
        click.echo(f"  Total cost:     ${summary['total_cost']:.6f}")
        if summary["models"]:
            click.echo("\n  Per-model breakdown:")
            for model, info in summary["models"].items():
                click.echo(
                    f"    {model:30s}  tokens={info['prompt_tokens'] + info['completion_tokens']:>8,}  ${info['cost']:.6f}"
                )
    elif month:
        summary = tracker.get_monthly_summary(month)
        click.echo(f"Monthly Cost Report: {summary['month']}")
        click.echo("=" * 60)
        click.echo(f"  Total calls:    {summary['calls']}")
        click.echo(f"  Prompt tokens:  {summary['prompt_tokens']:,}")
        click.echo(f"  Output tokens:  {summary['completion_tokens']:,}")
        click.echo(f"  Total cost:     ${summary['total_cost']:.6f}")
    else:
        summary = tracker.get_daily_summary()
        click.echo(f"Cost Report: {summary['date']}")
        click.echo("=" * 60)
        click.echo(f"  Total calls:    {summary['total_calls']}")
        click.echo(f"  Prompt tokens:  {summary['prompt_tokens']:,}")
        click.echo(f"  Output tokens:  {summary['completion_tokens']:,}")
        click.echo(f"  Total cost:     ${summary['total_cost']:.6f}")
        if summary["models"]:
            click.echo("\n  Per-model breakdown:")
            for model, info in summary["models"].items():
                total_tok = info["prompt_tokens"] + info["completion_tokens"]
                click.echo(f"    {model:30s}  tokens={total_tok:>8,}  ${info['cost']:.6f}")


@command_group.command()
@click.argument("task_id")
def cost_task(task_id: str) -> None:
    """Show cost breakdown for a specific task."""
    state_dir = WORKSPACE / "outputs" / "orchestra" / "state"
    from orchestra.cost import CostTracker

    tracker = CostTracker(state_dir)

    task_cost = tracker.get_task_cost(task_id)
    if not task_cost:
        click.echo(f"No cost data for task {task_id}.")
        return

    click.echo(f"Cost Report: Task {task_cost['task_id']}")
    click.echo("=" * 60)
    click.echo(f"  Model calls:      {task_cost['calls']}")
    click.echo(f"  Prompt tokens:    {task_cost['prompt_tokens']:,}")
    click.echo(f"  Output tokens:    {task_cost['completion_tokens']:,}")
    click.echo(f"  Total cost:       ${task_cost['total_cost']:.6f}")


@command_group.command()
def perf() -> None:
    """Show model performance statistics across all tasks."""
    state_dir = WORKSPACE / "outputs" / "orchestra" / "state"
    all_tasks = list_tasks(state_dir)
    if not all_tasks:
        click.echo("No tasks found.")
        return

        # Aggregate performance across all tasks
    perf_data: dict[str, dict[str, Any]] = {}
    for t in all_tasks:
        try:
            state = TaskState.load(t["task_id"], state_dir)
        except (FileNotFoundError, json.JSONDecodeError):
            continue
        performance: dict[str, dict[str, Any]] = state.data.get("performance", {})
        for model, data in performance.items():
            if model not in perf_data:
                perf_data[model] = {"total_calls": 0, "successes": 0, "roles": {}, "tokens_used": 0}
            perf_data[model]["total_calls"] += data["total_calls"]
            perf_data[model]["successes"] += data["successes"]
            perf_data[model]["tokens_used"] += data.get("tokens_used", 0)
            for role, role_data in data.get("roles", {}).items():
                if role not in perf_data[model]["roles"]:
                    perf_data[model]["roles"][role] = {"calls": 0, "successes": 0}
                perf_data[model]["roles"][role]["calls"] += role_data["calls"]
                perf_data[model]["roles"][role]["successes"] += role_data["successes"]

    if not perf_data:
        click.echo("No performance data recorded yet.")
        return

    click.echo("Model Performance")
    click.echo("=" * 70)
    click.echo(f"  {'Model':30s}  {'Calls':>6}  {'Success':>8}  {'Rate':>6}  {'Tokens':>12}")
    click.echo("-" * 70)
    for model, data in sorted(perf_data.items()):
        rate = (
            f"{100 * data['successes'] / data['total_calls']:.0f}%"
            if data["total_calls"] > 0
            else "N/A"
        )
        click.echo(
            f"  {model:30s}  {data['total_calls']:>6}  {data['successes']:>8}  {rate:>6}  {data['tokens_used']:>12,}"
        )
        for role, role_data in data.get("roles", {}).items():
            role_rate = (
                f"{100 * role_data['successes'] / role_data['calls']:.0f}%"
                if role_data["calls"] > 0
                else "N/A"
            )
            click.echo(
                f"    {role:28s}  {role_data['calls']:>6}  {role_data['successes']:>8}  {role_rate:>6}"
            )


@command_group.command()
@click.argument("task_id")
@click.option(
    "--step",
    default=None,
    help="Snapshot to restore: start, 5, implementation, 08-fixing-0. Omit to list.",
)
@click.option("--yes", is_flag=True, help="Do not prompt for confirmation.")
def restore(task_id: str, step: str | None, yes: bool) -> None:
    """Restore a per-step workspace snapshot for a task."""
    state_dir = WORKSPACE / "outputs" / "orchestra" / "state"
    root = state_dir / "backups" / task_id
    slots = list_slots(root)
    if not slots:
        click.echo(f"No backup for {task_id}.", err=True)
        sys.exit(1)
    if step is None:
        click.echo(f"Backups for {task_id} (state when that step started):")
        for slot in slots:
            click.echo(f"  {slot}")
        click.echo(f"Restore with: orchestra restore {task_id} --step start")
        click.echo("  --step 5            # before implementation")
        click.echo("  --step implementation")
        return
    try:
        dest = resolve_slot(root, step)
    except FileNotFoundError as exc:
        click.echo(str(exc), err=True)
        sys.exit(1)
    click.echo(f"This replaces current source files with [{dest.name}] from {task_id}.")
    if not yes and not click.confirm("Restore backup?"):
        click.echo("Aborted.")
        return
    n = restore_snapshot(WORKSPACE, dest)
    click.echo(f"Restored {n} files from {dest}")
