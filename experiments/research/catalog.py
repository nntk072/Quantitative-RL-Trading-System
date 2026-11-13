"""Declarative research experiment catalog.

The catalog groups variants by scientific question instead of encoding one
script or configuration file per run. Runtime services consume immutable
specifications and write execution-specific state under outputs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from configuration.paths import repository_root

ROOT = repository_root(__file__)
DEFAULT_CATALOG = ROOT / "config/research/experiments.yaml"


@dataclass(frozen=True, slots=True)
class VariantSpec:
    """One intervention inside a named research experiment."""

    variant_id: str
    config: str | None
    architecture: str | None
    role: str
    authorization: str | None
    overrides: tuple[str, ...]
    command: tuple[str, ...]
    artifact_roots: tuple[str, ...]
    depends_on: tuple[str, ...]
    component: str = "unspecified"


@dataclass(frozen=True, slots=True)
class ExecutionSpec:
    """Execution contract shared by all variants of an experiment."""

    kind: str
    seeds: tuple[int, ...]
    walk_forward_splits: int
    purge_bars: int
    embargo_bars: int
    additional_timesteps: int
    resource_lock: str | None


@dataclass(frozen=True, slots=True)
class ExperimentSpec:
    """A scientific question with a reusable set of variants."""

    experiment_id: str
    domain: str
    summary: str
    selection_role: str
    variants: tuple[VariantSpec, ...]
    execution: ExecutionSpec
    assemblies: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def variants_for_assembly(self, assembly_id: str) -> tuple[VariantSpec, ...]:
        """Resolve a named group of component implementations.

        Args:
            assembly_id: Registered selection of compatible experiment variants.

        Returns:
            Variant specifications in the order declared by the assembly.
        """
        try:
            members = self.assemblies[assembly_id]
        except KeyError as exc:
            raise KeyError(f"unknown assembly {assembly_id!r} for {self.experiment_id!r}") from exc
        return tuple(self.variant(member) for member in members)

    def variant(self, variant_id: str) -> VariantSpec:
        """Return one registered variant or fail closed.

        Args:
            variant_id: Registered variant identifier.

        Returns:
            Result produced by variant.
        """
        for item in self.variants:
            if item.variant_id == variant_id:
                return item
        raise KeyError(f"unknown variant {variant_id!r} for experiment {self.experiment_id!r}")


@dataclass(frozen=True, slots=True)
class ResearchCatalog:
    """Validated active research catalog."""

    schema_version: int
    protocol: str
    domains: dict[str, str]
    experiments: tuple[ExperimentSpec, ...]

    def experiment(self, experiment_id: str) -> ExperimentSpec:
        """Return one registered experiment or fail closed.

        Args:
            experiment_id: Registered research experiment identifier.

        Returns:
            Result produced by experiment.
        """
        for item in self.experiments:
            if item.experiment_id == experiment_id:
                return item
        raise KeyError(f"unknown research experiment: {experiment_id}")

    def by_domain(self, domain: str) -> tuple[ExperimentSpec, ...]:
        """Return all experiments in one research domain.

        Args:
            domain: Research domain identifier.

        Returns:
            Result produced by by_domain.
        """
        if domain not in self.domains:
            raise KeyError(f"unknown research domain: {domain}")
        return tuple(item for item in self.experiments if item.domain == domain)


def _mapping(value: Any, label: str) -> dict[str, Any]:
    """Return a validated string-keyed mapping.

    Args:
        value: Value to validate or transform.
        label: Field label used in validation errors.

    Returns:
        Result produced by _mapping.
    """
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{label} must be a string-keyed mapping")
    return dict(value)


def _string(value: Any, label: str) -> str:
    """Return a validated non-empty string.

    Args:
        value: Value to validate or transform.
        label: Field label used in validation errors.

    Returns:
        Result produced by _string.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value.strip()


def _relative_repo_path(value: Any, label: str) -> str:
    """Return a validated repository-relative path.

    Args:
        value: Value to validate or transform.
        label: Field label used in validation errors.

    Returns:
        Result produced by _relative_repo_path.
    """
    raw = _string(value, label)
    path = Path(raw)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{label} must remain inside the repository")
    return path.as_posix()


def _integer(value: Any, label: str, *, minimum: int = 0) -> int:
    """Return a validated bounded integer.

    Args:
        value: Value to validate or transform.
        label: Field label used in validation errors.
        minimum: Minimum accepted integer value.

    Returns:
        Result produced by _integer.
    """
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{label} must be an integer >= {minimum}")
    return value


def _variant(value: Any, *, experiment_id: str, variant_id: str, domain: str) -> VariantSpec:
    """Build one validated variant specification.

    Args:
        value: Value to validate or transform.
        experiment_id: Registered research experiment identifier.
        variant_id: Registered variant identifier.
        domain: Domain used as the default component classification.

    Returns:
        Result produced by _variant.
    """
    row = _mapping(value, f"experiments.{experiment_id}.variants.{variant_id}")
    config_raw = row.get("config")
    config = (
        None
        if config_raw is None
        else _relative_repo_path(
            config_raw,
            f"experiments.{experiment_id}.variants.{variant_id}.config",
        )
    )
    architecture_raw = row.get("architecture")
    architecture = (
        None
        if architecture_raw is None
        else _string(
            architecture_raw,
            f"experiments.{experiment_id}.variants.{variant_id}.architecture",
        )
    )
    authorization_raw = row.get("authorization")
    authorization = (
        None
        if authorization_raw is None
        else _string(
            authorization_raw,
            f"experiments.{experiment_id}.variants.{variant_id}.authorization",
        )
    )
    overrides_raw = row.get("overrides", [])
    if not isinstance(overrides_raw, list) or any(
        not isinstance(item, str) or not item.strip() for item in overrides_raw
    ):
        raise ValueError(
            f"experiments.{experiment_id}.variants.{variant_id}.overrides "
            "must be a list of non-empty strings"
        )
    command_raw = row.get("command", [])
    artifact_roots_raw = row.get("artifact_roots", [])
    depends_on_raw = row.get("depends_on", [])
    for label, raw in (
        ("command", command_raw),
        ("artifact_roots", artifact_roots_raw),
        ("depends_on", depends_on_raw),
    ):
        if not isinstance(raw, list) or any(
            not isinstance(item, str) or not item.strip() for item in raw
        ):
            raise ValueError(
                f"experiments.{experiment_id}.variants.{variant_id}.{label} "
                "must be a list of non-empty strings"
            )
    return VariantSpec(
        variant_id=variant_id,
        config=config,
        architecture=architecture,
        role=_string(
            row.get("role", "treatment"),
            f"experiments.{experiment_id}.variants.{variant_id}.role",
        ),
        authorization=authorization,
        overrides=tuple(item.strip() for item in overrides_raw),
        command=tuple(item.strip() for item in command_raw),
        artifact_roots=tuple(item.strip() for item in artifact_roots_raw),
        depends_on=tuple(item.strip() for item in depends_on_raw),
        component=_string(
            row.get("component", domain),
            f"experiments.{experiment_id}.variants.{variant_id}.component",
        ),
    )


def _execution(value: Any, *, experiment_id: str) -> ExecutionSpec:
    """Build one validated execution specification.

    Args:
        value: Value to validate or transform.
        experiment_id: Registered research experiment identifier.

    Returns:
        Result produced by _execution.
    """
    row = _mapping(value, f"experiments.{experiment_id}.execution")
    seeds_raw = row.get("seeds", [])
    if not isinstance(seeds_raw, list):
        raise ValueError(f"experiments.{experiment_id}.execution.seeds must be a list")
    seeds = tuple(
        _integer(item, f"experiments.{experiment_id}.execution.seeds", minimum=0)
        for item in seeds_raw
    )
    if len(seeds) != len(set(seeds)):
        raise ValueError(f"experiments.{experiment_id}.execution.seeds must be unique")
    resource_raw = row.get("resource_lock")
    resource_lock = (
        None
        if resource_raw is None
        else _string(resource_raw, f"experiments.{experiment_id}.execution.resource_lock")
    )
    return ExecutionSpec(
        kind=_string(row.get("kind"), f"experiments.{experiment_id}.execution.kind"),
        seeds=seeds,
        walk_forward_splits=_integer(
            row.get("walk_forward_splits", 0),
            f"experiments.{experiment_id}.execution.walk_forward_splits",
        ),
        purge_bars=_integer(
            row.get("purge_bars", 0),
            f"experiments.{experiment_id}.execution.purge_bars",
        ),
        embargo_bars=_integer(
            row.get("embargo_bars", 0),
            f"experiments.{experiment_id}.execution.embargo_bars",
        ),
        additional_timesteps=_integer(
            row.get("additional_timesteps", 0),
            f"experiments.{experiment_id}.execution.additional_timesteps",
        ),
        resource_lock=resource_lock,
    )


def load_research_catalog(path: str | Path = DEFAULT_CATALOG) -> ResearchCatalog:
    """Load and validate the active research catalog.

    Args:
        path: Path to the input or output artifact.

    Returns:
        Result produced by load_research_catalog.
    """
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = ROOT / resolved
    raw = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    root = _mapping(raw, "research catalog")
    schema = _integer(root.get("schema_version"), "schema_version", minimum=1)
    if schema != 1:
        raise ValueError(f"unsupported research catalog schema: {schema}")
    protocol = _relative_repo_path(root.get("protocol"), "protocol")
    domains_raw = _mapping(root.get("domains"), "domains")
    domains = {
        domain_id: _string(description, f"domains.{domain_id}")
        for domain_id, description in domains_raw.items()
    }
    if not domains:
        raise ValueError("research catalog requires at least one domain")
    library: dict[str, dict[str, Any]] = {}
    for component_id, component_raw in _mapping(root.get("components", {}), "components").items():
        component = _mapping(component_raw, f"components.{component_id}")
        definitions = _mapping(component.get("variants"), f"components.{component_id}.variants")
        for implementation_id, definition in definitions.items():
            key = f"{component_id}.{implementation_id}"
            template = _mapping(definition, f"components.{key}")
            if "use" in template or (
                "component" in template and template["component"] != component_id
            ):
                raise ValueError(f"invalid component implementation: {key}")
            library[key] = {**template, "component": component_id}
    experiments_raw = _mapping(root.get("experiments"), "experiments")
    experiments: list[ExperimentSpec] = []
    for experiment_id, raw_experiment in experiments_raw.items():
        row = _mapping(raw_experiment, f"experiments.{experiment_id}")
        domain = _string(row.get("domain"), f"experiments.{experiment_id}.domain")
        if domain not in domains:
            raise ValueError(f"experiment {experiment_id!r} references unknown domain {domain!r}")
        variants_raw = _mapping(row.get("variants"), f"experiments.{experiment_id}.variants")
        variants_list: list[VariantSpec] = []
        for variant_id, value in variants_raw.items():
            specification = _mapping(value, f"experiments.{experiment_id}.variants.{variant_id}")
            reference = specification.pop("use", None)
            if reference is not None:
                key = _string(reference, f"experiments.{experiment_id}.variants.{variant_id}.use")
                if key not in library:
                    raise ValueError(f"{experiment_id}/{variant_id} uses unknown component {key!r}")
                if (
                    "component" in specification
                    and specification["component"] != library[key]["component"]
                ):
                    raise ValueError(f"{experiment_id}/{variant_id} changes component identity")
                specification = {**library[key], **specification}
            variants_list.append(
                _variant(
                    specification, experiment_id=experiment_id, variant_id=variant_id, domain=domain
                )
            )
        variants = tuple(variants_list)
        if not variants:
            raise ValueError(f"experiment {experiment_id!r} requires at least one variant")
        identifiers = {variant.variant_id for variant in variants}
        for variant in variants:
            missing = set(variant.depends_on) - identifiers
            if missing:
                raise ValueError(
                    f"{experiment_id}/{variant.variant_id} has unknown dependencies: {sorted(missing)}"
                )
            if variant.variant_id in variant.depends_on:
                raise ValueError(f"{experiment_id}/{variant.variant_id} depends on itself")
        assemblies: dict[str, tuple[str, ...]] = {}
        for assembly_id, raw_members in _mapping(
            row.get("assemblies", {}), f"experiments.{experiment_id}.assemblies"
        ).items():
            if (
                not isinstance(raw_members, list)
                or not raw_members
                or any(not isinstance(member, str) or not member.strip() for member in raw_members)
                or len(set(raw_members)) != len(raw_members)
            ):
                raise ValueError(f"{experiment_id}/{assembly_id} requires distinct variant names")
            missing_members = set(raw_members) - identifiers
            if missing_members:
                raise ValueError(
                    f"{experiment_id}/{assembly_id} has unknown variants {sorted(missing_members)}"
                )
            members = tuple(raw_members)
            chosen = tuple(variant for variant in variants if variant.variant_id in members)
            if len({variant.component for variant in chosen}) != len(chosen):
                raise ValueError(
                    f"{experiment_id}/{assembly_id} selects multiple variants of a component"
                )
            for variant in chosen:
                if set(variant.depends_on) - set(members):
                    raise ValueError(f"{experiment_id}/{assembly_id} omits a required dependency")
            assemblies[assembly_id] = members
        experiments.append(
            ExperimentSpec(
                experiment_id=experiment_id,
                domain=domain,
                summary=_string(row.get("summary"), f"experiments.{experiment_id}.summary"),
                selection_role=_string(
                    row.get("selection_role"),
                    f"experiments.{experiment_id}.selection_role",
                ),
                variants=variants,
                assemblies=assemblies,
                execution=_execution(row.get("execution"), experiment_id=experiment_id),
            )
        )
    if not experiments:
        raise ValueError("research catalog requires at least one experiment")
    return ResearchCatalog(
        schema_version=schema,
        protocol=protocol,
        domains=domains,
        experiments=tuple(experiments),
    )


__all__ = [
    "DEFAULT_CATALOG",
    "ExecutionSpec",
    "ExperimentSpec",
    "ResearchCatalog",
    "VariantSpec",
    "load_research_catalog",
]
