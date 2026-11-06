#!/usr/bin/env python3
"""Rehash files and archived source snapshots declared by the research provenance DAG."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

from artifacts.atomic import write_json_atomic
from configuration.paths import repository_root
from experiments.runs.source_snapshot import verify_experiment_run_source_snapshot

ROOT = repository_root(__file__)
ARCHIVE_ROOT = ROOT.parent / "Quantitative-RL-Trading-System-research-archive"
DEFAULT_DAG = (
    ROOT / "evidence/research/releases/negative-evidence-readiness/EXPERIMENT_PROVENANCE_DAG.json"
)
DEFAULT_OUTPUT = (
    ROOT
    / "evidence/research/releases/negative-evidence-readiness/PROVENANCE_BYTE_VERIFICATION.json"
)
HASH_LENGTH = 64
GIT_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
MAX_GIT_SOURCE_BLOB_BYTES = 32 * 1024 * 1024


def _sha256(path: Path) -> tuple[str, int]:
    """Hash a file and reject changes to its identity or size during the read."""
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    after = path.stat()
    identity_before = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
    identity_after = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    if identity_before != identity_after:
        raise OSError(f"file changed while hashing: {path}")
    return digest.hexdigest(), after.st_size


def _resolve_path(value: Any, root: Path, archive_root: Path) -> tuple[Path | None, str | None]:
    """Resolve one repository-relative path while constraining symlink targets."""
    if not isinstance(value, str) or not value:
        return None, "path is missing"
    relative = PurePosixPath(value)
    if relative.is_absolute() or ".." in relative.parts:
        return None, "path is absolute or contains traversal"
    candidate = root / Path(*relative.parts)
    resolved = candidate.resolve()
    for allowed in (root.resolve(), archive_root.resolve()):
        try:
            resolved.relative_to(allowed)
            return resolved, None
        except ValueError:
            continue
    return None, "resolved path escapes approved roots"


def _snapshot_sources(path: Path) -> dict[str, str]:
    """Return verified path/hash pairs from a previously verified snapshot ZIP."""
    with zipfile.ZipFile(path, "r") as archive:
        manifest = json.loads(archive.read("source_manifest.json"))
    files = manifest.get("files")
    if not isinstance(files, dict):
        raise ValueError("source snapshot has no file hash mapping")
    return {str(name): str(digest) for name, digest in files.items()}


def _relocated_artifact_matches(
    relative_path: str,
    expected_hash: str,
    root: Path,
    archive_root: Path,
    artifact_index: dict[Path, dict[str, list[Path]]],
) -> list[tuple[Path, int]]:
    """Find byte-identical run artifacts under their original campaign directory.

    Archived campaign attempts may be nested under ``runs/attempts`` after
    recovery. Restrict the lookup to the campaign directory named by the
    manifest path, then require the declared digest to match.
    """
    relative = PurePosixPath(relative_path)
    if len(relative.parts) < 4 or relative.parts[0] != "outputs":
        return []
    campaign_root = root.joinpath(*relative.parts[:3]).resolve()
    allowed_roots = (root.resolve(), archive_root.resolve())
    if not any(_is_relative_to(campaign_root, allowed) for allowed in allowed_roots):
        return []
    if not campaign_root.is_dir():
        return []
    if campaign_root not in artifact_index:
        index: dict[str, list[Path]] = {}
        for candidate in campaign_root.rglob("*"):
            if candidate.is_file():
                index.setdefault(candidate.name, []).append(candidate)
        artifact_index[campaign_root] = index
    matches: list[tuple[Path, int]] = []
    for candidate in artifact_index[campaign_root].get(relative.name, []):
        resolved = candidate.resolve()
        if not any(_is_relative_to(resolved, allowed) for allowed in allowed_roots):
            continue
        if not candidate.is_file():
            continue
        try:
            actual_hash, size_bytes = _sha256(candidate)
        except OSError:
            continue
        if actual_hash == expected_hash:
            matches.append((resolved, size_bytes))
    return matches


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _source_run_commits(dag: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Map each source node to source commits declared by its consuming runs."""
    nodes = dag.get("nodes")
    edges = dag.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return {}
    runs = {
        str(node.get("id")): node
        for node in nodes
        if isinstance(node, dict) and node.get("kind") == "run"
    }
    by_source: dict[str, dict[str, dict[str, Any]]] = {}
    for edge in edges:
        if not isinstance(edge, dict) or edge.get("relation") != "uses_source":
            continue
        run_node_id = str(edge.get("from"))
        run = runs.get(run_node_id)
        source_id = edge.get("to")
        if not isinstance(source_id, str):
            continue
        commit = run.get("source_commit") if run is not None else None
        commit_is_valid = isinstance(commit, str) and (
            GIT_COMMIT_PATTERN.fullmatch(commit) is not None
        )
        commit_key = str(commit) if commit_is_valid else f"invalid:{run_node_id}"
        entry = by_source.setdefault(source_id, {}).setdefault(
            commit_key,
            {"source_commit": commit, "run_ids": [], "commit_is_valid": commit_is_valid},
        )
        run_id = run.get("run_id") if run is not None else run_node_id
        if isinstance(run_id, str) and run_id not in entry["run_ids"]:
            entry["run_ids"].append(run_id)
    return {source_id: list(commits.values()) for source_id, commits in by_source.items()}


def _verify_source_file_in_run_commits(
    *,
    node_id: str,
    path_value: Any,
    expected_hash: str,
    source_commits: dict[str, list[dict[str, Any]]],
    root: Path,
    blob_cache: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    """Verify declared source bytes in every unique linked run commit."""
    commits = source_commits.get(node_id, [])
    if not commits:
        return {"status": "not_linked", "linked_source_commit_count": 0, "checks": []}
    if not isinstance(path_value, str):
        return {"status": "invalid_path", "linked_source_commit_count": len(commits), "checks": []}
    relative = PurePosixPath(path_value)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        return {"status": "invalid_path", "linked_source_commit_count": len(commits), "checks": []}

    checks: list[dict[str, Any]] = []
    for linked in commits:
        commit_value = linked.get("source_commit")
        if not linked.get("commit_is_valid"):
            checks.append(
                {
                    "source_commit": commit_value,
                    "run_ids": linked["run_ids"],
                    "status": "invalid_commit",
                }
            )
            continue
        commit = str(commit_value)
        key = (commit, path_value)
        checked = blob_cache.get(key)
        if checked is None:
            spec = f"{commit}:{relative.as_posix()}"
            try:
                size_result = subprocess.run(
                    ["git", "cat-file", "-s", spec],
                    cwd=root,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=10,
                )
                if size_result.returncode != 0:
                    checked = {"status": "unavailable"}
                else:
                    size_bytes = int(size_result.stdout.strip())
                    if size_bytes > MAX_GIT_SOURCE_BLOB_BYTES:
                        checked = {"status": "too_large", "size_bytes": size_bytes}
                    else:
                        blob_result = subprocess.run(
                            ["git", "cat-file", "blob", spec],
                            cwd=root,
                            capture_output=True,
                            check=False,
                            timeout=10,
                        )
                        if blob_result.returncode != 0:
                            checked = {"status": "unavailable"}
                        else:
                            actual_hash = hashlib.sha256(blob_result.stdout).hexdigest()
                            checked = {
                                "status": "match" if actual_hash == expected_hash else "mismatch",
                                "actual_sha256": actual_hash,
                                "size_bytes": size_bytes,
                            }
            except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
                checked = {"status": "unavailable", "error": type(exc).__name__}
            blob_cache[key] = checked
        checks.append(
            {
                "source_commit": commit,
                "run_ids": linked["run_ids"],
                **checked,
            }
        )

    match_count = sum(check["status"] == "match" for check in checks)
    if match_count == len(checks):
        status = "verified"
    elif match_count:
        status = "partial"
    elif any(check["status"] == "mismatch" for check in checks):
        status = "mismatch"
    else:
        status = "unavailable"
    return {
        "status": status,
        "linked_source_commit_count": len(checks),
        "matching_source_commit_count": match_count,
        "checks": checks,
    }


def verify_provenance_dag_bytes(
    dag_path: Path = DEFAULT_DAG,
    *,
    root: Path = ROOT,
    archive_root: Path = ARCHIVE_ROOT,
) -> dict[str, Any]:
    """Rehash every declared file node and verify each complete source snapshot."""
    dag_path = dag_path.resolve()
    dag = json.loads(dag_path.read_text(encoding="utf-8"))
    if dag.get("schema") != "research-provenance-dag-v1":
        raise ValueError("unsupported research provenance DAG schema")
    nodes = dag.get("nodes")
    if not isinstance(nodes, list):
        raise ValueError("provenance DAG nodes must be a list")

    results: dict[str, dict[str, Any]] = {}
    hash_cache: dict[Path, tuple[str, int] | str] = {}
    artifact_index: dict[Path, dict[str, list[Path]]] = {}
    verified_snapshot_sources: set[tuple[str, str]] = set()
    source_commits = _source_run_commits(dag)
    git_source_blob_cache: dict[tuple[str, str], dict[str, Any]] = {}
    snapshot_payload_bytes = 0
    snapshot_file_count = 0

    for node in nodes:
        if node.get("kind") != "source_snapshot":
            continue
        node_id = str(node.get("id", ""))
        path, path_error = _resolve_path(node.get("path"), root, archive_root)
        if path_error:
            results[node_id] = {
                "kind": "source_snapshot",
                "status": "blocked",
                "reason": path_error,
            }
            continue
        assert path is not None
        if not path.is_file():
            results[node_id] = {
                "kind": "source_snapshot",
                "path": str(node["path"]),
                "status": "missing",
            }
            continue
        try:
            actual_hash, size_bytes = _sha256(path)
            record = {
                "sha256": node.get("sha256"),
                "manifest_sha256": node.get("manifest_sha256"),
                "file_count": node.get("file_count"),
            }
            if actual_hash != record["sha256"]:
                raise ValueError("source snapshot archive SHA-256 mismatch")
            valid, reason = verify_experiment_run_source_snapshot(path, record)
            if not valid:
                raise ValueError(reason)
            source_files = _snapshot_sources(path)
            verified_snapshot_sources.update(source_files.items())
            with zipfile.ZipFile(path, "r") as archive:
                snapshot_payload_bytes += sum(
                    info.file_size
                    for info in archive.infolist()
                    if info.filename != "source_manifest.json"
                )
            snapshot_file_count += len(source_files)
            hash_cache[path] = (actual_hash, size_bytes)
            results[node_id] = {
                "kind": "source_snapshot",
                "path": str(node["path"]),
                "sha256": actual_hash,
                "size_bytes": size_bytes,
                "embedded_source_files": len(source_files),
                "status": "verified",
            }
        except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
            results[node_id] = {
                "kind": "source_snapshot",
                "path": str(node["path"]),
                "status": "mismatch",
                "reason": str(exc),
            }

    hashed_node_count = 0
    for node in nodes:
        kind = str(node.get("kind", "unknown"))
        if kind == "source_snapshot":
            continue
        node_id = str(node.get("id", ""))
        expected = node.get("sha256")
        path_value = node.get("path")
        if not isinstance(expected, str) or len(expected) != HASH_LENGTH:
            results[node_id] = {"kind": kind, "status": "not_byte_addressed"}
            continue
        hashed_node_count += 1
        if kind == "source_file" and (str(path_value), expected) in verified_snapshot_sources:
            results[node_id] = {
                "kind": kind,
                "path": path_value,
                "sha256": expected,
                "status": "verified_in_source_snapshot",
            }
            continue
        path, path_error = _resolve_path(path_value, root, archive_root)
        if path_error:
            results[node_id] = {
                "kind": kind,
                "path": path_value,
                "status": "blocked",
                "reason": path_error,
            }
            continue
        assert path is not None
        if not path.is_file():
            if kind == "run_artifact":
                relocated = _relocated_artifact_matches(
                    str(path_value), expected, root, archive_root, artifact_index
                )
                if relocated:
                    results[node_id] = {
                        "kind": kind,
                        "path": path_value,
                        "verified_paths": [str(candidate) for candidate, _ in relocated],
                        "size_bytes": relocated[0][1],
                        "status": "verified_relocated",
                    }
                    continue
            result = {
                "kind": kind,
                "path": path_value,
                "status": "historical_source_unavailable" if kind == "source_file" else "missing",
            }
            if kind == "source_file":
                git_history = _verify_source_file_in_run_commits(
                    node_id=node_id,
                    path_value=path_value,
                    expected_hash=expected,
                    source_commits=source_commits,
                    root=root,
                    blob_cache=git_source_blob_cache,
                )
                result["git_source_commit_verification"] = git_history
                if git_history["status"] == "verified":
                    result["status"] = "verified_in_source_commit"
            results[node_id] = result
            continue
        cached = hash_cache.get(path)
        if cached is None:
            try:
                cached = _sha256(path)
            except OSError as exc:
                hash_cache[path] = str(exc)
                results[node_id] = {
                    "kind": kind,
                    "path": path_value,
                    "status": "unstable",
                    "reason": str(exc),
                }
                continue
            hash_cache[path] = cached
        if isinstance(cached, str):
            results[node_id] = {
                "kind": kind,
                "path": path_value,
                "status": "unstable",
                "reason": cached,
            }
            continue
        actual_hash, size_bytes = cached
        result = {
            "kind": kind,
            "path": path_value,
            "sha256": actual_hash,
            "expected_sha256": expected,
            "size_bytes": size_bytes,
            "status": "verified_current_path"
            if actual_hash == expected
            else "historical_source_unavailable"
            if kind == "source_file"
            else "mismatch",
        }
        if kind == "source_file" and result["status"] == "historical_source_unavailable":
            git_history = _verify_source_file_in_run_commits(
                node_id=node_id,
                path_value=path_value,
                expected_hash=expected,
                source_commits=source_commits,
                root=root,
                blob_cache=git_source_blob_cache,
            )
            result["git_source_commit_verification"] = git_history
            if git_history["status"] == "verified":
                result["status"] = "verified_in_source_commit"
        results[node_id] = result

    counts_by_kind: dict[str, dict[str, int]] = {}
    for result in results.values():
        kind_counts = counts_by_kind.setdefault(str(result["kind"]), {})
        status = str(result["status"])
        kind_counts[status] = kind_counts.get(status, 0) + 1
    statuses = Counter(str(result["status"]) for result in results.values())
    failures = [
        {"id": node_id, **result}
        for node_id, result in sorted(results.items())
        if result["status"]
        not in {
            "verified",
            "verified_in_source_snapshot",
            "verified_current_path",
            "verified_relocated",
            "verified_in_source_commit",
            "not_byte_addressed",
        }
    ]
    source_node_hashes = {
        str(node.get("id", "")): node.get("sha256")
        for node in nodes
        if node.get("kind") == "source_file"
    }
    git_source_verifications = [
        {
            "id": node_id,
            "path": result.get("path"),
            "expected_sha256": source_node_hashes.get(node_id),
            "verification": result["git_source_commit_verification"],
        }
        for node_id, result in sorted(results.items())
        if "git_source_commit_verification" in result
    ]
    if statuses["mismatch"] or statuses["blocked"] or statuses["unstable"]:
        overall = "mismatch"
    elif statuses["missing"] or statuses["historical_source_unavailable"]:
        overall = "incomplete"
    else:
        overall = "verified"
    dag_hash, dag_size = _sha256(dag_path)
    verifier_path = Path(__file__).resolve()
    verifier_hash, _ = _sha256(verifier_path)
    try:
        verifier_label = verifier_path.relative_to(root.resolve()).as_posix()
    except ValueError:
        verifier_label = str(verifier_path)
    return {
        "schema": "research-provenance-byte-verification-v1",
        "status": overall,
        "dag_path": dag_path.relative_to(root.resolve()).as_posix(),
        "dag_sha256": dag_hash,
        "dag_size_bytes": dag_size,
        "verifier_path": verifier_label,
        "verifier_sha256": verifier_hash,
        "declared_hashed_nodes": hashed_node_count,
        "nodes_verified": int(
            sum(
                statuses[key]
                for key in (
                    "verified",
                    "verified_in_source_snapshot",
                    "verified_current_path",
                    "verified_relocated",
                    "verified_in_source_commit",
                )
            )
        ),
        "source_snapshot_embedded_files_verified": snapshot_file_count,
        "source_snapshot_embedded_uncompressed_bytes": snapshot_payload_bytes,
        "node_counts_by_kind_and_status": counts_by_kind,
        "git_source_commit_verifications": git_source_verifications,
        "failure_count": len(failures),
        "failures": failures,
        "claim_scope": "byte identity for manifest-declared files, complete verified source snapshots, and source files recovered from every linked run source commit; does not enumerate unmanifested caches or outputs",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dag", type=Path, default=DEFAULT_DAG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--archive-root", type=Path, default=ARCHIVE_ROOT)
    args = parser.parse_args()
    report = verify_provenance_dag_bytes(
        args.dag if args.dag.is_absolute() else ROOT / args.dag,
        root=ROOT,
        archive_root=args.archive_root,
    )
    write_json_atomic(args.output if args.output.is_absolute() else ROOT / args.output, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
