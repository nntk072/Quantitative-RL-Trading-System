#!/usr/bin/env python3
"""Durable, allocation-bounded launcher for configured experiment run variants.

Does not create or cancel Slurm allocations. Runs in an existing compute-node job.
"""

from __future__ import annotations

import argparse
import csv
import fcntl
import hashlib
import json
import math
import os
import pathlib
import re
import signal
import socket
import subprocess
import sys
import time
from typing import Any, TextIO

from artifacts.layout import ArtifactLayout
from compute.slurm.worker_resources import (
    available_resources as available_resources,
)
from compute.slurm.worker_resources import (
    cgroup_memory_file as cgroup_memory_file,
)
from compute.slurm.worker_resources import (
    cpu_mask_for_range as cpu_mask_for_range,
)
from compute.slurm.worker_resources import (
    cpu_mask_for_slot as cpu_mask_for_slot,
)
from compute.slurm.worker_resources import (
    expand_slurm_hosts as expand_slurm_hosts,
)
from compute.slurm.worker_resources import (
    gpu_memory_inventory as gpu_memory_inventory,
)
from compute.slurm.worker_resources import (
    plan_worker_capacity as plan_worker_capacity,
)
from compute.slurm.worker_resources import (
    resolve_worker_nodes as resolve_worker_nodes,
)
from compute.slurm.worker_resources import (
    sample_resources as sample_resources,
)
from compute.slurm.worker_resources import (
    worker_command as worker_command,
)
from compute.slurm.worker_resources import (
    worker_node_cpu_ids as worker_node_cpu_ids,
)
from compute.slurm.worker_resources import (
    worker_node_resources as worker_node_resources,
)
from experiments.runs.artifact_validation import (
    hash_run_artifacts as hash_run_artifacts,
)
from experiments.runs.artifact_validation import (
    validate_experiment_run_evaluation as validate_experiment_run_evaluation,
)
from experiments.runs.artifact_validation import (
    verify_run_artifacts as verify_run_artifacts,
)
from experiments.runs.checkpoint_lineage import (
    archive_initial_checkpoints as archive_initial_checkpoints,
)
from experiments.runs.checkpoint_lineage import (
    build_initial_checkpoint_map as build_initial_checkpoint_map,
)
from experiments.runs.checkpoint_lineage import (
    choose_resume_checkpoint as choose_resume_checkpoint,
)
from experiments.runs.checkpoint_lineage import (
    latest_resumable_checkpoint as latest_resumable_checkpoint,
)
from experiments.runs.checkpoint_lineage import (
    validate_initial_checkpoints as validate_initial_checkpoints,
)
from experiments.runs.checkpoint_lineage import (
    verify_initial_checkpoint_models as verify_initial_checkpoint_models,
)
from experiments.runs.constants import DEFAULT_VARIANTS, ROOT
from experiments.runs.runtime_metadata import (
    runtime_metadata as runtime_metadata,
)
from experiments.runs.source_snapshot import (
    action_space_matches_width as action_space_matches_width,
)
from experiments.runs.source_snapshot import (
    cached_sha256_file as cached_sha256_file,
)
from experiments.runs.source_snapshot import (
    experiment_run_data_inputs as experiment_run_data_inputs,
)
from experiments.runs.source_snapshot import (
    experiment_run_source_files as experiment_run_source_files,
)
from experiments.runs.source_snapshot import (
    sha256_file as sha256_file,
)
from experiments.runs.source_snapshot import (
    verify_experiment_run_source_snapshot as verify_experiment_run_source_snapshot,
)
from experiments.runs.source_snapshot import (
    write_experiment_run_source_snapshot as write_experiment_run_source_snapshot,
)
from experiments.runs.state_store import (
    atomic_json as atomic_json,
)
from experiments.runs.state_store import (
    read_manifest as read_manifest,
)
from experiments.runs.state_store import (
    record as record,
)
from experiments.runs.state_store import (
    utc as utc,
)
from experiments.runs.state_store import (
    validate_inputs as validate_inputs,
)

TRAIN_ONE_VARIANT_SCRIPT = (
    ROOT / "scripts" / "research" / "frozen-launches" / "train_one_variant.sh"
)
RESOURCE_SAMPLER_SCRIPT = ROOT / "compute" / "slurm" / "resources.py"

__all__ = [
    "DEFAULT_VARIANTS",
    "RESOURCE_SAMPLER_SCRIPT",
    "ROOT",
    "TRAIN_ONE_VARIANT_SCRIPT",
    "action_space_matches_width",
    "archive_initial_checkpoints",
    "atomic_json",
    "available_resources",
    "build_initial_checkpoint_map",
    "cached_sha256_file",
    "experiment_run_data_inputs",
    "experiment_run_source_files",
    "choose_resume_checkpoint",
    "cpu_mask_for_slot",
    "cpu_mask_for_range",
    "gpu_memory_inventory",
    "expand_slurm_hosts",
    "hash_run_artifacts",
    "latest_resumable_checkpoint",
    "main",
    "normalize_experiment_run_config_overrides",
    "load_experiment_run_data_profile",
    "experiment_run_config_override_lines",
    "signal_stop",
    "read_manifest",
    "record",
    "resolve_worker_nodes",
    "runtime_metadata",
    "sample_resources",
    "plan_worker_capacity",
    "sha256_file",
    "STOP",
    "utc",
    "validate_experiment_run_evaluation",
    "validate_initial_checkpoints",
    "validate_inputs",
    "verify_experiment_run_source_snapshot",
    "verify_initial_checkpoint_models",
    "verify_run_artifacts",
    "worker_command",
    "worker_node_cpu_ids",
    "worker_node_resources",
    "write_experiment_run_source_snapshot",
]

STOP = False
_CACHE_FILE_HASHES: dict[tuple[str, int, int, int], str] = {}


def normalize_experiment_run_config_overrides(value: Any) -> dict[str, bool | int | float | str]:
    """Validate simple scalar config overrides declared by an experiment run spec."""
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("experiment run config_overrides must be a mapping")
    normalized: dict[str, bool | int | float | str] = {}
    for raw_key, raw_value in value.items():
        key = str(raw_key).strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*", key):
            raise ValueError(f"invalid experiment run config override key: {raw_key!r}")
        if isinstance(raw_value, bool):
            normalized[key] = raw_value
        elif isinstance(raw_value, int):
            normalized[key] = raw_value
        elif isinstance(raw_value, float) and math.isfinite(raw_value):
            normalized[key] = raw_value
        elif isinstance(raw_value, str) and key in {
            "data.cache_dir",
            "data.datasets.training.raw_dir",
            "data.datasets.testing.raw_dir",
            "data.prebuilt_feature_cache",
            "data.price_discretization.rounding",
        }:
            relative_path = pathlib.PurePosixPath(raw_value)
            if key != "data.price_discretization.rounding" and (
                not raw_value.strip() or relative_path.is_absolute() or ".." in relative_path.parts
            ):
                raise ValueError(f"experiment run {key} must be a non-empty relative path")
            if key == "data.price_discretization.rounding" and not raw_value.strip():
                raise ValueError(
                    "experiment run data.price_discretization.rounding must not be empty"
                )
            normalized[key] = raw_value
        else:
            raise ValueError(
                f"experiment run config override {key!r} must be a finite number, boolean, "
                "or supported relative data path/string"
            )
    return dict(sorted(normalized.items()))


def load_experiment_run_data_profile(profile: Any) -> dict[str, bool | int | float | str]:
    """Load an explicit reusable data mode from ``config/data_modes``."""
    if profile is None:
        return {}
    if not isinstance(profile, str) or not profile.strip():
        raise ValueError("experiment run data_profile must be a relative YAML path")
    profile_path = (ROOT / profile).resolve()
    try:
        relative = profile_path.relative_to(ROOT.resolve())
    except ValueError:
        raise ValueError("experiment run data_profile must stay inside the repository") from None
    if relative.parts[:2] != ("config", "data_modes") or profile_path.suffix not in {
        ".yaml",
        ".yml",
    }:
        raise ValueError("experiment run data_profile must be a YAML file under config/data_modes")
    import yaml

    try:
        raw = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"cannot load experiment run data profile {relative}: {exc}") from exc
    if (
        not isinstance(raw, dict)
        or raw.get("profile") != profile_path.stem
        or not isinstance(raw.get("data"), dict)
    ):
        raise ValueError(f"{relative} must contain a data mapping")

    flattened: dict[str, Any] = {}

    def visit(prefix: str, value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                visit(f"{prefix}.{key}" if prefix else str(key), child)
        else:
            flattened[prefix] = value

    visit("data", raw["data"])
    allowed = {
        "data.cache_dir",
        "data.datasets.training.raw_dir",
        "data.datasets.testing.raw_dir",
        "data.price_discretization.enabled",
        "data.price_discretization.increment",
        "data.price_discretization.rounding",
    }
    unexpected = set(flattened) - allowed
    if unexpected:
        raise ValueError(f"{relative} contains unsupported data settings: {sorted(unexpected)}")
    return normalize_experiment_run_config_overrides(flattened)


def experiment_run_config_override_lines(values: dict[str, bool | int | float | str]) -> str:
    """Serialize validated scalar overrides for the isolated trainer process."""
    lines = []
    for key, value in values.items():
        rendered = str(value).lower() if isinstance(value, bool) else str(value)
        lines.append(f"{key}={rendered}")
    return "\n".join(lines)


def signal_stop(_sig: int, _frame: object) -> None:
    global STOP
    STOP = True


def distribute_worker_slots(total: int, capacities: dict[str, int]) -> dict[str, int]:
    """Spread worker slots fairly without exceeding any node's resource limit."""
    targets = {node: 0 for node in sorted(capacities)}
    for _ in range(total):
        eligible = [node for node, capacity in capacities.items() if targets[node] < capacity]
        if not eligible:
            raise ValueError("requested worker count exceeds the resource-derived capacity")
        node = min(
            eligible,
            key=lambda candidate: (
                targets[candidate] / capacities[candidate],
                targets[candidate],
                candidate,
            ),
        )
        targets[node] += 1
    return targets


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment-run-spec", type=pathlib.Path)
    parser.add_argument("--variant-file", type=pathlib.Path)
    parser.add_argument("--seeds")
    parser.add_argument("--timesteps", type=int)
    parser.add_argument(
        "--workers",
        default="1",
        help="concurrent variants; use auto to fill CPU, RAM, and GPU capacity safely",
    )
    parser.add_argument("--n-envs", type=int, default=8)
    parser.add_argument(
        "--worker-nodes",
        help="comma-separated nodes inside the current allocation; workers are load-balanced across them",
    )
    parser.add_argument(
        "--worker-cpus",
        default="8",
        help="CPUs per variant worker; use auto to divide each node among its worker slots",
    )
    parser.add_argument("--worker-gpu-type", default="gh200")
    parser.add_argument("--worker-gpus-per-node", type=int, default=1)
    parser.add_argument("--max-workers-per-gpu", type=int, default=9)
    parser.add_argument("--gpu-memory-per-worker-gib", type=float, default=8.0)
    parser.add_argument("--data-source", choices=("frames", "bundle"))
    parser.add_argument("--experiment-run-id")
    parser.add_argument(
        "--initial-checkpoints",
        type=pathlib.Path,
        help="lineage map for checkpoints migrated from a prior experiment run",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--resume-fingerprint-override-reason",
        help=(
            "explicitly continue an existing experiment run when its current identity fingerprint "
            "differs; the original fingerprint remains the artifact/checkpoint lineage"
        ),
    )
    parser.add_argument("--benchmark", action="store_true")
    parser.add_argument(
        "--fast-reports",
        action="store_true",
        help="Skip per-trade PNGs during training; keep summary plots, metrics, JSON, CSV, and checkpoints",
    )
    parser.add_argument("--test-worker", type=pathlib.Path, help="inject mock worker for CI only")
    args = parser.parse_args()
    args.workers_auto = str(args.workers).lower() == "auto"
    args.worker_cpus_auto = str(args.worker_cpus).lower() == "auto"
    if not args.workers_auto:
        try:
            args.workers = int(args.workers)
        except (TypeError, ValueError):
            raise ValueError("--workers must be a positive integer or 'auto'") from None
    else:
        args.workers = 1  # replaced with a resource-derived count after input validation
    if not args.worker_cpus_auto:
        try:
            args.worker_cpus = int(args.worker_cpus)
        except (TypeError, ValueError):
            raise ValueError("--worker-cpus must be a positive integer or 'auto'") from None
    else:
        args.worker_cpus = 1  # replaced with a per-node CPU share after capacity planning
    import yaml

    evaluation: dict[str, Any] = {"locked_oos_role": "unspecified", "deterministic": False}
    config_overrides: dict[str, bool | int | float | str] = {}
    if args.experiment_run_spec:
        if any(
            value is not None
            for value in (
                args.variant_file,
                args.seeds,
                args.timesteps,
                args.data_source,
                args.experiment_run_id,
            )
        ):
            raise ValueError(
                "--experiment-run-spec cannot be combined with experiment run identity overrides"
            )
        args.experiment_run_spec = args.experiment_run_spec.resolve()
        try:
            args.experiment_run_spec.relative_to(ROOT)
        except ValueError:
            raise ValueError("experiment run spec must be stored inside this repository") from None
        spec = yaml.safe_load(args.experiment_run_spec.read_text(encoding="utf-8"))
        if not isinstance(spec, dict):
            raise ValueError("experiment run spec must be a YAML mapping")
        spec_variants = spec.get("variants")
        if not isinstance(spec_variants, list) or not spec_variants:
            raise ValueError("experiment run spec must contain a nonempty variants list")
        spec_variant_file = (
            ROOT / str(spec.get("variant_file", "config/experiment_runs/variant_list.txt"))
        ).resolve()
        listed = [
            line.strip()
            for line in spec_variant_file.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        if listed != [str(name) for name in spec_variants]:
            raise ValueError(
                "experiment run spec variants do not match its authoritative variant file"
            )
        evaluation = validate_experiment_run_evaluation(spec.get("evaluation", {}))
        profile_overrides = load_experiment_run_data_profile(spec.get("data_profile"))
        experiment_run_overrides = normalize_experiment_run_config_overrides(
            spec.get("config_overrides", {})
        )
        config_overrides = normalize_experiment_run_config_overrides(
            {**profile_overrides, **experiment_run_overrides}
        )
        default_config = yaml.safe_load(
            (ROOT / "config" / "base" / "default.yaml").read_text(encoding="utf-8")
        )
        if spec.get("split") != default_config["data"]["split"]:
            raise ValueError("experiment run split does not match the effective base configuration")
        args.variant_file = spec_variant_file
        args.seeds = " ".join(str(seed) for seed in spec.get("seeds", []))
        args.timesteps = int(spec["timesteps"])
        args.data_source = str(spec.get("data_source", "frames"))
        args.experiment_run_id = str(spec["experiment_run_id"])
    else:
        args.variant_file = args.variant_file or DEFAULT_VARIANTS
        args.seeds = args.seeds or "42 43 44 45 46"
        args.timesteps = args.timesteps or 20_000_000
        args.data_source = args.data_source or "frames"
        args.experiment_run_id = args.experiment_run_id or "core-18x5"
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,100}", args.experiment_run_id):
        raise ValueError("unsafe experiment run id")
    if (
        args.worker_cpus <= 0
        or args.worker_gpus_per_node <= 0
        or args.max_workers_per_gpu <= 0
        or args.gpu_memory_per_worker_gib <= 0
        or not re.fullmatch(r"[A-Za-z0-9]+", args.worker_gpu_type)
    ):
        raise ValueError("worker CPU/GPU count or GPU type is invalid")
    worker_nodes = resolve_worker_nodes(
        args.worker_nodes, dry_run=args.dry_run or bool(args.test_worker)
    )
    if worker_nodes and len(worker_nodes) > args.workers and not args.workers_auto:
        raise ValueError("worker count must be at least the number of worker nodes")
    jobs = validate_inputs(args)
    initial_checkpoints: dict[str, dict[str, Any]] = {}
    if args.initial_checkpoints is not None:
        args.initial_checkpoints = args.initial_checkpoints.resolve()
        try:
            args.initial_checkpoints.relative_to(ROOT.resolve())
        except ValueError:
            raise ValueError(
                "initial checkpoint map must be stored inside this repository"
            ) from None
        initial_checkpoints = validate_initial_checkpoints(
            args.initial_checkpoints, jobs, args.timesteps
        )
    # Source-of-truth variant lookup without changing training semantics.
    config = yaml.safe_load((ROOT / "config" / "experiments.yaml").read_text())
    known = {str(item["name"]) for item in config["variants"]}
    unknown = {str(j["variant"]) for j in jobs} - known
    if unknown:
        raise ValueError(f"unknown variants: {sorted(unknown)}")
    if args.benchmark and (len(jobs) != 1 or args.timesteps > 100_000):
        raise ValueError("benchmark requires one run and <=100000 training steps")
    if args.dry_run:
        print(
            json.dumps(
                {
                    "experiment_run_id": args.experiment_run_id,
                    "output_root": str(
                        ArtifactLayout(ROOT / "outputs")
                        .gpu_experiment_run(args.experiment_run_id)
                        .root
                    ),
                    "variant_file": str(args.variant_file),
                    "seeds": [int(seed) for seed in args.seeds.replace(",", " ").split()],
                    "steps_per_run": args.timesteps,
                    "runs": len(jobs),
                    "total_timesteps": len(jobs) * args.timesteps,
                    "workers": "auto (resolved inside allocation)"
                    if args.workers_auto
                    else args.workers,
                    "n_envs": args.n_envs,
                    "worker_nodes": worker_nodes,
                    "worker_cpus": (
                        "auto (resolved per node)"
                        if args.worker_cpus_auto and worker_nodes
                        else args.worker_cpus
                        if worker_nodes
                        else None
                    ),
                    "worker_gpu_type": args.worker_gpu_type if worker_nodes else None,
                    "worker_gpus_per_node": (args.worker_gpus_per_node if worker_nodes else None),
                    "data_source": args.data_source,
                    "config_overrides": config_overrides,
                    "fast_reports": args.fast_reports,
                    "initial_checkpoints": len(initial_checkpoints),
                    "keys": [j["key"] for j in jobs],
                },
                indent=2,
            )
        )
        return 0
    if not os.getenv("SLURM_JOB_ID") and not args.test_worker:
        raise RuntimeError("must run inside an existing Slurm compute allocation")
    resources = available_resources()
    cpus = resources["cpu_affinity"]
    memory_limit_bytes = int(resources["memory_limit_bytes"])
    if not memory_limit_bytes:
        memory_per_node_mib = os.getenv("SLURM_MEM_PER_NODE", "")
        if memory_per_node_mib.isdigit():
            memory_limit_bytes = int(memory_per_node_mib) * 1024**2
    worker_node_cpu_sets: dict[str, list[int]] = {}
    node_resources: dict[str, dict[str, Any]] = {}
    node_worker_capacity: dict[str, int] = {}
    node_worker_targets: dict[str, int] = {}
    worker_cpus_by_node: dict[str, int] = {}
    worker_cpu_counts_by_node: dict[str, list[int]] = {}
    worker_allocation_plan: dict[str, Any] | None = None
    if worker_nodes:
        queue_root = pathlib.Path(os.environ["EXPERIMENT_RUN_WORKER_QUEUE"])
        allocation_job_id = os.environ["SLURM_JOB_ID"]
        for node in worker_nodes:
            advertised = worker_node_resources(queue_root, allocation_job_id, node)
            worker_node_cpu_sets[node] = list(advertised["cpu_ids"])
            if not int(advertised["memory_limit_bytes"]):
                advertised["memory_limit_bytes"] = memory_limit_bytes
            if (
                not advertised["gpu_memory"]
                and node.split(".", maxsplit=1)[0] == socket.gethostname().split(".", maxsplit=1)[0]
            ):
                advertised["gpu_memory"] = gpu_memory_inventory()
            advertised["gpu_type"] = args.worker_gpu_type
            node_resources[node] = advertised
        worker_allocation_plan = plan_worker_capacity(
            node_resources,
            n_envs=args.n_envs,
            data_source=args.data_source,
            gpus_per_node=args.worker_gpus_per_node,
            max_workers_per_gpu=args.max_workers_per_gpu,
            gpu_memory_per_worker_gib=args.gpu_memory_per_worker_gib,
        )
        node_worker_capacity = {
            node: int(values["workers"]) for node, values in worker_allocation_plan["nodes"].items()
        }
        if not args.worker_cpus_auto:
            for node in worker_nodes:
                cpu_limited = max(
                    0,
                    (len(worker_node_cpu_sets[node]) - 1) // args.worker_cpus,
                )
                node_worker_capacity[node] = min(node_worker_capacity[node], cpu_limited)
                worker_allocation_plan["nodes"][node]["workers"] = node_worker_capacity[node]
        worker_allocation_plan["workers"] = sum(node_worker_capacity.values())
        if args.workers_auto:
            if sum(node_worker_capacity.values()) <= 0:
                raise RuntimeError("the current allocation has no safe experiment worker capacity")
            args.workers = min(len(jobs), sum(node_worker_capacity.values()))
        if args.workers < len(worker_nodes):
            raise ValueError("worker count must be at least the number of worker nodes")
        if args.workers > sum(node_worker_capacity.values()):
            raise RuntimeError(
                f"requested {args.workers} workers, but CPU/RAM/GPU capacity supports at most "
                f"{sum(node_worker_capacity.values())}; use --workers auto to fit the allocation"
            )
        node_worker_targets = distribute_worker_slots(args.workers, node_worker_capacity)
        worker_allocation_plan["workers_selected"] = args.workers
        for node, target in node_worker_targets.items():
            worker_allocation_plan["nodes"][node]["assigned_workers"] = target
        if args.worker_cpus_auto:
            for node, target in node_worker_targets.items():
                if target <= 0:
                    continue
                base, extra = divmod(len(worker_node_cpu_sets[node]) - 1, target)
                worker_cpu_counts_by_node[node] = [
                    base + (1 if index < extra else 0) for index in range(target)
                ]
                worker_cpus_by_node[node] = min(worker_cpu_counts_by_node[node])
        else:
            worker_cpus_by_node = {node: args.worker_cpus for node in worker_nodes}
            worker_cpu_counts_by_node = {
                node: [args.worker_cpus] * target
                for node, target in node_worker_targets.items()
                if target > 0
            }
        for node, target in node_worker_targets.items():
            if target <= 0:
                continue
            needed = sum(worker_cpu_counts_by_node[node]) + 1
            if needed > len(worker_node_cpu_sets[node]):
                raise RuntimeError(
                    f"worker plan needs {needed} CPUs on {node} including the sampler; "
                    f"manager exposes {len(worker_node_cpu_sets[node])}"
                )
        args.worker_cpus = min(worker_cpus_by_node.values()) if worker_cpus_by_node else 1
    else:
        # Local subprocess mode retains its explicit default; auto is available
        # only when the allocation exposes per-node worker managers.
        if args.workers_auto:
            raise ValueError("--workers auto requires --worker-nodes inside a Slurm allocation")
        worker_cpus_by_node = {}
        node_worker_targets = {}

    if not args.workers_auto and not worker_nodes:
        worker_nodes = []
    workers_per_node = max(node_worker_targets.values(), default=args.workers)
    envs_per_cpu = 12 if args.data_source == "bundle" else 2
    if workers_per_node * args.n_envs > cpus * envs_per_cpu:
        raise RuntimeError(f"requested vector environments exceed {envs_per_cpu} per available CPU")
    estimated_per_worker = {4: 12, 8: 19, 16: 35, 32: 67, 64: 132}.get(args.n_envs)
    if args.data_source == "bundle" and args.n_envs == 64:
        estimated_per_worker = 30
    if estimated_per_worker is None and not args.test_worker:
        raise ValueError("n-envs not benchmarked for memory: choose 4,8,16,32,64")
    if not worker_nodes and memory_limit_bytes and estimated_per_worker and not args.test_worker:
        recommended_bytes = int((workers_per_node * estimated_per_worker * 1.35 + 64) * 1024**3)
        if recommended_bytes > memory_limit_bytes:
            raise RuntimeError(
                f"insufficient cgroup RAM: needs >= {recommended_bytes // 1024**3} GiB"
            )
    experiment_run_artifacts = ArtifactLayout(ROOT / "outputs").gpu_experiment_run(
        args.experiment_run_id
    )
    out = experiment_run_artifacts.root
    experiment_run_artifacts.ensure_controller_directories()
    lock = experiment_run_artifacts.controller_lock.open("w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise RuntimeError("another controller owns this experiment run") from None
    archived_bootstrap = archive_initial_checkpoints(out, initial_checkpoints)
    manifest_path = experiment_run_artifacts.manifest
    started_time = time.monotonic()
    git_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    runtime = runtime_metadata()
    source_files = experiment_run_source_files(ROOT, args.experiment_run_spec)
    if args.initial_checkpoints is not None:
        source_files.append(args.initial_checkpoints)
    source_files = sorted(set(source_files))
    source_hashes = {str(path.relative_to(ROOT)): sha256_file(path) for path in source_files}
    raw_config = yaml.safe_load((ROOT / "config" / "base" / "default.yaml").read_text())
    data_config = raw_config["data"]
    for key, value in config_overrides.items():
        if not key.startswith("data."):
            continue
        cursor = data_config
        parts = key.split(".")[1:]
        for part in parts[:-1]:
            child = cursor.get(part)
            if not isinstance(child, dict):
                raise ValueError(
                    f"experiment run override {key!r} does not match the base data YAML"
                )
            cursor = child
        if parts[-1] not in cursor:
            raise ValueError(
                f"experiment run override {key!r} is not declared in the base data YAML"
            )
        cursor[parts[-1]] = value
    data_inputs = experiment_run_data_inputs(data_config)
    missing_inputs = [path for path, digest in data_inputs.items() if digest == "MISSING"]
    if missing_inputs and not args.test_worker:
        raise RuntimeError(f"configured market-data inputs missing: {missing_inputs}")
    identity = {
        "jobs": [x["key"] for x in jobs],
        "steps": args.timesteps,
        "workers_requested": "auto" if args.workers_auto else args.workers,
        "data_source": args.data_source,
        "workers": args.workers,
        "n_envs": args.n_envs,
        "worker_placement": {
            "mode": "slurm-node-steps" if worker_nodes else "local-subprocesses",
            "node_count": len(worker_nodes) if worker_nodes else 1,
            "gpu_type": args.worker_gpu_type if worker_nodes else "allocation-default",
            "gpus_per_node": args.worker_gpus_per_node if worker_nodes else None,
            "gpu_binding": "least-loaded-map_gpu" if worker_nodes else None,
            "cpus_per_worker": args.worker_cpus if worker_nodes else None,
            "cpus_per_node": worker_cpus_by_node if worker_nodes else None,
            "worker_cpu_counts_by_node": worker_cpu_counts_by_node if worker_nodes else None,
            "worker_allocation_plan": worker_allocation_plan,
            "cpu_binding": "unique-mask-per-worker" if worker_nodes else None,
        },
        "fast_reports": args.fast_reports,
        "evaluation": evaluation,
        "config_overrides": config_overrides,
        "runtime_compatibility": {
            "python": runtime["python"],
            "machine": runtime["machine"],
            "packages": runtime["packages"],
        },
        "git_sha": git_sha,
        "source_hashes": source_hashes,
        "data_inputs": data_inputs,
        "initial_checkpoint_lineage": {
            key: {name: value for name, value in checkpoint.items() if name != "checkpoint_path"}
            for key, checkpoint in initial_checkpoints.items()
        },
    }
    fingerprint = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    if initial_checkpoints:
        verify_initial_checkpoint_models(archived_bootstrap, initial_checkpoints)
    effective_identity = identity
    fingerprint_override: dict[str, Any] | None = None
    if manifest_path.exists():
        manifest = read_manifest(manifest_path)
        if not args.resume:
            raise RuntimeError("experiment run exists: use --resume")
        if manifest["fingerprint"] != fingerprint:
            reason = (args.resume_fingerprint_override_reason or "").strip()
            if not reason:
                raise RuntimeError("resume fingerprint mismatch")
            if len(reason) < 12:
                raise ValueError(
                    "resume fingerprint override reason must be at least 12 characters"
                )
            canonical_fingerprint = str(manifest.get("fingerprint", ""))
            canonical_identity: dict[str, Any] | None = None
            for item in manifest.get("jobs", []):
                attempts = int(item.get("attempts", 0))
                for attempt in range(attempts, 0, -1):
                    provenance_path = (
                        experiment_run_artifacts.attempt(str(item.get("key", "")), attempt)
                        / "attempt_provenance.json"
                    )
                    try:
                        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
                    except (OSError, ValueError):
                        continue
                    candidate = provenance.get("identity") if isinstance(provenance, dict) else None
                    if (
                        isinstance(provenance, dict)
                        and provenance.get("experiment_run_fingerprint") == canonical_fingerprint
                        and isinstance(candidate, dict)
                        and hashlib.sha256(
                            json.dumps(candidate, sort_keys=True).encode()
                        ).hexdigest()
                        == canonical_fingerprint
                    ):
                        canonical_identity = candidate
                        break
                if canonical_identity is not None:
                    break
            if canonical_identity is None:
                raise RuntimeError(
                    "cannot override resume fingerprint: no attempt contains the original "
                    "fingerprint identity"
                )
            if manifest.get("initial_checkpoint_lineage", {}) != canonical_identity.get(
                "initial_checkpoint_lineage", {}
            ):
                raise RuntimeError(
                    "cannot override resume fingerprint: original checkpoint lineage does "
                    "not match the experiment run manifest"
                )
            required_matches = {
                "jobs": [job["key"] for job in jobs],
                "steps": args.timesteps,
                "data_source": args.data_source,
                "n_envs": args.n_envs,
                "fast_reports": args.fast_reports,
                "evaluation": evaluation,
            }
            changed_required = [
                name
                for name, value in required_matches.items()
                if canonical_identity.get(name) != value
            ]
            if changed_required:
                raise RuntimeError(
                    "resume fingerprint override rejected; continuation-critical identity "
                    f"changed: {', '.join(changed_required)}"
                )
            effective_identity = identity
            identity = canonical_identity
            fingerprint_override = {
                "reason": reason,
                "canonical_fingerprint": canonical_fingerprint,
                "effective_fingerprint": fingerprint,
                "effective_identity": effective_identity,
                "continuation_critical_fields_verified": sorted(required_matches),
                "canonical_checkpoint_lineage_sha256": hashlib.sha256(
                    json.dumps(
                        canonical_identity.get("initial_checkpoint_lineage", {}), sort_keys=True
                    ).encode()
                ).hexdigest(),
                "effective_checkpoint_lineage_sha256": hashlib.sha256(
                    json.dumps(
                        effective_identity.get("initial_checkpoint_lineage", {}), sort_keys=True
                    ).encode()
                ).hexdigest(),
                "training_evidence_status": "exploratory_after_fingerprint_override",
                "recorded_at": utc(),
            }
            fingerprint = canonical_fingerprint
        if manifest.get("initial_checkpoint_lineage", {}) != identity["initial_checkpoint_lineage"]:
            raise RuntimeError("resume initial checkpoint lineage mismatch")
        snapshot_record = manifest.get("source_snapshot")
        if snapshot_record is not None:
            if not isinstance(snapshot_record, dict) or not isinstance(
                snapshot_record.get("path"), str
            ):
                raise RuntimeError("experiment run source snapshot record is invalid")
            snapshot_path = experiment_run_artifacts.resolve_recorded_path(snapshot_record["path"])
            if snapshot_path.parent != out.resolve():
                raise RuntimeError(
                    "experiment run source snapshot path escapes experiment run directory"
                )
            snapshot_valid, snapshot_reason = verify_experiment_run_source_snapshot(
                snapshot_path, snapshot_record
            )
            if not snapshot_valid:
                raise RuntimeError(f"experiment run source snapshot invalid: {snapshot_reason}")
        if manifest.get("data_source", "frames") != args.data_source:
            raise RuntimeError("resume data-source mismatch")
        if manifest.get("n_envs") != args.n_envs:
            raise RuntimeError("resume n-envs mismatch")
        if fingerprint_override is not None:
            manifest.setdefault("resume_fingerprint_overrides", []).append(
                {
                    key: value
                    for key, value in fingerprint_override.items()
                    if key != "effective_identity"
                }
            )
            override_path = experiment_run_artifacts.report(
                f"resume_fingerprint_override_{fingerprint_override['effective_fingerprint']}.json"
            )
            atomic_json(override_path, fingerprint_override)
            record(
                experiment_run_artifacts.report("resume_fingerprint_overrides.jsonl"),
                {
                    key: value
                    for key, value in fingerprint_override.items()
                    if key != "effective_identity"
                },
            )
        manifest.pop("stopping", None)
        jobs = manifest["jobs"]
        for item in jobs:
            if (
                item["status"] == "succeeded"
                and not experiment_run_artifacts.completion_marker(item["key"]).is_file()
            ):
                raise RuntimeError(f"completed marker missing for {item['key']}")
            if item["status"] == "succeeded":
                attempt_out = experiment_run_artifacts.attempt(item["key"], int(item["attempts"]))
                verified, reason = verify_run_artifacts(
                    attempt_out,
                    item["key"],
                    args.timesteps,
                    expected_fingerprint=fingerprint,
                    expected_attempt=int(item["attempts"]),
                )
                if not verified:
                    raise RuntimeError(f"completed artifacts invalid for {item['key']}: {reason}")
                if not args.test_worker and item.get("artifact_hashes") != hash_run_artifacts(
                    attempt_out
                ):
                    raise RuntimeError(f"completed artifacts changed for {item['key']}")
            if item["status"] == "running":
                item.update(
                    status="interrupted",
                    failure_reason="controller ended while the worker was active",
                    interrupted_at=utc(),
                )
            if item["status"] == "interrupted":
                item["resume_from_attempt"] = int(item["attempts"])
                item["status"] = "pending"
    else:
        source_snapshot = write_experiment_run_source_snapshot(
            ROOT,
            source_files,
            experiment_run_artifacts.source_snapshot,
            git_sha=git_sha,
            expected_source_hashes=source_hashes,
        )
        manifest = {
            "created": utc(),
            "hostname": socket.gethostname(),
            "job_id": os.getenv("SLURM_JOB_ID", "test"),
            "git_sha": git_sha,
            "source_hashes": source_hashes,
            "source_snapshot": source_snapshot,
            "data_inputs": data_inputs,
            "runtime": runtime,
            "fingerprint": fingerprint,
            "timesteps": args.timesteps,
            "n_envs": args.n_envs,
            "data_source": args.data_source,
            "fast_reports": args.fast_reports,
            "workers": args.workers,
            "worker_nodes": worker_nodes,
            "worker_cpus": args.worker_cpus if worker_nodes else None,
            "worker_cpus_by_node": worker_cpus_by_node if worker_nodes else None,
            "worker_cpu_counts_by_node": worker_cpu_counts_by_node if worker_nodes else None,
            "workers_requested": "auto" if args.workers_auto else args.workers,
            "worker_allocation_plan": worker_allocation_plan,
            "worker_gpu_type": args.worker_gpu_type if worker_nodes else None,
            "worker_gpus_per_node": args.worker_gpus_per_node if worker_nodes else None,
            "gpu_binding": "least-loaded-map_gpu" if worker_nodes else None,
            "evaluation": evaluation,
            "initial_checkpoint_lineage": identity["initial_checkpoint_lineage"],
            "jobs": jobs,
            "resources": available_resources(),
        }
        atomic_json(manifest_path, manifest)
    events = experiment_run_artifacts.queue
    scheduler = experiment_run_artifacts.log("scheduler.jsonl")
    running: dict[str, tuple[subprocess.Popen[bytes], TextIO, dict[str, Any]]] = {}
    signal.signal(signal.SIGTERM, signal_stop)
    signal.signal(signal.SIGINT, signal_stop)
    print(
        f"experiment run={args.experiment_run_id} runs={len(jobs)} workers={args.workers} "
        f"host={socket.gethostname()}",
        flush=True,
    )
    if worker_allocation_plan is not None:
        print(
            "worker resource plan=" + json.dumps(worker_allocation_plan, sort_keys=True),
            flush=True,
        )

    def snapshot() -> None:
        atomic_json(manifest_path, manifest)
        atomic_json(
            experiment_run_artifacts.report("experiment_run_status.json"),
            {
                "timestamp": utc(),
                "statuses": {
                    state: sum(j["status"] == state for j in jobs)
                    for state in ("pending", "running", "succeeded", "failed", "interrupted")
                },
            },
        )

    resource_samplers: list[tuple[subprocess.Popen[bytes], TextIO]] = []
    if worker_nodes:
        for node in worker_nodes:
            sampler_log = experiment_run_artifacts.log(f"resource_sampler_{node}.log").open(
                "a", encoding="utf-8"
            )
            sampler_cpu_mask, sampler_cpu_ids = cpu_mask_for_slot(
                worker_node_cpu_sets[node],
                sum(worker_cpu_counts_by_node[node]),
                1,
            )
            sampler_cmd = worker_command(
                [
                    sys.executable,
                    str(RESOURCE_SAMPLER_SCRIPT),
                    "--experiment-run",
                    str(manifest_path),
                    "--out",
                    str(experiment_run_artifacts.log(f"resources_{node}.csv")),
                ],
                node=node,
                gpu_type=args.worker_gpu_type,
                cpus=1,
                gpu_count=0,
                cpu_mask=sampler_cpu_mask,
                expected_cpu_ids=sampler_cpu_ids,
                step_cpus=cpus,
            )
            sampler_env = dict(os.environ)
            sampler_env.pop("CUDA_VISIBLE_DEVICES", None)
            sampler_proc = subprocess.Popen(
                sampler_cmd,
                cwd=ROOT,
                env=sampler_env,
                stdout=sampler_log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            resource_samplers.append((sampler_proc, sampler_log))

    def start(job: dict[str, Any]) -> None:
        key = job["key"]
        job["attempts"] += 1
        attempt = job["attempts"]
        for field in ("artifact_error", "artifact_hashes", "failure_reason"):
            job.pop(field, None)
        logpath = experiment_run_artifacts.worker_log(key, attempt)
        run_out = experiment_run_artifacts.attempt(key, attempt)
        run_out.mkdir(parents=True, exist_ok=True)
        resume_from_attempt = job.pop("resume_from_attempt", None)
        resume_checkpoint, resume_origin = choose_resume_checkpoint(
            out,
            key,
            int(resume_from_attempt) if resume_from_attempt else None,
            fingerprint,
            archived_bootstrap,
        )
        bootstrap_lineage = initial_checkpoints.get(key)
        resume_checkpoint_hash = sha256_file(resume_checkpoint) if resume_checkpoint else None
        worker_node = None
        worker_cpu_mask = None
        worker_cpu_ids: list[int] = []
        if worker_nodes:
            node_load = {
                node: sum(
                    1
                    for running_job in running.values()
                    if running_job[2].get("worker_node") == node
                )
                for node in worker_nodes
            }
            eligible_nodes = [
                node for node in worker_nodes if node_load[node] < node_worker_targets[node]
            ]
            if not eligible_nodes:
                raise RuntimeError("worker scheduler has no node with an available resource slot")
            worker_node = min(
                eligible_nodes,
                key=lambda node: (
                    node_load[node] / node_worker_targets[node],
                    node_load[node],
                    node,
                ),
            )
            worker_cpu_count = worker_cpu_counts_by_node[worker_node][node_load[worker_node]]
            cpu_start = sum(worker_cpu_counts_by_node[worker_node][: node_load[worker_node]])
            worker_cpu_mask, worker_cpu_ids = cpu_mask_for_range(
                worker_node_cpu_sets[worker_node], cpu_start, worker_cpu_count
            )
            job["worker_node"] = worker_node
            job["worker_cpu_mask"] = worker_cpu_mask
            job["worker_cpu_ids"] = worker_cpu_ids
            gpu_load = {
                gpu_id: sum(
                    1
                    for running_job in running.values()
                    if running_job[2].get("worker_node") == worker_node
                    and running_job[2].get("worker_gpu_id") == gpu_id
                )
                for gpu_id in range(args.worker_gpus_per_node)
            }
            worker_gpu_id = min(gpu_load, key=lambda gpu_id: (gpu_load[gpu_id], gpu_id))
            job["worker_gpu_id"] = worker_gpu_id
            job["remote_pid_file"] = str(run_out / "worker_process.json")
        atomic_json(
            run_out / "attempt_provenance.json",
            {
                "experiment_run_id": args.experiment_run_id,
                "experiment_run_fingerprint": fingerprint,
                "run_key": key,
                "variant": job["variant"],
                "seed": job["seed"],
                "attempt": attempt,
                "requested_timesteps": args.timesteps,
                "n_envs": args.n_envs,
                "data_source": args.data_source,
                "fast_reports": args.fast_reports,
                "evaluation": evaluation,
                "oos_selection_allowed": bool(evaluation.get("selection_allowed", False)),
                "identity": identity,
                "started": utc(),
                "hostname": socket.gethostname(),
                "slurm_job_id": os.getenv("SLURM_JOB_ID"),
                "worker_node": worker_node,
                "worker_gpu_id": job.get("worker_gpu_id"),
                "resume_from_attempt": resume_from_attempt,
                "resume_checkpoint": str(resume_checkpoint) if resume_checkpoint else None,
                "resume_checkpoint_sha256": resume_checkpoint_hash,
                "resume_origin": resume_origin,
                "initial_checkpoint_lineage": bootstrap_lineage,
                "resume_without_checkpoint_reason": (
                    "no intact checkpoint in the previous interrupted attempt"
                    if resume_from_attempt and resume_origin is None and resume_checkpoint is None
                    else None
                ),
            },
        )
        cmd = (
            [str(args.test_worker), key]
            if args.test_worker
            else ["bash", str(TRAIN_ONE_VARIANT_SCRIPT)]
        )
        if worker_nodes:
            cmd = worker_command(
                cmd,
                node=worker_node,
                gpu_type=args.worker_gpu_type,
                cpus=args.worker_cpus,
                gpu_count=1 if args.worker_gpus_per_node else 0,
                gpu_id=int(job["worker_gpu_id"]),
                available_gpu_count=args.worker_gpus_per_node,
                cpu_mask=worker_cpu_mask,
                expected_cpu_ids=worker_cpu_ids,
                step_cpus=cpus,
            )
        env = dict(
            os.environ,
            VARIANT=job["variant"],
            SEED=str(job["seed"]),
            STEPS=str(args.timesteps),
            OUT_DIR=str(run_out),
            LOG_DIR=str(experiment_run_artifacts.worker_logs),
            QUANT_RL_MAX_N_ENVS=str(args.n_envs),
            QUANT_RL_DATA_SOURCE=args.data_source,
            QUANT_RL_FAST_REPORTS="1" if args.fast_reports else "0",
            QUANT_RL_ALLOW_OOS_SELECTION=(
                "1" if evaluation.get("selection_allowed", False) else "0"
            ),
            QUANT_RL_EVALUATION_DETERMINISTIC=(
                "true" if evaluation.get("deterministic", False) else "false"
            ),
            QUANT_RL_CONFIG_OVERRIDES=experiment_run_config_override_lines(config_overrides),
            GPU_ID="0",
            PYTHONUNBUFFERED="1",
        )
        if worker_node is not None:
            # Slurm assigns this step's GPU; it is logical device zero in the worker.
            env.pop("CUDA_VISIBLE_DEVICES", None)
            env["EXPERIMENT_RUN_WORKER_PID_FILE"] = str(run_out / "worker_process.json")
        env.pop("RESUME_CHECKPOINT", None)
        if resume_checkpoint is not None:
            env["RESUME_CHECKPOINT"] = str(resume_checkpoint)
        handle = logpath.open("a", encoding="utf-8")
        handle.write(
            f"{utc()} START key={key} attempt={attempt} "
            f"host={worker_node or socket.gethostname()} controller={socket.gethostname()} "
            f"slurm={os.getenv('SLURM_JOB_ID')} git={git_sha} "
            f"resume={resume_checkpoint or 'none'} cmd={cmd}\n"
        )
        handle.flush()
        proc = subprocess.Popen(
            cmd, cwd=ROOT, env=env, stdout=handle, stderr=subprocess.STDOUT, start_new_session=True
        )
        job.update(status="running", pid=proc.pid, started=utc(), log=str(logpath))
        running[key] = (proc, handle, job)
        record(
            events,
            {
                "event": "start",
                "key": key,
                "attempt": attempt,
                "pid": proc.pid,
                "worker_node": worker_node,
                "worker_cpu_mask": worker_cpu_mask,
                "worker_cpu_ids": worker_cpu_ids,
                "log": str(logpath),
                "attempt_output": str(run_out),
            },
        )
        record(scheduler, {"action": "start", "key": key, "attempt": attempt})
        snapshot()

    last_sample = 0.0
    stop_sent = False
    stop_deadline: float | None = None
    while running or (not STOP and any(j["status"] == "pending" for j in jobs)):
        if STOP and not stop_sent:
            manifest["stopping"] = True
            snapshot()
            stop_deadline = time.monotonic() + 60
            for proc, _, _ in running.values():
                if proc.poll() is None:
                    try:
                        os.killpg(proc.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
            stop_sent = True
        if STOP and stop_deadline is not None and time.monotonic() >= stop_deadline:
            for proc, _, _ in running.values():
                if proc.poll() is None:
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
            stop_deadline = None
        while not STOP and len(running) < args.workers:
            next_job = next((j for j in jobs if j["status"] == "pending"), None)
            if next_job is None:
                break
            start(next_job)
        for key, (proc, handle, job) in list(running.items()):
            ret = proc.poll()
            if ret is None:
                continue
            handle.write(f"{utc()} END key={key} exit={ret}\n")
            handle.close()
            attempt_out = experiment_run_artifacts.attempt(key, int(job["attempts"]))
            verified, reason = (
                (True, "")
                if args.test_worker
                else verify_run_artifacts(
                    attempt_out,
                    key,
                    args.timesteps,
                    expected_fingerprint=fingerprint,
                    expected_attempt=int(job["attempts"]),
                )
            )
            success = ret == 0 and verified
            gate_failure = not verified and "training risk-survival gate failed" in reason
            interrupted = STOP and not success and not gate_failure
            artifact_hashes = hash_run_artifacts(attempt_out)
            failure_reason = None
            if not success:
                reasons = []
                if ret != 0:
                    reasons.append(f"worker exited with code {ret}")
                if not verified and reason:
                    reasons.append(reason)
                failure_reason = "; ".join(reasons) or "experiment run acceptance failed"
            job.update(
                status=("succeeded" if success else "interrupted" if interrupted else "failed"),
                exit_code=ret,
                ended=utc(),
                artifact_error=reason if ret == 0 else "",
                artifact_hashes=artifact_hashes,
            )
            if success:
                experiment_run_artifacts.completion_marker(key).touch()
            else:
                job["failure_reason"] = failure_reason
                record(
                    experiment_run_artifacts.failure_logs / "summary.jsonl",
                    {
                        "key": key,
                        "attempt": job["attempts"],
                        "exit_code": ret,
                        "reason": failure_reason,
                        "artifact_error": reason,
                        "artifact_hashes": artifact_hashes,
                        "log": job["log"],
                    },
                )
            record(
                events,
                {
                    "event": job["status"],
                    "key": key,
                    "attempt": job["attempts"],
                    "exit_code": ret,
                    "reason": "allocation boundary" if interrupted else failure_reason,
                },
            )
            del running[key]
            snapshot()
        if not worker_nodes and time.monotonic() - last_sample >= 30:
            sample_resources(experiment_run_artifacts.log("resources.csv"))
            last_sample = time.monotonic()
        if running:
            time.sleep(1)
    snapshot()
    for sampler_proc, sampler_log_handle in resource_samplers:
        try:
            sampler_proc.wait(timeout=60)
        except subprocess.TimeoutExpired:
            os.killpg(sampler_proc.pid, signal.SIGTERM)
            try:
                sampler_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(sampler_proc.pid, signal.SIGKILL)
                sampler_proc.wait()
        sampler_log_handle.close()
    if args.benchmark:
        elapsed = max(time.monotonic() - started_time, 0.001)
        with experiment_run_artifacts.report("benchmarks.csv").open(
            "a", newline="", encoding="utf-8"
        ) as f:
            csv.writer(f).writerow(
                [
                    utc(),
                    args.workers,
                    args.n_envs,
                    args.timesteps,
                    elapsed,
                    round(args.timesteps / elapsed, 2),
                    os.getenv("SLURM_JOB_ID", ""),
                ]
            )
    try:
        summary_script = pathlib.Path(__file__).resolve().with_name("reporting.py")
        summary_result = subprocess.run(
            [sys.executable, str(summary_script), "--experiment-run-dir", str(out)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if summary_result.returncode == 0:
            print(summary_result.stdout.rstrip(), flush=True)
        else:
            print(
                "WARNING: experiment run results summary generation failed: "
                f"{summary_result.stderr.strip() or summary_result.stdout.strip()}",
                flush=True,
            )
    except OSError as exc:
        print(f"WARNING: experiment run results summary could not start: {exc}", flush=True)
    return 1 if STOP or any(j["status"] != "succeeded" for j in jobs) else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
