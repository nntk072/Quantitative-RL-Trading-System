"""Independently reconstruct saved account equity from raw bars and fill events.

The audit is intentionally fail-closed: it requires exact raw-source frame
identity, a one-to-one bar mapping for every equity valuation, and a complete
identified fill ledger. It never uses saved PnL fields to calculate cashflows.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd
from omegaconf import OmegaConf

from configuration.paths import repository_root
from evaluation.reporting.run_manifest import dataframe_sha256
from market_data.loading.bars import load_bars
from market_data.splits.definitions import split_bars
from market_data.transforms.cleaning import clean
from market_data.transforms.price_grid import configured_price_grid_increment, quantize_bar_prices
from market_data.transforms.sessions import add_session_id, add_session_labels

ROOT = repository_root(__file__)
FILL_TYPES = {
    "open",
    "close",
    "stop_close",
    "tp_close",
    "forced_close",
    "eod_close",
    "tp_partial_close",
}
CLOSE_TYPES = FILL_TYPES - {"open"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_default(value: Any) -> Any:
    """Convert NumPy scalar values from pandas results to native JSON values."""
    if hasattr(value, "item"):
        return value.item()
    raise TypeError(f"unsupported JSON value: {type(value).__name__}")


def _rebuild_frame(config_path: Path, raw_path: Path, partition: str) -> tuple[pd.DataFrame, str]:
    cfg = OmegaConf.load(config_path)
    bars = load_bars(raw_path)
    bars = quantize_bar_prices(bars, configured_price_grid_increment(cfg))
    bars = clean(bars, tz=str(cfg.data.tz))
    bars = add_session_labels(bars, tz=str(cfg.data.tz), ny_end=str(cfg.session.end))
    bars = add_session_id(bars)
    train, test = split_bars(
        bars,
        str(cfg.data.split.train_end),
        str(cfg.data.split.test_start),
        str(cfg.data.split.train_start),
    )
    frame = train if partition == "training" else test
    return frame, dataframe_sha256(frame)


def _run_report(
    *,
    name: str,
    report_path: Path,
    identity_partition: dict[str, Any],
    abs_tolerance: float,
) -> dict[str, Any]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    run_dir = Path(report["inputs"]["equity.csv"]["path"]).parent
    partition = "training" if name.endswith("training") else "testing"
    raw_identity = identity_partition["raw_source_reconstructed_frame"]
    raw_path = Path(raw_identity["path"])
    reanalysis = json.loads((run_dir.parent / "reanalysis_manifest.json").read_text())
    source_run = Path(reanalysis["source_run"])
    config_path = source_run / "config.yaml"
    expected_config_hash = reanalysis["source_config_sha256"]
    config_hash = _sha256(config_path)
    raw_hash = _sha256(raw_path)

    frame, frame_hash = _rebuild_frame(config_path, raw_path, partition)
    expected_frame = identity_partition["expected_run_frame"]
    identity_ok = (
        config_hash == expected_config_hash
        and raw_hash == raw_identity["raw_sha256"]
        and frame_hash == expected_frame["sha256"]
        and len(frame) == int(expected_frame["rows"])
        and [str(c) for c in frame.columns] == list(expected_frame["columns"])
        and str(frame.index.min()) == expected_frame["start"]
        and str(frame.index.max()) == expected_frame["end"]
    )

    equity_path = run_dir / "equity.csv"
    trades_path = run_dir / "trades.csv"
    equity = pd.read_csv(equity_path, index_col=0, parse_dates=True)
    if list(equity.columns) != ["equity"]:
        raise ValueError(f"{name}: unexpected equity columns {list(equity.columns)}")
    equity.index = pd.DatetimeIndex(equity.index)
    if equity.index.tz is None:
        raise ValueError(f"{name}: equity timestamps must be timezone-aware")
    equity.index = equity.index.tz_convert("UTC")
    values = pd.to_numeric(equity["equity"], errors="coerce").to_numpy(dtype=float)

    cfg = OmegaConf.load(config_path)
    initial = float(cfg.account.initial_balance)
    contract_size = float(cfg.account.contract_size)
    point_size = float(cfg.costs.point_size)
    commission_per_lot = float(cfg.costs.commission_per_lot)
    bars = frame.copy()
    bars.index = pd.DatetimeIndex(bars.index).tz_convert("UTC")
    bar_times_ns = pd.DatetimeIndex(bars.index).to_numpy(dtype="datetime64[ns]").view("i8")
    bar_records = [
        {str(key): value for key, value in record.items()}
        for record in bars.to_dict(orient="records")
    ]
    bar_by_ns: dict[int, dict[str, Any]] = {
        int(timestamp): record for timestamp, record in zip(bar_times_ns, bar_records, strict=True)
    }
    with trades_path.open(encoding="utf-8") as source:
        trades = pd.read_csv(source, low_memory=False)
    fills = trades.loc[trades["type"].astype(str).isin(FILL_TYPES)].copy()
    fills["event_time"] = pd.to_datetime(
        fills["fill_time"], format="mixed", utc=True, errors="coerce"
    )
    if fills["event_time"].isna().any():
        raise ValueError(f"{name}: fill rows contain missing/invalid fill times")
    fills = fills.sort_values(["event_time"], kind="stable").reset_index(drop=True)
    fill_times = pd.DatetimeIndex(fills["event_time"])
    if fills["position_id"].isna().any() or fills["position_id"].astype(str).str.len().eq(0).any():
        raise ValueError(f"{name}: fill rows contain unidentified position IDs")

    positions: dict[str, dict[str, float]] = {}
    cash = initial
    fill_cursor = 0
    previous_time: pd.Timestamp | None = None
    reconstructed: list[float] = []
    row_diagnostics: list[dict[str, Any]] = []
    bar_mapping_failures = 0
    calculation_errors: list[dict[str, Any]] = []
    close_pnl_differences: list[float] = []
    event_count_by_type: dict[str, int] = {}

    for row_number, (valuation_time, saved_equity) in enumerate(
        zip(equity.index, values, strict=True)
    ):
        market_time: pd.Timestamp | None = None
        applied_events: list[str] = []
        if row_number > 0:
            market_time = (valuation_time - pd.Timedelta(minutes=1)).floor("min")
            bar = bar_by_ns.get(int(market_time.value))
            if bar is None:
                bar_mapping_failures += 1
                calculated = float("nan")
            else:
                bid = float(bar["close"])
                spread = float(bar["spread"])
                ask = bid + spread * point_size
                open_pnl = sum(
                    (bid if p["direction"] == 1 else ask - 0.0)
                    * p["direction"]
                    * p["size"]
                    * contract_size
                    - p["entry_price"] * p["direction"] * p["size"] * contract_size
                    for p in positions.values()
                )
                # Fill events after this bar-close mark are applied below.
                calculated = cash + open_pnl

        else:
            calculated = initial

        event_start = fill_cursor
        while fill_cursor < len(fill_times) and fill_times[fill_cursor] <= valuation_time:
            event = fills.iloc[fill_cursor]
            event_time = fill_times[fill_cursor]
            if previous_time is not None and event_time <= previous_time:
                calculation_errors.append(
                    {
                        "row": row_number,
                        "reason": "fill_not_after_previous_equity_time",
                        "time": str(event_time),
                    }
                )
            kind = str(event["type"])
            applied_events.append(f"{kind}:{event.get('position_id', '')}")
            event_count_by_type[kind] = event_count_by_type.get(kind, 0) + 1
            position_id = str(event["position_id"])
            price = float(event["price"])
            if kind == "open":
                size = float(event["lots"])
                direction = int(float(event["direction"]))
                if position_id in positions or size <= 0 or direction not in (-1, 1):
                    calculation_errors.append(
                        {
                            "row": row_number,
                            "reason": "invalid_or_duplicate_open",
                            "position_id": position_id,
                        }
                    )
                else:
                    cash -= commission_per_lot * size
                    positions[position_id] = {
                        "entry_price": price,
                        "direction": float(direction),
                        "size": size,
                    }
            elif kind in CLOSE_TYPES:
                position = positions.get(position_id)
                size = float(event["size"])
                if position is None or size <= 0 or size > position["size"] + 1e-8:
                    calculation_errors.append(
                        {
                            "row": row_number,
                            "reason": "close_without_sufficient_open_quantity",
                            "position_id": position_id,
                            "size": size,
                        }
                    )
                else:
                    pnl = (price - position["entry_price"]) * position[
                        "direction"
                    ] * size * contract_size - commission_per_lot * size
                    cash += pnl
                    # close_trade books realized PnL and resets equity to
                    # balance before any residual position is re-marked.
                    calculated = cash
                    if event.get("pnl") is not None and math.isfinite(float(event["pnl"])):
                        close_pnl_differences.append(pnl - float(event["pnl"]))
                    position["size"] -= size
                    if position["size"] <= 1e-8:
                        positions.pop(position_id)
                    else:
                        # Broker.close_position marks a remaining partial
                        # position at the executable close-side price.
                        position["last_mark"] = price
            fill_cursor += 1

        if fill_cursor > event_start and row_number > 0:
            # A tick partial-close leaves the remainder marked at that same
            # close-side execution quote; a later event can replace it.
            last_event = fills.iloc[fill_cursor - 1]
            if str(last_event["type"]) in CLOSE_TYPES:
                pos = positions.get(str(last_event["position_id"]))
                if pos is not None and "last_mark" in pos:
                    mark = float(pos.pop("last_mark"))
                    pnl = (
                        (mark - pos["entry_price"]) * pos["direction"] * pos["size"] * contract_size
                    )
                    calculated = cash + pnl

        reconstructed.append(float(calculated))
        if math.isfinite(float(calculated)) and math.isfinite(float(saved_equity)):
            row_diagnostics.append(
                {
                    "row": row_number,
                    "valuation_time_utc": str(valuation_time),
                    "market_bar_time_utc": str(market_time) if market_time is not None else None,
                    "saved_equity": float(saved_equity),
                    "reconstructed_equity": float(calculated),
                    "difference": float(calculated - saved_equity),
                    "cash_balance": float(cash),
                    "open_positions": {
                        key: {name: float(value) for name, value in position.items()}
                        for key, position in positions.items()
                    },
                    "events_applied": applied_events,
                }
            )
        previous_time = valuation_time

    diffs = [
        a - b
        for a, b in zip(reconstructed, values, strict=True)
        if math.isfinite(a) and math.isfinite(b)
    ]
    absolute = [abs(value) for value in diffs]
    all_fills_consumed = fill_cursor == len(fills)
    status = (
        "exact_reconstruction"
        if identity_ok
        and not bar_mapping_failures
        and not calculation_errors
        and all_fills_consumed
        and len(diffs) == len(values)
        and max(absolute, default=0.0) <= abs_tolerance
        else "reconciliation_mismatch"
    )
    worst_index = max(range(len(diffs)), key=lambda i: abs(diffs[i]), default=None)
    return {
        "name": name,
        "partition": partition,
        "status": status,
        "input_identity": {
            "exact_rebuilt_frame_match": identity_ok,
            "raw_path": raw_path.as_posix(),
            "raw_sha256": raw_hash,
            "config_path": config_path.as_posix(),
            "config_sha256": config_hash,
            "reanalysis_manifest_path": (run_dir.parent / "reanalysis_manifest.json").as_posix(),
            "reanalysis_manifest_sha256": _sha256(run_dir.parent / "reanalysis_manifest.json"),
            "historical_run_manifest": identity_partition["historical_run_manifest"],
            "frame_sha256": frame_hash,
            "expected_frame_sha256": expected_frame["sha256"],
        },
        "inputs": {
            "equity_path": equity_path.as_posix(),
            "equity_sha256": _sha256(equity_path),
            "fills_path": trades_path.as_posix(),
            "fills_sha256": _sha256(trades_path),
            "equity_rows": len(values),
            "fill_event_rows": len(fills),
            "fill_event_types": event_count_by_type,
        },
        "calculation": {
            "initial_balance": initial,
            "contract_size": contract_size,
            "point_size": point_size,
            "commission_per_lot": commission_per_lot,
            "valuation_convention": "At valuation T, mark pre-existing positions to the exact raw M1 bar at floor(T - 1 minute); then apply fill events through T. Remaining quantity after a partial close is re-marked at the recorded close-side fill price, following Broker.close_position.",
            "cashflows_calculated_from_fill_prices": True,
            "saved_pnl_used_for_calculation": False,
        },
        "comparison": {
            "bar_mapping_failure_count": bar_mapping_failures,
            "calculation_error_count": len(calculation_errors),
            "calculation_errors_first_20": calculation_errors[:20],
            "unconsumed_fill_event_count": len(fills) - fill_cursor,
            "ending_open_position_count": len(positions),
            "ending_open_position_ids": sorted(positions),
            "close_pnl_abs_difference_max": max(map(abs, close_pnl_differences), default=0.0),
            "max_abs_equity_difference": max(absolute, default=None),
            "mean_abs_equity_difference": sum(absolute) / len(absolute) if absolute else None,
            "within_tolerance_count": sum(v <= abs_tolerance for v in absolute),
            "tolerance_usd": abs_tolerance,
            "worst_row_index": worst_index,
            "worst_valuation_time_utc": str(equity.index[worst_index])
            if worst_index is not None
            else None,
            "worst_reconstructed_equity": reconstructed[worst_index]
            if worst_index is not None
            else None,
            "worst_saved_equity": values[worst_index] if worst_index is not None else None,
            "worst_difference": diffs[worst_index] if worst_index is not None else None,
            "largest_discrepancies": sorted(
                row_diagnostics, key=lambda item: abs(item["difference"]), reverse=True
            )[:20],
        },
    }


def audit_saved_equity_to_fills(
    packet_root: Path, identity_path: Path, output: Path, abs_tolerance: float = 1e-6
) -> dict[str, Any]:
    packet = json.loads((packet_root / "evidence_manifest.json").read_text(encoding="utf-8"))
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    partitions = {
        (str(value["arm"]).lower(), str(value["partition"])): value
        for value in identity["partitions"]
    }
    results = []
    for report_metadata in packet["reports"]:
        report_path = Path(report_metadata["path"])
        name = report_path.name
        if name not in {
            "a4a_training.json",
            "a4a_testing.json",
            "a4b_training.json",
            "a4b_testing.json",
        }:
            continue
        arm, partition = name.removesuffix(".json").split("_")
        results.append(
            _run_report(
                name=name.removesuffix(".json"),
                report_path=packet_root / name,
                identity_partition=partitions[(arm, partition)],
                abs_tolerance=abs_tolerance,
            )
        )
    overall = (
        "exact_reconstruction"
        if len(results) == 4 and all(r["status"] == "exact_reconstruction" for r in results)
        else "reconciliation_mismatch"
    )
    payload = {
        "schema_version": 1,
        "scope": "Independent account-equity reconstruction from hash-verified raw M1 bars and fill prices for the four preserved A4 partitions.",
        "status": overall,
        "analysis_script": Path(__file__).resolve().as_posix(),
        "analysis_script_sha256": _sha256(Path(__file__)),
        "input_identity_report": {
            "path": identity_path.resolve().as_posix(),
            "sha256": _sha256(identity_path),
        },
        "results": results,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=_json_default) + "\n",
        encoding="utf-8",
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--packet-root",
        type=Path,
        default=ROOT / "evidence/research/simulator_execution_parity/equity_series_reconciliation",
    )
    parser.add_argument(
        "--identity",
        type=Path,
        default=ROOT
        / "evidence/research/simulator_execution_parity/equity_series_reconciliation/source_reconstructed_bar_identity.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT
        / "evidence/research/simulator_execution_parity/equity_series_reconciliation/equity_fill_reconciliation.json",
    )
    parser.add_argument("--abs-tolerance", type=float, default=1e-6)
    args = parser.parse_args()
    result = audit_saved_equity_to_fills(
        args.packet_root, args.identity, args.output, args.abs_tolerance
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "output": args.output.as_posix(),
                "partitions": len(result["results"]),
            }
        )
    )
    return 0 if result["status"] == "exact_reconstruction" else 1


if __name__ == "__main__":
    raise SystemExit(main())
