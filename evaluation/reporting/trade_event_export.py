"""Convert raw trade-fill events into stable execution and position tables."""

from __future__ import annotations

from typing import Any

import pandas as pd

_FILL_EVENT_TYPES = frozenset(
    {"open", "close", "stop_close", "tp_close", "forced_close", "eod_close", "tp_partial_close"}
)
_CLOSE_EVENT_TYPES = _FILL_EVENT_TYPES - {"open"}
_EMPTY_TRADE_COLUMNS = (
    "type",
    "position_id",
    "fill_id",
    "time",
    "bar",
    "direction",
    "price",
    "pnl",
    "net_pnl",
    "position_net_pnl",
    "position_complete",
    "reason",
    "fill_quote_source",
)
_POSITION_COLUMNS = (
    "position_id",
    "direction",
    "thesis_candidate_id",
    "thesis_schema_version",
    "primary_idea",
    "primary_setup_timeframe",
    "primary_direction",
    "thesis_decision_time",
    "entry_time",
    "exit_time",
    "entry_price",
    "exit_price",
    "sl_price",
    "sl_ref",
    "sl_timeframe",
    "tp_price",
    "tp_ref",
    "tp_timeframe",
    "close_pnl",
    "net_pnl",
    "position_net_pnl",
    "fill_count",
    "completed",
    "holding_seconds",
    "exit_reason",
    "reconstruction_status",
)
_POSITION_ENTRY_METADATA = (
    "thesis_candidate_id",
    "thesis_schema_version",
    "primary_idea",
    "primary_setup_timeframe",
    "primary_direction",
    "thesis_decision_time",
    "sl_price",
    "sl_ref",
    "sl_timeframe",
    "tp_price",
    "tp_ref",
    "tp_timeframe",
)


def _fill_events(trades: pd.DataFrame) -> pd.DataFrame:
    """Return actual execution events, excluding rejects and order-only records."""
    if trades.empty or "type" not in trades.columns:
        return pd.DataFrame(columns=_EMPTY_TRADE_COLUMNS)
    return trades.loc[trades["type"].astype(str).isin(_FILL_EVENT_TYPES)].copy()


def _position_summaries(trades: pd.DataFrame) -> pd.DataFrame:
    """Reconstruct position-level rows from identified raw fill events."""
    fills = _fill_events(trades)
    if fills.empty:
        return pd.DataFrame(columns=_POSITION_COLUMNS)

    records: list[dict[str, Any]] = []
    identified = (
        fills["position_id"].notna()
        if "position_id" in fills.columns
        else pd.Series(False, index=fills.index)
    )
    unidentified_fills = fills.loc[~identified]
    for event_index, (_, event) in enumerate(unidentified_fills.iterrows()):
        is_open = str(event.get("type", "")) == "open"
        is_close = str(event.get("type", "")) in _CLOSE_EVENT_TYPES
        records.append(
            {
                "position_id": None,
                "direction": event.get("direction"),
                **{key: event.get(key) for key in _POSITION_ENTRY_METADATA},
                "entry_time": event.get("time") if is_open else None,
                "exit_time": event.get("time") if is_close else None,
                "entry_price": event.get("price") if is_open else None,
                "exit_price": event.get("price") if is_close else None,
                "close_pnl": event.get("pnl") if is_close else None,
                "net_pnl": event.get("net_pnl") if is_close else None,
                "position_net_pnl": event.get("position_net_pnl"),
                "fill_count": 1,
                "completed": bool(event.get("position_complete", False)),
                "holding_seconds": None,
                "exit_reason": event.get("reason"),
                "reconstruction_status": f"unidentified_event_{event_index}",
            }
        )

    if identified.any():
        identified_fills = fills.loc[identified]
        for position_id, events in identified_fills.groupby("position_id", sort=True, dropna=True):
            opens = events.loc[events["type"].astype(str) == "open"]
            closes = events.loc[events["type"].astype(str).isin(_CLOSE_EVENT_TYPES)]
            entry = opens.iloc[0] if not opens.empty else None
            last_close = closes.iloc[-1] if not closes.empty else None
            entry_metadata = entry if entry is not None else events.iloc[0]
            pnl_values = pd.to_numeric(closes.get("pnl", pd.Series(dtype=float)), errors="coerce")
            if "net_pnl" in closes.columns:
                net_values = pd.to_numeric(closes["net_pnl"], errors="coerce")
                if "pnl" in closes.columns:
                    net_values = net_values.fillna(pnl_values)
            else:
                net_values = pnl_values
            completed_values = (
                closes.get("position_complete", pd.Series(False, index=closes.index))
                .fillna(False)
                .astype(bool)
            )
            position_pnl_values = (
                pd.to_numeric(closes["position_net_pnl"], errors="coerce").dropna()
                if "position_net_pnl" in closes.columns
                else pd.Series(dtype=float)
            )
            final_net = (
                float(position_pnl_values.iloc[-1])
                if not position_pnl_values.empty
                else (float(net_values.sum()) if not closes.empty else None)
            )
            entry_time = None if entry is None else entry.get("time")
            exit_time = None if last_close is None else last_close.get("time")
            holding_seconds = None
            if entry_time is not None and exit_time is not None:
                try:
                    holding_seconds = float(
                        (pd.Timestamp(exit_time) - pd.Timestamp(entry_time)).total_seconds()
                    )
                except (TypeError, ValueError):
                    holding_seconds = None
            records.append(
                {
                    "position_id": str(position_id),
                    "direction": (
                        entry.get("direction")
                        if entry is not None
                        else events.iloc[0].get("direction")
                    ),
                    **{key: entry_metadata.get(key) for key in _POSITION_ENTRY_METADATA},
                    "entry_time": entry_time,
                    "exit_time": exit_time,
                    "entry_price": None if entry is None else entry.get("price"),
                    "exit_price": None if last_close is None else last_close.get("price"),
                    "close_pnl": float(pnl_values.sum()) if not closes.empty else None,
                    "net_pnl": float(net_values.sum()) if not closes.empty else None,
                    "position_net_pnl": final_net,
                    "fill_count": int(len(events)),
                    "completed": bool(completed_values.any()),
                    "holding_seconds": holding_seconds,
                    "exit_reason": None if last_close is None else last_close.get("reason"),
                    "reconstruction_status": "identified_by_position_id",
                }
            )
    return pd.DataFrame.from_records(records, columns=_POSITION_COLUMNS)
