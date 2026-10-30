from __future__ import annotations

import re
from pathlib import Path

from features.pipeline.feature_cache_identity import FEATURE_CACHE_VERSION
from market_data.loading import BAR_CACHE_VERSION
from market_data.loading.ticks import TICK_CACHE_VERSION

ROOT = Path(__file__).resolve().parents[2]
ACTIVE_NAMING_ROOTS = (
    "configuration",
    "artifacts",
    "market_data",
    "features",
    "trading",
    "simulation",
    "models",
    "learning",
    "training",
    "evaluation",
    "experiments",
    "live",
    "integrations",
    "compute",
    "orchestra",
    "scripts",
    "tests",
    "tools",
    "config",
    "docs",
    ".github/workflows",
)
ACTIVE_FILE_SUFFIXES = {".py", ".sh", ".yaml", ".yml", ".txt", ".md", ".json"}
PHASE_ONLY_MARKER = re.compile(r"(?:^|_)(?:p\d+|wp\d*|phase[-_]?\d+)(?:_|\.|$)", re.IGNORECASE)

# These files are versioned experiment run identities with functional descriptions,
# not reusable source modules. Their identity is already consumed by evidence.
HISTORICAL_EXPERIMENT_RUN_IDENTITIES = {
    "config/experiment_runs/p6_entry_fsm_viability_seed50_train2025_20261021_scratch1.yaml",
    "config/experiment_runs/variant_list_p6_entry_fsm.txt",
    "docs/thesis/p1_checkpoint_full_split_budget_2026-10-16.json",
}
HISTORICAL_OUTPUT_ROOTS = ("docs/thesis/evidence/", "docs/research/")
GENERIC_FILENAMES = {
    "base.py",
    "common.py",
    "core.py",
    "helper.py",
    "helpers.py",
    "utils.py",
    "misc.py",
    "state.py",
    "types.py",
    "models.py",
    "pipeline.py",
    "builder.py",
    "loader.py",
    "new_report.py",
    "final2.yaml",
    "test_everything.py",
    "run_stuff.sh",
}
# The old encoder path may be imported while loading historical SB3 archives.
# New source imports the canonical sequence_encoder_components module.
GENERIC_FILENAME_EXCEPTIONS = {
    "models/encoders/core.py": (
        "saved checkpoint metadata references models.encoders.core.TCNEncoder"
    ),
}


def test_active_repository_files_use_functional_names() -> None:
    violations: list[str] = []
    for root_name in ACTIVE_NAMING_ROOTS:
        root = ROOT / root_name
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if (
                not path.is_file()
                or path.is_symlink()
                or path.suffix.lower() not in ACTIVE_FILE_SUFFIXES
            ):
                continue
            relative = path.relative_to(ROOT).as_posix()
            if relative.startswith(HISTORICAL_OUTPUT_ROOTS):
                continue
            if relative in HISTORICAL_EXPERIMENT_RUN_IDENTITIES:
                continue
            if PHASE_ONLY_MARKER.search(path.name):
                violations.append(relative)

    assert not violations, (
        "Active source, test, config, command, or documentation filenames use "
        "phase/work-package IDs as primary names; rename to the owned functionality "
        "or document a narrow identity "
        f"exception:\n{chr(10).join(sorted(violations))}"
    )


def test_test_module_names_describe_behavior_without_suite_suffixes() -> None:
    test_root = ROOT / "tests"
    violations = sorted(
        path.relative_to(ROOT).as_posix()
        for path in test_root.rglob("test_*.py")
        if path.stem.endswith("_unittest")
    )

    assert not violations, (
        "Test modules should describe the behavior they verify; the `_unittest` "
        "suffix repeats the suite location instead of adding behavior: "
        f"{chr(10).join(violations)}"
    )


def test_active_repository_files_avoid_generic_placeholder_filenames() -> None:
    violations: list[str] = []
    for root_name in ACTIVE_NAMING_ROOTS:
        root = ROOT / root_name
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if (
                not path.is_file()
                or path.is_symlink()
                or path.suffix.lower() not in ACTIVE_FILE_SUFFIXES
            ):
                continue
            relative = path.relative_to(ROOT).as_posix()
            if relative.startswith(HISTORICAL_OUTPUT_ROOTS):
                continue
            uses_generic_name = path.name in GENERIC_FILENAMES or path.stem.endswith("_common")
            if uses_generic_name and relative not in GENERIC_FILENAME_EXCEPTIONS:
                violations.append(relative)

    assert not violations, (
        "Active files use generic placeholder names; rename by responsibility "
        "or add a narrowly justified compatibility exception: "
        f"{chr(10).join(sorted(violations))}"
    )
    assert all(reason.strip() for reason in GENERIC_FILENAME_EXCEPTIONS.values())


def test_operational_docs_match_live_market_cache_versions() -> None:
    config_doc = (ROOT / "docs" / "config.md").read_text(encoding="utf-8")
    architecture_map = (ROOT / ".agents" / "architecture.md").read_text(encoding="utf-8")

    assert (
        f"| `BAR_CACHE_VERSION` | `market_data/loading/market_data_ingestion.py` | `{BAR_CACHE_VERSION}` |"
        in config_doc
    )
    assert (
        f"| `FEATURE_CACHE_VERSION` | `features/pipeline/feature_cache_identity.py` | "
        f"`{FEATURE_CACHE_VERSION}` |" in config_doc
    )
    assert (
        f"| `FEATURE_CACHE_VERSION` | `features/pipeline/feature_cache_identity.py` | "
        f"`{FEATURE_CACHE_VERSION}` |" in architecture_map
    )
    assert (
        f"| `BAR_CACHE_VERSION` | `market_data/loading/market_data_ingestion.py` | "
        f"`{BAR_CACHE_VERSION}` |" in architecture_map
    )
    assert (
        f"| `TICK_CACHE_VERSION` | `market_data/loading/ticks.py` | "
        f"`{TICK_CACHE_VERSION}` |" in config_doc
    )
    assert (
        f"| `TICK_CACHE_VERSION` | `market_data/loading/ticks.py` | "
        f"`{TICK_CACHE_VERSION}` |" in architecture_map
    )
