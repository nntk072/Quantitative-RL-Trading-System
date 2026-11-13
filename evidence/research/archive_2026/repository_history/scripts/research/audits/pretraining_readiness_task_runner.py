"""Process execution and artifact provenance for readiness tasks."""

from __future__ import annotations

import hashlib
import os
import shlex
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from scripts.research.audits.pretraining_readiness_plan import TaskSpec

from artifacts.atomic import write_json_atomic
from configuration.paths import repository_root

ROOT = repository_root(__file__)


@dataclass(frozen=True, slots=True)
class TaskResult:
    """Persisted execution result for one readiness task."""

    task_id: str
    lane: str
    status: str
    depends_on: tuple[str, ...]
    resource_lock: str | None
    command: tuple[str, ...]
    return_code: int | None
    elapsed_seconds: float | None
    log_path: str | None
    log_sha256: str | None
    artifact_sha256: dict[str, str]
    blocker: str | None


def _sha256(path: Path) -> str:
    """Hash one file using bounded memory.

    Args:
        path: File to hash.

    Returns:
        Lowercase hexadecimal SHA-256 digest.
    """
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _artifact_hashes(roots: tuple[str, ...]) -> dict[str, str]:
    """Hash declared output files and identify missing or empty roots.

    Args:
        roots: Declared artifact files/directories.

    Returns:
        Path-to-SHA mapping, with explicit markers for missing or empty roots.
    """
    hashes: dict[str, str] = {}
    for raw_path in roots:
        path = Path(raw_path)
        if path.is_file():
            hashes[str(path)] = _sha256(path)
            continue
        if not path.is_dir():
            hashes[f"MISSING::{path}"] = ""
            continue
        files = [child for child in sorted(path.rglob("*")) if child.is_file()]
        if not files:
            hashes[f"EMPTY::{path}"] = ""
            continue
        for child in files:
            hashes[str(child)] = _sha256(child)
    return hashes


def persist_task_result(run_root: Path, result: TaskResult) -> None:
    """Atomically persist one completed, blocked, or failed task result.

    Args:
        run_root: Execution root.
        result: Task result to preserve.
    """
    result_path = run_root / "tasks" / result.task_id / "result.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(result_path, asdict(result))


def blocked_task_result(task: TaskSpec, reason: str, *, failed: bool = False) -> TaskResult:
    """Build a non-executed task result.

    Args:
        task: Task that cannot execute.
        reason: Dependency failure or runner error.
        failed: Whether the runner failed instead of a dependency blocking it.

    Returns:
        Persistable blocked or failed task result.
    """
    return TaskResult(
        task_id=task.task_id,
        lane=task.lane,
        status="fail" if failed else "blocked",
        depends_on=task.depends_on,
        resource_lock=task.resource_lock,
        command=task.command,
        return_code=None,
        elapsed_seconds=None,
        log_path=None,
        log_sha256=None,
        artifact_sha256={},
        blocker=reason,
    )


def run_task(task: TaskSpec, run_root: Path) -> TaskResult:
    """Execute a task and capture output, return code, and evidence hashes.

    Args:
        task: Fully expanded task specification.
        run_root: Execution root.

    Returns:
        Completed task result, persisted before return.
    """
    task_dir = run_root / "tasks" / task.task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    log_path = task_dir / "run.log"
    started = time.perf_counter()
    blocker = None
    return_code = 127
    with log_path.open("wb") as log:
        header = f"task_id={task.task_id}\nlane={task.lane}\ncommand={shlex.join(task.command)}\n\n"
        log.write(header.encode("utf-8"))
        log.flush()
        try:
            process = subprocess.run(
                list(task.command),
                cwd=ROOT,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=False,
                env=os.environ.copy(),
            )
            return_code = int(process.returncode)
        except OSError as exc:
            blocker = f"could not start direct child process: {exc}"
            log.write(f"\n{blocker}\n".encode())

    try:
        artifacts = _artifact_hashes(task.artifact_roots)
    except OSError as exc:
        artifacts = {}
        blocker = f"could not hash declared artifacts: {exc}"
    missing = any(key.startswith(("MISSING::", "EMPTY::")) for key in artifacts)
    if missing and blocker is None:
        blocker = "declared artifact root is missing or empty"
    result = TaskResult(
        task_id=task.task_id,
        lane=task.lane,
        status="pass" if return_code == 0 and blocker is None else "fail",
        depends_on=task.depends_on,
        resource_lock=task.resource_lock,
        command=task.command,
        return_code=return_code,
        elapsed_seconds=time.perf_counter() - started,
        log_path=str(log_path),
        log_sha256=_sha256(log_path),
        artifact_sha256=artifacts,
        blocker=blocker,
    )
    persist_task_result(run_root, result)
    return result
