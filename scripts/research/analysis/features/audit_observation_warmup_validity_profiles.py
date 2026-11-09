#!/usr/bin/env python3
"""Measure configured observation validity across effective feature profiles.

The generated inventory contains profiles with repeated effective feature
settings. This runner groups only configurations that share the feature-builder
identity and the observation-selection controls, then runs the existing
warmup-validity audit once per group. Profile groups run as direct child
processes so one persistent Slurm step can use bounded CPU parallelism without
per-profile Slurm fan-out.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shlex
from concurrent.futures import Future, ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from omegaconf import OmegaConf
from scripts.research.analysis.features.build_feature_configuration_inventory import (
    load_profile_config,
)
from scripts.research.analysis.features.verify_real_market_feature_prefix_invariance import (
    feature_config_key,
    load_inventory_profiles,
)

from configuration.paths import repository_root
from market_data.transforms.price_grid import configured_price_grid_increment

ROOT = repository_root(__file__)
DEFAULT_INVENTORY = (
    ROOT / "evidence/research/feature_causality/feature_configuration_inventory.json"
)
DEFAULT_OUTPUT = (
    ROOT / "evidence/research/feature_causality/observation_warmup_validity_all_profiles"
)
DEFAULT_CACHE = Path(
    "/scratch/work/nguyenl37/agent_plans/Quantitative-RL-Trading-System/"
    "observation_warmup_cache_all_profiles"
)
AUDIT_SCRIPT = ROOT / "scripts/research/analysis/features/audit_observation_warmup_validity.py"
SOURCE_PATHS = (
    Path(__file__).resolve(),
    AUDIT_SCRIPT,
    ROOT / "scripts/research/analysis/features/build_feature_configuration_inventory.py",
    ROOT / "scripts/research/analysis/features/verify_real_market_feature_prefix_invariance.py",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_hashes() -> dict[str, str]:
    return {str(path.relative_to(ROOT)): _sha256(path) for path in SOURCE_PATHS}


def _config_value(cfg: Any, key: str, default: Any = None) -> Any:
    """Select a resolved config value while preserving plain defaults."""
    value = OmegaConf.select(cfg, key, default=default)
    if OmegaConf.is_config(value):
        return OmegaConf.to_container(value, resolve=True)
    return value


def _observation_group_key(cfg: Any) -> str:
    """Include selection controls omitted from the feature-builder identity."""
    raw_columns = OmegaConf.select(cfg, "strategy.raw_columns") or []
    schedule = OmegaConf.select(cfg, "data.session_schedule_file")
    schedule_path = Path(str(schedule)).expanduser() if schedule else None
    if schedule_path is not None and not schedule_path.is_absolute():
        schedule_path = ROOT / schedule_path
    schedule_hash = (
        _sha256(schedule_path) if schedule_path is not None and schedule_path.is_file() else None
    )
    payload = {
        "feature_builder_key": feature_config_key(cfg),
        "agent_arch": str(OmegaConf.select(cfg, "agent.arch")),
        "raw_columns": list(raw_columns),
        "reachable_r_validity_mask": bool(
            OmegaConf.select(cfg, "env.reachable_r_validity_mask", default=False)
        ),
        "session_schedule_sha256": schedule_hash,
        "tick_execution_enabled": bool(
            OmegaConf.select(cfg, "costs.use_tick_execution", default=True)
        ),
        "tick_sources": {
            "datasets": _config_value(cfg, "data.datasets", default={}),
            "raw_dir": str(OmegaConf.select(cfg, "data.raw_dir")),
            "tick_files": _config_value(cfg, "data.tick_files", default={}),
        },
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def _tick_cache_key(cfg: Any) -> str:
    """Identify the TickBook cache partition shared by equivalent profiles."""
    payload = {
        "primary": str(OmegaConf.select(cfg, "data.primary")),
        "tick_sources": {
            "datasets": _config_value(cfg, "data.datasets", default={}),
            "raw_dir": str(OmegaConf.select(cfg, "data.raw_dir")),
            "tick_files": _config_value(cfg, "data.tick_files", default={}),
        },
        "timezone": str(OmegaConf.select(cfg, "data.tz")),
        "grid": configured_price_grid_increment(cfg),
        "tick_execution_enabled": bool(
            OmegaConf.select(cfg, "costs.use_tick_execution", default=True)
        ),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def _slug(value: str) -> str:
    result = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").lower()
    return result[:72] or "profile"


def group_profiles(profiles: list[tuple[str, Any]]) -> list[dict[str, Any]]:
    """Group profile IDs that share all model-facing audit controls."""
    groups: dict[str, dict[str, Any]] = {}
    for profile_id, cfg in profiles:
        key = _observation_group_key(cfg)
        group = groups.setdefault(
            key,
            {
                "group_key": key,
                "representative_profile": profile_id,
                "profile_ids": [],
            },
        )
        group["profile_ids"].append(profile_id)
    resolved = sorted(groups.values(), key=lambda item: item["group_key"])
    for group in resolved:
        group["profile_ids"].sort()
        group["directory"] = _slug(group["representative_profile"]) + "-" + group["group_key"][:12]
    return resolved


def resolve_groups(inventory_path: Path) -> tuple[list[dict[str, Any]], str]:
    """Resolve the inventory and group identical model-facing audit inputs."""
    profiles, inventory_hash = load_inventory_profiles(inventory_path)
    audit_profiles = [(profile_id, feature_cfg) for profile_id, feature_cfg, _meta in profiles]
    return group_profiles(audit_profiles), inventory_hash


def _build_regeneration_command(
    inventory_path: Path,
    output_dir: Path,
    cache_root: Path,
    workers: int,
) -> str:
    """Build a shell-safe command for regenerating this exact packet."""

    def display_path(path: Path) -> str:
        try:
            return path.relative_to(ROOT).as_posix()
        except ValueError:
            return str(path)

    return shlex.join(
        [
            ".venv/bin/python",
            "scripts/research/analysis/features/audit_observation_warmup_validity_profiles.py",
            "--inventory",
            display_path(inventory_path),
            "--output-dir",
            display_path(output_dir),
            "--cache-dir",
            display_path(cache_root),
            "--workers",
            str(workers),
        ]
    )


def prime_tick_caches(groups: list[dict[str, Any]], cache_root: Path) -> list[str]:
    """Build each distinct TickBook cache once before parallel profile workers."""
    from market_data.loading.tick_book_pipeline import build_tick_books

    cache_root.mkdir(parents=True, exist_ok=True)
    primed: dict[str, Any] = {}
    for group in groups:
        cfg = load_profile_config(str(group["representative_profile"]))
        if not bool(OmegaConf.select(cfg, "costs.use_tick_execution", default=True)):
            continue
        primary = str(OmegaConf.select(cfg, "data.primary"))
        key = _tick_cache_key(cfg)
        if key in primed:
            continue
        cfg.data.cache_dir = str(cache_root / key)
        print(
            f"priming_tick_cache={len(primed) + 1} "
            f"representative={group['representative_profile']} grid={configured_price_grid_increment(cfg)}",
            flush=True,
        )
        build_tick_books(cfg, symbols=[primary], datasets=["training"])
        primed[key] = group["representative_profile"]
    return [str(value) for value in primed.values()]


def _run_group(
    group: dict[str, Any],
    output_dir: Path,
    cache_root: Path,
    regeneration_command: str,
) -> dict[str, Any]:
    """Run the existing validity auditor for one resolved config group."""
    group_dir = output_dir / "profiles" / str(group["directory"])
    group_dir.mkdir(parents=True, exist_ok=False)
    cfg = load_profile_config(str(group["representative_profile"]))
    resolved_config_text = OmegaConf.to_yaml(cfg, resolve=True)
    config_digest = hashlib.sha256(resolved_config_text.encode("utf-8")).hexdigest()
    cache_dir = cache_root / _tick_cache_key(cfg)
    cache_dir.mkdir(parents=True, exist_ok=True)
    log_path = group_dir / "run.log"
    from scripts.research.analysis.features.audit_observation_warmup_validity import (
        build_audit_from_config,
    )

    summary = build_audit_from_config(
        cfg,
        config_label=str(group["representative_profile"]),
        config_sha256=config_digest,
        output_dir=group_dir,
        cache_dir=cache_dir,
        regeneration_command=regeneration_command,
    )
    log_path.write_text(
        json.dumps(
            {
                "group_key": group["group_key"],
                "representative_profile": group["representative_profile"],
                "profile_ids": group["profile_ids"],
                "status": summary["status"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    summary_path = group_dir / "warmup_validity_summary.json"
    try:
        group_directory = str(group_dir.relative_to(ROOT))
    except ValueError:
        group_directory = str(group_dir)
    result: dict[str, Any] = {
        "group_key": group["group_key"],
        "directory": group_directory,
        "representative_profile": group["representative_profile"],
        "profile_ids": group["profile_ids"],
        "return_code": 0,
        "log_sha256": _sha256(log_path),
        "profile_config_sha256": config_digest,
    }
    if summary_path.is_file():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        result["summary"] = summary
        result["summary_sha256"] = _sha256(summary_path)
        result["column_warmup_sha256"] = _sha256(group_dir / "column_warmup.csv")
    return result


def _write_json(path: Path, payload: Any) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.chmod(0o644)
    os.replace(temporary, path)


def run_inventory(
    inventory_path: Path,
    output_dir: Path,
    cache_root: Path,
    workers: int,
) -> dict[str, Any]:
    """Run each distinct observation contract once and write aggregate evidence."""
    if workers < 1:
        raise ValueError("workers must be at least 1")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty output directory: {output_dir}")
    source_hashes_at_start = _source_hashes()
    output_dir.mkdir(parents=True, exist_ok=True)
    groups, inventory_hash = resolve_groups(inventory_path)
    plan = {
        "schema_version": 1,
        "status": "priming_tick_caches",
        "inventory_path": str(inventory_path.relative_to(ROOT)),
        "inventory_sha256": inventory_hash,
        "workers": workers,
        "planned_groups": len(groups),
        "completed_groups": 0,
        "source_sha256_at_start": source_hashes_at_start,
        "groups": groups,
    }
    _write_json(output_dir / "run_plan.json", plan)
    primed_tick_cache_profiles = prime_tick_caches(groups, cache_root)
    plan["status"] = "running"
    plan["primed_tick_cache_profiles"] = primed_tick_cache_profiles
    _write_json(output_dir / "run_plan.json", plan)
    results: list[dict[str, Any]] = []
    errors: list[str] = []
    completed_count = 0
    regeneration_command = _build_regeneration_command(
        inventory_path,
        output_dir,
        cache_root,
        workers,
    )
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures: dict[Future[dict[str, Any]], dict[str, Any]] = {
            executor.submit(
                _run_group,
                group,
                output_dir,
                cache_root,
                regeneration_command,
            ): group
            for group in groups
        }
        for future in as_completed(futures):
            group = futures[future]
            completed_count += 1
            try:
                result = future.result()
                results.append(result)
                if result["return_code"] != 0:
                    errors.append(str(result["directory"]))
            except Exception as exc:
                errors.append(f"{group['directory']}: {type(exc).__name__}: {exc}")
            plan["completed_groups"] = completed_count
            plan["completed"] = sorted(results, key=lambda item: item["group_key"])
            plan["errors"] = errors
            _write_json(output_dir / "run_plan.json", plan)
            print(
                f"profile_groups_completed={completed_count}/{len(groups)} "
                f"representative={group['representative_profile']} errors={len(errors)}",
                flush=True,
            )

    results.sort(key=lambda item: item["group_key"])
    rows: list[dict[str, Any]] = []
    for result in results:
        column_path = ROOT / str(result["directory"]) / "column_warmup.csv"
        if not column_path.is_file():
            continue
        with column_path.open(newline="", encoding="utf-8") as stream:
            for row in csv.DictReader(stream):
                rows.append(
                    {
                        "profile_group": Path(str(result["directory"])).name,
                        "representative_profile": result["representative_profile"],
                        "profile_ids": json.dumps(result["profile_ids"], separators=(",", ":")),
                        **row,
                    }
                )
    columns = (
        "profile_group",
        "representative_profile",
        "profile_ids",
        "timeframe",
        "feature",
        "sampled_rows",
        "finite_rows",
        "nonfinite_rows",
        "nonfinite_fraction",
        "leading_nonfinite_rows",
        "interior_nonfinite_rows",
        "finite_zero_rows",
        "missing_collides_with_finite_zero",
    )
    with (output_dir / "column_warmup_all_profiles.csv").open(
        "w", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    source_hashes_at_end = _source_hashes()
    sources_unchanged = source_hashes_at_start == source_hashes_at_end
    summary = {
        "schema_version": 1,
        "status": (
            "complete"
            if not errors and len(results) == len(groups) and sources_unchanged
            else "incomplete"
        ),
        "inventory_path": str(inventory_path.relative_to(ROOT)),
        "inventory_sha256": inventory_hash,
        "profile_count": sum(len(group["profile_ids"]) for group in groups),
        "profile_group_count": len(groups),
        "completed_group_count": len(results),
        "failed_groups": errors,
        "workers": workers,
        "row_count": len(rows),
        "groups": results,
        "source_sha256": source_hashes_at_start,
        "source_sha256_at_end": source_hashes_at_end,
        "sources_unchanged_during_run": sources_unchanged,
        "limitations": [
            "Each effective observation contract is measured on the configured local training split.",
            "This reports nonfinite/finite-zero behavior; producer-specific cause attribution remains separate evidence.",
            "This is feature-contract evidence, not learned-policy or economic evidence.",
        ],
    }
    _write_json(output_dir / "observation_warmup_validity_all_profiles.json", summary)
    readme = [
        "# Observation validity across configured feature profiles",
        "",
        "This packet measures the configured model-facing training observations for each effective feature and observation contract in the feature inventory. It reports sampled, finite, non-finite, leading-warmup, and finite-zero counts by profile group, timeframe, and feature.",
        "",
        "`column_warmup_all_profiles.csv` is the consolidated per-feature table. Each `profiles/` subdirectory contains its resolved runtime configuration, source summary, per-feature table, and run log. `run_plan.json` records the inventory identity and group progress; `observation_warmup_validity_all_profiles.json` is the aggregate manifest.",
        "",
        "The packet measures feature validity, not the semantic cause of every missing value, learned-policy behavior, or economic performance. Producer-specific cause attribution remains a separate review.",
        "",
        "## Regeneration",
        "",
        f"`{regeneration_command}`",
        "",
    ]
    (output_dir / "README.md").write_text("\n".join(readme), encoding="utf-8")
    plan["status"] = summary["status"]
    plan["completed_groups"] = len(results)
    plan["errors"] = errors
    _write_json(output_dir / "run_plan.json", plan)
    checksum_lines = [
        f"{_sha256(path)}  {path.relative_to(output_dir).as_posix()}"
        for path in sorted(output_dir.rglob("*"))
        if path.is_file() and path.name != "SHA256SUMS"
    ]
    (output_dir / "SHA256SUMS").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args(argv)
    inventory = args.inventory if args.inventory.is_absolute() else ROOT / args.inventory
    output = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir
    cache = args.cache_dir if args.cache_dir.is_absolute() else ROOT / args.cache_dir
    summary = run_inventory(inventory.resolve(), output.resolve(), cache.resolve(), args.workers)
    print(
        json.dumps(
            {
                key: summary[key]
                for key in (
                    "status",
                    "profile_count",
                    "profile_group_count",
                    "completed_group_count",
                    "workers",
                    "row_count",
                    "failed_groups",
                )
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return 0 if summary["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
