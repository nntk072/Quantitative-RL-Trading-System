"""Measure the feature hot paths on small inputs (FEATURE-KERNELS baseline).

This is an engineering benchmark, not scientific evidence. It reports wall-clock
timings of the current Python reference functions and of candidate kernels on
(a) the tracked US100 M1 example and (b) a seeded synthetic M1 random walk.
Usage: python bench_feature_hotpaths.py --sizes 2000 20000 --repeats 5 --out PATH
         [--head-dir DIR]  DIR holds HEAD copies of swings.py and structure.py (renamed
                           old_swings.py / old_structure.py, see the record) for before/after timing.
The native cases run only when qrl_native is importable; otherwise they are recorded as skipped.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import platform
import statistics
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[4]
EXAMPLE = REPO_ROOT / "data" / "examples" / "US100.cash_M1_202412300105_202501020334.csv"


def load_example() -> pd.DataFrame:
    """Load the tracked US100 M1 example as an OHLC frame with a DatetimeIndex."""
    from market_data.arrow_schemas import mt5_export_to_bars

    frame = pd.read_csv(EXAMPLE, sep="\t", dtype=str).rename(columns=lambda n: n.strip("<>"))
    table, problems = mt5_export_to_bars(frame, instrument_id="US100.cash", timeframe="M1")
    if problems:
        raise RuntimeError(f"example did not parse cleanly: {problems[:3]}")
    df: pd.DataFrame = table.select(["event_time", "open", "high", "low", "close"]).to_pandas()
    df.index = pd.DatetimeIndex(df.pop("event_time"))
    return df


def synthetic(n: int, seed: int = 20260126) -> pd.DataFrame:
    """Build a seeded synthetic M1 OHLC random walk with plausible wicks."""
    rng = np.random.default_rng(seed)
    steps = rng.normal(0.0, 0.8, size=n)
    close = 18000.0 + np.cumsum(steps)
    open_ = np.concatenate([[close[0]], close[:-1]])
    wick = np.abs(rng.normal(0.0, 1.2, size=n))
    high = np.maximum(open_, close) + wick
    low = np.minimum(open_, close) - wick
    idx = pd.date_range("2025-01-02 00:00", periods=n, freq="1min", tz="UTC")
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close}, index=idx)


def _resample_polars(bars: pd.DataFrame, every: str) -> pd.DataFrame:
    """Candidate: Polars group_by_dynamic OHLC resample, including pandas<->Polars conversion."""
    import polars as pl

    lf = pl.from_pandas(bars.reset_index(names="t")).lazy()
    out = (
        lf.group_by_dynamic("t", every=every, label="left", closed="left")
        .agg(
            pl.col("open").first(),
            pl.col("high").max(),
            pl.col("low").min(),
            pl.col("close").last(),
        )
        .collect()
    )
    return out.to_pandas()


def _rolling_polars(bars: pd.DataFrame, window: int) -> Any:
    """Candidate: Polars rolling mean and population std on the four OHLC columns."""
    import polars as pl

    frame = pl.from_pandas(bars[["open", "high", "low", "close"]])
    means = frame.select(pl.all().rolling_mean(window, min_samples=1))
    stds = frame.select(pl.all().rolling_std(window, min_samples=2, ddof=0))
    return means.to_pandas(), stds.to_pandas()


def time_call(fn: Callable[[], Any], repeats: int) -> dict[str, float]:
    """Time a zero-argument callable; the first call is a discarded warm-up."""
    fn()
    samples: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - start)
    return {
        "median_s": statistics.median(samples),
        "min_s": min(samples),
        "max_s": max(samples),
        "repeats": float(repeats),
    }


def _structure_chain(bars: pd.DataFrame) -> Any:
    """Run the M1 structure sequence used by structure_stage.append_structure_features."""
    from features.technical.structure import (
        classify_structure,
        detect_pivots,
        detect_swings,
        structure_levels,
        swing_features,
    )
    from features.technical.swings import swing_history

    structure = structure_levels(bars, swing_period=3, atr_mult=0.8)
    pivots = detect_pivots(bars, left=3, right=3)
    swings = detect_swings(bars, pivots, atr_mult=0.8)
    structure_class = classify_structure(swings)
    return (
        structure,
        swing_features(bars, swings, structure_class, obs_window=60),
        swing_history(swings, n=3),
    )


HEAD_MODULES: dict[str, Any] = {}


def _load_head_modules(head_dir: Path) -> None:
    """Load the pre-change swings and structure modules from a HEAD copy for before/after timing."""
    import importlib.util
    import sys

    for name, filename in (("old_swings", "old_swings.py"), ("old_structure", "old_structure.py")):
        spec = importlib.util.spec_from_file_location(name, head_dir / filename)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load {filename} from {head_dir}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        HEAD_MODULES[name] = module


def _native_module_path() -> str | None:
    try:
        module = importlib.import_module("qrl_native")
    except ImportError:
        return None
    return str(getattr(module, "__file__", "unknown"))


def _native_available() -> bool:
    try:
        importlib.import_module("qrl_native")
    except ImportError:
        return False
    return True


def build_cases(bars: pd.DataFrame) -> dict[str, Callable[[], Any]]:
    """Return the timed callables for one input frame."""
    from features.pipeline.normalization import rolling_zscore
    from features.technical import indicators as ind
    from features.technical.structure import detect_pivots, detect_swings, structure_levels
    from features.technical.swings import detect_pivots_reference, retained_swing_levels
    from market_data.transforms.resample import resample

    pivots = detect_pivots(bars, left=3, right=3)
    swings_m1 = detect_swings(bars, pivots, atr_mult=0.8)
    cases: dict[str, Callable[[], Any]] = {
        "pivots_loop_reference": lambda: detect_pivots_reference(bars, left=3, right=3),
        "pivots_numpy_windows": lambda: detect_pivots(bars, left=3, right=3),
        "swings_python_loop": lambda: detect_swings(bars, pivots, atr_mult=0.8),
        "resample_M5_pandas": lambda: resample(bars, "M5"),
        "resample_H1_pandas": lambda: resample(bars, "H1"),
        "resample_D1_pandas": lambda: resample(bars, "D1"),
        "resample_M5_polars_incl_conversion": lambda: _resample_polars(bars, "5m"),
        "rolling_mean_std_pandas_no_mask": lambda: (
            bars[["open", "high", "low", "close"]].rolling(252, min_periods=1).mean(),
            bars[["open", "high", "low", "close"]].rolling(252, min_periods=2).std(ddof=0),
        ),
        "rolling_mean_std_polars_incl_conversion": lambda: _rolling_polars(bars, 252),
        "ema_pandas_ewm": lambda: ind.ema(bars["close"], 20),
        "atr_pandas_ewm": lambda: ind.atr(bars, 14),
        "rsi_pandas_ewm": lambda: ind.rsi(bars["close"], 14),
        "bollinger_pandas_rolling": lambda: ind.bollinger(bars["close"], 20),
        "m1_structure_chain": lambda: _structure_chain(bars),
        "structure_levels_python_backend": lambda: structure_levels(
            bars, swing_period=3, atr_mult=0.8
        ),
        "retained_levels_python_backend": lambda: retained_swing_levels(
            swings_m1, bars, max_levels=8
        ),
        "rolling_zscore_legacy_masked": lambda: rolling_zscore(
            bars[["open", "high", "low", "close"]],
            window=252,
            train_mask=pd.Series(True, index=bars.index),
        ),
    }
    if _native_available():
        from features.technical.swings import retained_swing_levels as _retained

        cases["retained_levels_native_backend"] = lambda: _retained(
            swings_m1, bars, max_levels=8, backend="native"
        )
        cases["structure_levels_native_backend"] = lambda: structure_levels(
            bars, swing_period=3, atr_mult=0.8, retained_backend="native"
        )
    if HEAD_MODULES:
        old_sw = HEAD_MODULES["old_swings"]
        old_st = HEAD_MODULES["old_structure"]
        cases["structure_levels_head_before_change"] = lambda: old_st.structure_levels(
            bars, swing_period=3, atr_mult=0.8
        )
        cases["pivots_head_loop_before_change"] = lambda: old_sw.detect_pivots(
            bars, left=3, right=3
        )
    return cases


def main() -> None:
    """Run the benchmark and write one JSON record."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", type=int, nargs="+", default=[2000, 20000])
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--only", nargs="*", default=None)
    parser.add_argument("--head-dir", type=Path, default=None)
    args = parser.parse_args()
    if args.head_dir is not None:
        _load_head_modules(args.head_dir)

    inputs: dict[str, pd.DataFrame] = {"example_us100_m1": load_example()}
    for n in args.sizes:
        inputs[f"synthetic_m1_{n}"] = synthetic(n)

    results: list[dict[str, Any]] = []
    for name, bars in inputs.items():
        for case_name, fn in build_cases(bars).items():
            if args.only and case_name not in args.only:
                continue
            timing = time_call(fn, args.repeats)
            results.append({"input": name, "rows": len(bars), "case": case_name, **timing})
            print(
                f"{name:24s} rows={len(bars):7d} {case_name:30s} median={timing['median_s']:.6f}s"
            )

    record = {
        "schema": "qrl.feature_kernels.benchmark.v1",
        "kind": "engineering_benchmark_not_scientific_evidence",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "cpu_count": os.cpu_count(),
        "omp_num_threads": os.environ.get("OMP_NUM_THREADS"),
        "loadavg_at_end": list(os.getloadavg()),
        "native_module": _native_module_path(),
        "pandas": pd.__version__,
        "numpy": np.__version__,
        "example_sha_note": "tracked file data/examples/US100.cash_M1_202412300105_202501020334.csv",
        "results": results,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
