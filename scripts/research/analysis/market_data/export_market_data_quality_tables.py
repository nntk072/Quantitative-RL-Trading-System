"""Export period quality tables and schema documentation from current audits.

This utility reuses the completed streaming quality scan and configured
timeframe comparison. It does not reread raw market data or infer an external
calendar, provider, flag definition, or unit that the source does not establish.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[4]
PACKET = Path("evidence/research/market_data_quality")
QUALITY = PACKET / "local_market_data_quality.json"
PARITY = PACKET / "configured_timeframe_parity.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object at {path}")
    return value


def write_period_table(profile: dict[str, Any], path: Path) -> int:
    rows: list[dict[str, Any]] = []
    for identity, summary in sorted(profile["quality_counts_by_instrument_role_timeframe"].items()):
        role, instrument, timeframe = identity.split("|", 2)
        for granularity, periods in sorted(summary.get("by_period", {}).items()):
            for label, counts in sorted(periods.items()):
                for metric, value in sorted(counts.items()):
                    rows.append(
                        {
                            "source_role": role,
                            "instrument": instrument,
                            "timeframe": timeframe,
                            "period_granularity": granularity,
                            "source_wall_clock_period": label,
                            "metric": metric,
                            "count": value,
                        }
                    )
    if not rows:
        raise ValueError("quality profile contains no period metrics")
    fields = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def write_coverage_table(parity: dict[str, Any], path: Path) -> int:
    rows: list[dict[str, Any]] = []
    for series in parity["timeframes"]:
        coverage = series.get("source_row_coverage", {})
        availability = series.get("availability", {})
        rows.append(
            {
                "role": series.get("dataset"),
                "symbol": series.get("symbol"),
                "timeframe": series.get("timeframe"),
                "origin": series.get("origin"),
                "status": series.get("status"),
                "native_rows": series.get("native_rows"),
                "m1_derived_rows": series.get("m1_derived_rows"),
                "common_timestamp_rows": series.get("common_timestamp_rows"),
                "expected_m1_grid_rows": coverage.get("expected_m1_grid_rows"),
                "observed_m1_rows": coverage.get("observed_m1_rows"),
                "bars": coverage.get("bars"),
                "bars_with_fewer_rows_than_grid": coverage.get("bars_with_fewer_rows_than_grid"),
                "bars_with_zero_observed_rows": coverage.get("bars_with_zero_observed_rows"),
                "bars_with_more_rows_than_grid": coverage.get("bars_with_more_rows_than_grid"),
                "rows_first_visible_exactly_at_close": availability.get(
                    "rows_first_visible_exactly_at_close"
                ),
                "rows_first_visible_after_close": availability.get(
                    "rows_first_visible_after_close"
                ),
                "rows_without_later_m1_bar": availability.get("rows_without_later_m1_bar"),
                "coverage_interpretation": coverage.get("interpretation"),
            }
        )
    if not rows:
        raise ValueError("timeframe report contains no series")
    fields = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def write_coverage_figure(rows: list[dict[str, Any]], path: Path) -> None:
    timeframes = ["M1", "M3", "M5", "M10", "M15", "M30", "H1", "H4", "D1"]
    roles = ["training", "testing"]
    symbols = sorted({str(row["symbol"]) for row in rows})
    colors = {symbol: color for symbol, color in zip(symbols, ("#2a6fbb", "#e07a2d"), strict=False)}
    fig, axes = plt.subplots(2, 1, figsize=(13, 8), sharex=True, sharey=True, layout="constrained")
    width = 0.36 if len(symbols) == 2 else 0.65 / max(len(symbols), 1)
    positions = {timeframe: index for index, timeframe in enumerate(timeframes)}
    for axis, role in zip(axes, roles, strict=True):
        selected = [row for row in rows if row["role"] == role]
        grouped: dict[tuple[str, str], list[float]] = {}
        for row in selected:
            expected = row.get("expected_m1_grid_rows")
            observed = row.get("observed_m1_rows")
            if expected is None or observed is None or int(expected) <= 0:
                continue
            grouped[(str(row["symbol"]), str(row["timeframe"]))] = [int(observed) / int(expected)]
        for symbol_index, symbol in enumerate(symbols):
            offset = (symbol_index - (len(symbols) - 1) / 2) * width
            x = []
            height = []
            for timeframe in timeframes:
                value = grouped.get((symbol, timeframe))
                if value:
                    x.append(positions[timeframe] + offset)
                    height.append(value[0])
            axis.bar(x, height, width=width, color=colors[symbol], label=symbol)
        axis.axhline(1.0, color="#444444", linewidth=0.9, linestyle="--")
        axis.set_ylabel(f"{role}\nobserved / nominal")
        axis.set_ylim(0, 1.04)
        axis.grid(axis="y", alpha=0.25)
        axis.legend(loc="lower left", ncol=len(symbols), frameon=False)
    axes[-1].set_xticks(range(len(timeframes)), timeframes)
    axes[-1].set_xlabel("Configured timeframe")
    fig.suptitle("Observed M1 source rows per nominal timeframe grid")
    fig.text(
        0.5,
        -0.01,
        "Configured-close clipping; partial bars are retained. This is descriptive grid occupancy, not calendar coverage or a data-loss classification.",
        ha="center",
        fontsize=9,
    )
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def write_dictionary(profile: dict[str, Any], path: Path, source_hashes: dict[str, str]) -> None:
    raw_inputs = profile["inputs"]
    roles = sorted({str(item.get("role", "unknown")) for item in raw_inputs})
    timeframe_paths = sorted(
        str(item["path"]) for item in raw_inputs if item.get("kind") in {"bar", "tick"}
    )
    role_text = ", ".join(f"`{role}`" for role in roles)
    path_examples = ", ".join(f"`{p}`" for p in timeframe_paths[:4])
    content = f"""# Local market-data dictionary

This dictionary describes the local MT5-shaped source files included in the
selected campaign input inventory. It documents field shape and known code
behavior; it does not infer provider semantics, rights, authoritative clocks,
or undocumented units. The audit input roles are {role_text}.

The examples below are **synthetic schema examples**, not copied market rows.
Raw data remains in its existing restricted location and is not bundled here.

## Bar CSV fields

The loader accepts intraday rows with `<DATE>`, `<TIME>`, `<OPEN>`, `<HIGH>`,
`<LOW>`, `<CLOSE>`, `<TICKVOL>`, `<VOL>`, `<SPREAD>`, and daily rows without
`<TIME>`. Date/time are parsed as wall-clock values and later localized using
configuration. Daily rows receive a midnight time in the loader. OHLC values
are source price units for the instrument; exact tick-size interpretation
depends on the configured symbol price grid. `TICKVOL` is an integer source
tick-volume field; `VOL` is an integer source-volume field whose external unit
is not established here. `SPREAD` is the source bar spread field; parser
documentation describes it as price points, but no external provider
definition is asserted.

| Field | Unit / representation | Missingness and interpretation |
|---|---|---|
| `<DATE>` | `YYYY.MM.DD` string | Required; source wall-clock date. |
| `<TIME>` | `HH:MM:SS` string | Present for intraday bars; absent for daily bars. |
| `<OPEN>`, `<HIGH>`, `<LOW>`, `<CLOSE>` | instrument price units | Required finite numeric OHLC; OHLC consistency is checked separately. |
| `<TICKVOL>` | integer source count | Source-defined tick volume; not treated as exchange volume. |
| `<VOL>` | integer source value | Unit/provider meaning not independently assessed. |
| `<SPREAD>` | source spread value | Parser docs say price points; symbol conversion and provider semantics are separate. |

Synthetic intraday example:

```text
<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>
2025.01.02\t01:05:00\t100.0\t101.0\t99.5\t100.5\t12\t0\t2.0
```

## Tick CSV fields

Tick exports contain `<DATE>`, `<TIME>`, `<BID>`, `<ASK>`, `<LAST>`,
`<VOLUME>`, and `<FLAGS>`. Tick time strings include milliseconds. The current
quality scan found `<LAST>` and `<VOLUME>` empty throughout the selected tick
exports. `<FLAGS>` is retained as an opaque source field; no flag meanings are
inferred. The configured TickBook builder reads bid/ask only, treats
non-finite and non-positive sides as missing, carries each side forward
independently, rejects invalid/crossed pairs, and retains source order for tied
timestamps. This behavior is not simultaneous-quote proof or within-tie
chronology.

| Field | Unit / representation | Missingness and interpretation |
|---|---|---|
| `<DATE>` | `YYYY.MM.DD` string | Required; source wall-clock date. |
| `<TIME>` | `HH:MM:SS.fff` string | Millisecond-formatted local wall-clock time. |
| `<BID>`, `<ASK>` | instrument price units | Required for a raw two-sided quote; may be missing/non-finite on individual rows. |
| `<LAST>` | source price value | Empty in selected tick exports; unused by the TickBook builder. |
| `<VOLUME>` | source numeric value | Empty in selected tick exports; unit not assessed and unused by TickBook builder. |
| `<FLAGS>` | opaque source string | Present in the exports; semantics intentionally not decoded. |

Synthetic tick example:

```text
<DATE>\t<TIME>\t<BID>\t<ASK>\t<LAST>\t<VOLUME>\t<FLAGS>
2025.01.02\t01:05:00.123\t100.0\t100.5\t\t\t6
```

## Configured session schedule

`config/ny_session_schedule.csv` contains `session_date`,
`scheduled_ny_close_broker_time`, and `scheduled_short`. These are configured
schedule fields used by local calculations; the file is not asserted to be an
authoritative venue calendar.

## Source and scope

- Current byte/quality report: [`local_market_data_quality.json`](local_market_data_quality.json)
- Configured timeframe comparison: [`configured_timeframe_parity.json`](configured_timeframe_parity.json)
- Example source paths: {path_examples}
- Source hashes recorded when generated: `market_data/loading/bars.py` = `{source_hashes["market_data/loading/bars.py"]}`; `market_data/loading/ticks.py` = `{source_hashes["market_data/loading/ticks.py"]}`; the input profile = `{source_hashes["evidence/research/market_data_quality/local_market_data_quality.json"]}`.
- The input profile records 39 manifested files and exact byte hashes. This dictionary contains no raw observations.
"""
    path.write_text(content, encoding="utf-8")


def export(root: Path, packet: Path) -> None:
    profile_path = root / QUALITY
    parity_path = root / PARITY
    profile = load_json(profile_path)
    parity = load_json(parity_path)
    if not profile.get("all_inputs_present") or not profile.get("all_input_hashes_match"):
        raise ValueError("market-data input manifest is not fully verified")

    period_path = packet / "period_quality_counts.csv"
    coverage_path = packet / "configured_timeframe_coverage.csv"
    coverage_figure_path = packet / "configured_bar_source_coverage.png"
    dictionary_path = packet / "local_data_dictionary.md"
    provenance_path = packet / "quality_table_provenance.json"
    packet.mkdir(parents=True, exist_ok=True)
    period_rows = write_period_table(profile, period_path)
    coverage_rows = write_coverage_table(parity, coverage_path)
    with coverage_path.open(newline="", encoding="utf-8") as handle:
        coverage_table_rows = list(csv.DictReader(handle))
    for row in coverage_table_rows:
        for key in ("expected_m1_grid_rows", "observed_m1_rows"):
            row[key] = None if row[key] in (None, "") else int(row[key])
    write_coverage_figure(coverage_table_rows, coverage_figure_path)
    source_hashes = {
        "market_data/loading/bars.py": sha256(root / "market_data/loading/bars.py"),
        "market_data/loading/ticks.py": sha256(root / "market_data/loading/ticks.py"),
        str(QUALITY): sha256(profile_path),
        str(PARITY): sha256(parity_path),
        "config/base/default.yaml": sha256(root / "config/base/default.yaml"),
        "config/ny_session_schedule.csv": sha256(root / "config/ny_session_schedule.csv"),
    }
    write_dictionary(profile, dictionary_path, source_hashes)
    provenance = {
        "schema": "qrl.market_data_quality_tables.v1",
        "generator_path": "scripts/research/analysis/market_data/export_market_data_quality_tables.py",
        "generator_sha256": sha256(Path(__file__).resolve()),
        "input_hashes": {
            str(QUALITY): source_hashes[str(QUALITY)],
            str(PARITY): source_hashes[str(PARITY)],
            "market_data/loading/bars.py": source_hashes["market_data/loading/bars.py"],
            "market_data/loading/ticks.py": source_hashes["market_data/loading/ticks.py"],
            "config/base/default.yaml": source_hashes["config/base/default.yaml"],
            "config/ny_session_schedule.csv": source_hashes["config/ny_session_schedule.csv"],
        },
        "outputs": {
            period_path.name: {"sha256": sha256(period_path), "rows": period_rows},
            coverage_path.name: {"sha256": sha256(coverage_path), "rows": coverage_rows},
            coverage_figure_path.name: {
                "sha256": sha256(coverage_figure_path),
                "plot_type": "descriptive nominal-grid occupancy",
            },
            dictionary_path.name: {"sha256": sha256(dictionary_path), "contains_raw_rows": False},
        },
        "period_basis": "parsed source wall-clock labels in the input quality report; no timezone/session reinterpretation",
        "raw_data_reread": False,
    }
    provenance_path.write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    readme_path = packet / "README.md"
    readme_base = (
        readme_path.read_text(encoding="utf-8")
        .split("\n## Data dictionary and period tables\n", 1)[0]
        .rstrip()
    )
    readme_path.write_text(
        readme_base
        + "\n\n## Data dictionary and period tables\n\n"
        + "[`period_quality_counts.csv`](period_quality_counts.csv) contains day/week/month quality metrics by source role, instrument, and timeframe. "
        + "[`configured_timeframe_coverage.csv`](configured_timeframe_coverage.csv) flattens the 32 configured parity/availability rows. "
        + "[`configured_bar_source_coverage.png`](configured_bar_source_coverage.png) plots observed M1 source rows against nominal configured grid slots, without treating partial bars as data loss. "
        + "[`local_data_dictionary.md`](local_data_dictionary.md) documents source fields, units and limits with synthetic examples. "
        + "These tables reuse the current machine reports and do not reread or bundle raw market rows. Their source/output hashes are in "
        + "[`quality_table_provenance.json`](quality_table_provenance.json).\n",
        encoding="utf-8",
    )

    checksum_files = sorted(
        path for path in packet.iterdir() if path.is_file() and path.name != "SHA256SUMS"
    )
    checksum_lines = [f"{sha256(path)}  {path.name}" for path in checksum_files]
    (packet / "SHA256SUMS").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "period_table_rows": period_rows,
                "coverage_rows": coverage_rows,
                "coverage_figure": str(coverage_figure_path),
                "data_dictionary": "written with synthetic examples",
                "raw_data_reread": False,
                "checksum_files": len(checksum_files),
            },
            indent=2,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--packet", type=Path, default=PACKET)
    args = parser.parse_args()
    root = args.root.resolve()
    packet = args.packet if args.packet.is_absolute() else root / args.packet
    export(root, packet)


if __name__ == "__main__":
    main()
