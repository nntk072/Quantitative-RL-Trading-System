"""Minimal reproducers for BASELINE-AUDIT defects (read-only; changes no source).

Run from the repository root with the x86 interpreter and PYTHONPATH set to the
checkout:

    PYTHONPATH=$PWD .venv-x86/bin/python \
        planning/native_modernization/baseline/reproducers/baseline_defect_reproducers.py

Each reproducer prints OBSERVED and EXPECTED values. The process exits 0 only when
every defect is observed exactly as recorded in defects.md, so a fixed defect makes
the script exit 1 and the record must then be updated.
"""

from __future__ import annotations

import os
import stat
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from artifacts.atomic import write_json_atomic
from artifacts.identity import artifact_id
from features.technical.structure import detect_session_levels
from market_data.splits.walkforward import purged_walk_forward
from market_data.transforms.align import join_symbols
from trading.execution.costs import CostModel

results: list[tuple[str, bool, str]] = []


def record(defect: str, reproduced: bool, detail: str) -> None:
    """Store one reproducer outcome for the final summary."""
    results.append((defect, reproduced, detail))
    print(f"[{defect}] reproduced={reproduced} {detail}")


def r_c1_invalid_direction_maps_to_bid() -> None:
    observed = CostModel().fill_price(99.5, 100.5, 0)
    record(
        "C1",
        observed == 99.5,
        f"fill_price(99.5, 100.5, direction=0) OBSERVED={observed} (bid); EXPECTED raise ValueError",
    )


def r_c2_slippage_not_applied() -> None:
    observed = CostModel(slippage_points=0.5).fill_price(99.5, 100.5, 1)
    record(
        "C2",
        observed == 100.5,
        f"CostModel(slippage_points=0.5).fill_price(long) OBSERVED={observed}; EXPECTED 101.0 per total_cost docstring",
    )


def r_prev_day_levels_all_null_tz_aware() -> None:
    idx = pd.date_range("2025-03-03 00:00", "2025-03-06 23:00", freq="1h", tz="UTC")
    close = 100.0 + np.arange(len(idx), dtype=float) * 0.01
    bars = pd.DataFrame(
        {"open": close, "high": close + 1.0, "low": close - 1.0, "close": close, "volume": 1.0},
        index=idx,
    )
    levels = detect_session_levels(bars)
    non_null = int(levels["prev_day_high"].notna().sum())
    record(
        "PREV-DAY-LEVELS",
        non_null == 0,
        f"tz-aware UTC 4-day hourly bars: prev_day_high non-null={non_null} of {len(levels)}; EXPECTED >0 after day 1",
    )


def r_prev_day_fixture_masks_defect() -> None:
    # Same fixture as tests/unit/features/test_session_levels.py (tz-naive, 5-minute bars from 01:05).
    dates = pd.date_range("2025-01-01 01:05", periods=300, freq="5min")
    rng = np.random.default_rng(42)
    high = np.cumsum(rng.standard_normal(300) * 0.1) + 100
    low = high - np.abs(rng.standard_normal(300) * 0.05)
    bars = pd.DataFrame(
        {"high": high, "low": low, "close": (high + low) / 2, "volume": 1000}, index=dates
    )
    levels = detect_session_levels(bars)
    non_null = int(levels["prev_day_high"].notna().sum())
    record(
        "PREV-DAY-FIXTURE-MASK",
        non_null > 0,
        f"tz-naive fixture: prev_day_high non-null={non_null} of {len(levels)} (values appear only on midnight-aligned stamps and their forward fill)",
    )


def r_empty_walk_forward_is_silent() -> None:
    folds = list(
        purged_walk_forward(100, n_splits=5, test_size=0.2, purge_bars=60, embargo_bars=20)
    )
    record(
        "WF-SILENT-EMPTY",
        len(folds) == 0,
        f"purged_walk_forward(n=100, purge=60, embargo=20) yields {len(folds)} folds with no error; EXPECTED an explicit error",
    )


def r_artifact_id_type_coercion() -> None:
    digest_int = artifact_id("probe", {"a": np.int64(3)}).digest
    digest_str = artifact_id("probe", {"a": "3"}).digest
    record(
        "ARTIFACT-ID-COERCION",
        digest_int == digest_str,
        "artifact_id(np.int64(3)) equals artifact_id('3'): unknown types are str()-coerced by json default=str",
    )


def r_atomic_new_file_mode() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "new.json"
        write_json_atomic(target, {"k": 1})
        mode = stat.S_IMODE(os.stat(target).st_mode)
        umask = os.umask(0)
        os.umask(umask)
        expected_default = 0o666 & ~umask
        record(
            "ATOMIC-NEW-FILE-MODE",
            mode != expected_default,
            f"new file mode via write_json_atomic={oct(mode)}; umask-default={oct(expected_default)}",
        )


def r_join_symbols_same_stamp() -> None:
    stamp = pd.Timestamp("2025-03-03 10:00", tz="UTC")
    primary = pd.DataFrame({"close": [100.0]}, index=pd.DatetimeIndex([stamp], name="datetime"))
    secondary = pd.DataFrame({"close": [555.0]}, index=pd.DatetimeIndex([stamp], name="datetime"))
    joined = join_symbols(primary, secondary, secondary_prefix="sec")
    value = float(joined["sec_close"].iloc[0])
    record(
        "JOIN-SAME-STAMP-REVIEW",
        value == 555.0,
        f"join_symbols joins the secondary bar opening at the same stamp: sec_close={value}; needs consumer decision-time contract (review item, not a confirmed defect)",
    )


if __name__ == "__main__":
    for fn in [
        r_c1_invalid_direction_maps_to_bid,
        r_c2_slippage_not_applied,
        r_prev_day_levels_all_null_tz_aware,
        r_prev_day_fixture_masks_defect,
        r_empty_walk_forward_is_silent,
        r_artifact_id_type_coercion,
        r_atomic_new_file_mode,
        r_join_symbols_same_stamp,
    ]:
        fn()
    unreproduced = [name for name, ok, _ in results if not ok]
    print(f"SUMMARY reproduced={sum(ok for _, ok, _ in results)} not_reproduced={unreproduced}")
    sys.exit(0 if not unreproduced else 1)
