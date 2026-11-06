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

import logging
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from training.configuration.survival_gate import build_survival_gate
from training.runner.reporting_runtime import finalize_training_run
from training.runner.seed_runtime import SeedRunContext, run_seed_training
from training.runner.setup_runtime import prepare_training_run
from training.runner.walk_forward_validation import run_walk_forward_validation

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def main() -> None:
    """Compose training setup, per-seed execution, reporting, and optional walk-forward validation."""
    prep = prepare_training_run()
    config = prep.configuration
    data = prep.data
    assets = prep.run_assets
    seed_context = SeedRunContext(preparation=prep)
    survival_qualification = str(config.cfg.env.get("reward_mode", "dsr")).lower() == "survival"
    seed_results: list[dict[str, Any]] = []

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
