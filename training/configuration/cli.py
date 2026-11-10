"""Training CLI parsing and resolved configuration loading."""

from __future__ import annotations

import argparse
import logging

from omegaconf import DictConfig

from configuration import apply_overrides, load_config
from training.configuration.strategy_overlays import (
    merge_strategy_config,
    strategy_overlay_path,
)
from training.configuration.variant_resolution import resolve_variant

log = logging.getLogger(__name__)


def parse_train_args() -> argparse.Namespace:
    """Parse CLI arguments for the RL training entrypoint.

    Returns:
        Result of parse CLI arguments for the RL training entrypoint.
    """
    parser = argparse.ArgumentParser(description="Train PPO/SAC on structure-aware trading.")
    parser.add_argument(
        "--config",
        default=None,
        help="Base config YAML (default: config/base/default.yaml). "
        "Lets this entrypoint load config/features_*_mtf.yaml variant configs.",
    )
    parser.add_argument("overrides", nargs="*", help="Config overrides")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument(
        "--seeds",
        nargs="+",
        type=int,
        default=None,
        help="Override seed list (default: single --seed)",
    )
    parser.add_argument(
        "--variant",
        default=None,
        help="Variant name from config/experiments.yaml (overrides --strategy if set in variant)",
    )
    parser.add_argument(
        "--quality-variant",
        default=None,
        help="New staged variant from config/quality_experiments.yaml",
    )
    parser.add_argument("--mvp", action="store_true", help="MVP mode: first 30 days only")
    parser.add_argument("--force", action="store_true", help="Force data pipeline rerun")
    parser.add_argument("--out", default="outputs", help="Base output directory")
    parser.add_argument(
        "--resume-checkpoint",
        default=None,
        help="Continue PPO or SAC optimizer/policy state from an intact checkpoint",
    )
    parser.add_argument(
        "--allow-legacy-observation-schema",
        action="store_true",
        help="Explicitly resume an unversioned account-state-v1 checkpoint",
    )
    parser.add_argument("--algo", choices=["ppo", "sac"], default=None, help="RL algorithm")
    parser.add_argument(
        "--arch",
        choices=[
            "tcn",
            "tcn_regime",
            "lite_tcn",
            "gru",
            "transformer",
            "mtf",
            "mtf_empty_stream_masked_v1",
            "mtf_reasoning",
            "mtf_shared_tcn_reasoning",
            "mtf_m1_tcn_htf_lite_reasoning",
            "mtf_m1_tcn_htf_snapshot_reasoning",
        ],
        default=None,
        help="Encoder architecture",
    )
    parser.add_argument(
        "--reward",
        choices=["dsr", "sweep"],
        default="dsr",
        help=(
            "Legacy sweep-shaping selector; the economic objective is configured "
            "separately with env.reward_mode"
        ),
    )
    parser.add_argument(
        "--strategy",
        choices=["baseline", "po3_ifvg", "distribution"],
        default="baseline",
        help="RL strategy variant (Agent.md: Idea 1 = po3_ifvg, Idea 2 = distribution, Idea 3 = baseline).",
    )
    parser.add_argument(
        "--use-vae",
        action="store_true",
        default=None,
        help="Condition the policy on a frozen VAE narrative latent (requires --vae-path)",
    )
    parser.add_argument(
        "--vae-path",
        default=None,
        help="Path to a trained VAE state_dict (.pth from qrl-train vae)",
    )
    parser.add_argument(
        "--vae-config",
        default="config/vae.yaml",
        help="VAE architecture YAML (must match the checkpoint)",
    )
    parser.add_argument(
        "--allow-locked-oos-for-selection",
        action="store_true",
        help="Rank on locked-OOS Sharpe. Only use if you knowingly tune on the holdout.",
    )
    parser.add_argument("--wandb", action="store_true", help="Log run metrics to Weights & Biases")
    parser.add_argument(
        "--walk-forward", action="store_true", help="Run purged walk-forward validation"
    )
    parser.add_argument("--wf-splits", type=int, default=5, help="Number of walk-forward folds")
    parser.add_argument("--purge-bars", type=int, default=60, help="Purge bars for walk-forward")
    parser.add_argument(
        "--embargo-bars", type=int, default=20, help="Embargo bars for walk-forward"
    )
    parser.add_argument(
        "--wf-steps",
        type=int,
        default=None,
        help="Timesteps per WF fold (default: reuse main timesteps)",
    )
    parser.add_argument(
        "--survival-campaign-dir",
        default=None,
        help="Stable artifact root for bounded survival qualification work units",
    )
    parser.add_argument(
        "--survival-campaign-phase",
        choices=("train_seed", "walk_forward_fold", "finalize"),
        default=None,
        help="Run one resumable survival qualification work unit",
    )
    parser.add_argument(
        "--survival-campaign-seed",
        type=int,
        default=None,
        help="Seed selected by a train_seed or walk_forward_fold campaign phase",
    )
    parser.add_argument(
        "--survival-campaign-fold",
        type=int,
        default=None,
        help="Fold selected by the walk_forward_fold campaign phase",
    )
    args = parser.parse_args()
    campaign_phase = args.survival_campaign_phase
    if (args.survival_campaign_dir is None) != (campaign_phase is None):
        parser.error("--survival-campaign-dir and --survival-campaign-phase must be used together")
    if campaign_phase in {"train_seed", "walk_forward_fold"}:
        if not args.seeds or len(args.seeds) < 6 or len(set(args.seeds)) != len(args.seeds):
            parser.error("bounded survival work requires the full set of unique --seeds")
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

    # Merge the selected strategy overlay exactly once. Baseline (Idea 3)
    # leaves cfg untouched.
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
        log.info("Applied staged RL quality variant: %s", quality_variant)

    return apply_overrides(cfg, args.overrides)
