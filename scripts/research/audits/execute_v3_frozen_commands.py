#!/usr/bin/env python3
"""Execute an immutable direct-command DAG inside the current allocation.

No Slurm allocation/cancellation commands are allowed. Experiment commands
require an explicit --allow-experiments switch and still run as direct child
processes of the current shell/allocation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from scripts.research.audits.record_pretraining_scientific_gate import file_sha256

from artifacts.atomic import write_json_atomic
from configuration.paths import repository_root

ROOT = repository_root(__file__)
FORBIDDEN_EXECUTABLES = {"salloc", "sbatch", "scancel", "srun"}


@dataclass(frozen=True, slots=True)
class CommandResult:
    command_id: str
    status: str
    return_code: int | None
    elapsed_seconds: float | None
    log_path: str | None
    log_sha256: str | None
    artifact_sha256: dict[str, str]
    blocker: str | None


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _git_state() -> tuple[str, bool]:
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()
    return sha, not dirty


def _validate_argv(argv: Any) -> tuple[str, ...]:
    if not isinstance(argv, list) or not argv or any(not isinstance(x, str) or not x for x in argv):
        raise ValueError("command argv must be a non-empty string list")
    for token in argv:
        if Path(token).name.lower() in FORBIDDEN_EXECUTABLES:
            raise ValueError(f"forbidden scheduler executable in command: {token}")
    return tuple(argv)


def _artifact_hashes(roots: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in roots:
        path = Path(raw)
        if path.is_file():
            result[str(path)] = file_sha256(path)
        elif path.is_dir():
            files = [child for child in sorted(path.rglob("*")) if child.is_file()]
            if not files:
                result[f"EMPTY::{path}"] = ""
            for child in files:
                result[str(child)] = file_sha256(child)
        else:
            result[f"MISSING::{path}"] = ""
    return result


def _run_one(command: dict[str, Any], run_root: Path, *, attempt: int) -> CommandResult:
    command_id = str(command["id"])
    task_dir = run_root / "commands" / command_id / f"attempt_{attempt:03d}"
    task_dir.mkdir(parents=True, exist_ok=True)
    log_path = task_dir / "run.log"
    started = time.perf_counter()
    with log_path.open("wb") as stream:
        process = subprocess.run(
            list(_validate_argv(command["argv"])),
            cwd=ROOT,
            env=os.environ.copy(),
            stdout=stream,
            stderr=subprocess.STDOUT,
            check=False,
        )
    elapsed = time.perf_counter() - started
    artifacts = _artifact_hashes(list(command.get("artifact_roots", [])))
    missing = any(key.startswith(("MISSING::", "EMPTY::")) for key in artifacts)
    return CommandResult(
        command_id=command_id,
        status="pass" if process.returncode == 0 and not missing else "fail",
        return_code=int(process.returncode),
        elapsed_seconds=elapsed,
        log_path=str(log_path),
        log_sha256=file_sha256(log_path),
        artifact_sha256=artifacts,
        blocker="declared artifact root missing or empty" if missing else None,
    )


def execute_bundle(
    bundle: dict[str, Any],
    *,
    run_root: Path,
    max_workers: int,
    allow_experiments: bool,
    resume: bool = False,
    max_runtime_seconds: float | None = None,
) -> dict[str, Any]:
    """Run one frozen direct-command bundle with dependencies and logical locks."""
    source_sha, clean = _git_state()
    if not clean:
        raise ValueError("frozen command execution requires a clean source tree")
    if bundle.get("schema_version") != "v3-frozen-command-bundle-v1":
        raise ValueError("unsupported frozen command bundle schema")
    if bundle.get("source_commit") != source_sha:
        raise ValueError("frozen command bundle source SHA is stale")
    commands = bundle.get("commands")
    if not isinstance(commands, list) or not commands:
        raise ValueError("frozen command bundle has no commands")
    by_id: dict[str, dict[str, Any]] = {}
    for row in commands:
        if not isinstance(row, dict):
            raise ValueError("frozen command row must be an object")
        command_id = str(row.get("id", "")).strip()
        if not command_id or command_id in by_id:
            raise ValueError("frozen command IDs must be unique")
        _validate_argv(row.get("argv"))
        if row.get("experiment") is True and not allow_experiments:
            raise ValueError(
                f"experiment command {command_id} requires explicit --allow-experiments"
            )
        by_id[command_id] = row
    for row in by_id.values():
        deps = row.get("depends_on", [])
        if not isinstance(deps, list) or set(deps) - set(by_id):
            raise ValueError(f"{row['id']} has invalid command dependencies")

    bundle_sha256 = hashlib.sha256(
        json.dumps(bundle, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    state_path = run_root / "execution_manifest.json"
    results: dict[str, CommandResult] = {}
    attempts: dict[str, int] = {command_id: 0 for command_id in by_id}
    if run_root.exists():
        if not resume or not state_path.is_file():
            raise ValueError("run root exists; pass --resume with its matching execution manifest")
        state = _object(state_path)
        if (
            state.get("schema_version") != "v3-frozen-command-execution-v1"
            or state.get("source_commit") != source_sha
            or state.get("bundle_sha256") != bundle_sha256
        ):
            raise ValueError("saved execution state does not match the frozen bundle and source")
        saved_rows = state.get("commands")
        if not isinstance(saved_rows, list):
            raise ValueError("saved execution state has no command records")
        saved_by_id = {
            str(row.get("command_id")): row for row in saved_rows if isinstance(row, dict)
        }
        if set(saved_by_id) != set(by_id):
            raise ValueError("saved execution state command set differs from the frozen bundle")
        for command_id, row in saved_by_id.items():
            status = row.get("status")
            if status == "pass":
                result = CommandResult(**row)
                current_artifacts = _artifact_hashes(
                    list(by_id[command_id].get("artifact_roots", []))
                )
                if result.artifact_sha256 != current_artifacts:
                    raise ValueError(f"completed command artifacts changed: {command_id}")
                results[command_id] = result
                attempts[command_id] = len(
                    list((run_root / "commands" / command_id).glob("attempt_*"))
                )
            elif status in {"fail", "blocked"}:
                raise ValueError(f"saved command {command_id} failed; inspect it before retrying")
            elif status in {"running", "pending"}:
                attempts[command_id] = len(
                    list((run_root / "commands" / command_id).glob("attempt_*"))
                )
            else:
                raise ValueError(f"saved command {command_id} has unknown status {status!r}")
    else:
        if resume:
            raise ValueError("cannot resume a run root that does not exist")
        run_root.mkdir(parents=True)

    pending = set(by_id) - set(results)
    active: dict[Future[CommandResult], dict[str, Any]] = {}
    active_locks: set[str] = set()
    started = time.perf_counter()

    def write_state(status: str, running: set[str] | None = None) -> None:
        records = []
        running = running or set()
        for command_id in by_id:
            if command_id in results:
                records.append(asdict(results[command_id]))
            else:
                records.append(
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
                        )
                    )
                )
        payload = {
            "schema_version": "v3-frozen-command-execution-v1",
            "source_commit": source_sha,
            "bundle_sha256": bundle_sha256,
            "phase": bundle.get("phase"),
            "status": status,
            "commands": records,
        }
        write_json_atomic(state_path, payload)

    write_state("running")

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        while pending or active:
            made_progress = False
            for command_id in sorted(tuple(pending)):
                if not active and max_runtime_seconds is not None:
                    elapsed = time.perf_counter() - started
                    expected = float(by_id[command_id].get("estimated_seconds", 0.0))
                    if elapsed + expected > max_runtime_seconds:
                        write_state("incomplete")
                        return _object(state_path)
                row = by_id[command_id]
                deps = list(row.get("depends_on", []))
                if any(dep not in results for dep in deps):
                    continue
                failed = [dep for dep in deps if results[dep].status != "pass"]
                if failed and row.get("run_after_failed_dependencies") is not True:
                    results[command_id] = CommandResult(
                        command_id=command_id,
                        status="blocked",
                        return_code=None,
                        elapsed_seconds=None,
                        log_path=None,
                        log_sha256=None,
                        artifact_sha256={},
                        blocker="dependency failure: " + ", ".join(failed),
                    )
                    pending.remove(command_id)
                    write_state("running")
                    made_progress = True
                    continue
                lock = row.get("resource_lock")
                if isinstance(lock, str) and lock in active_locks:
                    continue
                if len(active) >= max_workers:
                    break
                if isinstance(lock, str) and lock:
                    active_locks.add(lock)
                attempts[command_id] += 1
                active[pool.submit(_run_one, row, run_root, attempt=attempts[command_id])] = row
                pending.remove(command_id)
                write_state("running", {str(value["id"]) for value in active.values()})
                made_progress = True

            if active:
                done, _ = wait(active, return_when="FIRST_COMPLETED")
                for future in done:
                    row = active.pop(future)
                    result = future.result()
                    results[result.command_id] = result
                    lock = row.get("resource_lock")
                    if isinstance(lock, str) and lock:
                        active_locks.discard(lock)
                    write_state("running", {str(value["id"]) for value in active.values()})
                    made_progress = True
            if not made_progress and pending:
                raise RuntimeError("frozen command scheduler made no progress")

    status = "pass" if all(result.status == "pass" for result in results.values()) else "fail"
    write_state(status)
    payload = _object(state_path)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--max-workers", type=int, default=1)
    parser.add_argument("--allow-experiments", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--max-runtime-seconds", type=float, default=42_000)
    args = parser.parse_args()
    result = execute_bundle(
        _object(args.bundle.expanduser().resolve()),
        run_root=args.run_root.expanduser().resolve(),
        max_workers=args.max_workers,
        allow_experiments=args.allow_experiments,
        resume=args.resume,
        max_runtime_seconds=args.max_runtime_seconds,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 2 if result["status"] == "incomplete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
