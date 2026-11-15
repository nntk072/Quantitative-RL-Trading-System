"""Repository paths shared by experiment run workflow services."""

from configuration.paths import repository_root

ROOT = repository_root(__file__)
DEFAULT_VARIANTS = ROOT / "config" / "experiment_runs" / "variant_list.txt"
