"""Inventory resolved feature configurations used by repository run profiles.

This is a static configuration audit. It resolves the default, direct feature
and research overlays, experiment-run specs, and legacy catalog variants; it
does not build feature matrices or read market data.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from omegaconf import DictConfig, OmegaConf

from configuration.configuration_loader import (
    apply_overrides,
    load_config,
)
from configuration.paths import repository_root
from experiments.runs.execution import (
    experiment_run_config_override_lines,
    load_experiment_run_data_profile,
    normalize_experiment_run_config_overrides,
)
from training.configuration.strategy_overlays import merge_strategy_config, strategy_overlay_path
from training.configuration.variant_resolution import load_experiments, resolve_variant

ROOT = repository_root(__file__)
DEFAULT_OUTPUT = ROOT / "evidence" / "research" / "feature_causality"
INVENTORY_VERSION = "feature-configuration-inventory-v1"
RESOLVER_SOURCE_PATHS = (
    Path("configuration/configuration_loader.py"),
    Path("configuration/schema.py"),
    Path("experiments/runs/execution.py"),
    Path("training/configuration/variant_resolution.py"),
    Path("training/configuration/variant_risk_policy.py"),
)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _feature_tree(cfg: DictConfig) -> dict[str, Any]:
    result = OmegaConf.to_container(cfg.features, resolve=True)
    if not isinstance(result, dict):
        raise TypeError("resolved features config must be a mapping")
    return cast(dict[str, Any], result)


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    if isinstance(value, Mapping):
        for key, child in sorted(value.items(), key=lambda item: str(item[0])):
            path = f"{prefix}.{key}" if prefix else str(key)
            flattened.update(_flatten(child, path))
    else:
        flattened[prefix] = value
    return flattened


def _record(
    *,
    profile_id: str,
    profile_kind: str,
    source_paths: list[Path],
    cfg: DictConfig,
    notes: str = "",
) -> dict[str, Any]:
    feature_tree = _feature_tree(cfg)
    flat = _flatten(feature_tree)
    encoded = json.dumps(feature_tree, sort_keys=True, separators=(",", ":")).encode()
    true_switches = [
        key for key, value in flat.items() if isinstance(value, bool) and value is True
    ]
    timeframe_values = {
        key: value
        for key, value in flat.items()
        if "timeframe" in key.lower() and isinstance(value, (str, list, tuple))
    }
    source_records = [
        {"path": _relative(path), "sha256": _sha256_file(path)} for path in source_paths
    ]
    return {
        "profile_id": profile_id,
        "profile_kind": profile_kind,
        "source_paths": source_records,
        "source_sha256": _sha256_bytes(
            "\n".join(f"{item['path']}:{item['sha256']}" for item in source_records).encode()
        ),
        "feature_config_sha256": _sha256_bytes(encoded),
        "enabled_boolean_switches": true_switches,
        "configured_timeframe_fields": timeframe_values,
        "features": feature_tree,
        "notes": notes,
    }


def _profile_sources() -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    profiles: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []

    default_config_path = ROOT / "config" / "base" / "default.yaml"
    profiles.append(
        _record(
            profile_id="base/default",
            profile_kind="base",
            source_paths=[default_config_path],
            cfg=load_config(),
            notes="Canonical default feature configuration.",
        )
    )

    for directory, profile_kind in (
        ("features", "feature_overlay"),
        ("research", "research_overlay"),
    ):
        for path in sorted((ROOT / "config" / directory).glob("*.yaml")):
            raw = OmegaConf.load(path)
            if not isinstance(raw, DictConfig):
                raise ValueError(f"feature/research profile must be a mapping: {path}")
            if "schema_version" in raw:
                excluded.append(
                    {
                        "path": _relative(path),
                        "sha256": _sha256_file(path),
                        "reason": "versioned research contract; not a runtime configuration overlay",
                    }
                )
                continue
            cfg = load_config(config_path=path)
            profiles.append(
                _record(
                    profile_id=f"{directory}/{path.stem}",
                    profile_kind=profile_kind,
                    source_paths=[default_config_path, path],
                    cfg=cfg,
                    notes="Resolved over config/base/default.yaml.",
                )
            )

    for path in sorted((ROOT / "config").glob("[123]_*.yaml")):
        cfg = load_config(config_path=path)
        profiles.append(
            _record(
                profile_id=f"strategy_overlay/{path.stem}",
                profile_kind="legacy_strategy_overlay",
                source_paths=[default_config_path, path],
                cfg=cfg,
                notes="Resolved legacy strategy overlay; included because runtime can merge it.",
            )
        )

    for path in sorted((ROOT / "config" / "experiment_runs").glob("*.yaml")):
        spec = OmegaConf.load(path)
        if not isinstance(spec, DictConfig):
            raise ValueError(f"experiment run spec must be a mapping: {path}")
        cfg = load_config()
        sources = [default_config_path, path]
        data_profile = spec.get("data_profile")
        if data_profile:
            data_profile_path = ROOT / str(data_profile)
            # The run loader intentionally consumes data_modes as a constrained
            # data-only profile, not as a general config overlay. Its validated
            # contract excludes feature keys, so the feature tree remains base.
            mode = OmegaConf.load(data_profile_path)
            if "features" in mode:
                raise ValueError(f"data mode must not define features: {data_profile_path}")
            sources.append(data_profile_path)
        raw_overrides = spec.get("config_overrides") or {}
        overrides = (
            OmegaConf.to_container(raw_overrides, resolve=True)
            if OmegaConf.is_config(raw_overrides)
            else raw_overrides
        )
        if not isinstance(overrides, dict):
            raise ValueError(f"experiment run config_overrides must be a mapping: {path}")
        normalized_overrides = normalize_experiment_run_config_overrides(overrides)
        feature_overrides = {
            key: value for key, value in normalized_overrides.items() if key.startswith("features.")
        }
        if feature_overrides:
            cfg = apply_overrides(
                cfg,
                experiment_run_config_override_lines(feature_overrides).splitlines(),
            )
        profiles.append(
            _record(
                profile_id=f"experiment_run/{path.stem}",
                profile_kind="experiment_run_spec",
                source_paths=sources,
                cfg=cfg,
                notes=(
                    "Feature projection of the run spec; non-feature settings and data contents "
                    "are not evaluated. Effective override types use the runtime normalizer."
                ),
            )
        )

    experiments_path = ROOT / "config" / "experiments.yaml"
    experiment_catalog = load_experiments(experiments_path)
    for variant in experiment_catalog["variants"]:
        name = str(variant["name"])
        # A placeholder satisfies the resolver's declarative VAE-path guard;
        # no checkpoint is opened and VAE availability is not inferred here.
        resolved = resolve_variant(
            name,
            experiments_path=experiments_path,
            vae_path="__static_feature_inventory_only__.pth",
        )
        variant_base_path = ROOT / str(resolved["base_config"])
        cfg = load_config(config_path=variant_base_path)
        cfg = merge_strategy_config(cfg, str(resolved["strategy"]))
        cfg = apply_overrides(cfg, list(resolved["overrides"]))
        strategy_path = strategy_overlay_path(str(resolved["strategy"]))
        source_paths = [experiments_path, variant_base_path]
        if strategy_path is not None:
            source_paths.append(strategy_path)
        profiles.append(
            _record(
                profile_id=f"legacy_variant/{name}",
                profile_kind="resolved_legacy_variant",
                source_paths=source_paths,
                cfg=cfg,
                notes=(
                    "Resolved through training.configuration.variant_resolution; this records "
                    "declared feature settings, not historical artifact/cache equivalence."
                ),
            )
        )

    # These are runtime inputs, but they do not declare feature configuration.
    # Keep their scope visible so the inventory does not imply every YAML is a
    # feature profile.
    variant_dir = ROOT / "config" / "variants"
    for path in sorted(variant_dir.glob("*.yaml")):
        excluded.append(
            {
                "path": _relative(path),
                "sha256": _sha256_file(path),
                "reason": "risk-policy variant settings; not a feature pipeline overlay",
            }
        )

    for path in sorted((ROOT / "config" / "data_modes").glob("*.yaml")):
        excluded.append(
            {
                "path": _relative(path),
                "sha256": _sha256_file(path),
                "reason": "validated data-only profile; experiment-run feature tree inherits base",
            }
        )

    return profiles, excluded


def build_inventory() -> dict[str, Any]:
    """Resolve in-repository feature profiles and summarize their coverage."""
    profiles, excluded = _profile_sources()
    hashes: dict[str, list[str]] = {}
    for profile in profiles:
        hashes.setdefault(profile["feature_config_sha256"], []).append(profile["profile_id"])
    distinct = [
        {"feature_config_sha256": digest, "profile_ids": sorted(profile_ids)}
        for digest, profile_ids in sorted(hashes.items())
    ]
    return {
        "inventory_version": INVENTORY_VERSION,
        "generator": {
            "path": _relative(Path(__file__)),
            "sha256": _sha256_file(Path(__file__)),
        },
        "resolver_sources": [
            {"path": path.as_posix(), "sha256": _sha256_file(ROOT / path)}
            for path in RESOLVER_SOURCE_PATHS
        ],
        "scope": (
            "Static effective feature configuration for default, direct feature/research overlays, "
            "experiment-run specs, legacy experiment catalog variants, and data-mode overlays."
        ),
        "limitations": [
            "This inventory does not execute feature producers or inspect market rows.",
            "A resolved switch does not prove causal behavior, row availability, event cardinality, or feed timing.",
            "Experiment-run profiles are feature projections; run variant/runtime behavior is not executed.",
            "Profile equivalence is exact resolved feature-tree equality, not checkpoint/cache/data equivalence.",
        ],
        "profile_count": len(profiles),
        "distinct_feature_config_count": len(distinct),
        "profiles": profiles,
        "distinct_feature_configs": distinct,
        "excluded_sources": excluded,
    }


def load_profile_config(profile_id: str) -> DictConfig:
    """Resolve a complete runtime config for one inventoried feature profile.

    The inventory stores feature-tree projections. This resolver reconstructs
    the corresponding runtime config so real-market audits can retain each
    profile's data and session clock settings while using the exact inventoried
    feature settings.

    Args:
        profile_id: Stable ``profile_id`` from ``feature_configuration_inventory``.

    Returns:
        Complete configuration for that profile.

    Raises:
        KeyError: If the profile is not present in the current inventory sources.
    """
    if profile_id == "base/default":
        return load_config()

    prefix, _, name = profile_id.partition("/")
    if prefix in {"features", "research", "strategy_overlay"}:
        directory = "config" if prefix == "strategy_overlay" else f"config/{prefix}"
        path = ROOT / directory / f"{name}.yaml"
        if not path.is_file():
            raise KeyError(f"feature profile config is missing: {profile_id}")
        return load_config(config_path=path)

    if prefix == "experiment_run":
        path = ROOT / "config" / "experiment_runs" / f"{name}.yaml"
        if not path.is_file():
            raise KeyError(f"experiment-run feature profile is missing: {profile_id}")
        spec = OmegaConf.load(path)
        if not isinstance(spec, DictConfig):
            raise ValueError(f"experiment-run spec must be a mapping: {path}")
        cfg = load_config()
        data_overrides = load_experiment_run_data_profile(spec.get("data_profile"))
        raw_overrides = spec.get("config_overrides") or {}
        overrides = (
            OmegaConf.to_container(raw_overrides, resolve=True)
            if OmegaConf.is_config(raw_overrides)
            else raw_overrides
        )
        if not isinstance(overrides, dict):
            raise ValueError(f"experiment-run overrides must be a mapping: {path}")
        normalized = normalize_experiment_run_config_overrides({**data_overrides, **overrides})
        return apply_overrides(
            cfg,
            experiment_run_config_override_lines(normalized).splitlines(),
        )

    if prefix == "legacy_variant":
        experiments_path = ROOT / "config" / "experiments.yaml"
        resolved = resolve_variant(
            name,
            experiments_path=experiments_path,
            vae_path="__static_feature_inventory_only__.pth",
        )
        cfg = load_config(config_path=ROOT / str(resolved["base_config"]))
        cfg = merge_strategy_config(cfg, str(resolved["strategy"]))
        return apply_overrides(cfg, list(resolved["overrides"]))

    raise KeyError(f"unknown feature profile kind in {profile_id!r}")


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def write_inventory(output_dir: Path, inventory: dict[str, Any]) -> None:
    """Write machine-readable JSON and a compact one-row-per-profile CSV."""
    json_text = json.dumps(inventory, indent=2, sort_keys=True) + "\n"
    _atomic_write(output_dir / "feature_configuration_inventory.json", json_text)
    columns = (
        "profile_id",
        "profile_kind",
        "source_paths",
        "source_sha256",
        "feature_config_sha256",
        "enabled_boolean_switches",
        "configured_timeframe_fields",
        "notes",
    )
    from io import StringIO

    buffer = StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for profile in inventory["profiles"]:
        writer.writerow(
            {
                "profile_id": profile["profile_id"],
                "profile_kind": profile["profile_kind"],
                "source_paths": json.dumps(profile["source_paths"], sort_keys=True),
                "source_sha256": profile["source_sha256"],
                "feature_config_sha256": profile["feature_config_sha256"],
                "enabled_boolean_switches": json.dumps(
                    profile["enabled_boolean_switches"], separators=(",", ":")
                ),
                "configured_timeframe_fields": json.dumps(
                    profile["configured_timeframe_fields"], sort_keys=True, separators=(",", ":")
                ),
                "notes": profile["notes"],
            }
        )
    _atomic_write(output_dir / "feature_configuration_inventory.csv", buffer.getvalue())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output_dir = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir
    inventory = build_inventory()
    write_inventory(output_dir, inventory)
    print(
        json.dumps(
            {
                "output_dir": str(output_dir),
                "profile_count": inventory["profile_count"],
                "distinct_feature_config_count": inventory["distinct_feature_config_count"],
                "excluded_source_count": len(inventory["excluded_sources"]),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
