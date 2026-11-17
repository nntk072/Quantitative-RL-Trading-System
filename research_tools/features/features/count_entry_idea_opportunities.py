#!/usr/bin/env python3
"""Count cached entry-idea candidate contexts by source timeframe and year.

The report separates aligned active M1 bars from signal episodes and unique
timestamps. Higher-timeframe features are forward-filled onto the M1 spine, so
adding their active bars is intentionally reported as a non-unique total.

PO3 candidates combine confirmed setup flags from multiple source timeframes.
The cache stores that candidate as one multi-timeframe flag, so it is reported
once as ``Any TF``. PO3 manipulation/distribution state alone is not an entry
candidate and is not counted here.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq  # type: ignore[import-untyped]
from numpy.typing import NDArray

TIMEFRAMES = ("M1", "M3", "M5", "M10", "M15", "M30", "H1", "H4", "D1")
IDEAS = ("PO3", "Order block", "Standard deviation", "FVG/IFVG reaction")
IDEA_TIMEFRAMES = {
    "PO3": ("Any TF",),
    "Order block": TIMEFRAMES,
    "Standard deviation": TIMEFRAMES,
    "FVG/IFVG reaction": TIMEFRAMES,
}


def _column_for(columns: set[str], timeframe: str, stem: str) -> str | None:
    """Return the source-timeframe feature name, accepting legacy M1 names."""
    candidates = (stem, f"M1_{stem}") if timeframe == "M1" else (f"{timeframe}_{stem}",)
    return next((name for name in candidates if name in columns), None)


def _numeric(table: pd.DataFrame, name: str | None) -> NDArray[np.float64] | None:
    if name is None:
        return None
    return pd.to_numeric(table[name], errors="coerce").fillna(0.0).to_numpy(dtype=float)


def _active(
    table: pd.DataFrame, columns: set[str], timeframe: str, stem: str
) -> NDArray[np.float64] | None:
    return _numeric(table, _column_for(columns, timeframe, stem))


def _signals_for_timeframe(
    table: pd.DataFrame, columns: set[str], timeframe: str
) -> tuple[dict[str, tuple[NDArray[np.bool_], NDArray[np.bool_]]], dict[str, bool]]:
    """Build directional causal signal flags and report missing source fields."""
    n = len(table)
    zero = np.zeros(n, dtype=bool)
    result: dict[str, tuple[NDArray[np.bool_], NDArray[np.bool_]]] = {}
    available: dict[str, bool] = {}

    if timeframe == "Any TF":
        po3_long = _numeric(table, "entry_idea_po3_long")
        po3_short = _numeric(table, "entry_idea_po3_short")
        result["PO3"] = (
            zero.copy() if po3_long is None else po3_long > 0.0,
            zero.copy() if po3_short is None else po3_short > 0.0,
        )
        available["PO3"] = po3_long is not None and po3_short is not None
    else:
        result["PO3"] = (zero.copy(), zero.copy())
        available["PO3"] = False

    for label, stem in (("Order block", "ob"),):
        long = _active(table, columns, timeframe, f"{stem}_bull_retest")
        short = _active(table, columns, timeframe, f"{stem}_bear_retest")
        result[label] = (
            zero.copy() if long is None else long > 0,
            zero.copy() if short is None else short > 0,
        )
        available[label] = long is not None or short is not None

    for label, stem in (("Standard deviation", "standard_deviation_entry"),):
        long = _active(table, columns, timeframe, f"{stem}_long")
        short = _active(table, columns, timeframe, f"{stem}_short")
        result[label] = (
            zero.copy() if long is None else long > 0,
            zero.copy() if short is None else short > 0,
        )
        available[label] = long is not None or short is not None

    fvg_long = _active(table, columns, timeframe, "fvg_retest_bull")
    fvg_short = _active(table, columns, timeframe, "fvg_retest_bear")
    ifvg_long = _active(table, columns, timeframe, "ifvg_retest_bull")
    ifvg_short = _active(table, columns, timeframe, "ifvg_retest_bear")
    fvg_long_signal = zero.copy()
    fvg_short_signal = zero.copy()
    if fvg_long is not None:
        fvg_long_signal |= fvg_long > 0
    if fvg_short is not None:
        fvg_short_signal |= fvg_short > 0
    if ifvg_long is not None:
        fvg_long_signal |= ifvg_long > 0
    if ifvg_short is not None:
        fvg_short_signal |= ifvg_short > 0
    result["FVG/IFVG reaction"] = (fvg_long_signal, fvg_short_signal)
    available["FVG/IFVG reaction"] = any(
        value is not None for value in (fvg_long, fvg_short, ifvg_long, ifvg_short)
    )

    return result, available


def _episode_starts(signal: NDArray[np.bool_]) -> int:
    if not signal.size:
        return 0
    return int(signal[0]) + int(np.count_nonzero(signal[1:] & ~signal[:-1]))


def _markdown_table(frame: pd.DataFrame) -> str:
    columns = [str(column) for column in frame.columns]
    rows = [[str(value) for value in row] for row in frame.itertuples(index=False, name=None)]
    widths = [
        max([len(columns[index]), *(len(row[index]) for row in rows)])
        for index in range(len(columns))
    ]

    def render(row: list[str]) -> str:
        cells = [value.ljust(widths[index]) for index, value in enumerate(row)]
        return "| " + " | ".join(cells) + " |"

    divider = "| " + " | ".join("-" * width for width in widths) + " |"
    return "\n".join([render(columns), divider, *(render(row) for row in rows)])


def _markdown(summary: pd.DataFrame, detail: pd.DataFrame, cache_path: Path) -> str:
    detail_columns = [
        "year",
        "idea",
        "timeframe",
        "available",
        "active_m1_bars",
        "episode_starts",
        "both_sides_active_m1_bars",
        "long_active_m1_bars",
        "short_active_m1_bars",
    ]
    lines = [
        "# Entry-idea opportunity counts",
        "",
        f"- Feature cache: `{cache_path}`",
        f"- Cached M1 rows: {int(detail.groupby('year', dropna=False)['m1_rows'].first().sum()):,}",
        "- Timeframes: M1, M3, M5, M10, M15, M30, H1, H4, D1.",
        "- Primary ideas: confirmed PO3 entry candidate, order-block retest, standard-deviation/Fibonacci entry, and FVG/IFVG retest.",
        "",
        "## Annual totals",
        "",
        _markdown_table(summary),
        "",
        "## Counts by idea and timeframe",
        "",
        _markdown_table(detail[detail_columns]),
        "",
        "## How to read these counts",
        "",
        "`active_m1_bars` counts M1 observations where that idea flag is active. An aligned higher-timeframe state may repeat across many M1 bars, so summing these values across timeframes double-counts correlated context.",
        "`episode_starts` counts false-to-true transitions for one idea, timeframe, and direction. It is a context-episode count, not an executable trade count. The family totals in the annual table sum these episodes across source timeframes.",
        "PO3 is counted from the cache's confirmed `entry_idea_po3_long/short` flags, which require an IFVG-confirmed distribution and a still-active gap. It is shown once as `Any TF` because this composite flag does not retain per-source-timeframe attribution. A manipulation/distribution state or liquidity sweep by itself is not counted as a PO3 entry candidate.",
        "The FVG/IFVG family combines bullish and bearish FVG retests with inverse-FVG retests, then counts each direction's active union once per source timeframe.",
        "`unique_bars_with_both_directions` counts rows where the union of the four reported idea families has both long and short context. It does not mean both sides were independently entry-ready. `cache_entry_idea_rows_with_both_directions` counts rows where the aggregate cache flags consumed by the entry state machine have both sides active; when a row otherwise supplies candidate evidence, the state machine treats those flags as conflicting evidence.",
        "`both_sides_active_m1_bars` counts same-idea, same-timeframe bars with both directions active. `unique_bars_any_idea` counts each cached timestamp once even when ideas or timeframes overlap.",
        "These are cached market-context signals before NY-session eligibility, policy actions, stop/target construction, account limits, and execution. They do not imply the same number of trades.",
        "A signal source is marked unavailable when the cache has no corresponding source columns; its zero count must not be interpreted as evidence of no market opportunities.",
        "",
    ]
    return "\n".join(lines)


def count_opportunities(cache_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    parquet = pq.ParquetFile(cache_path)
    schema_columns = set(parquet.schema.names)
    required = {
        "datetime",
        "entry_idea_po3_long",
        "entry_idea_po3_short",
        "entry_idea_long_count",
        "entry_idea_short_count",
    }
    for timeframe in TIMEFRAMES:
        for stem in (
            "po3_distribution",
            "po3_distribution_direction",
            "po3_manipulation_active",
            "po3_manipulation_direction",
            "sweep_low",
            "sweep_high",
            "ob_bull_retest",
            "ob_bear_retest",
            "standard_deviation_entry_long",
            "standard_deviation_entry_short",
            "fvg_retest_bull",
            "fvg_retest_bear",
            "ifvg_retest_bull",
            "ifvg_retest_bear",
        ):
            name = _column_for(schema_columns, timeframe, stem)
            if name is not None:
                required.add(name)
    missing = required - schema_columns
    if missing:
        raise ValueError(f"cache is missing required columns: {sorted(missing)}")
    table = pd.read_parquet(cache_path, columns=sorted(required))
    time_values = table["datetime"] if "datetime" in table.columns else table.index
    timestamps = pd.Series(
        pd.to_datetime(time_values, errors="coerce"), index=table.index, name="datetime"
    )
    valid_time = timestamps.notna().to_numpy()
    years = timestamps.dt.year.to_numpy()
    idea_long_count = _numeric(table, "entry_idea_long_count")
    idea_short_count = _numeric(table, "entry_idea_short_count")
    ambiguous_direction = (
        np.zeros(len(table), dtype=bool)
        if idea_long_count is None or idea_short_count is None
        else (idea_long_count > 0.0) & (idea_short_count > 0.0)
    )
    all_signals: dict[tuple[str, str], tuple[NDArray[np.bool_], NDArray[np.bool_]]] = {}
    source_available: dict[tuple[str, str], bool] = {}
    for timeframe in ("Any TF", *TIMEFRAMES):
        signals, available = _signals_for_timeframe(table, schema_columns, timeframe)
        for idea, sides in signals.items():
            all_signals[(idea, timeframe)] = sides
            source_available[(idea, timeframe)] = available[idea]

    detail_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []
    for year in sorted(set(years[valid_time])):
        year_mask = valid_time & (years == year)
        year_idea_masks: dict[str, NDArray[np.bool_]] = {}
        year_idea_long_masks: dict[str, NDArray[np.bool_]] = {}
        year_idea_short_masks: dict[str, NDArray[np.bool_]] = {}
        idea_episode_counts: dict[str, int] = {}
        total_cells = 0
        total_events = 0
        both_side_cells = 0
        for idea in IDEAS:
            tf_masks: list[NDArray[np.bool_]] = []
            idea_events = 0
            for timeframe in IDEA_TIMEFRAMES[idea]:
                long_all, short_all = all_signals[(idea, timeframe)]
                long_signal = long_all[year_mask]
                short_signal = short_all[year_mask]
                combined = long_signal | short_signal
                both_sides = long_signal & short_signal
                tf_masks.append(combined)
                starts = _episode_starts(long_signal) + _episode_starts(short_signal)
                idea_events += starts
                total_cells += int(np.count_nonzero(combined))
                total_events += starts
                both_side_cells += int(np.count_nonzero(both_sides))
                detail_rows.append(
                    {
                        "year": int(year),
                        "m1_rows": int(np.count_nonzero(year_mask)),
                        "idea": idea,
                        "timeframe": timeframe,
                        "available": source_available[(idea, timeframe)],
                        "active_m1_bars": int(np.count_nonzero(combined)),
                        "episode_starts": starts,
                        "both_sides_active_m1_bars": int(np.count_nonzero(both_sides)),
                        "long_active_m1_bars": int(np.count_nonzero(long_signal)),
                        "short_active_m1_bars": int(np.count_nonzero(short_signal)),
                    }
                )
            idea_episode_counts[idea] = idea_events
            year_idea_masks[idea] = np.logical_or.reduce(tf_masks)
            year_idea_long_masks[idea] = np.logical_or.reduce(
                [
                    all_signals[(idea, timeframe)][0][year_mask]
                    for timeframe in IDEA_TIMEFRAMES[idea]
                ]
            )
            year_idea_short_masks[idea] = np.logical_or.reduce(
                [
                    all_signals[(idea, timeframe)][1][year_mask]
                    for timeframe in IDEA_TIMEFRAMES[idea]
                ]
            )
        idea_matrix = np.vstack([year_idea_masks[idea] for idea in IDEAS])
        active_idea_count = idea_matrix.sum(axis=0)
        unique_any = active_idea_count > 0
        long_any = np.logical_or.reduce(list(year_idea_long_masks.values()))
        short_any = np.logical_or.reduce(list(year_idea_short_masks.values()))
        both_raw_direction_bars = long_any & short_any
        cache_both_direction_bars = int(np.count_nonzero(ambiguous_direction[year_mask]))
        summary_rows.append(
            {
                "year": int(year),
                "m1_rows": int(np.count_nonzero(year_mask)),
                "idea_timeframe_active_bars_sum": total_cells,
                "idea_timeframe_episode_starts_sum": total_events,
                "idea_timeframe_both_sides_bars_sum": both_side_cells,
                "unique_bars_any_idea": int(np.count_nonzero(unique_any)),
                "unique_bars_directionally_unambiguous": int(
                    np.count_nonzero((long_any | short_any) & ~both_raw_direction_bars)
                ),
                "unique_bars_with_both_directions": int(np.count_nonzero(both_raw_direction_bars)),
                "cache_entry_idea_rows_with_both_directions": cache_both_direction_bars,
                "unique_bars_2plus_ideas": int(np.count_nonzero(active_idea_count >= 2)),
                "unique_bars_3plus_ideas": int(np.count_nonzero(active_idea_count >= 3)),
                "po3_signal_episode_starts": idea_episode_counts["PO3"],
                "order_block_signal_episode_starts": idea_episode_counts["Order block"],
                "standard_deviation_signal_episode_starts": idea_episode_counts[
                    "Standard deviation"
                ],
                "fvg_ifvg_reaction_signal_episode_starts": idea_episode_counts["FVG/IFVG reaction"],
                "po3_unique_bars": int(np.count_nonzero(year_idea_masks["PO3"])),
                "order_block_unique_bars": int(np.count_nonzero(year_idea_masks["Order block"])),
                "standard_deviation_unique_bars": int(
                    np.count_nonzero(year_idea_masks["Standard deviation"])
                ),
                "fvg_ifvg_reaction_unique_bars": int(
                    np.count_nonzero(year_idea_masks["FVG/IFVG reaction"])
                ),
            }
        )
    return pd.DataFrame(summary_rows), pd.DataFrame(detail_rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", required=True, type=Path, help="feature parquet cache")
    parser.add_argument("--out-dir", required=True, type=Path, help="output directory")
    args = parser.parse_args()
    if not args.cache.is_file():
        parser.error(f"feature cache does not exist: {args.cache}")
    summary, detail = count_opportunities(args.cache)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = args.out_dir / "annual_summary.csv"
    detail_path = args.out_dir / "by_idea_timeframe.csv"
    report_path = args.out_dir / "entry_idea_opportunity_counts.md"
    summary.to_csv(summary_path, index=False)
    detail.to_csv(detail_path, index=False)
    report_path.write_text(_markdown(summary, detail, args.cache), encoding="utf-8")
    print(f"report={report_path}")
    print(f"summary_csv={summary_path}")
    print(f"detail_csv={detail_path}")
    print(summary.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
