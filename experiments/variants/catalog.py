"""Validate and render the model and experiment variant catalog."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

from configuration.paths import repository_root
from models.architecture_ids import ENCODER_ARCHITECTURE_IDS
from training.configuration.variant_resolution import (
    ALGOS,
    PROJECT_ROOT,
    load_experiments,
    resolve_variant,
)
from training.configuration.variant_risk_policy import load_variant_ftmo_config

CATALOG_PATH = PROJECT_ROOT / "config" / "variant_catalog.yaml"
CATALOG_PAGE_PATH = PROJECT_ROOT / "docs" / "model_variants.md"
_COMPARISON_TYPES = {"descriptive", "ladder", "matched", "screening"}
_ROLES = {"candidate", "control", "reference", "rung", "treatment"}


class CatalogError(ValueError):
    """Raised when catalog metadata disagrees with runnable configuration."""


def _require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CatalogError(f"{field} must be a non-empty string")
    return value.strip()


def validate_catalog_index(
    metadata: dict[str, Any],
    experiments: dict[str, Any],
    *,
    root: Path = PROJECT_ROOT,
    architecture_ids: tuple[str, ...] = ENCODER_ARCHITECTURE_IDS,
    algorithms: tuple[str, ...] = ALGOS,
) -> None:
    """Validate classification metadata against the current experiment matrix."""
    if metadata.get("schema_version") != 1:
        raise CatalogError("variant catalog schema_version must be 1")
    if not isinstance(experiments.get("variants"), list):
        raise CatalogError("experiment configuration must contain a variants list")

    current_names: set[str] = set()
    for row in experiments["variants"]:
        if not isinstance(row, dict):
            raise CatalogError("every experiment variant must be a mapping")
        name = _require_text(row.get("name"), "experiment variant name")
        if name in current_names:
            raise CatalogError(f"experiment variant is declared more than once: {name}")
        current_names.add(name)

    catalog_algorithms = metadata.get("algorithms")
    if not isinstance(catalog_algorithms, dict) or set(catalog_algorithms) != set(algorithms):
        raise CatalogError("catalog algorithms must exactly match the supported algorithm IDs")
    for algo, details in catalog_algorithms.items():
        if not isinstance(details, dict):
            raise CatalogError(f"algorithm metadata must be a mapping: {algo}")
        _require_text(details.get("title"), f"algorithm {algo} title")
        _require_text(details.get("description"), f"algorithm {algo} description")

    architectures = metadata.get("architectures")
    if not isinstance(architectures, list):
        raise CatalogError("catalog architectures must be a list")
    architecture_names: list[str] = []
    for item in architectures:
        if not isinstance(item, dict):
            raise CatalogError("every architecture metadata entry must be a mapping")
        arch_id = _require_text(item.get("id"), "architecture id")
        architecture_names.append(arch_id)
        _require_text(item.get("title"), f"architecture {arch_id} title")
        _require_text(item.get("description"), f"architecture {arch_id} description")
    if len(architecture_names) != len(set(architecture_names)):
        raise CatalogError("architecture IDs must be unique")
    if set(architecture_names) != set(architecture_ids):
        raise CatalogError("catalog architecture IDs must match the lightweight encoder registry")

    families = metadata.get("families")
    if not isinstance(families, list) or not families:
        raise CatalogError("catalog must contain at least one research family")
    family_ids: set[str] = set()
    classified_names: set[str] = set()
    for family in families:
        family_id, entries = _validate_family(family)
        if family_id in family_ids:
            raise CatalogError(f"duplicate family ID: {family_id}")
        family_ids.add(family_id)
        labels: set[str] = set()
        roles: list[str] = []
        for entry in entries:
            variant = _require_text(entry.get("variant"), f"{family_id} variant")
            label = _require_text(entry.get("label"), f"{family_id} label")
            role = _require_text(entry.get("role"), f"{family_id} role")
            if label in labels:
                raise CatalogError(f"duplicate arm label {label!r} in family {family_id}")
            labels.add(label)
            if role not in _ROLES:
                raise CatalogError(f"invalid role {role!r} in family {family_id}")
            roles.append(role)
            _require_text(entry.get("description"), f"{family_id} description")
            changed = entry.get("changed_factors")
            if not isinstance(changed, list) or any(
                not isinstance(value, str) for value in changed
            ):
                raise CatalogError(f"{family_id} changed_factors must be a list of strings")

            sources = entry.get("historical_sources", [])
            if not isinstance(sources, list) or any(
                not isinstance(source, str) for source in sources
            ):
                raise CatalogError(f"{family_id} historical_sources must be a list of paths")
            if variant in current_names:
                classified_names.add(variant)
            else:
                if not sources:
                    raise CatalogError(
                        f"non-selectable variant {variant!r} needs a frozen historical source"
                    )
                for source in sources:
                    _validate_historical_source(root, source, family_id)

        if family["comparison_type"] == "matched":
            if roles.count("control") != 1 or roles.count("treatment") < 1:
                raise CatalogError(
                    f"matched family {family_id} needs one control and at least one treatment"
                )

    missing = current_names - classified_names
    if missing:
        raise CatalogError(f"selectable variants missing from catalog: {sorted(missing)}")


def _validate_family(family: Any) -> tuple[str, list[dict[str, Any]]]:
    if not isinstance(family, dict):
        raise CatalogError("every catalog family must be a mapping")
    family_id = _require_text(family.get("id"), "family id")
    _require_text(family.get("title"), f"family {family_id} title")
    _require_text(family.get("question"), f"family {family_id} question")
    comparison_type = _require_text(
        family.get("comparison_type"), f"family {family_id} comparison_type"
    )
    if comparison_type not in _COMPARISON_TYPES:
        raise CatalogError(f"unsupported comparison type {comparison_type!r} in {family_id}")
    entries = family.get("entries")
    if not isinstance(entries, list) or not entries:
        raise CatalogError(f"family {family_id} must contain entries")
    if any(not isinstance(entry, dict) for entry in entries):
        raise CatalogError(f"every entry in {family_id} must be a mapping")
    return family_id, entries


def _validate_historical_source(root: Path, source: str, family_id: str) -> None:
    relative = Path(source)
    resolved = (root / relative).resolve()
    if not resolved.is_relative_to(root.resolve()) or not resolved.is_file():
        raise CatalogError(
            f"{family_id} historical source is missing or outside the repo: {source}"
        )


def build_catalog() -> dict[str, Any]:
    """Resolve current variant settings and attach their research metadata."""
    try:
        metadata = yaml.safe_load(CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise CatalogError(f"cannot read catalog metadata at {CATALOG_PATH}: {exc}") from exc
    if not isinstance(metadata, dict):
        raise CatalogError("catalog metadata must be a mapping")

    experiments = load_experiments()
    validate_catalog_index(metadata, experiments)
    resolved_by_name: dict[str, dict[str, Any]] = {}
    for row in experiments["variants"]:
        name = str(row["name"])
        resolved = resolve_variant(name, vae_path="catalog-metadata-only.pth")
        resolved["risk"] = load_variant_ftmo_config(name)
        resolved_by_name[name] = resolved

    families: list[dict[str, Any]] = []
    for family in metadata["families"]:
        family_copy = {key: value for key, value in family.items() if key != "entries"}
        entries: list[dict[str, Any]] = []
        for entry in family["entries"]:
            row = dict(entry)
            resolved_entry = resolved_by_name.get(str(entry["variant"]))
            row["status"] = "Selectable" if resolved_entry is not None else "Historical"
            if resolved_entry is not None:
                row["resolved"] = resolved_entry
            entries.append(row)
        family_copy["entries"] = entries
        families.append(family_copy)

    architecture_algorithms: dict[str, set[str]] = {
        str(item["id"]): set() for item in metadata["architectures"]
    }
    architecture_variants: dict[str, set[str]] = {
        str(item["id"]): set() for item in metadata["architectures"]
    }
    for name, resolved in resolved_by_name.items():
        arch = str(resolved["arch"])
        architecture_algorithms[arch].add(str(resolved["algo"]))
        architecture_variants[arch].add(name)

    architectures = []
    for item in metadata["architectures"]:
        arch_id = str(item["id"])
        architectures.append(
            {
                **item,
                "algorithms": sorted(architecture_algorithms[arch_id]),
                "variants": sorted(architecture_variants[arch_id]),
            }
        )
    return {
        "algorithms": metadata["algorithms"],
        "architectures": architectures,
        "families": families,
    }


def _markdown_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


def _risk_summary(risk: dict[str, Any]) -> str:
    return (
        f"{risk['limit_value_mode']}; trade ${risk['risk_per_trade_limit']:,.0f}; "
        f"daily ${risk['daily_loss_limit']:,.0f}; max ${risk['max_loss_limit']:,.0f}; "
        f"size cap ${risk['risk_sizing_limit_usd']:,.0f}"
    )


def _history_links(sources: list[str]) -> str:
    return ", ".join(f"[source](../{_markdown_cell(source)})" for source in sources)


def render_catalog(catalog: dict[str, Any]) -> str:
    """Render a deterministic, human-readable Markdown catalog."""
    lines = [
        "# Model and Experiment Variant Catalog",
        "",
        "Generated from `config/variant_catalog.yaml` and resolved experiment settings.",
        "Regenerate with `qrl-experiment catalog --write`; validate with `--check`.",
        "Settings stay in their source YAML files; A/B labels are local to each family.",
        "",
        "## Policy algorithms",
        "",
        "| ID | Algorithm | Description |",
        "|---|---|---|",
    ]
    for algo, details in sorted(catalog["algorithms"].items()):
        lines.append(
            f"| `{algo}` | {_markdown_cell(details['title'])} | "
            f"{_markdown_cell(details['description'])} |"
        )
    lines.extend(
        [
            "",
            "## Encoder architectures",
            "",
            "Algorithm/encoder pairs below are shown only when a selectable variant uses them.",
            "A registered encoder with no listed pair currently has no matrix variant.",
            "",
            "| Encoder ID | Architecture | Description | Configured algorithms | Selectable variant count |",
            "|---|---|---|---|---|",
        ]
    )
    for architecture in catalog["architectures"]:
        algos = ", ".join(architecture["algorithms"]) or "—"
        variant_count = len(architecture["variants"])
        lines.append(
            f"| `{architecture['id']}` | {_markdown_cell(architecture['title'])} | "
            f"{_markdown_cell(architecture['description'])} | {algos} | {variant_count} |"
        )

    for family in catalog["families"]:
        family_id = str(family["id"])
        lines.extend(
            [
                "",
                f"## {_markdown_cell(family['title'])}",
                "",
                f"**Family:** `{family_id}`",
                "",
                f"**Research question:** {_markdown_cell(family['question'])}",
                "",
                f"**Comparison type:** `{family['comparison_type']}`",
                "",
                "| Arm | Variant | Status | Role | Algorithm | Encoder | Reward | Strategy | Risk policy | Description / changed factors | Sources |",
                "|---|---|---|---|---|---|---|---|---|---|---|",
            ]
        )
        for entry in family["entries"]:
            resolved = entry.get("resolved")
            if resolved:
                algo = f"`{resolved['algo']}`"
                arch = f"`{resolved['arch']}`"
                reward = f"`{resolved['reward_mode']}`"
                strategy = f"`{resolved['strategy']}`"
                risk = _risk_summary(resolved["risk"])
            else:
                algo = arch = reward = strategy = risk = "—"
            changes = ", ".join(entry["changed_factors"]) or "None declared"
            description = f"{entry['description']} Changes: {changes}."
            sources = _history_links(entry.get("historical_sources", [])) or "—"
            lines.append(
                f"| {entry['label']} | `{entry['variant']}` | {entry['status']} | "
                f"{entry['role']} | {algo} | {arch} | {reward} | {strategy} | "
                f"{risk} | {_markdown_cell(description)} | {sources} |"
            )
    historical_entries = [
        entry
        for family in catalog["families"]
        for entry in family["entries"]
        if entry["status"] == "Historical"
    ]
    if not historical_entries:
        lines.extend(
            [
                "",
                "No retired variant IDs were found in the preserved frozen run configurations.",
                "Retired rows require a non-selectable variant and a verifiable source record.",
            ]
        )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Write the generated page or fail if it is stale."""
    parser = argparse.ArgumentParser(description="Generate or validate the model variant catalog.")
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument("--write", action="store_true", help="write the generated Markdown")
    operation.add_argument("--check", action="store_true", help="fail when Markdown is stale")
    args = parser.parse_args(argv)
    try:
        generated = render_catalog(build_catalog())
        if args.write:
            CATALOG_PAGE_PATH.write_text(generated, encoding="utf-8")
            try:
                display_path = CATALOG_PAGE_PATH.relative_to(repository_root(__file__))
            except ValueError:
                display_path = CATALOG_PAGE_PATH
            print(f"Wrote {display_path}")
            return 0
        existing = CATALOG_PAGE_PATH.read_text(encoding="utf-8")
        if existing != generated:
            print(f"Catalog page is stale: {CATALOG_PAGE_PATH}", file=sys.stderr)
            return 1
    except (CatalogError, OSError, ValueError) as exc:
        print(f"Cannot build model variant catalog: {exc}", file=sys.stderr)
        return 2
    print("Model variant catalog is current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
