"""Pipeline lifecycle and one-shot planning commands for Orchestra."""

from __future__ import annotations

import sys

import click

from orchestra.prompts import render_prompt
from orchestra.task_orchestration import WORKSPACE, Pipeline
from orchestra.task_state_store import Phase, TaskState

command_group = click.Group()


@command_group.command()
@click.argument("task")
@click.option(
    "--complexity",
    type=click.Choice(["trivial", "medium", "complex"]),
    default=None,
    help="Override task complexity (auto-detected if not set).",
)
@click.option(
    "--tier",
    type=click.Choice(["T0", "T1", "T2", "T3", "T4"]),
    default=None,
    help="Override task tier (T0..T4). Takes precedence over --complexity.",
)
@click.option(
    "--planners",
    default=3,
    help="Number of parallel planners.",
    type=int,
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be done without spawning sessions.",
)
@click.option(
    "--reviewers",
    default=2,
    help="Number of reviewers.",
    type=int,
)
@click.option(
    "--critics",
    default=2,
    help="Number of critics.",
    type=int,
)
@click.option(
    "--escalate",
    is_flag=True,
    help="Allow escalation to Gemini.",
)
@click.option(
    "--max-fixes",
    default=3,
    help="Maximum fix loop iterations.",
    type=int,
)
@click.option(
    "--keep-alive",
    is_flag=True,
    help="Keep tmux panes visible after a successful agent exit until the "
    "task finishes. Failed/fallback panes are always closed. "
    "Watch with 'tmux ls', attach with 'tmux attach -t <session>'.",
)
@click.option(
    "--resume",
    default=None,
    help="Resume a task by ID (restarts the saved phase, or the failed step).",
)
@click.option(
    "--from",
    "start_phase",
    default=None,
    help="On --resume, start at this step (1=triage … 10=report, or planning).",
)
def run(
    task: str,
    complexity: str | None,
    tier: str | None,
    planners: int,
    reviewers: int,
    critics: int,
    dry_run: bool,
    escalate: bool,
    max_fixes: int,
    keep_alive: bool,
    resume: str | None,
    start_phase: str | None,
) -> None:
    """Run a task through the full orchestra pipeline."""
    pipeline = Pipeline(
        planner_count=planners,
        critic_count=critics,
        reviewer_count=reviewers,
        dry_run=dry_run,
        max_fixes=max_fixes,
        keep_alive=keep_alive,
    )
    pipeline.escalate_mode = escalate
    if escalate:
        click.echo("  [ESCALATION MODE] Gemini and other escalation-only models enabled.")

    try:
        state = pipeline.run(
            task,
            resume_from=resume,
            complexity=complexity,
            start_phase=start_phase,
            tier=tier,
        )
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc

    if state.phase == Phase.DONE:
        click.echo(f"\nState saved: {state.task_id}")
    elif state.phase == Phase.FAILED:
        click.echo(f"\nTask FAILED in phase {state.phase.value}. Resume with:")
        click.echo(f'  orchestra run "{task}" --resume {state.task_id}')
        click.echo(f'  orchestra run "{task}" --resume {state.task_id} --from 10')
    elif state.phase == Phase.PARKED:
        click.echo(f"\nTask PARKED: {state.data.get('park_reason', 'no models')}")
        click.echo("  Run: orchestra doctor")
        click.echo(f'  Then: orchestra run "{task}" --resume {state.task_id}')


@command_group.command()
@click.option("--tier1", is_flag=True, help="Run Tier-1 network catalog probes (no generation).")
def doctor(tier1: bool) -> None:
    """Check model health (Tier-0 local; optional Tier-1 catalog)."""
    from orchestra.health import derive_status
    from orchestra.model_provider_registry import load_models

    pipeline = Pipeline(dry_run=True)
    models = load_models()
    registry = pipeline.router.health
    registry.probe_tier0(models, check_version=True)
    if tier1:
        registry.probe_tier1(models)
    click.echo("Orchestra Doctor")
    click.echo("=" * 72)
    click.echo(f"  {'Model':28s}  {'Status':12s}  {'Auth':5s}  {'CLI':8s}")
    click.echo("-" * 72)
    for model in models:
        facts = registry.get(model)
        status = derive_status(facts)
        auth = "?" if facts.auth_ok is None else ("yes" if facts.auth_ok else "no")
        click.echo(f"  {model.registry_id:28s}  {status.value:12s}  {auth:5s}  {model.cli:8s}")
    click.echo("\nNo inference calls were made.")


@command_group.command()
@click.argument("task_id")
@click.option("--max-fixes", default=3, help="Maximum fix iterations.", type=int)
def fix(task_id: str, max_fixes: int) -> None:
    """Run fix loop on an existing task."""
    state_dir = WORKSPACE / "outputs" / "orchestra" / "state"
    try:
        state = TaskState.load(task_id, state_dir)
    except FileNotFoundError:
        click.echo(f"Task {task_id} not found.", err=True)
        sys.exit(1)

    if state.phase not in (Phase.FIXING, Phase.VERIFICATION):
        state.set_phase(Phase.FIXING)

    pipeline = Pipeline(max_fixes=max_fixes)
    click.echo(f"Fixing task: {task_id}")
    click.echo(f"Current phase: {state.phase.value}")
    state = pipeline.run(state.task_description, resume_from=task_id)

    if state.phase == Phase.DONE:
        click.echo("\n[SUCCESS] All tests pass after fixes.")
    else:
        click.echo("\n[FAILED] Could not fix all issues.")


@command_group.command()
@click.option("--all", "kill_all", is_flag=True, help="Kill all orchestra sessions.")
def cleanup(kill_all: bool) -> None:
    """Clean up orchestra-managed tmux sessions."""
    pipeline = Pipeline()
    if kill_all:
        count = pipeline.sessions.cleanup(prefix="orchestra-")
        click.echo(f"Killed {count} orchestra sessions.")
    else:
        sessions = pipeline.sessions
        orchestra_sessions = [s for s in sessions.list_sessions() if s.startswith("orchestra-")]
        if not orchestra_sessions:
            click.echo("No orchestra sessions found.")
        else:
            click.echo("Active orchestra sessions:")
            for s in orchestra_sessions:
                click.echo(f"  {s}")


@command_group.command()
@click.argument("task")
@click.option("--model", help="Specific model to use.")
@click.option("--dry-run", is_flag=True, help="Show commands without executing.")
def plan(task: str, model: str | None, dry_run: bool) -> None:
    """Quick plan: triage + single planner. No implementation."""
    pipeline = Pipeline(dry_run=dry_run)
    router = pipeline.router
    sessions = pipeline.sessions

    triage_models = router.select("triage", count=1)
    if not triage_models:
        click.echo("No triage model available", err=True)
        sys.exit(1)
    triage_model = triage_models[0]
    click.echo(f"Triage: {triage_model.display_name}")
    triage_prompt = render_prompt("triage", task=task)

    if dry_run:
        click.echo(
            f"  Command: {' '.join(sessions.build_command(triage_model, triage_prompt)[:3])}..."
        )
        return

    triage_session = sessions.spawn(triage_model, "triage", triage_prompt)
    triage_output = sessions.collect(triage_session, timeout=600, lines=50)
    click.echo(triage_output)

    if model:
        plan_model = next((m for m in router.models if m.display_name == model), None)
        if not plan_model:
            click.echo(f"Model {model} not found", err=True)
            sys.exit(1)
    else:
        plan_models = router.select("planner", count=1)
        if not plan_models:
            click.echo("No planner model available", err=True)
            sys.exit(1)
        plan_model = plan_models[0]
    click.echo(f"\nPlanner: {plan_model.display_name}")
    plan_prompt = render_prompt(
        "planner", task=task, triage=triage_output, workspace=str(WORKSPACE)
    )
    plan_session = sessions.spawn(plan_model, "planner", plan_prompt)
    plan_output = sessions.collect(plan_session, timeout=600, lines=200)
    click.echo(plan_output)
