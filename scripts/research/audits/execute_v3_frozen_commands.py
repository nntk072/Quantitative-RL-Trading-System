#!/usr/bin/env python3
"""Execute an immutable direct-command DAG inside the current allocation.

No Slurm allocation/cancellation commands are allowed. Experiment commands
require an explicit --allow-experiments switch and still run as direct child
processes of the current shell/allocation.
"""

from __future__ import annotations

import argparse
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


def _run_one(command: dict[str, Any], run_root: Path) -> CommandResult:
    command_id = str(command["id"])
    task_dir = run_root / "commands" / command_id
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

    if run_root.exists():
        raise ValueError("run root must be fresh")
    run_root.mkdir(parents=True)

    pending = set(by_id)
    results: dict[str, CommandResult] = {}
    active: dict[Future[CommandResult], dict[str, Any]] = {}
    active_locks: set[str] = set()

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        while pending or active:
            made_progress = False
            for command_id in sorted(tuple(pending)):
                row = by_id[command_id]
                deps = list(row.get("depends_on", []))
                if any(dep not in results for dep in deps):
                    continue
                failed = [dep for dep in deps if results[dep].status != "pass"]
                if failed:
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
                    made_progress = True
                    continue
                lock = row.get("resource_lock")
                if isinstance(lock, str) and lock in active_locks:
                    continue
                if len(active) >= max_workers:
                    break
                if isinstance(lock, str) and lock:
                    active_locks.add(lock)
                active[pool.submit(_run_one, row, run_root)] = row
                pending.remove(command_id)
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
                    made_progress = True
            if not made_progress and pending:
                raise RuntimeError("frozen command scheduler made no progress")

    payload = {
        "schema_version": "v3-frozen-command-execution-v1",
        "source_commit": source_sha,
        "phase": bundle.get("phase"),
        "status": "pass" if all(result.status == "pass" for result in results.values()) else "fail",
        "commands": [asdict(results[command_id]) for command_id in by_id],
    }
    write_json_atomic(run_root / "execution_manifest.json", payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--max-workers", type=int, default=1)
    parser.add_argument("--allow-experiments", action="store_true")
    args = parser.parse_args()
    result = execute_bundle(
        _object(args.bundle.expanduser().resolve()),
        run_root=args.run_root.expanduser().resolve(),
        max_workers=args.max_workers,
        allow_experiments=args.allow_experiments,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
