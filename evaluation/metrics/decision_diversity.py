"""Decoded trade-decision diversity.

Raw action spread and the selected market reference are different objects.
This module reads open rows only. It does not change the reward.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

_CONDITIONERS: tuple[str, ...] = (
    "strategy",
    "session",
    "manipulation",
    "volatility_regime",
    "trend_regime",
    "direction",
    "primary_idea",
    "primary_setup_timeframe",
)
_RR_PCTS: tuple[int, ...] = (10, 25, 50, 75, 90, 95)


@dataclass(frozen=True)
class DiversityThresholds:
    """Printed warnings. None of these enter the reward."""

    sl_top_share: float = 0.80
    tp_top_share: float = 0.80
    rr_p75: float = 1.25
    ema_lo: float = 0.02
    ema_hi: float = 0.98
    action_std: float = 0.05
    min_prior_trades: int = 50
    min_prior_sl_choices: int = 30
    min_prior_tp_choices: int = 30
    min_prior_direction_choices: int = 30
    rank_edge: float = 0.05
    direction_min_share: float = 0.90
    min_prior_risk_steps: int = 1000
    risk_u_max: float = 0.05


def thresholds_from_mapping(raw: dict[str, Any] | None) -> DiversityThresholds:
    """Build thresholds from ``training.dashboard.diversity``.

    Args:
        raw: Key-value data used for the raw.

    Returns:
        Result of build thresholds from ``training.dashboard.diversity``.
    """
    base = DiversityThresholds()
    if not raw:
        return base
    values = {field: raw[field] for field in base.__dataclass_fields__ if field in raw}
    return DiversityThresholds(**values)


def reference_family(name: object) -> str:
    """Coarse family of a level name. A joined name uses its first piece.

    An ``M5_`` / ``M15_`` / ``H1_`` prefix is ``htf``, so a higher-timeframe
    swing is not counted as the M1 swing.

    Args:
        name: Name used to identify the requested file, artifact, or item.

    Returns:
        Text returned by ``reference_family``.
    """
    text = "" if name is None or (isinstance(name, float) and np.isnan(name)) else str(name)
    head = text.split("|", 1)[0].strip().lower()
    if not head or head == "ema_21":
        return ""
    for prefix in ("h1_", "m15_", "m5_"):
        if head.startswith(prefix):
            return "htf"
    if "sweep" in head:
        return "sweep"
    if "fvg" in head:
        return "fvg"
    if head.startswith("dev_") or head == "dev":
        return "deviation"
    if "prev_week" in head:
        return "prev_week"
    if "prev_day" in head:
        return "prev_day"
    if head.startswith("asian") or head.startswith("london"):
        return "session"
    if "swing" in head:
        return "swing"
    return head


def candidate_rank(index: object, count: object) -> float:
    """Ordinal place of a choice in ``[0, 1]``. One candidate has rank 0.

    A missing index, including an EMA exit, is NaN.

    Args:
        index: Position or label identifying the requested item.
        count: Count used by the operation described above.

    Returns:
        Numeric result returned by ``candidate_rank``.
    """
    try:
        idx = float(index)  # type: ignore[arg-type]
        n = float(count)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return float("nan")
    if not np.isfinite(idx) or not np.isfinite(n) or idx < 0.0 or n <= 0.0:
        return float("nan")
    if n <= 1.0:
        return 0.0
    return float(idx) / (n - 1.0)


def shannon_entropy(labels: pd.Series) -> float:
    """Entropy in nats. A single label has entropy 0.

    Args:
        labels: Tabular data used for the labels.

    Returns:
        Numeric result returned by ``shannon_entropy``.
    """
    clean = labels.astype(str)
    clean = clean[clean.ne("") & clean.ne("nan")]
    if clean.empty:
        return float("nan")
    prob = clean.value_counts(normalize=True).to_numpy(dtype=float)
    return float(-np.sum(prob * np.log(prob)))


@dataclass
class DiversityReport:
    """Shares, quantiles, and the terminal text for one set of opens."""

    text: str
    warnings: list[str]
    sl_shares: pd.Series
    tp_shares: pd.Series
    exit_shares: pd.Series
    joint: pd.DataFrame
    rr: pd.Series
    opens: pd.DataFrame
    by_conditioner: dict[str, pd.DataFrame]


def diversity_report(
    trades: pd.DataFrame,
    thresholds: DiversityThresholds | None = None,
) -> DiversityReport:
    """Summarize open rows. Empty input still returns a report.

    Args:
        trades: Trade records used to calculate the requested report or metric.
        thresholds: Thresholds used by the operation described above.

    Returns:
        Result of summarize open rows. Empty input still returns a report.
    """
    limits = thresholds or DiversityThresholds()
    opens = _opens(trades)
    if opens.empty:
        text = "TRADE DECISION DIVERSITY\nno strategy opens\n"
        return DiversityReport(
            text,
            [],
            pd.Series(dtype=float),
            pd.Series(dtype=float),
            pd.Series(dtype=float),
            pd.DataFrame(),
            pd.Series(dtype=float),
            opens,
            {},
        )
    frame = opens.copy()
    frame["sl_family"] = _label(frame, "sl_ref").map(reference_family)
    frame["tp_family"] = _label(frame, "tp_ref").map(reference_family)
    frame["sl_rank"] = _ranks(frame, "sl_index", "n_sl")
    frame["tp_rank"] = _ranks(frame, "tp_index", "n_tp")
    if "exit_mode" in frame.columns:
        structural = frame["exit_mode"].astype(str).ne("ema_21")
    else:
        structural = pd.Series(True, index=frame.index)
    tp_labels = frame.loc[structural, "tp_family"]
    sl_shares = _shares(frame["sl_family"])
    tp_shares = _shares(tp_labels)
    exit_shares = _exit_shares(frame)
    joint = _joint(frame.loc[structural])
    if "planned_rr" in frame.columns:
        rr = pd.to_numeric(frame.loc[structural, "planned_rr"], errors="coerce")
    else:
        rr = pd.Series(dtype=float)
    rr = rr.dropna()
    grouped = {
        name: _conditional_counts(frame, name) for name in _CONDITIONERS if name in frame.columns
    }
    warnings = _warnings(frame, sl_shares, tp_shares, exit_shares, rr, limits)
    text = _format(frame, sl_shares, tp_shares, exit_shares, rr, warnings, grouped)
    return DiversityReport(
        text, warnings, sl_shares, tp_shares, exit_shares, joint, rr, frame, grouped
    )


def format_diversity_text(
    trades: pd.DataFrame,
    thresholds: DiversityThresholds | None = None,
) -> str:
    """Terminal block for one trade log.

    Args:
        trades: Trade records used to calculate the requested report or metric.
        thresholds: Thresholds used by the operation described above.

    Returns:
        Text returned by ``format_diversity_text``.
    """
    return diversity_report(trades, thresholds).text


def active_prior_names(
    trades: pd.DataFrame,
    thresholds: DiversityThresholds | None = None,
) -> set[str]:
    """Names whose interval of opens is a recognized collapse.

    Family share never activates a name. Intensity and risk are never returned.
    Rank evidence uses only rows with a real menu (``n >= 2``).

    Args:
        trades: Trade records used to calculate the requested report or metric.
        thresholds: Thresholds used by the operation described above.

    Returns:
        Result of names whose interval of opens is a recognized collapse.
    """
    limits = thresholds or DiversityThresholds()
    opens = _opens(trades)
    names: set[str] = set()
    if opens.empty:
        return names
    if _stop_prior(opens, limits):
        names.add("stop")
    if _target_prior(opens, limits):
        names.add("target")
    if len(opens) >= int(limits.min_prior_trades) and _exit_collapsed(opens, limits):
        names.add("exit")
    if _direction_prior(opens, limits):
        names.add("direction")
    return names


def risk_mean_collapsed(
    mean_u: float,
    n: int,
    thresholds: DiversityThresholds | None = None,
) -> bool:
    """True when the risk coordinate is parked at or below the entry floor.

    ``mean_u`` is the unit-interval risk action over the training interval,
    not an open-trade sample. A mean of 0.5 is the neutral Gaussian and stays off.

    Args:
        mean_u: Numeric value used for the mean u.
        n: Numeric value used for the n.
        thresholds: Thresholds used by the operation described above.

    Returns:
        Whether risk mean collapsed meets the requested condition.
    """
    limits = thresholds or DiversityThresholds()
    if int(n) < int(limits.min_prior_risk_steps):
        return False
    if not np.isfinite(mean_u):
        return False
    return float(mean_u) <= float(limits.risk_u_max)


def choice_rank_median(trades: pd.DataFrame, side: str) -> float:
    """Median rank on multi-candidate rows. EMA exits are left out of target.

    Args:
        trades: Trade records used to calculate the requested report or metric.
        side: Text or path value identifying the side.

    Returns:
        Numeric result returned by ``choice_rank_median``.
    """
    opens = _opens(trades)
    if side == "sl":
        rows = _choice_rows(opens, "n_sl")
        ranks = _ranks(rows, "sl_index", "n_sl")
    elif side == "tp":
        rows = _choice_rows(opens, "n_tp", _structural_mask(opens))
        ranks = _ranks(rows, "tp_index", "n_tp")
    else:
        raise ValueError(f"unknown rank side {side}")
    finite = [rank for rank in ranks if np.isfinite(rank)]
    if not finite:
        return float("nan")
    return float(np.median(finite))


def _label(frame: pd.DataFrame, column: str) -> pd.Series:
    """Process the requested value.

    Args:
        frame: Input data frame to process.
        column: Text or path value identifying the column.

    Returns:
        Result of process the requested value.
    """
    if column not in frame.columns:
        return pd.Series("", index=frame.index)
    return frame[column]


def _ranks(frame: pd.DataFrame, index_name: str, count_name: str) -> list[float]:
    """Process the requested value.

    Args:
        frame: Input data frame to process.
        index_name: Text or path value identifying the index name.
        count_name: Text or path value identifying the count name.

    Returns:
        Values returned by ``_ranks``, in the declared order.
    """
    idx = frame[index_name] if index_name in frame.columns else pd.Series(np.nan, index=frame.index)
    count = (
        frame[count_name] if count_name in frame.columns else pd.Series(np.nan, index=frame.index)
    )
    return [candidate_rank(a, b) for a, b in zip(idx.tolist(), count.tolist(), strict=False)]


def _opens(trades: pd.DataFrame) -> pd.DataFrame:
    """Process the requested value.

    Args:
        trades: Trade records used to calculate the requested report or metric.

    Returns:
        DataFrame returned by ``_opens``.
    """
    if trades.empty or "sl_ref" not in trades.columns:
        return pd.DataFrame()
    if "type" in trades.columns:
        return trades.loc[trades["type"].astype(str).eq("open")].copy()
    return trades.copy()


def _shares(labels: pd.Series) -> pd.Series:
    """Process the requested value.

    Args:
        labels: Tabular data used for the labels.

    Returns:
        Result of process the requested value.
    """
    clean = labels.astype(str)
    clean = clean[clean.ne("") & clean.ne("nan")]
    if clean.empty:
        return pd.Series(dtype=float)
    return clean.value_counts(normalize=True).sort_values(ascending=False)


def _exit_shares(frame: pd.DataFrame) -> pd.Series:
    """Process shares.

    Args:
        frame: Input data frame to process.

    Returns:
        Result of process shares.
    """
    if "exit_mode" not in frame.columns:
        return pd.Series(dtype=float)
    labels = frame["exit_mode"].astype(str)
    labels = labels[labels.ne("") & labels.ne("nan")]
    if labels.empty:
        return pd.Series(dtype=float)
    return labels.value_counts(normalize=True).sort_values(ascending=False)


def _structural_mask(frame: pd.DataFrame) -> pd.Series:
    """Process mask.

    Args:
        frame: Input data frame to process.

    Returns:
        Result of process mask.
    """
    if "exit_mode" not in frame.columns:
        return pd.Series(True, index=frame.index)
    return frame["exit_mode"].astype(str).ne("ema_21")


def _choice_rows(
    frame: pd.DataFrame,
    count_name: str,
    extra: pd.Series | None = None,
) -> pd.DataFrame:
    """Rows with a real menu. ``n == 1`` is not a collapse.

    Args:
        frame: Input data frame to process.
        count_name: Text or path value identifying the count name.
        extra: Tabular data used for the extra.

    Returns:
        DataFrame returned by ``_choice_rows``.
    """
    if frame.empty or count_name not in frame.columns:
        return frame.iloc[0:0]
    counts = pd.to_numeric(frame[count_name], errors="coerce")
    mask = counts.ge(2)
    if extra is not None:
        mask = mask & extra.reindex(frame.index).fillna(False)
    return frame.loc[mask]


def _std_below(frame: pd.DataFrame, column: str, limit: float) -> bool:
    """Process below.

    Args:
        frame: Input data frame to process.
        column: Text or path value identifying the column.
        limit: Numeric value used for the limit.

    Returns:
        Whether std below meets the requested condition.
    """
    if column not in frame.columns or frame.empty:
        return False
    values = pd.to_numeric(frame[column], errors="coerce").dropna()
    if values.size < 2:
        return False
    return float(values.std(ddof=0)) < float(limit)


def _rank_parked(frame: pd.DataFrame, index_name: str, count_name: str, edge: float) -> bool:
    """Process parked.

    Args:
        frame: Input data frame to process.
        index_name: Text or path value identifying the index name.
        count_name: Text or path value identifying the count name.
        edge: Numeric value used for the edge.

    Returns:
        Whether rank parked meets the requested condition.
    """
    ranks = np.asarray(_ranks(frame, index_name, count_name), dtype=float)
    finite = ranks[np.isfinite(ranks)]
    if finite.size == 0:
        return False
    median = float(np.median(finite))
    return median <= float(edge) or median >= 1.0 - float(edge)


def _stop_prior(opens: pd.DataFrame, limits: DiversityThresholds) -> bool:
    """Stop prior.

    Args:
        opens: Tabular data used for the opens.
        limits: Limits used by the operation described above.

    Returns:
        Whether stop prior meets the requested condition.
    """
    rows = _choice_rows(opens, "n_sl")
    if len(rows) < int(limits.min_prior_sl_choices):
        return False
    return _std_below(rows, "stop_u", limits.action_std) or _rank_parked(
        rows, "sl_index", "n_sl", limits.rank_edge
    )


def _target_prior(opens: pd.DataFrame, limits: DiversityThresholds) -> bool:
    """Process prior.

    Args:
        opens: Tabular data used for the opens.
        limits: Limits used by the operation described above.

    Returns:
        Whether target prior meets the requested condition.
    """
    rows = _choice_rows(opens, "n_tp", _structural_mask(opens))
    if len(rows) < int(limits.min_prior_tp_choices):
        return False
    return _std_below(rows, "target_u", limits.action_std) or _rank_parked(
        rows, "tp_index", "n_tp", limits.rank_edge
    )


def _exit_collapsed(opens: pd.DataFrame, limits: DiversityThresholds) -> bool:
    """Same band as the printed EXIT COLLAPSE warning.

    Args:
        opens: Tabular data used for the opens.
        limits: Limits used by the operation described above.

    Returns:
        Whether exit collapsed meets the requested condition.
    """
    shares = _exit_shares(opens)
    if shares.empty:
        return False
    if "ema_21" in shares.index:
        ema = float(shares["ema_21"])
        return ema < float(limits.ema_lo) or ema > float(limits.ema_hi)
    return float(shares.iloc[0]) > float(limits.ema_hi)


def _direction_prior(opens: pd.DataFrame, limits: DiversityThresholds) -> bool:
    """Process prior.

    Args:
        opens: Tabular data used for the opens.
        limits: Limits used by the operation described above.

    Returns:
        Whether direction prior meets the requested condition.
    """
    if "direction" not in opens.columns or len(opens) < int(limits.min_prior_trades):
        return False
    dirs = pd.to_numeric(opens["direction"], errors="coerce")
    nonflat = dirs[dirs.notna() & dirs.ne(0)]
    if len(nonflat) < int(limits.min_prior_direction_choices):
        return False
    long = int((nonflat > 0).sum())
    short = int((nonflat < 0).sum())
    total = long + short
    if total <= 0:
        return False
    return max(long, short) / total >= float(limits.direction_min_share)


def _joint(frame: pd.DataFrame) -> pd.DataFrame:
    """Process the requested value.

    Args:
        frame: Input data frame to process.

    Returns:
        DataFrame returned by ``_joint``.
    """
    if frame.empty:
        return pd.DataFrame()
    sl = frame["sl_family"].astype(str)
    tp = frame["tp_family"].astype(str)
    keep = sl.ne("") & tp.ne("") & sl.ne("nan") & tp.ne("nan")
    if not bool(keep.any()):
        return pd.DataFrame()
    return pd.crosstab(sl[keep], tp[keep])


def _conditional_counts(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    """Process counts.

    Args:
        frame: Input data frame to process.
        column: Text or path value identifying the column.

    Returns:
        DataFrame returned by ``_conditional_counts``.
    """
    group = frame[column]
    if group is None:
        return pd.DataFrame()
    labels = group.astype(str)
    keep = labels.ne("") & labels.ne("nan") & frame["sl_family"].astype(str).ne("")
    if not bool(keep.any()):
        return pd.DataFrame()
    return pd.crosstab(labels[keep], frame.loc[keep, "sl_family"])


def _warnings(
    frame: pd.DataFrame,
    sl_shares: pd.Series,
    tp_shares: pd.Series,
    exit_shares: pd.Series,
    rr: pd.Series,
    limits: DiversityThresholds,
) -> list[str]:
    """Process the requested value.

    Args:
        frame: Input data frame to process.
        sl_shares: Tabular data used for the sl shares.
        tp_shares: Tabular data used for the tp shares.
        exit_shares: Tabular data used for the exit shares.
        rr: Tabular data used for the rr.
        limits: Limits used by the operation described above.

    Returns:
        Values returned by ``_warnings``, in the declared order.
    """
    found: list[str] = []
    if not sl_shares.empty and float(sl_shares.iloc[0]) > limits.sl_top_share:
        found.append(
            f"SL COLLAPSE  top {sl_shares.index[0]} {100.0 * float(sl_shares.iloc[0]):.0f}%"
        )
    if not tp_shares.empty and float(tp_shares.iloc[0]) > limits.tp_top_share:
        found.append(
            f"TP COLLAPSE  top {tp_shares.index[0]} {100.0 * float(tp_shares.iloc[0]):.0f}%"
        )
    if not rr.empty:
        p75 = float(np.quantile(rr.to_numpy(dtype=float), 0.75))
        if p75 < limits.rr_p75:
            found.append(f"RR COLLAPSE  P75 {p75:.2f}")
    if not exit_shares.empty and "ema_21" in exit_shares.index:
        ema = float(exit_shares["ema_21"])
        if ema < limits.ema_lo or ema > limits.ema_hi:
            found.append(f"EXIT COLLAPSE  ema_21 {100.0 * ema:.1f}%")
    elif not exit_shares.empty and float(exit_shares.iloc[0]) > limits.ema_hi:
        found.append(
            f"EXIT COLLAPSE  {exit_shares.index[0]} {100.0 * float(exit_shares.iloc[0]):.1f}%"
        )
    for column, label in (("stop_u", "stop_u"), ("target_u", "target_u")):
        if column not in frame.columns:
            continue
        values = pd.to_numeric(frame[column], errors="coerce").dropna()
        if values.size >= 2 and float(values.std(ddof=0)) < limits.action_std:
            found.append(f"ACTION COLLAPSE  {label} std {float(values.std(ddof=0)):.3f}")
    return found


def _format(
    frame: pd.DataFrame,
    sl_shares: pd.Series,
    tp_shares: pd.Series,
    exit_shares: pd.Series,
    rr: pd.Series,
    warnings: list[str],
    grouped: dict[str, pd.DataFrame],
) -> str:
    """Format the requested value.

    Args:
        frame: Input data frame to process.
        sl_shares: Tabular data used for the sl shares.
        tp_shares: Tabular data used for the tp shares.
        exit_shares: Tabular data used for the exit shares.
        rr: Tabular data used for the rr.
        warnings: Items supplied for the warnings, in input order.
        grouped: Tabular data used for the grouped.

    Returns:
        Text returned by ``_format``.
    """
    lines = ["TRADE DECISION DIVERSITY", _block("SL", frame["sl_family"], sl_shares)]
    if "exit_mode" in frame.columns:
        structural = frame["exit_mode"].astype(str).ne("ema_21")
    else:
        structural = pd.Series(True, index=frame.index)
    lines.append(_block("TP", frame.loc[structural, "tp_family"], tp_shares))
    exit_line = "Exit:"
    if exit_shares.empty:
        exit_line += "  n/a"
    else:
        exit_line += "  " + "  ".join(
            f"{name} {100.0 * float(share):.0f}%" for name, share in exit_shares.items()
        )
    lines.append(exit_line)
    lines.append("Planned RR:  " + _rr_text(rr))
    lines.append("SL rank:  " + _rank_text(frame["sl_rank"]))
    lines.append("TP rank:  " + _rank_text(frame.loc[structural, "tp_rank"]))
    if "stop_u" in frame.columns:
        stop_u = pd.to_numeric(frame["stop_u"], errors="coerce")
        lines.append(
            f"stop_u std {float(stop_u.std(ddof=0)) if stop_u.notna().sum() else float('nan'):.3f}"
            f"  unique sl families {int(frame['sl_family'].replace('', np.nan).nunique(dropna=True))}"
        )
    for name, table in grouped.items():
        if table.empty or len(table.index) < 1:
            continue
        lines.append(f"by {name}:")
        for level, row in table.iterrows():
            total = float(row.sum())
            if total <= 0.0:
                continue
            top = row.sort_values(ascending=False).head(4)
            bits = "  ".join(
                f"{col} {100.0 * float(value) / total:.0f}%" for col, value in top.items() if value
            )
            lines.append(f"  {level}  {bits}")
    for warning in warnings:
        lines.append(f"WARNING  {warning}")
    return "\n".join(lines) + "\n"


def _block(title: str, labels: pd.Series, shares: pd.Series) -> str:
    """Process the requested value.

    Args:
        title: Text or path value identifying the title.
        labels: Tabular data used for the labels.
        shares: Tabular data used for the shares.

    Returns:
        Text returned by ``_block``.
    """
    clean = labels.astype(str)
    clean = clean[clean.ne("") & clean.ne("nan")]
    entropy = shannon_entropy(clean)
    effective = float(np.exp(entropy)) if np.isfinite(entropy) else float("nan")
    top = float(shares.iloc[0]) if not shares.empty else float("nan")
    listed = "  ".join(f"{name} {100.0 * float(share):.0f}%" for name, share in shares.items())
    return (
        f"{title}:  unique {clean.nunique()}  effective {effective:.2f}  "
        f"entropy {entropy:.2f}  top {100.0 * top:.0f}%  {listed}"
    )


def _rr_text(rr: pd.Series) -> str:
    """Process text.

    Args:
        rr: Tabular data used for the rr.

    Returns:
        Text returned by ``_rr_text``.
    """
    if rr.empty:
        return "n/a"
    values = rr.to_numpy(dtype=float)
    parts = [f"P{pct} {float(np.quantile(values, pct / 100.0)):.2f}" for pct in _RR_PCTS]
    return "  ".join(parts)


def _rank_text(ranks: pd.Series) -> str:
    """Process text.

    Args:
        ranks: Tabular data used for the ranks.

    Returns:
        Text returned by ``_rank_text``.
    """
    values = pd.to_numeric(ranks, errors="coerce").dropna()
    if values.empty:
        return "n/a"
    arr = values.to_numpy(dtype=float)
    return f"median {float(np.median(arr)):.2f}  P90 {float(np.quantile(arr, 0.90)):.2f}"
