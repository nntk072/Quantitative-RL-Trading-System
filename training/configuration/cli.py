"""Training CLI parsing and resolved configuration loading."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import subprocess
from datetime import date
from pathlib import Path

from omegaconf import DictConfig, OmegaConf

from configuration import apply_overrides, load_config
from training.cli_arguments import build_train_parser
from training.configuration.research_protocol import (
    EXPECTED_EXPOSED,
    EXPECTED_SEEDS,
    load_research_protocol,
)
from training.configuration.strategy_overlays import (
    merge_strategy_config,
    strategy_overlay_path,
)
from training.configuration.variant_resolution import resolve_variant

log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[2]


def _validate_confirmatory_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    """Fail closed unless a confirmatory launch matches its registered protocol arm.

    Args:
        parser: Parser used to report invalid launch arguments.
        args: Parsed arguments for the requested training launch.
    """
    if not args.confirmatory:
        if (
            args.confirmatory_arm is not None
            or args.expected_config_sha256 is not None
            or args.expected_resolved_config_sha256 is not None
            or args.expected_source_commit is not None
        ):
            parser.error("confirmatory arm and config hash require --confirmatory")
        return

    if tuple(args.seeds or ()) != EXPECTED_SEEDS:
        parser.error("confirmatory work requires protocol seeds 42..47 in order")
    if (
        args.config is None
        or args.confirmatory_arm is None
        or args.expected_config_sha256 is None
        or args.expected_resolved_config_sha256 is None
        or args.expected_source_commit is None
        or args.variant is not None
        or args.quality_variant is not None
        or args.overrides
        or args.mvp
        or args.allow_locked_oos_for_selection
        or args.use_vae
        or args.algo != "ppo"
        or args.reward != "dsr"
        or args.strategy != "baseline"
        or not args.walk_forward
    ):
        parser.error("confirmatory launch requires a frozen registered arm without overrides")

    protocol = load_research_protocol(ROOT / "config/research/prospective_research_protocol.yaml")
    policy = protocol["policy"]
    arm_configs = {
        "q0_control": policy["control_config"],
        "q0_canonical": policy["canonical_survival_config"],
        "q0_price_geometry": policy["price_geometry_config"],
        "representation_a": policy["gate_ii_ablation_configs"]["A"],
        "representation_b": policy["gate_ii_ablation_configs"]["B"],
        "representation_c": policy["gate_ii_ablation_configs"]["C"],
    }
    expected_config = (ROOT / arm_configs[args.confirmatory_arm]).resolve()
    supplied_config = Path(args.config).expanduser()
    supplied_config = (
        supplied_config if supplied_config.is_absolute() else ROOT / supplied_config
    ).resolve()
    if supplied_config != expected_config:
        parser.error("confirmatory arm config does not match the registered protocol config")
    if hashlib.sha256(expected_config.read_bytes()).hexdigest() != args.expected_config_sha256:
        parser.error("confirmatory config SHA-256 differs from the frozen launch plan")
    current_source = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    dirty_source = subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=ROOT, text=True
    ).strip()
    if current_source != args.expected_source_commit or dirty_source:
        parser.error("confirmatory work requires the frozen, clean source commit")

    walk_forward = protocol["replication"]["walk_forward"]
    config = load_config(config_path=expected_config)
    resolved_config = OmegaConf.to_container(config, resolve=True)
    resolved_json = json.dumps(resolved_config, sort_keys=True, separators=(",", ":"), default=str)
    if (
        hashlib.sha256(resolved_json.encode("utf-8")).hexdigest()
        != args.expected_resolved_config_sha256
    ):
        parser.error("confirmatory resolved config SHA-256 differs from the frozen launch plan")
    if (
        args.arch != str(config.agent.arch)
        or args.wf_splits != int(walk_forward["splits"])
        or args.purge_bars != int(walk_forward["purge_bars"])
        or args.embargo_bars != int(walk_forward["embargo_bars"])
        or (args.wf_steps is not None and args.wf_steps != int(config.ppo.total_timesteps))
    ):
        parser.error("confirmatory architecture or walk-forward budget differs from protocol")


def parse_train_args() -> argparse.Namespace:
    """Parse CLI arguments for the RL training entrypoint.

    Returns:
        Result of parse CLI arguments for the RL training entrypoint.
    """
    parser = build_train_parser()
    args = parser.parse_args()
    _validate_confirmatory_args(parser, args)
    campaign_phase = args.survival_campaign_phase
    if (args.survival_campaign_dir is None) != (campaign_phase is None):
        parser.error("--survival-campaign-dir and --survival-campaign-phase must be used together")
    if campaign_phase is not None:
        if tuple(args.seeds or ()) != EXPECTED_SEEDS:
            parser.error("bounded confirmatory work requires protocol seeds 42..47 in order")
    if campaign_phase in {"train_seed", "walk_forward_fold"}:
        if args.survival_campaign_seed is None:
            parser.error(f"{campaign_phase} requires --survival-campaign-seed")
    elif args.survival_campaign_seed is not None:
        parser.error("--survival-campaign-seed is only valid for a seed or fold phase")
    if campaign_phase == "walk_forward_fold":
        if not args.walk_forward or args.wf_splits < 5:
            parser.error("walk_forward_fold requires at least five configured walk-forward splits")
        if args.survival_campaign_fold is None:
            parser.error("walk_forward_fold requires --survival-campaign-fold")
    elif args.survival_campaign_fold is not None:
        parser.error("--survival-campaign-fold is only valid for walk_forward_fold")
    if args.variant:
        resolved = resolve_variant(args.variant, vae_path=args.vae_path)
        args.resolved_variant = resolved
        args.algo = args.algo or resolved["algo"]
        args.arch = args.arch or resolved["arch"]
        args.use_vae = resolved["use_vae"] if args.use_vae is None else args.use_vae
        args.strategy = resolved["strategy"]
    else:
        args.algo = args.algo or "ppo"
        args.use_vae = bool(args.use_vae)
    return args


def load_merged_config(args: argparse.Namespace) -> DictConfig:
    """Load base config and resolve one experiment variant if requested.

    CLI ``overrides`` apply *after* the declarative variant resolution so an
    explicit command-line override remains the final value.

    Args:
        args: Parsed command-line arguments for this operation.

    Returns:
        Result of load base config and resolve one experiment variant if requested.
    """
    resolved = getattr(args, "resolved_variant", None)
    if getattr(args, "variant", None) and resolved is None:
        resolved = resolve_variant(args.variant, vae_path=getattr(args, "vae_path", None))
        args.algo = getattr(args, "algo", None) or resolved["algo"]
        args.arch = getattr(args, "arch", None) or resolved["arch"]
        args.use_vae = (
            resolved["use_vae"] if getattr(args, "use_vae", None) is None else args.use_vae
        )
        args.strategy = resolved["strategy"]
    config_path = args.config
    if config_path is None and resolved is not None:
        config_path = resolved["base_config"]
    cfg = load_config(None, config_path=config_path)
    selected_strategy = str(resolved["strategy"] if resolved is not None else args.strategy)

    # Merge the selected strategy overlay exactly once. Baseline leaves cfg untouched.
    variant_path = strategy_overlay_path(selected_strategy)
    cfg = merge_strategy_config(cfg, selected_strategy)
    if variant_path is not None:
        log.info("Merged strategy config: %s", variant_path)

    # Use the same fully explicit override set as experiment run launchers. This
    # keeps reward, architecture-related flags, risk policy, and variant
    # config_overrides from acquiring a second runtime interpretation.
    if resolved is not None:
        cfg = apply_overrides(cfg, list(resolved["overrides"]))
        log.info(
            "Resolved variant: %s (strategy=%s)",
            args.variant,
            selected_strategy,
        )

    quality_variant = getattr(args, "quality_variant", None)
    if quality_variant:
        if getattr(args, "variant", None) or args.strategy != "baseline":
            raise ValueError(
                "--quality-variant cannot be combined with historical --variant or a "
                "non-baseline --strategy"
            )
        from training.configuration.quality import apply_quality_variant

        cfg = apply_quality_variant(cfg, str(quality_variant))
        log.info("Applied learning-quality variant: %s", quality_variant)

    cfg = apply_overrides(cfg, args.overrides)
    if getattr(args, "allow_locked_oos_for_selection", False):
        split = cfg.data.split
        train_start_value = split.get("train_start")
        train_end_value = split.get("train_end")
        test_start_value = split.get("test_start")
        test_data_end_value = cfg.data.datasets.testing.get("end_date")
        train_start = (
            date.fromisoformat(str(train_start_value)[:10])
            if train_start_value is not None
            else date.min
        )
        train_end = (
            date.fromisoformat(str(train_end_value)[:10])
            if train_end_value is not None
            else date.max
        )
        test_start = (
            date.fromisoformat(str(test_start_value)[:10])
            if test_start_value is not None
            else date.min
        )
        test_data_end = (
            date.fromisoformat(str(test_data_end_value)[:10])
            if test_data_end_value is not None
            else date.max
        )
        exposed_start, exposed_end = map(date.fromisoformat, EXPECTED_EXPOSED)
        train_overlaps = train_start <= exposed_end and train_end >= exposed_start
        test_overlaps = test_start <= exposed_end and test_data_end >= exposed_start
        if train_overlaps or test_overlaps:
            raise ValueError("the exposed report-only period cannot be used for selection")
    return cfg
