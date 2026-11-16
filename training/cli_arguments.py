"""Training command arguments without importing run-time configuration."""

from __future__ import annotations

import argparse


def build_train_parser() -> argparse.ArgumentParser:
    """Build the stable training command parser without loading run resources.

    Returns:
        The parser used by both training entrypoints.
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
        help="Registered learning-quality variant",
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
        help="Strategy variant: baseline, PO3/IFVG, or distribution.",
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
    return parser
