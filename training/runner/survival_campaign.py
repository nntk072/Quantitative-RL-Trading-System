"""Identity checks for a bounded survival qualification campaign."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from artifacts.atomic import write_text_atomic
from configuration.paths import repository_root
from evaluation.reporting.run_manifest import source_state
from training.configuration.survival_gate import survival_config_identity

ROOT = repository_root(__file__)


def validate_survival_campaign(
    *,
    run_dir: Path,
    cfg: Any,
    args: Any,
    create: bool,
) -> dict[str, Any]:
    """Create or verify the immutable source and protocol identity for a campaign.

    Args:
        run_dir: Directory containing campaign identity metadata.
        cfg: Loaded configuration used by the campaign.
        args: Parsed arguments defining seeds and validation protocol.
        create: Whether a missing identity may be created.

    Returns:
        Validated campaign identity mapping.
    """
    current_source = source_state(ROOT)
    if not current_source.get("available") or current_source.get("dirty_files"):
        raise ValueError("survival campaign requires a clean, identifiable source tree")
    seeds = [int(seed) for seed in (args.seeds or [args.seed])]
    identity = {
        "source": current_source,
        "config_identity": survival_config_identity(cfg),
        "seeds": seeds,
        "algo": str(args.algo),
        "arch": str(args.arch),
        "strategy": str(args.strategy),
        "reward_selector": str(args.reward),
        "wf_splits": int(args.wf_splits),
        "purge_bars": int(args.purge_bars),
        "embargo_bars": int(args.embargo_bars),
        "training_timesteps": int(cfg.ppo.total_timesteps),
        "wf_steps": int(args.wf_steps or cfg.ppo.total_timesteps),
    }
    path = run_dir / "survival_campaign.json"
    if not path.is_file():
        if not create:
            raise FileNotFoundError(f"survival campaign identity is missing: {path}")
        write_text_atomic(
            path,
            json.dumps(
                {"schema_version": "survival-campaign-v1", "identity": identity},
                indent=2,
            ),
        )
        return identity
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"survival campaign identity is unreadable: {path}") from exc
    if (
        not isinstance(saved, dict)
        or saved.get("schema_version") != "survival-campaign-v1"
        or saved.get("identity") != identity
    ):
        raise ValueError("survival campaign source or protocol identity changed")
    return identity
