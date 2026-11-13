"""Validated plan contracts for the pre-training readiness runner."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from omegaconf import OmegaConf

ROOT = Path(__file__).resolve().parents[3]
FORBIDDEN_EXECUTABLES = {"salloc", "sbatch", "scancel", "srun"}
_TASK_ID = re.compile(r"^[a-z][a-z0-9_]*$")
_BARRIER_ID = re.compile(r"^[A-Z][A-Z0-9_]*$")


@dataclass(frozen=True, slots=True)
class TaskSpec:
    """One direct-process node in the readiness DAG."""

    task_id: str
    lane: str
    description: str
    depends_on: tuple[str, ...]
    resource_lock: str | None
    command: tuple[str, ...]
    artifact_roots: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BarrierSpec:
    """Named aggregation of tasks corresponding to a V3 barrier."""

    barrier_id: str
    description: str
    requires: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReadinessPlan:
    """Validated immutable execution plan loaded from YAML."""

    schema_version: str
    tasks: tuple[TaskSpec, ...]
    barriers: tuple[BarrierSpec, ...]
    external_scientific_gates: tuple[str, ...]


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    """Validate and return a mapping node.

    Args:
        value: Parsed configuration value.
        label: Field label used in validation errors.

    Returns:
        Mapping view of ``value``.
    """
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a mapping")
    return value


def _sequence(value: Any, label: str) -> list[Any]:
    """Validate and return a list node.

    Args:
        value: Parsed configuration value.
        label: Field label used in validation errors.

    Returns:
        List view of ``value``.
    """
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    return value


def _validate_command(command: tuple[str, ...]) -> None:
    """Reject empty commands, shell strings, and Slurm scheduler commands.

    Args:
        command: Direct-process argv tokens.
    """
    if not command or any(not token.strip() for token in command):
        raise ValueError("task command must contain non-empty argv tokens")
    for token in command:
        executable = Path(token).name.lower()
        if executable in FORBIDDEN_EXECUTABLES:
            raise ValueError(f"forbidden executable in readiness DAG: {executable}")
        for forbidden in FORBIDDEN_EXECUTABLES:
            if re.search(rf"(?<![\w.-]){forbidden}(?![\w.-])", token):
                raise ValueError(f"forbidden executable in readiness DAG: {forbidden}")
    if Path(command[0]).name.lower() in {"bash", "sh"}:
        if len(command) < 2 or command[1] in {"-c", "-lc", "-ec"}:
            raise ValueError("readiness DAG shell tasks must name a script file")
        script_path = Path(command[1])
        if not script_path.is_absolute():
            script_path = ROOT / script_path
        if script_path.is_file():
            contents = script_path.read_text(encoding="utf-8")
            for executable in FORBIDDEN_EXECUTABLES:
                if re.search(rf"(?<![\w.-]){executable}(?![\w.-])", contents):
                    raise ValueError(
                        f"readiness shell task contains forbidden scheduler command: {executable}"
                    )


def _validate_dag(tasks: tuple[TaskSpec, ...]) -> None:
    """Validate task identities, dependency references, and acyclicity.

    Args:
        tasks: Parsed task definitions.
    """
    ids = [task.task_id for task in tasks]
    if not tasks:
        raise ValueError("pretraining readiness plan must contain tasks")
    if len(ids) != len(set(ids)):
        raise ValueError("pretraining readiness task IDs must be unique")
    known = set(ids)
    by_id = {task.task_id: task for task in tasks}
    for task in tasks:
        if not _TASK_ID.fullmatch(task.task_id):
            raise ValueError(f"invalid readiness task ID: {task.task_id!r}")
        if task.lane not in {"A", "B", "C", "D", "E", "F"}:
            raise ValueError(f"{task.task_id} has an invalid lane: {task.lane!r}")
        if len(task.depends_on) != len(set(task.depends_on)):
            raise ValueError(f"{task.task_id} has duplicate dependencies")
        if task.resource_lock is not None and not re.fullmatch(
            r"[a-z][a-z0-9_]*", task.resource_lock
        ):
            raise ValueError(f"{task.task_id} has an invalid resource lock")
        unknown = set(task.depends_on) - known
        if unknown:
            raise ValueError(f"{task.task_id} has unknown dependencies: {sorted(unknown)}")
        if task.task_id in task.depends_on:
            raise ValueError(f"{task.task_id} cannot depend on itself")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(task_id: str) -> None:
        if task_id in visited:
            return
        if task_id in visiting:
            raise ValueError(f"cycle detected at pretraining readiness task {task_id}")
        visiting.add(task_id)
        for dependency in by_id[task_id].depends_on:
            visit(dependency)
        visiting.remove(task_id)
        visited.add(task_id)

    for task_id in ids:
        visit(task_id)


def _parse_tasks(root: Mapping[str, Any]) -> tuple[TaskSpec, ...]:
    """Parse task records and validate the resulting dependency graph.

    Args:
        root: Parsed readiness-plan mapping.

    Returns:
        Immutable validated task specifications.
    """
    tasks: list[TaskSpec] = []
    for index, value in enumerate(_sequence(root.get("tasks"), "tasks")):
        row = _mapping(value, f"tasks[{index}]")
        command = tuple(str(token) for token in _sequence(row.get("command"), "command"))
        _validate_command(command)
        task = TaskSpec(
            task_id=str(row.get("id", "")).strip(),
            lane=str(row.get("lane", "")).strip(),
            description=str(row.get("description", "")).strip(),
            depends_on=tuple(
                str(item) for item in _sequence(row.get("depends_on", []), "depends_on")
            ),
            resource_lock=(None if row.get("resource_lock") is None else str(row["resource_lock"])),
            command=command,
            artifact_roots=tuple(
                str(item) for item in _sequence(row.get("artifact_roots", []), "artifact_roots")
            ),
        )
        if not task.task_id or not task.lane or not task.description:
            raise ValueError("each task requires non-empty id, lane, and description")
        tasks.append(task)

    task_tuple = tuple(tasks)
    _validate_dag(task_tuple)
    return task_tuple


def _parse_barriers(
    root: Mapping[str, Any], tasks: tuple[TaskSpec, ...]
) -> tuple[BarrierSpec, ...]:
    """Parse and validate named barriers against the task inventory.

    Args:
        root: Parsed readiness-plan mapping.
        tasks: Validated tasks referenced by barrier requirements.

    Returns:
        Immutable barrier specifications.
    """
    known = {task.task_id for task in tasks}
    barriers: list[BarrierSpec] = []
    for index, value in enumerate(_sequence(root.get("barriers"), "barriers")):
        row = _mapping(value, f"barriers[{index}]")
        barrier = BarrierSpec(
            barrier_id=str(row.get("id", "")).strip(),
            description=str(row.get("description", "")).strip(),
            requires=tuple(str(item) for item in _sequence(row.get("requires", []), "requires")),
        )
        if not _BARRIER_ID.fullmatch(barrier.barrier_id) or not barrier.description:
            raise ValueError("each barrier requires a valid id and description")
        if not barrier.requires:
            raise ValueError(f"barrier {barrier.barrier_id} must require at least one task")
        unknown = set(barrier.requires) - known
        if unknown:
            raise ValueError(f"barrier references unknown tasks: {sorted(unknown)}")
        barriers.append(barrier)
    barrier_ids = [barrier.barrier_id for barrier in barriers]
    if len(barrier_ids) != len(set(barrier_ids)):
        raise ValueError("pretraining readiness barrier IDs must be unique")
    return tuple(barriers)


def _parse_external_gates(root: Mapping[str, Any]) -> tuple[str, ...]:
    """Parse the explicit gates that remain outside implementation readiness.

    Args:
        root: Parsed readiness-plan mapping.

    Returns:
        Unique non-empty scientific gate identifiers.
    """
    external = tuple(
        str(item)
        for item in _sequence(root.get("external_scientific_gates"), "external_scientific_gates")
    )
    if not external or any(not item for item in external):
        raise ValueError("scientific gates must remain explicit and external")
    if len(external) != len(set(external)):
        raise ValueError("external scientific gates must be unique")
    return external


def load_plan(path: Path) -> ReadinessPlan:
    """Load and validate the V3 pre-training execution DAG.

    Args:
        path: YAML path containing the DAG.

    Returns:
        Validated readiness plan.
    """
    raw = OmegaConf.to_container(OmegaConf.load(path), resolve=True)
    root = _mapping(raw, "pretraining readiness plan")
    if root.get("schema_version") != "pretraining-parallel-readiness-v1":
        raise ValueError("unsupported pretraining readiness plan schema")
    if root.get("scientific_training_authorization") != "never_from_this_plan_alone":
        raise ValueError("execution DAG must not self-authorize scientific training")

    tasks = _parse_tasks(root)
    barriers = _parse_barriers(root, tasks)
    external = _parse_external_gates(root)
    return ReadinessPlan(str(root["schema_version"]), tasks, barriers, external)


def expand_token(token: str, *, python: str, run_root: Path, source_sha: str) -> str:
    """Expand approved execution-plan placeholders.

    Args:
        token: Raw command or artifact token.
        python: Selected Python executable.
        run_root: Output root for this execution.
        source_sha: Current Git commit.

    Returns:
        Expanded token.
    """
    replacements = {
        "{python}": python,
        "{repo}": str(ROOT),
        "{run_root}": str(run_root),
        "{source_sha}": source_sha,
    }
    result = token
    for key, value in replacements.items():
        result = result.replace(key, value)
    if "{" in result or "}" in result:
        raise ValueError(f"unresolved placeholder in token: {token}")
    return result


def resolve_task(
    task: TaskSpec,
    *,
    python: str,
    run_root: Path,
    source_sha: str,
) -> TaskSpec:
    """Expand one task's command and artifact paths.

    Args:
        task: Parsed task.
        python: Selected Python executable.
        run_root: Execution output root.
        source_sha: Current Git SHA.

    Returns:
        Fully expanded task.
    """
    command = tuple(
        expand_token(token, python=python, run_root=run_root, source_sha=source_sha)
        for token in task.command
    )
    _validate_command(command)
    artifact_roots = tuple(
        expand_token(token, python=python, run_root=run_root, source_sha=source_sha)
        for token in task.artifact_roots
    )
    for raw_path in artifact_roots:
        path = Path(raw_path)
        if not path.is_absolute():
            path = ROOT / path
        try:
            path.resolve().relative_to(run_root.resolve())
        except ValueError as exc:
            raise ValueError(f"declared artifact root must be inside run root: {raw_path}") from exc
    return TaskSpec(
        task.task_id,
        task.lane,
        task.description,
        task.depends_on,
        task.resource_lock,
        command,
        artifact_roots,
    )


def plan_summary(plan: ReadinessPlan) -> dict[str, Any]:
    """Return a non-executing JSON summary of the DAG.

    Args:
        plan: Validated readiness plan.

    Returns:
        Plan summary with authorization disabled.
    """
    return {
        "schema_version": plan.schema_version,
        "executes_commands": False,
        "tasks": [
            {
                "id": task.task_id,
                "lane": task.lane,
                "depends_on": list(task.depends_on),
                "resource_lock": task.resource_lock,
                "command": list(task.command),
                "artifact_roots": list(task.artifact_roots),
            }
            for task in plan.tasks
        ],
        "barriers": [asdict(barrier) for barrier in plan.barriers],
        "external_scientific_gates": list(plan.external_scientific_gates),
        "scientific_training_authorized": False,
        "price_training_authorized": False,
    }
