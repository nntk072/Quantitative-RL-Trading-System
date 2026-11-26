"""Full pre-2026 M1 window check for FEATURE-KERNELS (exactness and timing).

The window is the training window of the active config (data.split.train_start to
train_end, inclusive: 2024-12-30 to 2025-12-31). Rows dated on or after 2026-01-01 are
excluded by the date filter before parsing and are never converted into bars or
measured. The source is the full-period M1 export in the original checkout's data
directory, which is the only M1 source present.

The check requires bit-exact agreement (pandas check_exact=True) between the Python
reference and the native backend, and between the new Python path and the pre-change
HEAD copy. Timings are reported as medians over repeats after one warm-up call.

Usage:
  python full_pre2026_window_check.py --source CSV --head-dir DIR --out JSON [--repeats N]
Exit status is 0 only when every exactness check passes.
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import importlib
import json
import os
import platform
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

bench: Any = importlib.import_module("bench_feature_hotpaths")

TRAIN_START = "2024.12.30"
TRAIN_END = "2025.12.31"
CONFIGS: tuple[tuple[int, float], ...] = ((3, 0.8), (2, 0.0))


def load_window(source: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Parse the pre-2026 window with the repository's MT5 export loader."""
    from market_data.arrow_schemas import mt5_export_to_bars

    raw = pd.read_csv(source, sep="\t", dtype=str).rename(columns=lambda n: n.strip("<>"))
    window = raw[(raw["DATE"] >= TRAIN_START) & (raw["DATE"] <= TRAIN_END)].reset_index(drop=True)
    table, problems = mt5_export_to_bars(window, instrument_id="US100.cash", timeframe="M1")
    if problems:
        raise RuntimeError(f"window did not parse cleanly: {problems[:3]}")
    bars: pd.DataFrame = table.select(["event_time", "open", "high", "low", "close"]).to_pandas()
    bars.index = pd.DatetimeIndex(bars.pop("event_time"))
    if bars.index.max() >= pd.Timestamp("2026-01-01", tz=bars.index.tz):
        raise RuntimeError("window contains a 2026 bar; refusing")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    meta = {
        "source_file": str(source),
        "source_sha256": digest,
        "train_start": "2024-12-30",
        "train_end": "2025-12-31",
        "rows": int(len(bars)),
        "first_bar": str(bars.index.min()),
        "last_bar": str(bars.index.max()),
    }
    return bars, meta


def exact(a: pd.DataFrame, b: pd.DataFrame) -> dict[str, Any]:
    """Compare two frames with check_exact and report the outcome."""
    try:
        pd.testing.assert_frame_equal(a, b, check_exact=True)
    except AssertionError as err:
        return {"exact": False, "detail": str(err)[:800]}
    return {"exact": True, "detail": ""}


def main() -> int:
    """Run every exactness check and timing, then write one JSON record."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--head-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()

    from features.technical import structure as new_structure
    from features.technical import swings as sw
    from features.technical.native_kernels import load_qrl_native

    bench._load_head_modules(args.head_dir)
    head_st = bench.HEAD_MODULES["old_structure"]
    load_qrl_native()

    bars, meta = load_window(args.source)
    record: dict[str, Any] = {
        "schema": "qrl.feature_kernels.full_window.v1",
        "kind": "engineering_check_not_scientific_evidence",
        "window": meta,
        "host": platform.node(),
        "slurm": {
            k: os.environ.get(k)
            for k in (
                "SLURM_JOB_ID",
                "SLURM_JOB_PARTITION",
                "SLURM_CPUS_ON_NODE",
                "SLURM_MEM_PER_NODE",
            )
        },
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "native_module": str(importlib.import_module("qrl_native").__file__),
        "exact_checks": {},
        "timings": {},
        "configs": [],
    }

    for swing_period, atr_mult in CONFIGS:
        tag = f"left{swing_period}_atr{atr_mult}"
        pivots_ref = sw.detect_pivots_reference(bars, left=swing_period, right=swing_period)
        pivots = sw.detect_pivots(bars, left=swing_period, right=swing_period)
        record["exact_checks"][f"pivots_vectorized_eq_reference:{tag}"] = exact(pivots, pivots_ref)
        swings = sw.detect_swings(bars, pivots, atr_mult=atr_mult)
        py_ret = sw.retained_swing_levels(swings, bars, max_levels=8, backend="python")
        na_ret = sw.retained_swing_levels(swings, bars, max_levels=8, backend="native")
        record["exact_checks"][f"retained_native_eq_python:{tag}"] = exact(na_ret, py_ret)
        py_sl = new_structure.structure_levels(bars, swing_period=swing_period, atr_mult=atr_mult)
        na_sl = new_structure.structure_levels(
            bars, swing_period=swing_period, atr_mult=atr_mult, retained_backend="native"
        )
        record["exact_checks"][f"structure_levels_native_eq_python:{tag}"] = exact(na_sl, py_sl)
        head_sl = head_st.structure_levels(bars, swing_period=swing_period, atr_mult=atr_mult)
        record["exact_checks"][f"structure_levels_python_eq_head_before_change:{tag}"] = exact(
            py_sl, head_sl
        )
        record["configs"].append(
            {
                "tag": tag,
                "swing_period": swing_period,
                "atr_mult": atr_mult,
                "structure_levels_rows": int(len(py_sl)),
            }
        )

        timings: dict[str, tuple[Any, tuple[Any, ...], dict[str, Any]]] = {
            f"pivots_loop_reference:{tag}": (
                sw.detect_pivots_reference,
                (bars,),
                {"left": swing_period, "right": swing_period},
            ),
            f"pivots_vectorized:{tag}": (
                sw.detect_pivots,
                (bars,),
                {"left": swing_period, "right": swing_period},
            ),
            f"detect_swings_python:{tag}": (
                sw.detect_swings,
                (bars, pivots),
                {"atr_mult": atr_mult},
            ),
            f"retained_python:{tag}": (
                sw.retained_swing_levels,
                (swings, bars),
                {"max_levels": 8, "backend": "python"},
            ),
            f"retained_native:{tag}": (
                sw.retained_swing_levels,
                (swings, bars),
                {"max_levels": 8, "backend": "native"},
            ),
            f"structure_levels_python:{tag}": (
                new_structure.structure_levels,
                (bars,),
                {"swing_period": swing_period, "atr_mult": atr_mult},
            ),
            f"structure_levels_native:{tag}": (
                new_structure.structure_levels,
                (bars,),
                {"swing_period": swing_period, "atr_mult": atr_mult, "retained_backend": "native"},
            ),
            f"structure_levels_head_before_change:{tag}": (
                head_st.structure_levels,
                (bars,),
                {"swing_period": swing_period, "atr_mult": atr_mult},
            ),
        }
        for name, (fn, call_args, call_kwargs) in timings.items():
            record["timings"][name] = bench.time_call(
                functools.partial(fn, *call_args, **call_kwargs), args.repeats
            )
            print(f"{name} median={record['timings'][name]['median_s']:.4f}s", flush=True)

        native_call = record["timings"][f"structure_levels_native:{tag}"]["median_s"]
        swings_t = record["timings"][f"detect_swings_python:{tag}"]["median_s"]
        share = swings_t / native_call
        record.setdefault("derived", {})[tag] = {
            "detect_swings_share_of_native_structure_levels": share,
            "threshold": 0.25,
            "zigzag_port_warranted": bool(share > 0.25),
            "native_speedup_vs_python_structure_levels": record["timings"][
                f"structure_levels_python:{tag}"
            ]["median_s"]
            / native_call,
            "native_speedup_vs_head_structure_levels": record["timings"][
                f"structure_levels_head_before_change:{tag}"
            ]["median_s"]
            / native_call,
        }

    failed = [k for k, v in record["exact_checks"].items() if not v["exact"]]
    record["status"] = "passed" if not failed else "failed"
    record["failed_checks"] = failed
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"STATUS={record['status']} failed={failed}", flush=True)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
