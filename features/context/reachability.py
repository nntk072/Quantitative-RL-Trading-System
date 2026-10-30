"""Causal cap on a reward-ratio target, in ATR units.

The cap is a high quantile of completed NY session ranges divided by ``atr_5``.
It is multiplied back by the current ATR, so the same rule accepts a small
shock in a quiet year and a much larger point move when the index and ATR
have grown. There is no fixed point distance.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from market_data.transforms.sessions import ny_session_mask


def max_tp_distance(
    bars: pd.DataFrame,
    atr: pd.Series,
    *,
    n_sessions: int = 20,
    quantile: float = 0.90,
) -> pd.Series:
    """Price distance a take-profit may sit from entry at each bar.

    Uses only NY sessions that have already closed before the bar. Until one
    session has closed, the value is NaN and the caller must not refuse a trade
    for reach. With fewer than ``n_sessions`` closed sessions the quantile is
    expanding.
    """
    idx = pd.DatetimeIndex(bars.index)
    atr_a = pd.to_numeric(atr.reindex(idx), errors="coerce").to_numpy(dtype=float)
    high = pd.to_numeric(bars["high"], errors="coerce").to_numpy(dtype=float)
    low = pd.to_numeric(bars["low"], errors="coerce").to_numpy(dtype=float)
    ny = ny_session_mask(idx).to_numpy()
    out = pd.Series(np.nan, index=idx, name="max_tp_distance")
    if not ny.any():
        return out

    day_codes, _ = pd.factorize(idx.normalize(), sort=False)
    sessions: list[tuple[int, float]] = []
    for code in pd.unique(day_codes[ny]):
        pos = np.flatnonzero(ny & (day_codes == code))
        if pos.size == 0:
            continue
        end_i = int(pos[-1])
        atr_end = float(atr_a[end_i])
        rng = float(np.nanmax(high[pos]) - np.nanmin(low[pos]))
        if not np.isfinite(atr_end) or atr_end <= 0.0 or not np.isfinite(rng) or rng < 0.0:
            continue
        sessions.append((end_i, rng / atr_end))
    if not sessions:
        return out

    end_is = np.array([s[0] for s in sessions], dtype=int)
    ratios = np.array([s[1] for s in sessions], dtype=float)
    # Number of sessions whose last bar is strictly before this bar.
    counts = np.searchsorted(end_is, np.arange(len(idx)), side="left")
    change_at = np.flatnonzero(np.diff(counts, prepend=-1))
    ratio_out = np.full(len(idx), np.nan)
    for j, i0 in enumerate(change_at):
        k = int(counts[i0])
        i1 = int(change_at[j + 1]) if j + 1 < len(change_at) else len(idx)
        if k <= 0:
            continue
        window = ratios[max(0, k - n_sessions) : k]
        ratio_out[i0:i1] = float(np.quantile(window, quantile))
    dist = ratio_out * atr_a
    dist[~np.isfinite(atr_a) | (atr_a <= 0.0)] = np.nan
    out.iloc[:] = dist
    return out


def reachable_r_series(bars: pd.DataFrame, features: pd.DataFrame) -> pd.Series:
    """Causal reward room: max take-profit distance divided by structural stop.

    The side is the distribution direction when it is set, otherwise the
    higher-timeframe bias. A flat bar uses the tighter of the two stops.
    The ratio is scale-free, so it can sit in the model sequence.
    """
    idx = bars.index
    if "atr_5" not in features.columns or "close" not in bars.columns:
        return pd.Series(0.0, index=idx, name="reachable_r")
    dist = max_tp_distance(bars, features["atr_5"]).reindex(idx)
    close = pd.to_numeric(bars["close"], errors="coerce")
    atr = pd.to_numeric(features["atr_5"].reindex(idx), errors="coerce")
    if "po3_manipulation_low" in features.columns and "po3_manipulation_high" in features.columns:
        risk_long = (
            close - pd.to_numeric(features["po3_manipulation_low"].reindex(idx), errors="coerce")
        ).clip(lower=0.0)
        risk_short = (
            pd.to_numeric(features["po3_manipulation_high"].reindex(idx), errors="coerce") - close
        ).clip(lower=0.0)
    else:
        risk_long = atr.clip(lower=0.0)
        risk_short = atr.clip(lower=0.0)
    if "po3_distribution_direction" in features.columns:
        direction = pd.to_numeric(
            features["po3_distribution_direction"].reindex(idx), errors="coerce"
        ).fillna(0.0)
    elif "htf_day_bias" in features.columns:
        direction = pd.to_numeric(features["htf_day_bias"].reindex(idx), errors="coerce").fillna(
            0.0
        )
    else:
        direction = pd.Series(0.0, index=idx)
    long_a = risk_long.to_numpy(dtype=float)
    short_a = risk_short.to_numpy(dtype=float)
    side = direction.to_numpy(dtype=float)
    risk = np.where(side < 0.0, short_a, long_a)
    tighter = np.minimum(
        np.where(long_a > 0.0, long_a, np.inf),
        np.where(short_a > 0.0, short_a, np.inf),
    )
    risk = np.where(side == 0.0, tighter, risk)
    atr_a = atr.to_numpy(dtype=float)
    missing = ~np.isfinite(risk) | (risk <= 0.0)
    risk = np.where(missing, atr_a, risk)
    room = dist.to_numpy(dtype=float)
    ratio = room / np.where(risk > 1e-8, risk, np.nan)
    ratio = np.clip(np.nan_to_num(ratio, nan=0.0, posinf=0.0, neginf=0.0), 0.0, 20.0)
    return pd.Series(ratio, index=idx, name="reachable_r")


def attach_reachable_r(
    obs: pd.DataFrame,
    bars: pd.DataFrame,
    features: pd.DataFrame,
) -> pd.DataFrame:
    """Append ``reachable_r`` after raw price columns have been dropped."""
    out = obs.copy()
    out["reachable_r"] = (
        reachable_r_series(bars, features).reindex(obs.index).fillna(0.0).astype(float)
    )
    return out


def rr_reaches(entry: float, sl: float, rr_ratio: float, max_distance: float) -> bool:
    """True when ``rr_ratio * |entry - sl|`` fits inside ``max_distance``.

    A non-finite cap means no completed session yet, so the trade is allowed.
    """
    if not np.isfinite(max_distance):
        return True
    risk = abs(float(entry) - float(sl))
    return float(rr_ratio) * risk <= float(max_distance) + 1e-9
