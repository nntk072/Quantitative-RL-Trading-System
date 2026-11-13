"""Reusable direct-command execution for research experiments.

The executor does not allocate or cancel scheduler jobs.  It runs only direct
child processes inside the caller's current environment and records immutable
command and artifact identities for resumable work.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from artifacts.atomic import write_json_atomic
from artifacts.identity import file_sha256
from configuration.paths import repository_root

ROOT = repository_root(__file__)
FORBIDDEN_EXECUTABLES = frozenset({"salloc", "sbatch", "scancel", "srun"})


@dataclass(frozen=True, slots=True)
class CommandSpec:
    """One executable work unit in a research experiment."""

    command_id: str
    argv: tuple[str, ...]
    depends_on: tuple[str, ...] = ()
    resource_lock: str | None = None
    artifact_roots: tuple[str, ...] = ()
    experiment: bool = False
    continue_on_dependency_failure: bool = False
    accepted_return_codes: tuple[int, ...] = (0,)
    estimated_seconds: float = 0.0
    variant_id: str | None = None
    component: str | None = None
    seed: int | None = None
    result_artifact: str | None = None


@dataclass(frozen=True, slots=True)
class CommandBundle:
    """Source-bound command graph for one named experiment."""

    source_commit: str
    experiment_id: str
    domain: str
    commands: tuple[CommandSpec, ...]
    schema_version: int = 1


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Persisted result of one command attempt."""

    command_id: str
    status: str
    return_code: int | None
    elapsed_seconds: float | None
    log_path: str | None
    log_sha256: str | None
    artifact_sha256: dict[str, str]
    blocker: str | None
    variant_id: str | None = None
    component: str | None = None
    seed: int | None = None
    result_artifact: str | None = None


def _git_state() -> tuple[str, bool]:
    """Return the current source commit and clean-tree state.

    Returns:
        Result produced by _git_state.
    """
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()
    return sha, not dirty


def _validate_argv(argv: tuple[str, ...]) -> None:
    """Reject empty commands and scheduler-allocation executables.

    Args:
        argv: Command-line arguments for this operation.
    """
    if not argv or any(not item for item in argv):
        raise ValueError("command argv must contain non-empty tokens")
    for token in argv:
        if Path(token).name.lower() in FORBIDDEN_EXECUTABLES:
            raise ValueError(f"research command contains forbidden scheduler executable: {token}")


def _artifact_hashes(roots: tuple[str, ...]) -> dict[str, str]:
    """Hash declared result files and directory contents.

    Args:
        roots: Declared artifact roots to hash.

    Returns:
        Result produced by _artifact_hashes.
    """
    result: dict[str, str] = {}
    for raw in roots:
        path = Path(raw)
        if path.is_file():
            result[str(path)] = file_sha256(path)
            continue
        if path.is_dir():
            files = tuple(child for child in sorted(path.rglob("*")) if child.is_file())
            if not files:
                result[f"EMPTY::{path}"] = ""
            for child in files:
                result[str(child)] = file_sha256(child)
            continue
        result[f"MISSING::{path}"] = ""
    return result


def bundle_payload(bundle: CommandBundle) -> dict[str, Any]:
    """Return a JSON-serializable command-bundle payload.

    Args:
        bundle: Frozen source-bound command bundle.

    Returns:
        Result produced by bundle_payload.
    """
    return {
        "schema_version": bundle.schema_version,
        "source_commit": bundle.source_commit,
        "experiment_id": bundle.experiment_id,
        "domain": bundle.domain,
        "commands": [
            {
                "id": item.command_id,
                "argv": list(item.argv),
                "depends_on": list(item.depends_on),
                "resource_lock": item.resource_lock,
                "artifact_roots": list(item.artifact_roots),
                "experiment": item.experiment,
                "continue_on_dependency_failure": item.continue_on_dependency_failure,
                "accepted_return_codes": list(item.accepted_return_codes),
                "estimated_seconds": item.estimated_seconds,
                "variant_id": item.variant_id,
                "component": item.component,
                "seed": item.seed,
                "result_artifact": item.result_artifact,
            }
            for item in bundle.commands
        ],
    }


def bundle_from_payload(value: Any) -> CommandBundle:
    """Validate a JSON-like payload and return the typed command bundle.

    Args:
        value: Value to validate or transform.

    Returns:
        Result produced by bundle_from_payload.
    """
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ValueError("unsupported research command bundle")
    source_commit = value.get("source_commit")
    experiment_id = value.get("experiment_id")
    domain = value.get("domain")
    if not isinstance(source_commit, str) or len(source_commit) != 40:
        raise ValueError("research command bundle requires a full source commit")
    if not isinstance(experiment_id, str) or not experiment_id.strip():
        raise ValueError("research command bundle requires experiment_id")
    if not isinstance(domain, str) or not domain.strip():
        raise ValueError("research command bundle requires domain")
    raw_commands = value.get("commands")
    if not isinstance(raw_commands, list) or not raw_commands:
        raise ValueError("research command bundle requires commands")
    commands: list[CommandSpec] = []
    ids: set[str] = set()
    for raw in raw_commands:
        if not isinstance(raw, dict):
            raise ValueError("research command rows must be mappings")
        command_id = raw.get("id")
        argv = raw.get("argv")
        depends_on = raw.get("depends_on", [])
        artifact_roots = raw.get("artifact_roots", [])
        if not isinstance(command_id, str) or not command_id.strip() or command_id in ids:
            raise ValueError("research command IDs must be unique non-empty strings")
        if (
            not isinstance(argv, list)
            or not argv
            or any(not isinstance(item, str) or not item for item in argv)
        ):
            raise ValueError(f"{command_id}: argv must be a non-empty string list")
        if not isinstance(depends_on, list) or any(
            not isinstance(item, str) for item in depends_on
        ):
            raise ValueError(f"{command_id}: depends_on must be a string list")
        if not isinstance(artifact_roots, list) or any(
            not isinstance(item, str) for item in artifact_roots
        ):
            raise ValueError(f"{command_id}: artifact_roots must be a string list")
        lock = raw.get("resource_lock")
        if lock is not None and not isinstance(lock, str):
            raise ValueError(f"{command_id}: resource_lock must be a string or null")
        accepted_raw = raw.get("accepted_return_codes", [0])
        if (
            not isinstance(accepted_raw, list)
            or not accepted_raw
            or any(isinstance(item, bool) or not isinstance(item, int) for item in accepted_raw)
        ):
            raise ValueError(f"{command_id}: accepted_return_codes must be an integer list")
        variant_id = raw.get("variant_id")
        component = raw.get("component")
        if any(
            value is not None and (not isinstance(value, str) or not value.strip())
            for value in (variant_id, component)
        ):
            raise ValueError(
                f"{command_id}: variant_id and component must be non-empty strings or null"
            )
        seed = raw.get("seed")
        if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int) or seed < 0):
            raise ValueError(f"{command_id}: seed must be a non-negative integer or null")
        result_artifact = raw.get("result_artifact")
        if result_artifact is not None and (
            not isinstance(result_artifact, str) or not result_artifact.strip()
        ):
            raise ValueError(f"{command_id}: result_artifact must be a non-empty string or null")
        estimated = raw.get("estimated_seconds", 0.0)
        if isinstance(estimated, bool) or not isinstance(estimated, (int, float)):
            raise ValueError(f"{command_id}: estimated_seconds must be numeric")
        command = CommandSpec(
            command_id=command_id,
            argv=tuple(argv),
            depends_on=tuple(depends_on),
            resource_lock=lock,
            artifact_roots=tuple(artifact_roots),
            experiment=raw.get("experiment") is True,
            continue_on_dependency_failure=raw.get("continue_on_dependency_failure") is True,
            accepted_return_codes=tuple(accepted_raw),
            estimated_seconds=float(estimated),
            variant_id=variant_id,
            component=component,
            seed=seed,
            result_artifact=result_artifact,
        )
        _validate_argv(command.argv)
        commands.append(command)
        ids.add(command_id)
    for command in commands:
        unknown = set(command.depends_on) - ids
        if unknown:
            raise ValueError(f"{command.command_id}: unknown dependencies {sorted(unknown)}")
    return CommandBundle(
        source_commit=source_commit,
        experiment_id=experiment_id,
        domain=domain,
        commands=tuple(commands),
    )


def _run_one(command: CommandSpec, run_root: Path, *, attempt: int) -> CommandResult:
    """Execute one command attempt and capture artifact identities.

    Args:
        command: Command specification to execute.
        run_root: Directory containing execution state and command attempts.
        attempt: One-based execution-attempt number.

    Returns:
        Result produced by _run_one.
    """
    task_dir = run_root / "commands" / command.command_id / f"attempt_{attempt:03d}"
    task_dir.mkdir(parents=True, exist_ok=True)
    log_path = task_dir / "run.log"
    started = time.perf_counter()
    with log_path.open("wb") as stream:
        process = subprocess.run(
            list(command.argv),
            cwd=ROOT,
            env=os.environ.copy(),
            stdout=stream,
            stderr=subprocess.STDOUT,
            check=False,
        )
    elapsed = time.perf_counter() - started
    artifacts = _artifact_hashes(command.artifact_roots)
    missing = any(key.startswith(("MISSING::", "EMPTY::")) for key in artifacts)
    blocker = "declared artifact root missing or empty" if missing else None
    return CommandResult(
        command_id=command.command_id,
        status=(
            "passed"
            if process.returncode in command.accepted_return_codes and not missing
            else "failed"
        ),
        return_code=int(process.returncode),
        elapsed_seconds=elapsed,
        log_path=str(log_path),
        log_sha256=file_sha256(log_path),
        artifact_sha256=artifacts,
        blocker=blocker,
        variant_id=command.variant_id,
        component=command.component,
        seed=command.seed,
        result_artifact=command.result_artifact,
    )


def _load_state(path: Path) -> dict[str, Any]:
    """Load and validate a persisted execution-state object.

    Args:
        path: Path to the input or output artifact.

    Returns:
        Result produced by _load_state.
    """
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"execution state must be a JSON object: {path}")
    return value


def execute_command_bundle(
    bundle: CommandBundle,
    *,
    run_root: Path,
    max_workers: int,
    allow_experiments: bool,
    resume: bool = False,
    retry_failed: bool = False,
    max_runtime_seconds: float | None = None,
) -> dict[str, Any]:
    """Execute one source-bound command graph and persist resumable state.

    Args:
        bundle: Frozen source-bound command bundle.
        run_root: Directory containing execution state and command attempts.
        max_workers: Maximum number of concurrently active commands.
        allow_experiments: Whether commands that allocate experimental compute are authorized.
        resume: Whether to resume an existing execution state.
        retry_failed: Whether reviewed failed commands may be retried.
        max_runtime_seconds: Optional execution time budget.

    Returns:
        Result produced by execute_command_bundle.
    """
    if max_workers < 1:
        raise ValueError("max_workers must be positive")
    source_sha, clean = _git_state()
    if not clean:
        raise ValueError("research execution requires a clean source tree")
    if bundle.source_commit != source_sha:
        raise ValueError("research command bundle source commit is stale")
    if any(item.experiment for item in bundle.commands) and not allow_experiments:
        raise ValueError("experiment commands require explicit allow_experiments=True")
    by_id = {item.command_id: item for item in bundle.commands}
    if len(by_id) != len(bundle.commands):
        raise ValueError("research command IDs must be unique")
    for item in bundle.commands:
        _validate_argv(item.argv)
        unknown = set(item.depends_on) - set(by_id)
        if unknown:
            raise ValueError(f"{item.command_id}: unknown dependencies {sorted(unknown)}")

    serialized = bundle_payload(bundle)
    bundle_sha256 = hashlib.sha256(
        json.dumps(serialized, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    state_path = run_root / "execution_manifest.json"
    results: dict[str, CommandResult] = {}
    attempts = {command_id: 0 for command_id in by_id}

    if run_root.exists():
        if not resume or not state_path.is_file():
            raise ValueError("run root exists; resume requires its execution manifest")
        state = _load_state(state_path)
        if (
            state.get("schema_version") != 1
            or state.get("source_commit") != source_sha
            or state.get("bundle_sha256") != bundle_sha256
        ):
            raise ValueError("saved execution state does not match bundle and source")
        saved_rows = state.get("commands")
        if not isinstance(saved_rows, list):
            raise ValueError("saved execution state has no command records")
        saved = {str(row.get("command_id")): row for row in saved_rows if isinstance(row, dict)}
        if set(saved) != set(by_id):
            raise ValueError("saved execution command set differs from the bundle")
        for command_id, row in saved.items():
            attempt_dir = run_root / "commands" / command_id
            attempts[command_id] = len(tuple(attempt_dir.glob("attempt_*")))
            status = row.get("status")
            if status == "passed":
                result = CommandResult(**row)
                if result.artifact_sha256 != _artifact_hashes(by_id[command_id].artifact_roots):
                    raise ValueError(f"completed command artifacts changed: {command_id}")
                results[command_id] = result
            elif status == "failed" and not retry_failed:
                raise ValueError(
                    f"saved command {command_id} failed; use retry_failed=True after review"
                )
            elif status not in {"failed", "blocked", "running", "pending"}:
                raise ValueError(f"saved command {command_id} has unknown status {status!r}")
    else:
        if resume:
            raise ValueError("cannot resume a missing run root")
        run_root.mkdir(parents=True)

    pending = set(by_id) - set(results)
    active: dict[Future[CommandResult], CommandSpec] = {}
    active_locks: set[str] = set()
    started = time.perf_counter()

    def write_state(status: str, running: set[str] | None = None) -> None:
        """Persist the current command-graph execution state.

        Args:
            status: Recorded review or execution status.
            running: Identifiers of commands currently running.
        """
        running = running or set()
        rows: list[dict[str, Any]] = []
        for command_id in by_id:
            if command_id in results:
                rows.append(asdict(results[command_id]))
                continue
            rows.append(
                asdict(
                    CommandResult(
                        command_id=command_id,
                        status="running" if command_id in running else "pending",
                        return_code=None,
                        elapsed_seconds=None,
                        log_path=None,
                        log_sha256=None,
                        artifact_sha256={},
                        blocker=None,
                        variant_id=by_id[command_id].variant_id,
                        component=by_id[command_id].component,
                        seed=by_id[command_id].seed,
                        result_artifact=by_id[command_id].result_artifact,
                    )
                )
            )
        write_json_atomic(
            state_path,
            {
                "schema_version": 1,
                "source_commit": source_sha,
                "bundle_sha256": bundle_sha256,
                "experiment_id": bundle.experiment_id,
                "domain": bundle.domain,
                "status": status,
                "commands": rows,
            },
        )

    write_state("running")
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        while pending or active:
            made_progress = False
            for command_id in sorted(tuple(pending)):
                command = by_id[command_id]
                if not active and max_runtime_seconds is not None:
                    elapsed = time.perf_counter() - started
                    if elapsed + command.estimated_seconds > max_runtime_seconds:
                        write_state("incomplete")
                        return _load_state(state_path)
                if any(dependency not in results for dependency in command.depends_on):
                    continue
                failed_dependencies = [
                    dependency
                    for dependency in command.depends_on
                    if results[dependency].status != "passed"
                ]
                if failed_dependencies and not command.continue_on_dependency_failure:
                    results[command_id] = CommandResult(
                        command_id=command_id,
                        status="blocked",
                        return_code=None,
                        elapsed_seconds=None,
                        log_path=None,
                        log_sha256=None,
                        artifact_sha256={},
                        blocker="dependency failure: " + ", ".join(failed_dependencies),
                        variant_id=command.variant_id,
                        component=command.component,
                        seed=command.seed,
                        result_artifact=command.result_artifact,
                    )
                    pending.remove(command_id)
                    made_progress = True
                    continue
                if command.resource_lock and command.resource_lock in active_locks:
                    continue
                if len(active) >= max_workers:
                    break
                attempts[command_id] += 1
                if command.resource_lock:
                    active_locks.add(command.resource_lock)
                future = pool.submit(_run_one, command, run_root, attempt=attempts[command_id])
                active[future] = command
                pending.remove(command_id)
                made_progress = True

            if active:
                done, _ = wait(active, return_when="FIRST_COMPLETED")
                for future in done:
                    command = active.pop(future)
                    result = future.result()
                    results[result.command_id] = result
                    if command.resource_lock:
                        active_locks.discard(command.resource_lock)
                    made_progress = True
                write_state("running", {item.command_id for item in active.values()})
            elif made_progress:
                write_state("running")

            if not made_progress and pending:
                raise RuntimeError("research command scheduler made no progress")

    final_status = (
        "passed" if all(result.status == "passed" for result in results.values()) else "failed"
    )
    write_state(final_status)
    return _load_state(state_path)


__all__ = [
    "CommandBundle",
    "CommandResult",
    "CommandSpec",
    "bundle_from_payload",
    "bundle_payload",
    "execute_command_bundle",
]
