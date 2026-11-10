"""Train PPO/SAC agent on structure-aware trading environment.

Trains a PPO or SAC policy to learn entry/exit timing and risk/reward parameter selection
using swing structure and SMT divergence features.

Usage
-----
    cd Quantitative-RL-Trading-System
    uv run python -m training.runner.training --seed 42
    uv run python -m training.runner.training --mvp --seed 42  # MVP: first 30 days
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from evaluation.reporting.run_manifest import file_sha256
from training.configuration.survival_gate import build_survival_gate
from training.runner.configuration_stage import _prepare_training_configuration
from training.runner.reporting_runtime import finalize_training_run
from training.runner.seed_runtime import SeedRunContext, run_seed_training
from training.runner.setup_runtime import prepare_training_run
from training.runner.survival_campaign import validate_survival_campaign
from training.runner.walk_forward_validation import run_walk_forward_validation

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def _verify_completed_campaign_seed(seed_dir: Path) -> None:
    """Fail closed unless a previously completed seed has its exact artifacts.

    Args:
        seed_dir: Directory containing the completed seed run artifacts.
    """
    manifest_path = seed_dir / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    checkpoint_path = seed_dir / str(manifest["artifact_paths"]["checkpoint"])
    if (
        not checkpoint_path.is_file()
        or file_sha256(checkpoint_path) != manifest["checkpoint"]["sha256"]
    ):
        raise ValueError("completed campaign seed checkpoint is missing or changed")
    for name in ("train_equity_gate.json", "train_path_outcome.json"):
        if not (seed_dir / name).is_file():
            raise ValueError(f"completed campaign seed artifact is missing: {name}")


def main() -> None:
    """Compose training setup, per-seed execution, reporting, and optional walk-forward validation."""
    args = None
    if any(arg.startswith("--survival-campaign-") for arg in sys.argv[1:]):
        from training.configuration.cli import parse_train_args

        args = parse_train_args()
    campaign_phase = args.survival_campaign_phase if args is not None else None
    if campaign_phase is not None:
        assert args is not None
    if args is not None and campaign_phase == "train_seed" and args.resume_checkpoint is None:
        seed_checkpoint = (
            Path(args.survival_campaign_dir).expanduser().resolve()
            / "seeds"
            / f"seed{args.survival_campaign_seed}"
            / "model"
            / "ppo_latest.zip"
        )
        if seed_checkpoint.is_file():
            args.resume_checkpoint = str(seed_checkpoint)
    if campaign_phase == "finalize":
        configuration = _prepare_training_configuration(args)
        args = configuration.args
        cfg = configuration.cfg
        run_dir = Path(args.survival_campaign_dir).expanduser().resolve()
        seeds = [int(seed) for seed in (args.seeds or [args.seed])]
        if not args.walk_forward or len(seeds) < 6 or len(set(seeds)) != len(seeds):
            raise SystemExit(
                "survival campaign finalization requires the complete seed/fold request"
            )
        validate_survival_campaign(run_dir=run_dir, cfg=cfg, args=args, create=False)
        build_survival_gate(
            cfg=cfg,
            args=args,
            run_dir=run_dir,
            seed_results=[{"seed": seed} for seed in seeds],
            seeds=seeds,
        )
        log.info("Survival campaign gate written: %s", run_dir / "survival_phase_gate.json")
        return

    prep = prepare_training_run() if args is None else prepare_training_run(args)
    config = prep.configuration
    data = prep.data
    assets = prep.run_assets
    seed_context = SeedRunContext(preparation=prep)
    survival_qualification = str(config.cfg.env.get("reward_mode", "dsr")).lower() == "survival"
    seed_results: list[dict[str, Any]] = []

    if campaign_phase is not None:
        campaign_args = args
        if campaign_args is None:
            raise RuntimeError("survival campaign arguments were not parsed")
        if not survival_qualification or not campaign_args.walk_forward or campaign_args.mvp:
            raise SystemExit("bounded campaign phases require uncapped survival qualification")
        seeds = list(assets.seeds)
        campaign_seed = int(campaign_args.survival_campaign_seed)
        if len(seeds) < 6 or len(set(seeds)) != len(seeds) or campaign_seed not in seeds:
            raise SystemExit("bounded campaign phase requires the configured unique seed set")
        seed_dir = assets.run_dir / "seeds" / f"seed{campaign_seed}"
        if campaign_phase == "train_seed":
            if (seed_dir / "run_manifest.json").exists():
                _verify_completed_campaign_seed(seed_dir)
                log.info(
                    "Seed %d artifacts are already complete; skipping duplicate training",
                    campaign_seed,
                )
                return
            latest_checkpoint = seed_dir / "model" / "ppo_latest.zip"
            if latest_checkpoint.is_file() and not campaign_args.resume_checkpoint:
                raise SystemExit(
                    "campaign seed has an incomplete checkpoint; resume explicitly with "
                    f"--resume-checkpoint {latest_checkpoint}"
                )
            if (
                campaign_args.resume_checkpoint
                and Path(campaign_args.resume_checkpoint).expanduser().resolve().parent
                != (seed_dir / "model").resolve()
            ):
                raise SystemExit("campaign resume checkpoint must belong to the selected seed")
            seed_results, _ = run_seed_training(seed_context, selected_seeds=[campaign_seed])
            return
        if campaign_phase == "walk_forward_fold":
            if not (seed_dir / "run_manifest.json").is_file():
                raise SystemExit(f"seed {campaign_seed} must finish training before walk-forward")
            run_walk_forward_validation(
                args=config.args,
                timesteps=int(config.cfg.ppo.total_timesteps),
                train_bars=data.train_bars,
                train_sec=data.train_sec,
                cfg=config.cfg,
                cache_dir=data.cache_dir,
                primary_sym=data.primary_sym,
                primary_ticks=data.primary_ticks,
                schedule_path=data.schedule_path,
                feature_columns=data.feature_columns,
                run_dir=seed_dir,
                env_vae=data.env_vae,
                pre_ny_by_date=data.pre_ny_by_date,
                device=config.device,
                vae_model=data.vae_model,
                seed=campaign_seed,
                only_fold=int(campaign_args.survival_campaign_fold),
            )
            return
        raise SystemExit(f"unsupported survival campaign phase: {campaign_phase}")

    try:
        seed_results, timesteps = run_seed_training(seed_context)
        finalize_training_run(
            cfg=config.cfg,
            args=config.args,
            is_multi_seed=assets.is_multi_seed,
            seed_results=seed_results,
            timesteps=int(timesteps),
            train_bar_count=assets.train_bar_count,
            test_bar_count=assets.test_bar_count,
            run_dir=assets.run_dir,
            feat_cache=data.feat_cache,
            feature_columns=data.feature_columns,
            seeds=assets.seeds,
        )
        for result in seed_results if survival_qualification else seed_results[-1:]:
            seed_dir = (
                assets.run_dir / "seeds" / f"seed{int(result['seed'])}"
                if assets.is_multi_seed
                else assets.run_dir
            )
            run_walk_forward_validation(
                args=config.args,
                timesteps=int(timesteps),
                train_bars=data.train_bars,
                train_sec=data.train_sec,
                cfg=config.cfg,
                cache_dir=data.cache_dir,
                primary_sym=data.primary_sym,
                primary_ticks=data.primary_ticks,
                schedule_path=data.schedule_path,
                feature_columns=data.feature_columns,
                run_dir=seed_dir,
                env_vae=data.env_vae,
                pre_ny_by_date=data.pre_ny_by_date,
                device=config.device,
                vae_model=data.vae_model,
                seed=int(result["seed"]),
            )
    except (Exception, SystemExit) as training_failure:
        if survival_qualification:
            try:
                build_survival_gate(
                    cfg=config.cfg,
                    args=config.args,
                    run_dir=assets.run_dir,
                    seed_results=seed_results,
                    seeds=assets.seeds,
                    forced_failures=[
                        "survival qualification execution failed: "
                        f"{str(training_failure) or 'SystemExit'}"
                    ],
                )
            except (Exception, SystemExit) as gate_failure:
                log.error("Survival qualification failed closed: %s", gate_failure)
        raise

    if survival_qualification:
        build_survival_gate(
            cfg=config.cfg,
            args=config.args,
            run_dir=assets.run_dir,
            seed_results=seed_results,
            seeds=assets.seeds,
        )
    log.info("Training complete. Run directory: %s", assets.run_dir)


if __name__ == "__main__":
    main()
