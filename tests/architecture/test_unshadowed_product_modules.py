from pathlib import Path

PRODUCT_PACKAGES = (
    "artifacts",
    "compute",
    "configuration",
    "decisioning",
    "evaluation",
    "experiments",
    "features",
    "integrations",
    "learning",
    "live",
    "market_data",
    "models",
    "research_tools",
    "simulation",
    "trading",
    "training",
)


def test_product_modules_are_not_shadowed_by_same_named_packages() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    shadowed = sorted(
        module.relative_to(repository_root).as_posix()
        for package in PRODUCT_PACKAGES
        for module in (repository_root / package).rglob("*.py")
        if (module.parent / module.stem).is_dir()
    )

    assert shadowed == []
