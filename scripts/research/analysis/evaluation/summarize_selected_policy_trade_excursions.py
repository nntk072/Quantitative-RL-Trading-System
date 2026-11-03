#!/usr/bin/env python3
"""Summarize executable-side tick MFE/MAE bounds for completed positions.

The command reads preserved fills and position summaries, then measures
liquidation-side price excursions in the configured TickBook. It does not
replay policy decisions or alter the campaign outputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import tempfile
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
from omegaconf import OmegaConf

from artifacts.atomic import write_json_atomic
from configuration.paths import repository_root
from evaluation.metrics.trade_excursions import trade_excursion_bounds
from market_data.loading.ticks import TickBook, build_tick_book

ROOT = repository_root(__file__)
DEFAULT_QUALITY_REPORT = (
    ROOT / "evidence/research/releases/negative-evidence-readiness/local_market_data_quality.json"
)
DEFAULT_OUTPUT = ROOT / "evidence/research/selected_policy_trade_lifecycle/trade_excursions"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _path_identity(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def _parse_arm(value: str) -> tuple[str, Path, Path]:
    name, separator, fills_value = value.partition("=")
    if not separator or not re.fullmatch(r"[a-z][a-z0-9_]*", name):
        raise argparse.ArgumentTypeError("arm must be NAME=/path/to/fills.csv")
    fills = Path(fills_value).expanduser()
    if not fills.is_file() or fills.name != "fills.csv":
        raise argparse.ArgumentTypeError(f"arm fills file is missing or not fills.csv: {fills}")
    positions = fills.with_name("positions.csv")
    if not positions.is_file():
        raise argparse.ArgumentTypeError(f"arm positions file is missing: {positions}")
    return name, positions.resolve(), fills.resolve()


def _parse_named_path(value: str) -> tuple[str, Path]:
    name, separator, path_value = value.partition("=")
    if not separator or not re.fullmatch(r"[a-z][a-z0-9_]*", name):
        raise argparse.ArgumentTypeError("config must be NAME=/path/to/config.yaml")
    path = Path(path_value).expanduser()
    if not path.is_file() or path.name != "config.yaml":
        raise argparse.ArgumentTypeError(f"config file is missing or not config.yaml: {path}")
    return name, path.resolve()


def _tick_settings(config_path: Path) -> tuple[str, float | None]:
    config = OmegaConf.load(config_path)
    timezone = str(OmegaConf.select(config, "data.tz"))
    grid_enabled = bool(
        OmegaConf.select(config, "data.price_discretization.enabled", default=False)
    )
    grid_increment = (
        float(OmegaConf.select(config, "data.price_discretization.increment"))
        if grid_enabled
        else None
    )
    return timezone, grid_increment


def _utc_timestamp(value: Any, *, position_id: str, field: str) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        raise ValueError(f"{position_id} {field} is missing a timezone")
    return timestamp.tz_convert("UTC")


def _quote_at_exact_time(
    book: TickBook, timestamp: pd.Timestamp, *, position_id: str, event: str
) -> tuple[float, float, int]:
    timestamp_ns = timestamp.value
    first = int(np.searchsorted(book._ts, timestamp_ns, side="left"))
    last = int(np.searchsorted(book._ts, timestamp_ns, side="right"))
    if first == last:
        raise ValueError(f"{position_id} {event} fill timestamp has no exact TickBook row")
    return float(book._bid[first]), float(book._ask[first]), last - first


def _bool_column(series: pd.Series) -> pd.Series:
    return series.astype("string").str.strip().str.lower().isin({"true", "1", "yes"})


def summarize_arm(
    name: str,
    positions_path: Path,
    fills_path: Path,
    book: TickBook,
) -> pd.DataFrame:
    positions = pd.read_csv(positions_path, low_memory=False)
    fills = pd.read_csv(fills_path, low_memory=False)
    required_positions = {
        "position_id",
        "direction",
        "entry_time",
        "exit_time",
        "entry_price",
        "exit_price",
        "completed",
        "holding_seconds",
        "exit_reason",
        "position_net_pnl",
    }
    required_fills = {
        "type",
        "position_id",
        "direction",
        "price",
        "actual_tick_time",
        "position_complete",
        "fill_id",
        "modeled_stop_risk_usd",
        "sl_price",
        "lots",
    }
    if missing := required_positions - set(positions.columns):
        raise ValueError(f"{name} positions are missing columns: {sorted(missing)}")
    if missing := required_fills - set(fills.columns):
        raise ValueError(f"{name} fills are missing columns: {sorted(missing)}")

    completed_positions = positions.loc[_bool_column(positions["completed"])].copy()
    if completed_positions["position_id"].duplicated().any():
        raise ValueError(f"{name} positions contain duplicate completed position IDs")
    position_ids = set(completed_positions["position_id"].astype(str))
    event_ids = set(fills["position_id"].dropna().astype(str))
    if position_ids != event_ids:
        raise ValueError(
            f"{name} fill/position ID mismatch: "
            f"positions_only={len(position_ids - event_ids)}, "
            f"events_only={len(event_ids - position_ids)}"
        )

    records: list[dict[str, Any]] = []
    for position in completed_positions.to_dict(orient="records"):
        position_id = str(position["position_id"])
        events = fills.loc[fills["position_id"].astype("string").eq(position_id)]
        opening = events.loc[events["type"].eq("open")]
        closes = events.loc[_bool_column(events["position_complete"])].copy()
        if len(opening) != 1 or closes.empty or closes["fill_id"].isna().all():
            raise ValueError(f"{name} {position_id} lacks one open or a completed close fill")
        opening_row = opening.iloc[0]
        closing_rows = closes.loc[closes["fill_id"].notna()].copy()
        close_times = pd.to_datetime(closing_rows["actual_tick_time"], utc=True, errors="coerce")
        if close_times.isna().any():
            raise ValueError(f"{name} {position_id} has an invalid final close timestamp")
        final_close = closing_rows.loc[close_times.idxmax()]

        direction_value = float(position["direction"])
        if direction_value not in (-1.0, 1.0):
            raise ValueError(f"{name} {position_id} direction must be -1 or 1")
        direction = int(direction_value)
        entry_time = _utc_timestamp(
            opening_row["actual_tick_time"], position_id=position_id, field="entry"
        )
        exit_time = _utc_timestamp(
            final_close["actual_tick_time"], position_id=position_id, field="exit"
        )
        if entry_time > exit_time:
            raise ValueError(f"{name} {position_id} exits before entry")
        entry_price = float(opening_row["price"])
        exit_price = float(cast(Any, final_close["price"]))
        entry_bid, entry_ask, entry_tie_rows = _quote_at_exact_time(
            book, entry_time, position_id=position_id, event="entry"
        )
        exit_bid, exit_ask, exit_tie_rows = _quote_at_exact_time(
            book, exit_time, position_id=position_id, event="exit"
        )
        entry_side_price = entry_ask if direction == 1 else entry_bid
        exit_side_price = exit_bid if direction == 1 else exit_ask
        if not math.isclose(entry_side_price, entry_price, rel_tol=0.0, abs_tol=1e-8):
            raise ValueError(f"{name} {position_id} entry does not match current TickBook quote")
        if not math.isclose(exit_side_price, exit_price, rel_tol=0.0, abs_tol=1e-8):
            raise ValueError(f"{name} {position_id} exit does not match current TickBook quote")

        stop_price = float(opening_row["sl_price"])
        stop_distance = abs(entry_price - stop_price)
        if not math.isfinite(stop_distance) or stop_distance <= 0.0:
            raise ValueError(f"{name} {position_id} has invalid initial stop geometry")
        initial_risk = float(opening_row["modeled_stop_risk_usd"])
        if not math.isfinite(initial_risk) or initial_risk <= 0.0:
            raise ValueError(f"{name} {position_id} has invalid modeled stop risk")

        start_ns, end_ns = entry_time.value, exit_time.value
        first = int(np.searchsorted(book._ts, start_ns, side="left"))
        last = int(np.searchsorted(book._ts, end_ns, side="right"))
        liquidation_prices = book._bid if direction == 1 else book._ask
        excursion = trade_excursion_bounds(
            book._ts[first:last],
            liquidation_prices[first:last],
            entry_time_ns=start_ns,
            exit_time_ns=end_ns,
            direction=direction,
            entry_price=entry_price,
            entry_liquidation_price=entry_bid if direction == 1 else entry_ask,
            exit_liquidation_price=exit_bid if direction == 1 else exit_ask,
        )
        records.append(
            {
                "arm": name,
                "position_id": position_id,
                "direction": direction,
                "entry_time_utc": entry_time.isoformat(),
                "exit_time_utc": exit_time.isoformat(),
                "entry_price": entry_price,
                "exit_price": exit_price,
                "initial_stop_price": stop_price,
                "initial_stop_distance_points": stop_distance,
                "initial_modeled_stop_risk_usd": initial_risk,
                "holding_seconds": float(position["holding_seconds"]),
                "exit_reason": str(position["exit_reason"]),
                "position_net_pnl_usd": float(position["position_net_pnl"]),
                "realized_r": float(position["position_net_pnl"]) / initial_risk,
                "mfe_points_lower": excursion.mfe_price_lower,
                "mfe_points_upper": excursion.mfe_price_upper,
                "mae_points_lower": excursion.mae_price_lower,
                "mae_points_upper": excursion.mae_price_upper,
                "mfe_r_lower": excursion.mfe_price_lower / stop_distance,
                "mfe_r_upper": excursion.mfe_price_upper / stop_distance,
                "mae_r_lower": excursion.mae_price_lower / stop_distance,
                "mae_r_upper": excursion.mae_price_upper / stop_distance,
                "inclusive_tick_rows": excursion.inclusive_tick_rows,
                "strict_interior_tick_rows": excursion.strict_interior_tick_rows,
                "entry_timestamp_tie_rows": entry_tie_rows,
                "exit_timestamp_tie_rows": exit_tie_rows,
                "mfe_lower_r_reaches_one": excursion.mfe_price_lower >= stop_distance,
                "mfe_upper_r_reaches_one": excursion.mfe_price_upper >= stop_distance,
            }
        )
    return pd.DataFrame(records).sort_values("entry_time_utc", kind="stable")


def _distribution(values: pd.Series) -> dict[str, Any]:
    data = values.to_numpy(dtype=np.float64)
    if data.size == 0:
        return {"n": 0}
    return {
        "n": int(data.size),
        "mean": float(np.mean(data)),
        "median": float(np.median(data)),
        "quantiles": {str(q): float(np.quantile(data, q)) for q in (0.05, 0.25, 0.5, 0.75, 0.95)},
    }


def _write_csv_exclusive(frame: pd.DataFrame, path: Path) -> str:
    payload = frame.to_csv(index=False, lineterminator="\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError as exc:
            raise FileExistsError(f"refusing to overwrite evidence: {path}") from exc
    finally:
        temporary.unlink(missing_ok=True)
    return hashlib.sha256(payload).hexdigest()


def run(
    arms: Sequence[tuple[str, Path, Path]],
    *,
    configs: Sequence[tuple[str, Path]],
    tick_csv: Path,
    quality_report_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    if not arms:
        raise ValueError("at least one --arm is required")
    names = [name for name, _, _ in arms]
    if len(names) != len(set(names)):
        raise ValueError("arm names must be unique")
    config_names = [name for name, _ in configs]
    if len(config_names) != len(set(config_names)) or set(config_names) != set(names):
        raise ValueError("provide exactly one uniquely named config for each arm")
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite evidence directory: {output_dir}")
    if not tick_csv.is_file() or not quality_report_path.is_file():
        raise FileNotFoundError("config, tick CSV, and local quality report must exist")

    config_settings: dict[str, dict[str, Any]] = {}
    for name, path in configs:
        timezone, grid_increment = _tick_settings(path)
        config_settings[name] = {
            "path": _path_identity(path),
            "sha256": _sha256_file(path),
            "timezone": timezone,
            "price_grid_increment": grid_increment,
        }
    tick_setting_pairs = {
        (item["timezone"], item["price_grid_increment"]) for item in config_settings.values()
    }
    if len(tick_setting_pairs) != 1:
        raise ValueError("matched arm configs have different TickBook timezone/grid settings")
    timezone, price_grid_increment = next(iter(tick_setting_pairs))
    quality_report = json.loads(quality_report_path.read_text(encoding="utf-8"))
    tick_relative = tick_csv.resolve().relative_to(ROOT).as_posix()
    tick_record = next(
        (item for item in quality_report["inputs"] if item.get("path") == tick_relative), None
    )
    if tick_record is None or not tick_record.get("hash_matches_manifest"):
        raise ValueError("selected tick CSV has no matching record in the quality evidence")
    tick_hash = _sha256_file(tick_csv)
    if tick_hash != tick_record.get("observed_sha256"):
        raise ValueError("tick CSV differs from the current local quality evidence")
    tick_stat_before = tick_csv.stat()
    quality_hash = _sha256_file(quality_report_path)

    book = build_tick_book(
        tick_csv,
        tz=timezone,
        price_grid_increment=price_grid_increment,
    )
    frames = {
        name: summarize_arm(name, positions_path, fills_path, book)
        for name, positions_path, fills_path in arms
    }
    tick_stat_after = tick_csv.stat()
    if (tick_stat_before.st_ino, tick_stat_before.st_size, tick_stat_before.st_mtime_ns) != (
        tick_stat_after.st_ino,
        tick_stat_after.st_size,
        tick_stat_after.st_mtime_ns,
    ):
        raise RuntimeError("tick CSV changed while the excursion summary was running")

    output_dir.mkdir(parents=True, exist_ok=False)
    file_records: dict[str, dict[str, str]] = {}
    try:
        for name, positions_path, fills_path in arms:
            csv_path = output_dir / f"{name}_trade_excursions.csv"
            digest = _write_csv_exclusive(frames[name], csv_path)
            file_records[csv_path.name] = {"sha256": digest, "role": "per_position_excursions"}
            file_records[f"{name}_positions_source"] = {
                "path": _path_identity(positions_path),
                "sha256": _sha256_file(positions_path),
            }
            file_records[f"{name}_fills_source"] = {
                "path": _path_identity(fills_path),
                "sha256": _sha256_file(fills_path),
            }

        summaries: dict[str, Any] = {}
        for name, frame in frames.items():
            summaries[name] = {
                "completed_positions": int(len(frame)),
                "positions_with_entry_timestamp_ties": int(
                    frame["entry_timestamp_tie_rows"].gt(1).sum()
                ),
                "positions_with_exit_timestamp_ties": int(
                    frame["exit_timestamp_tie_rows"].gt(1).sum()
                ),
                "positions_with_excursion_bounds": int(
                    (
                        frame["mfe_points_lower"].ne(frame["mfe_points_upper"])
                        | frame["mae_points_lower"].ne(frame["mae_points_upper"])
                    ).sum()
                ),
                "mfe_r_lower": _distribution(frame["mfe_r_lower"]),
                "mfe_r_upper": _distribution(frame["mfe_r_upper"]),
                "mae_r_lower": _distribution(frame["mae_r_lower"]),
                "mae_r_upper": _distribution(frame["mae_r_upper"]),
                "share_reaching_one_r": {
                    "definite_lower_bound": float(frame["mfe_lower_r_reaches_one"].mean()),
                    "possible_upper_bound": float(frame["mfe_upper_r_reaches_one"].mean()),
                },
            }
        report: dict[str, Any] = {
            "schema": "qrl.selected_policy_trade_excursions.v1",
            "created_at_utc": datetime.now(UTC).isoformat(),
            "evidence_role": (
                "descriptive per-position excursion bounds from current configured TickBook quotes; "
                "not policy replay, a cost intervention, or causal loss attribution"
            ),
            "period_role": "selected_pair_development_training_2024-12-30_to_2025-12-31",
            "measurement": {
                "price_side": "bid liquidation price for longs; ask liquidation price for shorts",
                "entry_baseline": "recorded opening fill price",
                "excursion_units": "price points and price points divided by initial stop distance",
                "lower_bound": "strictly interior tick rows plus recorded entry and exit liquidation-side prices",
                "upper_bound": "all source rows in the inclusive position interval plus recorded endpoint prices",
                "endpoint_ties": "source rows at entry/exit timestamps have unresolved sub-timestamp order; bounds include/exclude them",
                "tickbook_contract": "configured TickBook side carry-forward and price-grid behavior",
                "interpretation_limits": [
                    "The export does not establish sub-timestamp chronology for tied rows.",
                    "The configured TickBook carries a missing quote side; these results measure that parser contract, not a no-carry sensitivity.",
                    "A price excursion is descriptive and does not prove a feasible alternative fill or exit policy.",
                    "The two policy arms have different trade cohorts and are summarized separately, not as a matched causal comparison.",
                    "Source clock and session labels use the selected run configuration and are not externally authoritative.",
                ],
            },
            "inputs": {
                "tick_csv": {
                    "path": tick_relative,
                    "sha256": tick_hash,
                    "bytes": tick_stat_after.st_size,
                    "local_quality_report_path": quality_report_path.resolve()
                    .relative_to(ROOT)
                    .as_posix(),
                    "local_quality_report_sha256": quality_hash,
                    "quality_report_source_sha256": tick_record["observed_sha256"],
                },
                "config": {
                    "arms": config_settings,
                    "shared_timezone": timezone,
                    "shared_price_grid_increment": price_grid_increment,
                },
                "tickbook_content_sha256": book.content_sha256(),
                "arms": [name for name, _, _ in arms],
            },
            "arm_summaries": summaries,
            "artifacts": file_records,
        }
        report_path = output_dir / "selected_policy_trade_excursions.json"
        write_json_atomic(report_path, report, default=None)
    except Exception:
        for item in output_dir.iterdir():
            if item.is_file():
                item.unlink()
        output_dir.rmdir()
        raise
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--arm",
        action="append",
        type=_parse_arm,
        default=[],
        help="completed positions/fills pair as NAME=/path/to/fills.csv (repeatable)",
    )
    parser.add_argument("--ticks-csv", type=Path, required=True)
    parser.add_argument(
        "--config",
        action="append",
        type=_parse_named_path,
        default=[],
        help="arm config as NAME=/path/to/config.yaml (repeat for each arm)",
    )
    parser.add_argument("--quality-report", type=Path, default=DEFAULT_QUALITY_REPORT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.out_dir if args.out_dir.is_absolute() else ROOT / args.out_dir
    report = run(
        args.arm,
        configs=args.config,
        tick_csv=args.ticks_csv,
        quality_report_path=args.quality_report,
        output_dir=output,
    )
    print(
        json.dumps(
            {
                "output_dir": str(output),
                "schema": report["schema"],
                "arm_summaries": report["arm_summaries"],
            },
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
