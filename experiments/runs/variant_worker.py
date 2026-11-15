"""Resolve and execute one registered training variant in a worker process."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from artifacts.atomic import write_json_atomic
from training.configuration.variant_resolution import resolve_variant, train_args

ROOT = Path(__file__).resolve().parents[2]


def _values(raw: str) -> list[str]:
    """Split comma- or whitespace-separated worker values.

    Args:
        raw: Environment variable containing one or more values.

    Returns:
        Non-empty values in their input order.
    """
    return [value for value in raw.replace(",", " ").split() if value]


def _config_overrides(raw: str) -> list[str]:
    """Return non-empty configuration override lines.

    Args:
        raw: Newline-delimited configuration overrides.

    Returns:
        Trimmed non-empty override strings in their input order.
    """
    return [line.strip() for line in raw.splitlines() if line.strip()]


def _worker_command(seed: int, output: Path, resolved: dict[str, Any]) -> list[str]:
    """Build the training command for one resolved variant and seed.

    Args:
        seed: Training seed selected for the worker.
        output: Directory receiving the run's artifacts.
        resolved: Validated variant settings returned by the resolver.

    Returns:
        Command and arguments for one training process.
    """
    args = train_args(resolved, seed)
    resume = os.getenv("RESUME_CHECKPOINT")
    command = [os.getenv("PYTHON", sys.executable), "-u", "-m", "training.runner.training"]
    if resume:
        command.extend(["--resume-checkpoint", resume])
    command.extend(args)
    command.extend(["--out", str(output)])

    if os.getenv("QUANT_RL_FULL_REPORTS") == "1":
        command.extend(
            ["output.report_profile=full", "output.max_order_charts=200", "output.save_html=true"]
        )
    elif os.getenv("QUANT_RL_FAST_REPORTS") == "1":
        command.extend(
            [
                "output.report_profile=experiment_run_fast",
                "output.max_order_charts=0",
                "output.save_html=false",
            ]
        )

    data_source = os.getenv("QUANT_RL_DATA_SOURCE")
    if data_source:
        if data_source not in {"frames", "bundle"}:
            raise ValueError(f"invalid QUANT_RL_DATA_SOURCE: {data_source}")
        command.append(f"env.data_source={data_source}")

    selection = os.getenv("QUANT_RL_ALLOW_OOS_SELECTION", "0")
    if selection == "1":
        command.append("--allow-locked-oos-for-selection")
    elif selection != "0":
        raise ValueError("QUANT_RL_ALLOW_OOS_SELECTION must be 0 or 1")
    return command


def main() -> int:
    """Resolve worker settings, run selected seeds, and record completion.

    Returns:
        Zero when all selected runs succeed, otherwise the last failure code.
    """
    variant = os.getenv("VARIANT", "").strip()
    if not variant:
        raise ValueError("VARIANT is required; select a name from config/experiments.yaml")

    vae_path = os.getenv("VAE_PATH") or None
    step_override = os.getenv("STEPS")
    seeds_override = os.getenv("SEEDS")
    resolved = resolve_variant(
        variant,
        steps=int(step_override) if step_override else None,
        seeds=[int(seed) for seed in _values(seeds_override)] if seeds_override else None,
        vae_path=vae_path,
        config_overrides=_config_overrides(os.getenv("QUANT_RL_CONFIG_OVERRIDES", "")),
    )
    seed_override = os.getenv("SEED")
    seeds = [int(seed_override)] if seed_override else resolved["seeds"]
    output_root = Path(os.getenv("OUT_DIR", ROOT / "outputs" / "gpu_matrix"))
    if not output_root.is_absolute():
        output_root = ROOT / output_root
    log_root = Path(os.getenv("LOG_DIR", output_root / "logs"))
    if not log_root.is_absolute():
        log_root = ROOT / log_root
    output_root.mkdir(parents=True, exist_ok=True)
    log_root.mkdir(parents=True, exist_ok=True)

    pid_file = os.getenv("EXPERIMENT_RUN_WORKER_PID_FILE")
    if pid_file:
        pid_path = Path(pid_file)
        pid_path.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(
            pid_path, {"hostname": os.uname().nodename.split(".")[0], "pid": os.getpid()}
        )

    overall = 0
    for seed in seeds:
        tag = f"{variant}__seed{seed}"
        run_output = output_root / tag
        log_path = log_root / f"{tag}.log"
        done_marker = output_root / f"{tag}.done"
        failed_marker = output_root / f"{tag}.failed"
        run_output.mkdir(parents=True, exist_ok=True)
        write_json_atomic(
            run_output / "resolved_config.json",
            {**resolved, "seed": seed, "train_args": train_args(resolved, seed)},
        )
        command = _worker_command(seed, run_output, resolved)
        print(
            "=== "
            f"variant={variant} algo={resolved['algo']} arch={resolved['arch']} "
            f"strategy={resolved['strategy']} reward={resolved['reward_mode']} "
            f"features={resolved['feature_profile']} steps={resolved['steps']} seed={seed} ===",
            flush=True,
        )
        if os.getenv("DRY_RUN") == "1":
            print("DRY_RUN " + tag + ": " + " ".join(command), flush=True)
            continue
        if done_marker.is_file():
            print(f"SKIP {tag} (already done)", flush=True)
            continue

        failed_marker.unlink(missing_ok=True)
        environment = dict(os.environ)
        environment["CUDA_VISIBLE_DEVICES"] = os.getenv("GPU_ID", "0")
        environment.setdefault("QUANT_RL_MAX_N_ENVS", "64")
        environment["PYTHONUNBUFFERED"] = "1"
        with log_path.open("a", encoding="utf-8") as log:
            process = subprocess.run(
                command,
                cwd=ROOT,
                env=environment,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=False,
            )
        if process.returncode == 0:
            failed_marker.unlink(missing_ok=True)
            done_marker.touch()
        else:
            failed_marker.touch()
            overall = process.returncode or 1
        print(f"=== {tag} exit={process.returncode} ===", flush=True)
    return overall


if __name__ == "__main__":
    raise SystemExit(main())
