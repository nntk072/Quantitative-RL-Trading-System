#!/usr/bin/env python3
"""Execute bounded pre-training implementation/evidence tasks in parallel.

The runner launches direct child processes only. It never allocates Slurm
resources or starts scientific training. Independent tasks may overlap; a failed
task blocks only dependants while unrelated lanes continue. A passing run proves
command completion, not scientific acceptance.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import asdict
from pathlib import Path
from typing import Any

from scripts.research.audits.pretraining_readiness_plan import (
    ReadinessPlan,
    TaskSpec,
    load_plan,
    plan_summary,
    resolve_task,
)
from scripts.research.audits.pretraining_readiness_task_runner import (
    TaskResult,
    blocked_task_result,
    persist_task_result,
    run_task,
)

from artifacts.atomic import write_json_atomic
from configuration.paths import repository_root

ROOT = repository_root(__file__)
DEFAULT_PLAN = ROOT / "config/research/pretraining_parallel_readiness.yaml"
_DIRTY_SMOKE_TASKS = {
    "candidate_policy_contract",
    "prospective_protocol",
    "simulator_accounting_contract",
    "static_contract",
}


def _git_state() -> tuple[str, list[str]]:
    """Return current source SHA and porcelain dirty paths."""
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)
    return sha, dirty.splitlines()


def _inside_repository(path: Path) -> bool:
    """Return whether ``path`` resolves inside the repository.

    Args:
        path: Candidate output path.

    Returns:
        Whether the path resolves under the repository root.
    """
    try:
        path.resolve().relative_to(ROOT.resolve())
    except ValueError:
        return False
    return True


def _validate_run_root(run_root: Path) -> Path:
    """Require a fresh absolute output directory outside the checkout.

    Args:
        run_root: Requested evidence output root.

    Returns:
        Resolved absolute output path.
    """
    requested = run_root.expanduser()
    if not requested.is_absolute():
        requested = Path.cwd() / requested
    requested = Path(os.path.abspath(requested))
    try:
        requested.relative_to(ROOT.resolve())
    except ValueError:
        pass
    else:
        raise ValueError("--run-root must be outside the repository")
    resolved = requested.resolve()
    if resolved.exists():
        raise ValueError("--run-root must not already exist")
    if _inside_repository(resolved):
        raise ValueError("--run-root must be outside the repository")
    return resolved


def _closure(plan: ReadinessPlan, selected: set[str]) -> set[str]:
    """Add transitive dependencies for a requested task subset.

    Args:
        plan: Validated readiness plan.
        selected: Explicit task IDs.

    Returns:
        Selection plus all dependencies.
    """
    by_id = {task.task_id: task for task in plan.tasks}
    unknown = selected - set(by_id)
    if unknown:
        raise ValueError(f"unknown --only task IDs: {sorted(unknown)}")
    closure = set(selected)
    pending = list(selected)
    while pending:
        task = by_id[pending.pop()]
        for dependency in task.depends_on:
            if dependency not in closure:
                closure.add(dependency)
                pending.append(dependency)
    return closure


def _barrier_results(plan: ReadinessPlan, results: dict[str, TaskResult]) -> list[dict[str, Any]]:
    """Compute barrier state for tasks included in one execution.

    Args:
        plan: Full readiness plan.
        results: Results for selected tasks.

    Returns:
        Barrier records with pass, fail, or not-selected status.
    """
    barriers = []
    for barrier in plan.barriers:
        required = set(barrier.requires)
        if not required.issubset(results):
            status = "not_selected"
        elif all(results[task_id].status == "pass" for task_id in required):
            status = "pass"
        else:
            status = "fail"
        barriers.append(
            {
                "barrier_id": barrier.barrier_id,
                "description": barrier.description,
                "requires": list(barrier.requires),
                "status": status,
            }
        )
    return barriers


def _collect_finished_tasks(
    active: dict[Future[TaskResult], TaskSpec],
    active_locks: set[str],
    output_root: Path,
) -> dict[str, TaskResult]:
    """Wait for finished tasks, persist runner failures, and release locks.

    Args:
        active: Future-to-task records currently running.
        active_locks: Resource locks held by those tasks.
        output_root: Directory for task result records.

    Returns:
        Results for the tasks completed in this wait.
    """
    done, _ = wait(active, return_when="FIRST_COMPLETED")
    results: dict[str, TaskResult] = {}
    for future in done:
        task = active.pop(future)
        try:
            result = future.result()
        except Exception as exc:
            result = blocked_task_result(task, f"runner failure: {exc!r}", failed=True)
            persist_task_result(output_root, result)
        results[task.task_id] = result
        if task.resource_lock:
            active_locks.discard(task.resource_lock)
    return results


def _execute_tasks(
    tasks: tuple[TaskSpec, ...], output_root: Path, max_workers: int
) -> dict[str, TaskResult]:
    """Schedule task processes while enforcing dependencies and resource locks.

    Args:
        tasks: Selected tasks with dependencies expanded and validated.
        output_root: Directory for logs and atomic result records.
        max_workers: Maximum number of concurrent child processes.

    Returns:
        Results indexed by task ID.
    """
    by_id = {task.task_id: task for task in tasks}
    pending = set(by_id)
    results: dict[str, TaskResult] = {}
    active: dict[Future[TaskResult], TaskSpec] = {}
    active_locks: set[str] = set()

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        while pending or active:
            for task_id in sorted(tuple(pending)):
                task = by_id[task_id]
                if any(dependency not in results for dependency in task.depends_on):
                    continue
                failed = [
                    dependency
                    for dependency in task.depends_on
                    if results[dependency].status != "pass"
                ]
                if failed:
                    result = blocked_task_result(task, f"dependency failure: {', '.join(failed)}")
                    results[task_id] = result
                    persist_task_result(output_root, result)
                    pending.remove(task_id)
                    continue
                if task.resource_lock and task.resource_lock in active_locks:
                    continue
                if len(active) >= max_workers:
                    break
                if task.resource_lock:
                    active_locks.add(task.resource_lock)
                active[pool.submit(run_task, task, output_root)] = task
                pending.remove(task_id)

            results.update(_collect_finished_tasks(active, active_locks, output_root))
            if (
                pending
                and not active
                and all(
                    any(dependency not in results for dependency in by_id[task_id].depends_on)
                    for task_id in pending
                )
            ):
                raise RuntimeError("scheduler made no progress")
    return results


def run_plan(
    plan: ReadinessPlan,
    *,
    run_root: Path,
    python: str,
    max_workers: int,
    selected_tasks: set[str] | None = None,
) -> dict[str, Any]:
    """Execute the bounded DAG with dependencies and logical resource locks.

    Args:
        plan: Validated readiness plan.
        run_root: New output directory outside the repository.
        python: Python executable used by Python tasks.
        max_workers: Maximum active direct child processes.
        selected_tasks: Optional task subset; dependencies are added automatically.

    Returns:
        Execution manifest. Scientific and PRICE authorization are always false.
    """
    if isinstance(max_workers, bool) or max_workers < 1:
        raise ValueError("max_workers must be positive")
    if not python.strip():
        raise ValueError("python executable must not be empty")
    output_root = _validate_run_root(run_root)
    source_sha, dirty_paths = _git_state()
    selected = None if selected_tasks is None else _closure(plan, selected_tasks)
    tasks = tuple(
        resolve_task(task, python=python, run_root=output_root, source_sha=source_sha)
        for task in plan.tasks
        if selected is None or task.task_id in selected
    )
    if not tasks:
        raise ValueError("no readiness tasks selected")

    output_root.mkdir(parents=True, exist_ok=False)
    results = _execute_tasks(tasks, output_root, max_workers)

    rows = [asdict(results[task.task_id]) for task in tasks]
    manifest = {
        "schema_version": "pretraining-parallel-readiness-run-v1",
        "source_commit": source_sha,
        "source_dirty_at_start": bool(dirty_paths),
        "dirty_paths_at_start": dirty_paths,
        "run_root": str(output_root),
        "max_workers": max_workers,
        "selected_tasks": [task.task_id for task in tasks],
        "execution_status": "pass" if all(row["status"] == "pass" for row in rows) else "fail",
        "tasks": rows,
        "barriers": _barrier_results(plan, results),
        "external_scientific_gates": list(plan.external_scientific_gates),
        "scientific_training_authorized": False,
        "price_training_authorized": False,
        "authorization_reason": "Execution completion is not scientific acceptance.",
    }
    write_json_atomic(output_root / "pretraining_parallel_readiness_manifest.json", manifest)
    return manifest


def _allow_dirty_smoke(plan: ReadinessPlan, only: list[str] | None) -> None:
    """Limit dirty-tree execution to explicitly selected implementation smoke tasks.

    Args:
        plan: Validated readiness plan.
        only: Explicit user-selected task IDs.
    """
    if only is None:
        raise ValueError("--allow-dirty requires --only with bounded smoke tasks")
    selected = _closure(plan, set(only))
    disallowed = selected - _DIRTY_SMOKE_TASKS
    if disallowed:
        raise ValueError(
            f"dirty-tree smoke cannot run feature evidence or release tasks: {sorted(disallowed)}"
        )


def main(argv: list[str] | None = None) -> int:
    """Run or inspect the readiness DAG.

    Args:
        argv: Optional command-line arguments for tests and embedding.

    Returns:
        Process exit code; nonzero indicates a failed execution manifest.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--run-root", type=Path)
    parser.add_argument("--python", default=os.environ.get("QRL_PYTHON", ".venv/bin/python"))
    parser.add_argument("--max-workers", type=int, default=3)
    parser.add_argument("--only", nargs="+")
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args(argv)

    plan_path = args.plan if args.plan.is_absolute() else ROOT / args.plan
    plan = load_plan(plan_path)
    if args.plan_only:
        print(json.dumps(plan_summary(plan), indent=2, sort_keys=True))
        return 0
    if args.run_root is None:
        raise SystemExit("--run-root is required unless --plan-only is used")

    _, dirty_paths = _git_state()
    if dirty_paths:
        if not args.allow_dirty:
            raise SystemExit("readiness execution requires a clean source tree")
        _allow_dirty_smoke(plan, args.only)
    run_root = _validate_run_root(args.run_root)
    manifest = run_plan(
        plan,
        run_root=run_root,
        python=args.python,
        max_workers=args.max_workers,
        selected_tasks=None if args.only is None else set(args.only),
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0 if manifest["execution_status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
