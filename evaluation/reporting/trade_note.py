"""Human-readable trade note for the per-trade order charts.

Both renderers (matplotlib PNG and plotly HTML) build their caption here so the
two always agree. Nothing here changes a price, a level, or the environment; it
only turns an open/close row into plain-language lines.
"""

from __future__ import annotations

import ast
import math
from collections.abc import Mapping, Sequence
from typing import Any

_SIDE_TF: tuple[str, ...] = ("M1", "M3", "M5", "M10", "M15", "M30", "H1", "H2", "H4", "D1", "W1")

_SIMPLE: dict[str, str] = {
    "last_swing_low": "swing low (M1)",
    "last_swing_high": "swing high (M1)",
    "asian_low": "Asia session low",
    "asian_high": "Asia session high",
    "london_low": "London session low",
    "london_high": "London session high",
    "prev_day_high": "previous day high",
    "prev_day_low": "previous day low",
    "yesterday_high": "previous day high",
    "yesterday_low": "previous day low",
    "prev_day_high_low": "previous day high/low",
    "ctx_prev_week_high": "previous week high",
    "ctx_prev_week_low": "previous week low",
    "sweep_high_level": "swept liquidity high",
    "sweep_low_level": "swept liquidity low",
    "smt_swing": "Smart Money Technique divergence (SMT) swing",
    "sl_reference": "strategy stop reference",
    "ema_21": "EMA-21 exit",
}

_LEVEL_ENTRY: dict[str, str] = {
    "asian_low": "swept Asia session low",
    "asian_high": "swept Asia session high",
    "london_low": "swept London session low",
    "london_high": "swept London session high",
    "prev_day_high": "previous day high",
    "prev_day_low": "previous day low",
    "ctx_prev_week_high": "previous week high",
    "ctx_prev_week_low": "previous week low",
}

_MANIPULATION: dict[str, str] = {
    "done": 'manipulation "done" (phase completed)',
    "none": "no manipulation yet",
    "against": "PO3 manipulation is currently against this trade direction",
}

_ENTRY_IDEA_LABELS: dict[str, str] = {
    "po3": "PO3 setup",
    "order_block": "Order Block reaction",
    "standard_deviation": "Fib-like swing retracement (0.5-0.786)",
    "fvg_retest": "FVG/IFVG reaction",
}

_ENTRY_SETUP_LABELS: dict[str, str] = {
    "po3": "PO3 setup",
    "order_block": "Order Block reaction",
    "standard_deviation": "swing retracement",
    "fvg_retest": "FVG/IFVG reaction",
    "sweep": "liquidity sweep context",
    "swing": "swing context",
}


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value).strip()


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def pretty_ref(name: Any) -> str:
    """Raw level reference in plain language.

    ``asian_low|H1_last_swing_low`` becomes ``Asia session low + swing low (H1)``.
    An empty or ``nan`` input returns ``""``.
    """
    text = _text(name)
    if not text or text.lower() == "nan":
        return ""
    out: list[str] = []
    for part in (p.strip() for p in text.split("|")):
        if not part:
            continue
        if part in _SIMPLE:
            out.append(_SIMPLE[part])
            continue
        hit = next(
            (
                (tf, swing)
                for tf in _SIDE_TF
                for swing in ("last_swing_low", "last_swing_high")
                if part == f"{tf}_{swing}"
            ),
            None,
        )
        if hit is not None:
            out.append(f"swing {'low' if hit[1].endswith('low') else 'high'} ({hit[0]})")
            continue
        timeframe = next((tf for tf in _SIDE_TF if part.startswith(f"{tf}_")), None)
        ref_name = part[len(timeframe) + 1 :] if timeframe else part
        suffix = f" ({timeframe})" if timeframe else ""
        if "ifvg" in ref_name:
            out.append(
                f"Inverse Fair Value Gap ({'bullish' if 'bull' in ref_name else 'bearish'}){suffix}"
            )
            continue
        if "fvg" in ref_name:
            out.append(f"Fair Value Gap ({'bullish' if 'bull' in ref_name else 'bearish'}){suffix}")
            continue
        if part.startswith("dev"):
            deviation = part.split("_", 1)[-1]
            try:
                multiple = float(deviation)
            except ValueError:
                out.append(f"range projection {deviation}x")
                continue
            if multiple == 0.0:
                out.append("swing low (0x range projection)")
            elif multiple == 1.0:
                out.append("swing high (1x range projection)")
            else:
                out.append(f"range projection {multiple:g}x")
            continue
        out.append((f"{timeframe} " if timeframe else "") + ref_name.replace("_", " "))
    return " + ".join(out)


def entry_reason(open_row: Any) -> str:
    """Why the trade was taken, from columns already on the open row.

    ``enforce_gate`` is false in both idea configs, so this describes the setup
    the strategy offered, not a filter that blocked other trades.
    """
    parts: list[str] = []
    raw_ideas = open_row.get("entry_ideas")
    if _text(raw_ideas):
        idea_names = [str(value) for value in _sequence_value(raw_ideas)]
        timeframe_map = _mapping_value(open_row.get("entry_idea_timeframes"))
        if idea_names:
            for idea in idea_names:
                label = _ENTRY_IDEA_LABELS.get(idea, idea.replace("_", " "))
                raw_timeframes = timeframe_map.get(idea, [])
                timeframes = (
                    [raw_timeframes]
                    if isinstance(raw_timeframes, str)
                    else [str(value) for value in _sequence_value(raw_timeframes)]
                )
                timeframe_text = f" ({', '.join(timeframes)})" if timeframes else ""
                parts.append(label + timeframe_text)
            if len(idea_names) > 1:
                parts.append(f"{len(idea_names)} entry ideas overlap at the signal")
        else:
            candidate_types = [
                str(value) for value in _sequence_value(open_row.get("entry_setup_types"))
            ]
            candidate_parts = [
                _ENTRY_SETUP_LABELS.get(value, value.replace("_", " ")) for value in candidate_types
            ]
            if candidate_parts:
                origin_time = _clock(open_row.get("entry_origin_time"))
                origin_text = f" formed at {origin_time}" if origin_time else " formed earlier"
                parts.append(
                    "candidate"
                    + origin_text
                    + ": "
                    + " + ".join(candidate_parts)
                    + "; policy chose to trigger at this signal bar"
                )
            else:
                parts.append("no named entry-idea signal or saved candidate")
        zones = _sequence_value(open_row.get("entry_idea_zones"))
        if zones:
            zone_text: list[str] = []
            for zone in zones:
                if not isinstance(zone, Mapping):
                    continue
                family = _text(zone.get("family")).upper()
                if _text(zone.get("idea")) == "po3" and family in {"FVG", "IFVG"}:
                    family = "FVG → IFVG" if family == "IFVG" else "FVG origin"
                timeframe = _text(zone.get("timeframe"))
                side = _text(zone.get("side"))
                low = _number(zone.get("low"))
                high = _number(zone.get("high"))
                if low is None or high is None:
                    continue
                zone_text.append(f"{family} {side} ({timeframe}) {low:.2f}-{high:.2f}")
            if zone_text:
                parts.append("linked zones: " + "; ".join(zone_text))
    else:
        level = _LEVEL_ENTRY.get(_text(open_row.get("level_type")))
        if level is None:
            level = pretty_ref(open_row.get("level_type"))
        parts.append(level or "strategy offered this side (no swept level)")
    state = _text(open_row.get("manipulation")).lower()
    if state:
        manipulation_text = _MANIPULATION.get(state, f"manipulation {state}")
        if state == "against":
            direction = _number(open_row.get("direction"))
            side = "long" if direction is not None and direction > 0 else "short"
            manipulation_text = f"PO3 context currently opposes this {side}"
            if _text(open_row.get("strategy")) == "baseline":
                manipulation_text += "; baseline entry logic does not require PO3 confirmation"
        parts.append(manipulation_text)
    phase = _number(open_row.get("distribution_phase"))
    if phase is not None and phase > 0.0:
        parts.append("PO3 distribution active")
    return "Entry: " + ", ".join(parts)


def _sequence_value(raw: Any) -> list[Any]:
    if isinstance(raw, str):
        try:
            raw = ast.literal_eval(raw)
        except (SyntaxError, ValueError):
            return []
    if raw is None or isinstance(raw, (bytes, float, int, bool)):
        return []
    try:
        return list(raw)
    except TypeError:
        return []


def _mapping_value(raw: Any) -> Mapping[str, Any]:
    if isinstance(raw, str):
        try:
            raw = ast.literal_eval(raw)
        except (SyntaxError, ValueError):
            return {}
    return raw if isinstance(raw, Mapping) else {}


def _clock(value: Any) -> str:
    text = _text(value)
    if len(text) >= 23 and text[19] == ".":
        return text[11:23]
    return text[11:19] if len(text) >= 19 else (text[11:16] if len(text) >= 16 else text)


def build_trade_note(
    open_row: Any,
    close_row: Any,
    *,
    entry_price: float,
    exit_price: float,
    direction: int,
    pnl: float,
    pnl_calc: float,
    duration_mins: int,
    duration_secs: int,
    lots: float,
    close_reason_detail: str,
    extra_notes: Sequence[str] | None = None,
    position_events: Any = None,
    signal_time: Any = None,
    entry_fill_time: Any = None,
) -> list[str]:
    """Caption lines shown under both subplots of one trade chart."""
    dir_label = "Long" if direction == 1 else "Short" if direction == -1 else "Flat"
    fill_source = _text(open_row.get("fill_quote_source"))
    fill_kind = "tick fill" if fill_source == "tick" else "logged fill"
    signal = _clock(signal_time) if _text(signal_time) else "not recorded"
    entry_time_value = entry_fill_time if _text(entry_fill_time) else open_row.get("time")
    entry_time = _clock(entry_time_value)
    lines = [
        f"ENTRY: {dir_label} | Signal {signal} | {fill_kind} {entry_time} @ {entry_price:.2f}"
        f" | Volume {lots:.2f} lots | Reason: {entry_reason(open_row).removeprefix('Entry: ')}",
        f"RESULT: Net realized PnL ${pnl:+.2f} | Fill-price calc ${pnl_calc:+.2f}"
        f" | Difference ${pnl - pnl_calc:+.2f} | Closed {_clock(close_row.get('time'))}"
        f" ({duration_mins}m{duration_secs:02d}s), {close_reason_detail}",
    ]

    exit_mode = _text(open_row.get("exit_mode"))
    sl_ref = _text(open_row.get("sl_ref"))
    tp_ref = _text(open_row.get("tp_ref"))
    sl_price = _number(open_row.get("sl_price"))
    tp_price = _number(open_row.get("tp_price"))
    ema_exit = exit_mode == "ema_21" or tp_ref.lower() == "ema_21"

    stop_activity: list[str] = []
    target_activity: list[str] = []
    if sl_price is not None:
        distance = abs(entry_price - sl_price)
        stop_activity.append(
            f"SL 1 initial {sl_price:.2f} ({pretty_ref(sl_ref) or 'stop'}, {distance:.2f} points from entry)"
        )
    else:
        stop_activity.append("SL 1 initial price not recorded")

    target_legs = _sequence_value(open_row.get("tp_legs"))
    target_fraction_total = 0.0
    target_count = 0
    if target_legs:
        for leg in target_legs:
            if not isinstance(leg, dict):
                continue
            leg_number = leg.get("leg", "?")
            target_price = _number(leg.get("executed_price"))
            fraction = _number(leg.get("lot_fraction"))
            if fraction is not None:
                target_fraction_total += fraction
            target_count += 1
            reference = pretty_ref(leg.get("reference"))
            if target_price is not None:
                fraction_text = f" ({fraction:.1%} of entry size)" if fraction is not None else ""
                target_activity.append(
                    f"TP {leg_number} {target_price:.2f}"
                    + (f" ({reference})" if reference else "")
                    + fraction_text
                )
    elif tp_price is not None and not ema_exit:
        target_activity.append(f"TP 1 {tp_price:.2f} ({pretty_ref(tp_ref) or 'target'})")
    runner_fraction = _number(open_row.get("ema_runner_fraction")) or 0.0
    if ema_exit and runner_fraction > 0.0 and target_count:
        target_activity.append(
            f"TP {target_count + 1} EMA-21 runner exit after TP {target_count} partial target(s)"
            f" ({runner_fraction:.1%} of entry size; target legs close {target_fraction_total:.1%})"
        )
    if ema_exit and tp_price is None:
        target_activity.append("No fixed TP; EMA-21 closed the full position in this run")

    if position_events is not None and hasattr(position_events, "iterrows"):
        sl_updates = position_events.loc[position_events["type"].eq("sl_update")]
        for update_i, (_, update) in enumerate(sl_updates.iterrows(), start=2):
            effective = update.get("effective_time")
            if not _text(effective):
                effective = update.get("time")
            reconstructed = (
                " (reconstructed from saved config)"
                if "reconstructed" in _text(update.get("reason"))
                else ""
            )
            stop_activity.append(
                f"SL {update_i} moved {_clock(effective)} to {float(update['price']):.2f}"
                f" ({_text(update.get('reason')).replace('_', ' ')}{reconstructed})"
            )
        tp_updates = position_events.loc[position_events["type"].eq("tp_update")]
        for _, update in tp_updates.iterrows():
            effective = update.get("effective_time")
            if not _text(effective):
                effective = update.get("time")
            slot = _number(update.get("tp_slot"))
            target_activity.append(
                f"TP {int(slot) if slot is not None else '?'} updated {_clock(effective)} "
                f"to {float(update['price']):.2f} ({_text(update.get('reason')).replace('_', ' ')})"
            )
        for _, fill in position_events.loc[
            position_events["type"].isin(
                ["tp_partial_close", "tp_close", "stop_close", "close", "forced_close", "eod_close"]
            )
        ].iterrows():
            kind = _text(fill.get("type"))
            reason = _text(fill.get("reason")).replace("_", " ")
            fill_time = fill.get("actual_tick_time")
            if not _text(fill_time):
                fill_time = fill.get("time")
            source_value = _text(fill.get("fill_quote_source"))
            source = "tick fill" if source_value == "tick" else source_value or "logged execution"
            tp_slot = _number(fill.get("tp_slot"))
            size = _number(fill.get("size"))
            size_text = f" | {size:.2f} lots" if size is not None else ""
            fill_pnl = _number(fill.get("pnl"))
            pnl_text = f" | realized ${fill_pnl:+.2f}" if fill_pnl is not None else ""
            if kind == "tp_partial_close":
                label = f"TP {int(tp_slot) if tp_slot is not None else '?'} partial fill"
                target_activity.append(
                    f"{label} {_clock(fill_time)} @ {float(fill['price']):.2f} ({source})"
                    f"{size_text}{pnl_text} ({reason})"
                )
            elif kind == "tp_close":
                label = f"TP {int(tp_slot) if tp_slot is not None else '?'} fill"
                target_activity.append(
                    f"{label} {_clock(fill_time)} @ {float(fill['price']):.2f} ({source})"
                    f"{size_text}{pnl_text} ({reason})"
                )
            elif "stop" in kind or "sl" in reason:
                stop_activity.append(
                    f"SL fill {_clock(fill_time)} @ {float(fill['price']):.2f} ({source})"
                    f"{size_text}{pnl_text} ({reason})"
                )
            else:
                target_activity.append(
                    f"Other exit fill {_clock(fill_time)} @ {float(fill['price']):.2f} ({source})"
                    f"{size_text}{pnl_text} ({reason})"
                )

    lines.append("STOP LOSS (SL): " + "; ".join(stop_activity))
    lines.append("TAKE PROFIT (TP): " + "; ".join(target_activity or ["no fixed target recorded"]))
    for note in extra_notes or ():
        lines.append(f"Context: {note}")
    return lines


def _short_reference(value: Any) -> str:
    text = pretty_ref(value)
    for long, short in (
        ("Inverse Fair Value Gap", "IFVG"),
        ("Fair Value Gap", "FVG"),
        ("Order Block", "OB"),
        ("Asia session", "Asia"),
        ("London session", "London"),
        ("bullish", "bull"),
        ("bearish", "bear"),
    ):
        text = text.replace(long, short)
    return text


def _plot_reason(open_row: Any) -> str:
    """Short, plot-only reason that keeps FVG and IFVG reactions distinct."""
    setup_types = {str(value) for value in _sequence_value(open_row.get("entry_setup_types"))}
    raw_ideas = [str(value) for value in _sequence_value(open_row.get("entry_ideas"))]
    zones = _sequence_value(open_row.get("entry_idea_zones"))
    families = {str(zone.get("family", "")).lower() for zone in zones if isinstance(zone, Mapping)}
    reasons: list[str] = []
    labels = {
        "po3": "PO3",
        "order_block": "OB reaction",
        "standard_deviation": "Fib retracement",
        "sweep": "liquidity sweep",
        "swing": "swing",
    }
    for idea in (*raw_ideas, *sorted(setup_types)):
        if idea in {"fvg_retest", "fvg_reaction", "ifvg_reaction", "ifvg"}:
            if idea in {"ifvg_reaction", "ifvg"}:
                gap_reasons = ["IFVG reaction"]
            elif idea == "fvg_reaction":
                gap_reasons = ["FVG reaction"]
            elif "ifvg_reaction" in setup_types or "ifvg" in setup_types:
                gap_reasons = ["IFVG reaction"]
            elif "fvg_reaction" in setup_types:
                gap_reasons = ["FVG reaction"]
            elif _number(open_row.get("ifvg_zone_low")) is not None:
                gap_reasons = ["IFVG reaction"]
            elif families == {"fvg"}:
                gap_reasons = ["FVG reaction"]
            elif families == {"ifvg"}:
                gap_reasons = ["IFVG reaction"]
            else:
                gap_reasons = ["Gap reaction type unrecorded"]
            reasons.extend(gap_reasons)
        elif idea in labels:
            reasons.append(labels[idea])

    timeframes = _mapping_value(open_row.get("entry_idea_timeframes"))
    tf_tags: list[str] = []
    for idea, values in timeframes.items():
        label = labels.get(str(idea))
        if label not in reasons:
            continue
        vals = [values] if isinstance(values, str) else _sequence_value(values)
        tf_tags.extend(str(value) for value in vals)
    if not reasons:
        reasons.append("setup not recorded")
    result = " + ".join(dict.fromkeys(reasons))
    if tf_tags:
        result += " (" + ", ".join(dict.fromkeys(tf_tags)) + ")"
    if _text(open_row.get("manipulation")).lower() == "against":
        result += " · PO3 opposing"
    return result


def _clip_plot_line(text: str, max_chars: int = 150) -> str:
    return text if len(text) <= max_chars else text[: max_chars - 1].rstrip() + "…"


def build_trade_plot_note(
    open_row: Any,
    close_row: Any,
    *,
    entry_price: float,
    exit_price: float,
    direction: int,
    pnl: float,
    lots: float,
    close_reason_detail: str,
    position_events: Any = None,
    signal_time: Any = None,
    entry_fill_time: Any = None,
) -> list[str]:
    """Build five compact rows intended to live inside a trade chart."""
    side = "Long" if direction == 1 else "Short" if direction == -1 else "Flat"
    signal = _clock(signal_time) if _text(signal_time) else "?"
    fill_time = entry_fill_time if _text(entry_fill_time) else open_row.get("time")
    fill_source = "tick" if _text(open_row.get("fill_quote_source")) == "tick" else "logged"
    entry_line = (
        f"ENTRY {side} {signal}→{_clock(fill_time)} @ {entry_price:.2f}"
        f" · {lots:.2f} lots · {fill_source}"
    )
    reason_line = f"REASON {_plot_reason(open_row)}"

    stop_parts: list[str] = []
    sl_price = _number(open_row.get("sl_price"))
    if sl_price is not None:
        ref = _short_reference(open_row.get("sl_ref"))
        stop_parts.append(f"{sl_price:.2f}" + (f" {ref}" if ref else ""))
    for _, event in position_events.iterrows() if hasattr(position_events, "iterrows") else ():
        kind = _text(event.get("type"))
        when = event.get("actual_tick_time", event.get("effective_time", event.get("time")))
        clock = _clock(when)
        if kind == "sl_update":
            price = _number(event.get("price"))
            if price is not None:
                stop_parts.append(f"move {clock}→{price:.2f}")
        elif "stop" in kind or "sl" in _text(event.get("reason")):
            price = _number(event.get("price"))
            realized = _number(event.get("pnl"))
            fill = f"fill {clock}"
            if price is not None:
                fill += f" @ {price:.2f}"
            if realized is not None:
                fill += f" ${realized:+.2f}"
            stop_parts.append(fill)
    stop_line = "SL " + (" · ".join(stop_parts) if stop_parts else "not recorded")

    target_parts: list[str] = []
    target_legs = _sequence_value(open_row.get("tp_legs"))
    if target_legs:
        for leg in target_legs:
            if not isinstance(leg, Mapping):
                continue
            price = _number(leg.get("executed_price"))
            number = leg.get("leg", "?")
            ref = _short_reference(leg.get("reference"))
            if price is not None:
                target_parts.append(f"TP{number} {price:.2f}" + (f" {ref}" if ref else ""))
    else:
        tp_price = _number(open_row.get("tp_price"))
        if tp_price is not None:
            ref = _short_reference(open_row.get("tp_ref"))
            target_parts.append(f"TP1 {tp_price:.2f}" + (f" {ref}" if ref else ""))
    for _, event in position_events.iterrows() if hasattr(position_events, "iterrows") else ():
        kind = _text(event.get("type"))
        when = event.get("actual_tick_time", event.get("effective_time", event.get("time")))
        clock = _clock(when)
        slot = _number(event.get("tp_slot"))
        slot_text = f"TP{int(slot)}" if slot is not None else "TP"
        if kind == "tp_update":
            price = _number(event.get("price"))
            if price is not None:
                target_parts.append(f"{slot_text} move {clock}→{price:.2f}")
        elif kind in {"tp_partial_close", "tp_close"}:
            price = _number(event.get("price"))
            realized = _number(event.get("pnl"))
            fill = f"{slot_text} fill {clock}"
            if price is not None:
                fill += f" @ {price:.2f}"
            if realized is not None:
                fill += f" ${realized:+.2f}"
            target_parts.append(fill)
    if not target_parts and _text(open_row.get("exit_mode")) == "ema_21":
        target_parts.append("EMA21 runner after partial")
    target_line = "TP " + (" · ".join(target_parts) if target_parts else "not recorded")

    reason = _text(close_reason_detail).lower().replace("_", " ")
    if "stop" in reason or reason in {"sl", "structure sl"}:
        reason = "SL hit"
    elif "tp" in reason or "target" in reason:
        reason = "TP hit"
    elif "breakeven" in reason or reason == "be":
        reason = "BE"
    elif "ema" in reason:
        reason = "EMA exit"
    elif not reason:
        reason = "closed"
    exit_line = f"EXIT {_clock(close_row.get('time'))} @ {exit_price:.2f} · {reason} · ${pnl:+.2f}"
    return [
        _clip_plot_line(line)
        for line in (entry_line, reason_line, stop_line, target_line, exit_line)
    ]


__all__ = ["build_trade_note", "build_trade_plot_note", "entry_reason", "pretty_ref"]
