"""Source identity, bounded subprocess execution and local evidence persistence."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import time
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
OUTPUT = ROOT / "outputs/quality-local"


def quality_file_sha256(path: Path) -> str:
    """Hash a file in bounded memory."""
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_quality_json(path: Path) -> Any:
    """Read JSON; invalid evidence raises instead of producing an empty report."""
    return json.loads(path.read_text(encoding="utf-8"))


def write_quality_json(path: Path, data: Any) -> None:
    """Publish complete JSON atomically, never permitting nonfinite numeric values."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temp.write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n")
    temp.replace(path)


def quality_git(*args: str, root: Path = ROOT) -> bytes:
    """Run a read-only Git query in the repository."""
    return subprocess.check_output(["git", *args], cwd=root)


def quality_source_paths(root: Path = ROOT) -> list[str]:
    """Enumerate tracked and unignored working-tree files, including local additions."""
    raw = quality_git("ls-files", "-z", "--cached", "--others", "--exclude-standard", root=root)
    names = {os.fsdecode(name) for name in raw.split(b"\0") if name}
    return sorted(p for p in names if (root / p).is_file() or (root / p).is_symlink())


def quality_source_identity(root: Path = ROOT) -> dict[str, Any]:
    """Fingerprint the exact working tree and dependency lock, not just HEAD."""
    source = hashlib.sha256()
    for name in quality_source_paths(root):
        path = root / name
        value = (
            hashlib.sha256(os.fsencode(os.readlink(path))).hexdigest()
            if path.is_symlink()
            else quality_file_sha256(path)
        )
        source.update(os.fsencode(name) + b"\0" + value.encode() + b"\0")
    lock = root / "uv.lock"
    policy = root / "tools/quality/local_checks/policy.json"
    return {
        "source_commit": quality_git("rev-parse", "HEAD", root=root).decode().strip(),
        "git_tree_sha": quality_git("rev-parse", "HEAD^{tree}", root=root).decode().strip(),
        "source_branch": quality_git("branch", "--show-current", root=root).decode().strip() or "detached",
        "tree_sha256": source.hexdigest(),
        "dirty": bool(quality_git("status", "--porcelain", "--untracked-files=normal", root=root)),
        "lock_sha256": quality_file_sha256(lock) if lock.is_file() else None,
        "policy_sha256": quality_file_sha256(policy) if policy.is_file() else None,
        "platform": platform.platform(),
        "architecture": platform.machine(),
        "python": sys.version,
    }


def quality_timestamp() -> str:
    """Return an unambiguous UTC timestamp for local evidence."""
    return datetime.now(UTC).isoformat()


def quality_tool_versions() -> dict[str, str | None]:
    """Record relevant installed distribution versions without running installers."""
    result: dict[str, str | None] = {}
    for name in ("coverage", "pytest", "pytest-cov", "hypothesis", "mutmut", "ruff", "mypy"):
        try:
            result[name] = version(name)
        except PackageNotFoundError:
            result[name] = None
    return result


def quality_executable(name: str) -> str | None:
    """Prefer the selected Python environment before searching PATH."""
    local = Path(sys.executable).parent / name
    if local.is_file() and os.access(local, os.X_OK):
        return str(local)
    analyzer_bin = os.environ.get("QRL_ANALYZER_BIN")
    if analyzer_bin:
        candidate = Path(analyzer_bin) / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return shutil.which(name)


def run_quality_process(
    command: list[str],
    out: Path,
    timeout: int,
    *,
    cwd: Path = ROOT,
    env: dict[str, str] | None = None,
    findings_codes: tuple[int, ...] = (),
) -> dict[str, Any]:
    """Run a bounded command without a shell and retain separate stdout and stderr."""
    if timeout <= 0 or not command:
        raise ValueError("Invalid execution budget or command")
    out.parent.mkdir(parents=True, exist_ok=True)
    exe = quality_executable(command[0])
    if not exe:
        return {"status": "missing_tool", "command": command[0]}
    start = time.monotonic()
    stderr = out.with_suffix(out.suffix + ".stderr")
    with out.open("wb") as stdout, stderr.open("wb") as error:
        try:
            proc = subprocess.Popen(
                [exe, *command[1:]],
                cwd=cwd,
                env={**os.environ, **(env or {})},
                stdout=stdout,
                stderr=error,
                start_new_session=os.name == "posix",
            )
        except OSError as exc:
            return {"status": "error", "error": str(exc)}
        try:
            code = proc.wait(timeout=timeout)
            status = "ok" if code == 0 else "findings" if code in findings_codes else "error"
        except subprocess.TimeoutExpired:
            if os.name == "posix":
                os.killpg(proc.pid, signal.SIGKILL)
            else:
                proc.kill()
            code = proc.wait()
            status = "timeout"
    return {
        "status": status,
        "returncode": code,
        "seconds": time.monotonic() - start,
        "stdout": str(out),
        "stderr": str(stderr),
    }


def create_quality_run() -> Path:
    """Allocate an isolated directory in the ignored local evidence store."""
    result = OUTPUT / f"{datetime.now(UTC):%Y%m%dT%H%M%S}-{uuid4().hex[:12]}"
    result.mkdir(parents=True)
    return result


def publish_quality_manifest(
    out: Path, before: dict[str, Any], started: str, action: str, result: dict[str, Any], mode: str = "advisory"
) -> dict[str, Any]:
    """Bind outputs to the measured source state, refusing changed-tree success."""
    after = quality_source_identity()
    unchanged = before == after
    artifacts = {
        p.relative_to(out).as_posix(): quality_file_sha256(p)
        for p in sorted(out.rglob("*"))
        if p.is_file() and not p.is_symlink() and p.name != "manifest.json"
    }
    manifest = {
        "schema_version": 1,
        **before,
        "run_id": out.name,
        "action": action,
        "started_at": started,
        "finished_at": quality_timestamp(),
        "tool_versions": quality_tool_versions(),
        "enforcement_mode": mode,
        "execution_status": result.get("status", "ok") if unchanged else "source_changed",
        "source_unchanged": unchanged,
        "result": result,
        "artifacts": artifacts,
    }
    write_quality_json(out / "manifest.json", manifest)
    return manifest


def verify_quality_manifest(manifest_path: Path) -> dict[str, Any]:
    """Verify every referenced artifact; this establishes integrity, not authenticity."""
    value = read_quality_json(manifest_path)
    root = manifest_path.parent.resolve()
    if value.get("schema_version") != 1 or value.get("source_unchanged") is not True:
        raise ValueError("Invalid or inconsistent run manifest")
    artifacts = value["artifacts"]
    if not isinstance(artifacts, dict):
        raise ValueError("Invalid artifact inventory")
    actual = {
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_file() and not p.is_symlink() and p.name != "manifest.json"
    }
    if set(artifacts) != actual:
        raise ValueError("Missing or unexpected artifact files")
    for name, expected in artifacts.items():
        path = root / name
        if path.is_symlink() or not path.resolve().is_relative_to(root) or quality_file_sha256(path) != expected:
            raise ValueError(f"Artifact integrity failure: {name}")
    return {"status": "ok", "manifest": str(manifest_path), "artifact_count": len(artifacts)}
