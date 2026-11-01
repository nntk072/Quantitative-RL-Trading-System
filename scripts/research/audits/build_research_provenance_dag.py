#!/usr/bin/env python3
"""Export manifest-declared experiment provenance without reading raw data."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = (
    ROOT / "evidence/research/releases/negative-evidence-readiness-2026-11-01/"
    "EXPERIMENT_PROVENANCE_DAG.json"
)


def _node_id(kind: str, identity: str) -> str:
    """Return a stable node identifier for one kind and identity pair."""
    digest = hashlib.sha256(f"{kind}\0{identity}".encode()).hexdigest()
    return f"{kind}:{digest[:20]}"


def _hash_value(value: Any) -> str | None:
    """Extract a declared SHA-256 from common manifest value shapes."""
    if isinstance(value, str) and len(value) == 64:
        return value
    if isinstance(value, Mapping):
        for key in ("sha256", "hash", "content_hash"):
            candidate = value.get(key)
            if isinstance(candidate, str) and len(candidate) == 64:
                return candidate
    return None


def _add_node(nodes: dict[str, dict[str, Any]], kind: str, identity: str, **fields: Any) -> str:
    node_id = _node_id(kind, identity)
    nodes.setdefault(node_id, {"id": node_id, "kind": kind, **fields})
    return node_id


def build_dag(root: Path = ROOT) -> dict[str, Any]:
    """Build a deduplicated DAG from experiment and campaign manifests."""
    nodes: dict[str, dict[str, Any]] = {}
    edges: set[tuple[str, str, str]] = set()
    issues: list[dict[str, str]] = []
    manifest_paths = sorted(
        [*root.glob("outputs/gpu_experiment_runs/*/experiment_run.json")]
        + [*root.glob("outputs/gpu_campaigns/*/campaign.json")]
    )

    for manifest_path in manifest_paths:
        relative_manifest = manifest_path.relative_to(root).as_posix()
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            issues.append({"path": relative_manifest, "error": str(exc)})
            continue

        manifest_digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        run_id = str(payload.get("run_id", payload.get("campaign_id", manifest_path.parent.name)))
        run_identity = f"{run_id}|{relative_manifest}|{payload.get('fingerprint', '')}"
        run_node = _add_node(
            nodes,
            "run",
            run_identity,
            run_id=run_id,
            fingerprint=payload.get("fingerprint"),
            source_commit=payload.get(
                "source_commit", payload.get("source_sha", payload.get("git_sha"))
            ),
            timesteps=payload.get("timesteps"),
            n_envs=payload.get("n_envs"),
            data_source=payload.get("data_source"),
            evaluation=payload.get("evaluation"),
            manifest_path=relative_manifest,
        )
        manifest_node = _add_node(
            nodes,
            "manifest",
            f"{relative_manifest}|{manifest_digest}",
            path=relative_manifest,
            sha256=manifest_digest,
            availability="present_and_hashed",
        )
        edges.add((manifest_node, run_node, "declares"))

        for data_key, raw_value in sorted((payload.get("data_inputs") or {}).items()):
            path = str(data_key).split(":", 1)[-1]
            digest = _hash_value(raw_value)
            input_node = _add_node(
                nodes,
                "data_input",
                f"{path}|{digest or 'hash-unavailable'}",
                path=path,
                sha256=digest,
                availability="manifest_declared_not_rehashed",
            )
            edges.add((run_node, input_node, "uses_input"))

        for source_path, digest in sorted((payload.get("source_hashes") or {}).items()):
            source_node = _add_node(
                nodes,
                "source_file",
                f"{source_path}|{digest}",
                path=source_path,
                sha256=str(digest),
                availability="manifest_declared_not_rehashed",
            )
            edges.add((run_node, source_node, "uses_source"))

        snapshot = payload.get("source_snapshot") or {}
        if isinstance(snapshot, Mapping) and snapshot.get("path"):
            path = str(snapshot["path"])
            digest = str(snapshot.get("sha256", "")) or None
            snapshot_node = _add_node(
                nodes,
                "source_snapshot",
                f"{path}|{digest or 'hash-unavailable'}",
                path=(manifest_path.parent / path).relative_to(root).as_posix(),
                sha256=digest,
                manifest_sha256=snapshot.get("manifest_sha256"),
                file_count=snapshot.get("file_count"),
                availability="manifest_declared_not_rehashed",
            )
            edges.add((run_node, snapshot_node, "pins_source_snapshot"))

        for job in payload.get("jobs", []):
            if not isinstance(job, Mapping):
                continue
            job_identity = f"{relative_manifest}|{job.get('key', job.get('variant', 'unknown'))}|{job.get('seed', '')}"
            job_node = _add_node(
                nodes,
                "job",
                job_identity,
                key=job.get("key"),
                variant=job.get("variant"),
                seed=job.get("seed"),
                status=job.get("status", "unknown"),
                failure_reason=job.get("failure_reason"),
                started=job.get("started"),
                ended=job.get("ended"),
                attempts_reported=job.get("attempts"),
                log_path=job.get("log"),
            )
            edges.add((run_node, job_node, "contains_job"))
            for artifact_path, digest in sorted((job.get("artifact_hashes") or {}).items()):
                resolved = (manifest_path.parent / str(artifact_path)).as_posix()
                artifact_node = _add_node(
                    nodes,
                    "run_artifact",
                    f"{resolved}|{digest}",
                    path=Path(resolved).relative_to(root).as_posix(),
                    sha256=str(digest),
                    availability="manifest_declared_not_rehashed",
                )
                edges.add((job_node, artifact_node, "records_artifact"))

    return {
        "schema": "research-provenance-dag-v1",
        "scope": "all discovered campaign.json and experiment_run.json manifests; declared input/source/artifact hashes are not rehashed here",
        "manifest_count": len(manifest_paths),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "issues": issues,
        "nodes": sorted(nodes.values(), key=lambda item: item["id"]),
        "edges": [
            {"from": source, "to": target, "relation": relation}
            for source, target, relation in sorted(edges)
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = build_dag()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"Wrote {args.output}: {result['manifest_count']} manifests, "
        f"{result['node_count']} nodes, {result['edge_count']} edges, "
        f"{len(result['issues'])} manifest issues"
    )
    return 0 if not result["issues"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
