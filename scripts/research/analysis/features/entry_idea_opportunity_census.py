#!/usr/bin/env python3
"""Describe training-only eligibility for the canonical 108 setup candidates.

This is an offline context census. It does not simulate orders, fills, returns,
or trades and must not be interpreted as policy or execution evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
from omegaconf import DictConfig, OmegaConf
from scripts.research.analysis.features.training_context import (
    DEFAULT_CONFIG,
    TIMEFRAMES,
    _timestamp,
)
from scripts.research.analysis.features.training_context import (
    candidate_supported as _candidate_supported,
)
from scripts.research.analysis.features.training_context import (
    training_slice as _training_slice,
)

from configuration.configuration_loader import load_config
from configuration.paths import repository_root
from decisioning.trade_setup import TRADE_SETUP_CANDIDATES
from features import build_features
from features.context.trade_setup_candidates import (
    TRADE_SETUP_EVENT_IDENTITY_VERSION,
    trade_setup_candidate_event_time_fields,
    trade_setup_candidate_feature_columns,
)
from features.po3.fvg import build_fvg_zone_features_with_event_ledger
from features.po3.fvg_detection import FVGConfig
from market_data.loading.market_data_ingestion import run_pipeline

ROOT = repository_root(__file__)
DEFAULT_OUTPUT = ROOT / "evidence/research/trade_setup_opportunity_census"
HORIZONS = (1, 5, 15, 30, 60, 240)
FVG_EVENT_COLUMNS = (
    "confirmation_bar",
    "confirmation_time_ns",
    "side",
    "zone_start_time_ns",
    "source_origin_bar",
    "source_origin_time_ns",
    "zone_low",
    "zone_high",
    "selected_by_scalar",
)


def _volatility_regime(bars: pd.DataFrame) -> tuple[pd.Series, dict[str, float]]:
    """Assign descriptive ATR terciles using thresholds fitted on training rows."""
    close = pd.to_numeric(bars["close"], errors="coerce")
    high = pd.to_numeric(bars["high"], errors="coerce")
    low = pd.to_numeric(bars["low"], errors="coerce")
    previous_close = close.shift(1)
    true_range = pd.concat(
        [(high - low).abs(), (high - previous_close).abs(), (low - previous_close).abs()],
        axis=1,
    ).max(axis=1)
    volatility = true_range.rolling(20, min_periods=20).mean() / close.abs().replace(0, np.nan)
    quantiles = volatility.quantile([1.0 / 3.0, 2.0 / 3.0])
    lower, upper = float(quantiles.iloc[0]), float(quantiles.iloc[1])
    values = pd.Series("middle", index=bars.index, dtype="object")
    values.loc[volatility <= lower] = "low"
    values.loc[volatility > upper] = "high"
    values.loc[volatility.isna()] = "warmup_unknown"
    return values, {"lower_tercile": lower, "upper_tercile": upper}


def _candidate_identity_frame(
    features: pd.DataFrame, candidate_id: int, active: pd.Series
) -> pd.DataFrame:
    """Vectorize source-time identity resolution for one candidate over a feature matrix."""
    if not features.columns.is_unique:
        raise ValueError("candidate identity census requires unique feature columns")
    if not active.index.equals(features.index):
        raise ValueError("candidate active mask must share the feature index")

    active_values = active.to_numpy(dtype=bool)
    resolved = active_values.copy()
    source_times: dict[str, np.ndarray[Any, Any]] = {}
    for position, (field, scale) in enumerate(
        trade_setup_candidate_event_time_fields(candidate_id)
    ):
        output_name = f"source_time_{position}_ns"
        normalized = np.zeros(len(features), dtype=np.int64)
        if field not in features.columns:
            resolved[:] = False
        else:
            numeric = pd.to_numeric(features[field], errors="coerce").to_numpy(dtype=float)
            finite = np.isfinite(numeric)
            resolved &= finite
            normalized[finite] = np.rint(numeric[finite] * scale).astype(np.int64)
        source_times[output_name] = normalized

    status = np.full(len(features), "inactive", dtype=object)
    status[active_values] = "missing_source_event_time"
    status[resolved] = "identified"
    return pd.DataFrame({"status": status, **source_times}, index=features.index)


def _distinct_event_count(identity_frame: pd.DataFrame, mask: np.ndarray[Any, Any]) -> int:
    """Count unique resolved timestamp tuples for selected rows."""
    time_columns = [name for name in identity_frame.columns if name.startswith("source_time_")]
    if not mask.any():
        return 0
    values = identity_frame.loc[mask, time_columns].to_numpy(dtype=np.int64)
    return int(np.unique(values, axis=0).shape[0])


def _cross_timeframe_alignment_metrics(
    left_identity: pd.DataFrame,
    left_active: pd.Series,
    right_identity: pd.DataFrame,
    right_active: pd.Series,
) -> dict[str, int]:
    """Count exact source-time tuple alignment for two candidate streams.

    Exact tuple alignment is an observable timestamp relationship only. It
    does not establish that the candidates refer to one logical market event.
    """
    indexes = (left_identity.index, left_active.index, right_identity.index, right_active.index)
    if any(not indexes[0].equals(index) for index in indexes[1:]):
        raise ValueError("cross-timeframe candidates must share the same row index")
    left_columns = [
        name
        for name in left_identity.columns
        if isinstance(name, str) and name.startswith("source_time_")
    ]
    right_columns = [
        name
        for name in right_identity.columns
        if isinstance(name, str) and name.startswith("source_time_")
    ]
    if not left_columns or len(left_columns) != len(right_columns):
        raise ValueError("cross-timeframe candidates must have matching source-time tuple shapes")

    left_identified = left_identity["status"].eq("identified").to_numpy(dtype=bool)
    right_identified = right_identity["status"].eq("identified").to_numpy(dtype=bool)
    joint_active = left_active.to_numpy(dtype=bool) & right_active.to_numpy(dtype=bool)
    both_identified = joint_active & left_identified & right_identified
    left_times = left_identity[left_columns].to_numpy(dtype=np.int64)
    right_times = right_identity[right_columns].to_numpy(dtype=np.int64)
    aligned = both_identified & np.all(left_times == right_times, axis=1)
    return {
        "jointly_active_m1_rows": int(joint_active.sum()),
        "jointly_identified_m1_rows": int(both_identified.sum()),
        "exact_source_time_tuple_aligned_m1_rows": int(aligned.sum()),
        "distinct_aligned_source_time_tuples": _distinct_event_count(left_identity, aligned),
    }


def _source_time_tuple_clusters(
    candidate_streams: dict[int, tuple[pd.Series, pd.DataFrame]],
) -> pd.DataFrame:
    """Group exact family/direction source-time tuples across candidate timeframes.

    This reports a conservative identity relation: candidates share a cluster
    only when their ordered, normalized source-time values are exactly equal.
    It does not infer that different tuples represent different economic events.
    """
    clusters: dict[tuple[str, int, tuple[int, ...]], dict[str, Any]] = {}
    tuple_widths: dict[tuple[str, int], int] = {}
    reference_index: pd.Index | None = None
    for candidate in TRADE_SETUP_CANDIDATES[1:]:
        stream = candidate_streams.get(candidate.candidate_id)
        if stream is None:
            continue
        active, identity = stream
        if not active.index.equals(identity.index):
            raise ValueError("candidate identity and active mask must share an index")
        if reference_index is None:
            reference_index = identity.index
        elif not reference_index.equals(identity.index):
            raise ValueError("candidate source-time streams must share an index")
        columns = [
            name
            for name in identity.columns
            if isinstance(name, str) and name.startswith("source_time_")
        ]
        if not columns:
            raise ValueError("candidate identity must contain source-time tuple columns")
        assert candidate.idea is not None
        family_key = (candidate.idea, candidate.direction)
        prior_width = tuple_widths.setdefault(family_key, len(columns))
        if prior_width != len(columns):
            raise ValueError(f"{candidate.idea} source-time tuple widths differ across candidates")
        active_values = active.to_numpy(dtype=bool)
        identified = identity["status"].eq("identified").to_numpy(dtype=bool)
        times = identity[columns].to_numpy(dtype=np.int64)
        for row_position in np.flatnonzero(active_values & identified):
            source_tuple = tuple(int(value) for value in times[row_position])
            key = (candidate.idea, candidate.direction, source_tuple)
            cluster = clusters.setdefault(
                key,
                {
                    "candidate_ids": set(),
                    "timeframes": set(),
                    "row_timeframes": {},
                    "candidate_row_occurrences": 0,
                },
            )
            cluster["candidate_ids"].add(candidate.candidate_id)
            assert candidate.setup_timeframe is not None
            cluster["timeframes"].add(candidate.setup_timeframe)
            row_timeframes = cluster["row_timeframes"].setdefault(int(row_position), set())
            row_timeframes.add(candidate.setup_timeframe)
            cluster["candidate_row_occurrences"] += 1

    timeframe_order = {timeframe: rank for rank, timeframe in enumerate(TIMEFRAMES)}
    rows: list[dict[str, Any]] = []
    for (idea, direction, source_tuple), cluster in sorted(clusters.items()):
        row_timeframes = cluster["row_timeframes"]
        timeframes = sorted(cluster["timeframes"], key=lambda timeframe: timeframe_order[timeframe])
        active_rows = sorted(row_timeframes)
        index = candidate_streams[min(cluster["candidate_ids"])][0].index
        rows.append(
            {
                "idea": idea,
                "direction": "long" if direction > 0 else "short",
                "source_time_tuple_ns": json.dumps(source_tuple, separators=(",", ":")),
                "candidate_ids": json.dumps(sorted(cluster["candidate_ids"])),
                "timeframes": json.dumps(timeframes),
                "candidate_count": len(cluster["candidate_ids"]),
                "timeframe_count": len(timeframes),
                "candidate_row_occurrences": int(cluster["candidate_row_occurrences"]),
                "unique_active_m1_rows": len(active_rows),
                "rows_with_multiple_timeframes": sum(
                    len(row_timeframes[position]) > 1 for position in active_rows
                ),
                "max_concurrent_timeframes": max(
                    len(row_timeframes[position]) for position in active_rows
                ),
                "first_active_m1_time": pd.Timestamp(index[active_rows[0]]).isoformat(),
                "last_active_m1_time": pd.Timestamp(index[active_rows[-1]]).isoformat(),
            }
        )
    return pd.DataFrame(
        rows,
        columns=(
            "idea",
            "direction",
            "source_time_tuple_ns",
            "candidate_ids",
            "timeframes",
            "candidate_count",
            "timeframe_count",
            "candidate_row_occurrences",
            "unique_active_m1_rows",
            "rows_with_multiple_timeframes",
            "max_concurrent_timeframes",
            "first_active_m1_time",
            "last_active_m1_time",
        ),
    )


def _identity_lifecycle_metrics(identity_frame: pd.DataFrame, active: pd.Series) -> dict[str, int]:
    """Describe how source-time identities persist over active candidate rows.

    Counts are observed identity episodes, adjacent identity changes, and IDs
    reused across disconnected active-mask episodes. They do not assert that a
    source-time tuple equals one logically distinct market event.
    """
    if not active.index.equals(identity_frame.index):
        raise ValueError("candidate active mask must share the identity frame index")
    active_values = active.to_numpy(dtype=bool)
    identified = identity_frame["status"].eq("identified").to_numpy(dtype=bool)
    time_columns = [name for name in identity_frame.columns if name.startswith("source_time_")]
    times = identity_frame[time_columns].to_numpy(dtype=np.int64)
    previous_active = np.zeros(len(active_values), dtype=bool)
    previous_identified = np.zeros(len(identified), dtype=bool)
    same_identity_as_previous = np.zeros(len(identified), dtype=bool)
    if len(active_values) > 1:
        previous_active[1:] = active_values[:-1]
        previous_identified[1:] = identified[:-1]
        same_identity_as_previous[1:] = np.all(times[1:] == times[:-1], axis=1)

    identified_episode_starts = identified & ~(previous_identified & same_identity_as_previous)
    adjacent_identity_changes = (
        active_values
        & previous_active
        & identified
        & previous_identified
        & ~same_identity_as_previous
    )
    active_episode_ids = np.cumsum(active_values & ~previous_active)
    episodes_by_identity: dict[tuple[int, ...], set[int]] = {}
    for row in np.flatnonzero(identified):
        identity = tuple(int(value) for value in times[row])
        episodes_by_identity.setdefault(identity, set()).add(int(active_episode_ids[row]))
    return {
        "identified_identity_episode_starts": int(identified_episode_starts.sum()),
        "adjacent_active_identity_changes": int(adjacent_identity_changes.sum()),
        "distinct_ids_reused_across_active_episodes": sum(
            len(episode_ids) > 1 for episode_ids in episodes_by_identity.values()
        ),
    }


def _configured_fvg_config(cfg: DictConfig) -> FVGConfig:
    """Resolve the same FVG retest buffer used by the configured feature path."""
    configured_fraction = OmegaConf.select(cfg, "features.gap_reaction_buffer_fraction")
    configured_enabled = OmegaConf.select(cfg, "features.gap_reaction_buffer_enabled")
    enabled = True if configured_enabled is None else bool(configured_enabled)
    fraction = 0.1 if configured_fraction is None else float(configured_fraction)
    return FVGConfig(
        reaction_buffer_fraction=fraction,
        reaction_buffer_enabled=enabled,
    )


def _validate_fvg_scalar_projection(
    events: pd.DataFrame,
    scalar: pd.DataFrame,
) -> None:
    """Require one selected per-zone source for each scalar retest pulse."""
    if not events.empty and tuple(events.columns) != FVG_EVENT_COLUMNS:
        raise AssertionError("FVG event ledger columns differ from the declared schema")
    for side, flag, origin in (
        ("bullish", "fvg_retest_bull", "fvg_bull_retest_origin_time_ns"),
        ("bearish", "fvg_retest_bear", "fvg_bear_retest_origin_time_ns"),
    ):
        selected = events.loc[events["side"].eq(side) & events["selected_by_scalar"]].sort_values(
            "confirmation_bar"
        )
        expected_bars = np.flatnonzero(scalar[flag].to_numpy(dtype=bool))
        if selected["confirmation_bar"].astype(int).tolist() != expected_bars.tolist():
            raise AssertionError(f"per-zone {side} events do not match scalar FVG retest rows")
        expected_origins = scalar[origin].to_numpy(dtype=float)[expected_bars].astype("int64")
        if not np.array_equal(
            selected["zone_start_time_ns"].to_numpy(dtype="int64"), expected_origins
        ):
            raise AssertionError(
                f"per-zone {side} selection does not match scalar source-zone time"
            )
    if events.duplicated(["confirmation_bar", "side", "zone_start_time_ns"]).any():
        raise AssertionError("a source FVG zone confirmed more than once on one row and side")


def _fvg_collision_tables(
    events: pd.DataFrame,
    bars: pd.DataFrame,
    volatility_regime: pd.Series,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Summarize overlapping FVG confirmations by source row, month, and regime."""
    collision_columns = (
        "confirmation_bar",
        "confirmation_time_ns",
        "confirmation_month",
        "volatility_regime",
        "side",
        "per_zone_confirmation_count",
        "suppressed_per_zone_confirmations",
        "selected_zone_start_time_ns",
    )
    monthly_columns = (
        "confirmation_month",
        "volatility_regime",
        "side",
        "per_zone_confirmations",
        "scalar_confirmation_pulses",
        "suppressed_per_zone_confirmations",
        "collision_rows",
    )
    if events.empty:
        return pd.DataFrame(columns=collision_columns), pd.DataFrame(columns=monthly_columns)

    collision_rows: list[dict[str, Any]] = []
    for (bar_value, side), group in events.groupby(["confirmation_bar", "side"], sort=True):
        if len(group) < 2:
            continue
        selected = group.loc[group["selected_by_scalar"]]
        if len(selected) != 1:
            raise AssertionError("each same-row FVG collision must select exactly one zone")
        bar = int(cast(int, bar_value))
        selected_event = selected.iloc[0]
        collision_rows.append(
            {
                "confirmation_bar": bar,
                "confirmation_time_ns": int(group["confirmation_time_ns"].iloc[0]),
                "confirmation_month": pd.Timestamp(bars.index[bar]).strftime("%Y-%m"),
                "volatility_regime": str(volatility_regime.iloc[bar]),
                "side": str(side),
                "per_zone_confirmation_count": int(len(group)),
                "suppressed_per_zone_confirmations": int(len(group) - 1),
                "selected_zone_start_time_ns": int(selected_event["zone_start_time_ns"]),
            }
        )
    collisions = pd.DataFrame.from_records(collision_rows, columns=collision_columns)

    monthly_work = events.copy()
    monthly_work["confirmation_month"] = [
        pd.Timestamp(bars.index[int(bar)]).strftime("%Y-%m")
        for bar in monthly_work["confirmation_bar"]
    ]
    monthly_work["volatility_regime"] = [
        str(volatility_regime.iloc[int(bar)]) for bar in monthly_work["confirmation_bar"]
    ]
    monthly = monthly_work.groupby(
        ["confirmation_month", "volatility_regime", "side"], sort=True
    ).agg(
        per_zone_confirmations=("side", "size"),
        scalar_confirmation_pulses=("selected_by_scalar", "sum"),
    )
    monthly["suppressed_per_zone_confirmations"] = (
        monthly["per_zone_confirmations"] - monthly["scalar_confirmation_pulses"]
    )
    if collisions.empty:
        monthly["collision_rows"] = 0
    else:
        collision_counts = collisions.groupby(
            ["confirmation_month", "volatility_regime", "side"]
        ).size()
        monthly["collision_rows"] = collision_counts
    monthly = monthly.fillna({"collision_rows": 0}).reset_index()
    monthly["collision_rows"] = monthly["collision_rows"].astype(int)
    return collisions, monthly.loc[:, list(monthly_columns)]


def _write_output_checksums(output_dir: Path) -> None:
    """Hash every generated packet file except the checksum file itself."""
    rows = []
    for path in sorted(output_dir.iterdir(), key=lambda item: item.name):
        if path.is_file() and path.name != "OUTPUT_SHA256SUMS":
            rows.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}")
    (output_dir / "OUTPUT_SHA256SUMS").write_text("\n".join(rows) + "\n", encoding="utf-8")


def _source_hashes() -> dict[str, str]:
    paths = (
        "features/pipeline/feature_matrix_builder.py",
        "features/pipeline/feature_cache_identity.py",
        "features/context/entry_ideas.py",
        "features/context/trade_setup_candidates.py",
        "features/po3/fvg.py",
        "features/po3/ifvg_detection.py",
        "features/po3/po3_phase_state.py",
        "features/po3/zones.py",
        "features/pipeline/feature_build_inputs.py",
        "decisioning/trade_setup.py",
        "market_data/loading/market_data_ingestion.py",
        "market_data/transforms/sessions.py",
        "scripts/research/analysis/features/entry_idea_opportunity_census.py",
    )
    return {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in paths}


def _git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def build_census(
    cfg: DictConfig,
    output_dir: Path,
    *,
    config_path: Path = DEFAULT_CONFIG,
) -> dict[str, Any]:
    """Build and persist the training-only candidate census."""
    cfg.data.cache_dir = str(ROOT / "cache/trade_setup_opportunity_census")
    dataset = run_pipeline(cfg, datasets=["training"])
    primary_symbol = str(cfg.data.primary)
    secondary_symbol = str(cfg.data.secondary)
    train_start = str(cfg.data.split.train_start)
    train_end = str(cfg.data.split.train_end)
    primary_frames = _training_slice(dataset[primary_symbol], train_start, train_end)
    secondary_frames = _training_slice(dataset[secondary_symbol], train_start, train_end)
    primary = primary_frames["M1"]
    secondary = secondary_frames["M1"]
    if primary.empty or secondary.empty:
        raise ValueError("configured training-only M1 input is empty")
    if primary.index.max() > _timestamp(train_end, pd.DatetimeIndex(primary.index)) + pd.Timedelta(
        days=1
    ):
        raise AssertionError("training M1 slice includes rows after train_end")

    train_mask = pd.Series(True, index=primary.index, dtype=bool)
    features = build_features(
        primary,
        secondary,
        cfg=cfg,
        train_mask=train_mask,
        timeframe_bars=primary_frames,
        secondary_timeframe_bars=secondary_frames,
    )
    index = pd.DatetimeIndex(features.index)
    session = primary["session"].reindex(index).astype(str).str.lower()
    session_id = primary["session_id"].reindex(index)
    volatility_regime, regime_thresholds = _volatility_regime(primary.reindex(index))
    months = pd.Series(index.tz_localize(None).to_period("M").astype(str), index=index)
    fvg_scalar, fvg_events = build_fvg_zone_features_with_event_ledger(
        primary,
        fvg_config=_configured_fvg_config(cfg),
    )
    fvg_events = fvg_events.reindex(columns=FVG_EVENT_COLUMNS)
    _validate_fvg_scalar_projection(fvg_events, fvg_scalar)
    fvg_collisions, fvg_monthly = _fvg_collision_tables(
        fvg_events,
        primary,
        volatility_regime.reindex(primary.index),
    )
    support: dict[str, list[str]] = {
        idea: [timeframe for timeframe in TIMEFRAMES if _candidate_supported(cfg, idea, timeframe)]
        for idea in (
            "po3",
            "order_block",
            "standard_deviation",
            "fvg_retest",
            "ifvg_retest",
            "ifvg_unretested",
        )
    }

    summary_rows: list[dict[str, Any]] = []
    grouped_rows: list[dict[str, Any]] = []
    horizon_rows: list[dict[str, Any]] = []
    identity_summary_rows: list[dict[str, Any]] = []
    identity_grouped_rows: list[dict[str, Any]] = []
    supported_candidate_streams: dict[int, tuple[pd.Series, pd.DataFrame]] = {}
    candidate_columns = dict(trade_setup_candidate_feature_columns())
    for candidate in TRADE_SETUP_CANDIDATES[1:]:
        column = candidate_columns[candidate.candidate_id]
        if column not in features.columns:
            active = pd.Series(False, index=index)
            column_present = False
        else:
            numeric = pd.to_numeric(features[column], errors="coerce")
            active = numeric.notna() & np.isfinite(numeric) & numeric.gt(0.0)
            column_present = True
        identity_frame = _candidate_identity_frame(features, candidate.candidate_id, active)
        identity_status = identity_frame["status"].to_numpy(dtype=object)
        identified = identity_status == "identified"
        missing_source_time = identity_status == "missing_source_event_time"
        assert candidate.idea is not None
        assert candidate.setup_timeframe is not None
        family_supported = candidate.setup_timeframe in support[candidate.idea]
        if family_supported:
            supported_candidate_streams[candidate.candidate_id] = (active, identity_frame)
        episode_start = active & ~active.shift(1, fill_value=False)
        summary_rows.append(
            {
                "candidate_id": candidate.candidate_id,
                "idea": candidate.idea,
                "timeframe": candidate.setup_timeframe,
                "direction": "long" if candidate.direction > 0 else "short",
                "feature_column": column,
                "feature_column_present": column_present,
                "family_enabled_by_audit_config": family_supported,
                "support_status": "supported" if family_supported else "unsupported_by_config",
                "active_m1_rows": int(active.sum()),
                "episode_starts": int(episode_start.sum()),
                "active_rows_in_configured_ny_session": int((active & session.eq("ny")).sum()),
            }
        )
        active_values = active.to_numpy(dtype=bool)
        identity_summary_rows.append(
            {
                "candidate_id": candidate.candidate_id,
                "idea": candidate.idea,
                "timeframe": candidate.setup_timeframe,
                "direction": "long" if candidate.direction > 0 else "short",
                "support_status": "supported" if family_supported else "unsupported_by_config",
                "active_m1_rows": int(active_values.sum()),
                "identified_source_event_rows": int(identified.sum()),
                "missing_source_event_time_rows": int(missing_source_time.sum()),
                "distinct_source_event_ids": _distinct_event_count(identity_frame, identified),
                "identity_coverage_fraction": (
                    float(identified.sum() / active_values.sum()) if active_values.any() else np.nan
                ),
                **_identity_lifecycle_metrics(identity_frame, active),
            }
        )

        for month in sorted(months.unique()):
            month_mask = months.eq(month)
            for regime in ("low", "middle", "high", "warmup_unknown"):
                group_mask = month_mask & volatility_regime.eq(regime)
                group_active = active & group_mask
                grouped_rows.append(
                    {
                        "candidate_id": candidate.candidate_id,
                        "idea": candidate.idea,
                        "timeframe": candidate.setup_timeframe,
                        "direction": "long" if candidate.direction > 0 else "short",
                        "month": month,
                        "volatility_regime": regime,
                        "support_status": "supported"
                        if family_supported
                        else "unsupported_by_config",
                        "m1_rows": int(group_mask.sum()),
                        "configured_ny_session_rows": int((group_mask & session.eq("ny")).sum()),
                        "active_m1_rows": int(group_active.sum()),
                        "episode_starts": int((episode_start & group_mask).sum()),
                        "active_rows_in_configured_ny_session": int(
                            (group_active & session.eq("ny")).sum()
                        ),
                    }
                )
                group_active_values = group_active.to_numpy(dtype=bool)
                group_identified = group_active_values & identified
                group_missing = group_active_values & missing_source_time
                identity_grouped_rows.append(
                    {
                        "candidate_id": candidate.candidate_id,
                        "idea": candidate.idea,
                        "timeframe": candidate.setup_timeframe,
                        "direction": "long" if candidate.direction > 0 else "short",
                        "month": month,
                        "volatility_regime": regime,
                        "support_status": "supported"
                        if family_supported
                        else "unsupported_by_config",
                        "active_m1_rows": int(group_active_values.sum()),
                        "identified_source_event_rows": int(group_identified.sum()),
                        "missing_source_event_time_rows": int(group_missing.sum()),
                        "distinct_source_event_ids": _distinct_event_count(
                            identity_frame, group_identified
                        ),
                    }
                )

        positions = np.flatnonzero(active.to_numpy())
        ids = session_id.to_numpy()
        for horizon in HORIZONS:
            future_positions = positions + horizon
            in_range = future_positions < len(index)
            same_day = np.zeros(len(positions), dtype=bool)
            same_day[in_range] = ids[future_positions[in_range]] == ids[positions[in_range]]
            horizon_rows.append(
                {
                    "candidate_id": candidate.candidate_id,
                    "idea": candidate.idea,
                    "timeframe": candidate.setup_timeframe,
                    "direction": "long" if candidate.direction > 0 else "short",
                    "horizon_m1_rows": horizon,
                    "support_status": "supported" if family_supported else "unsupported_by_config",
                    "active_rows_with_horizon_coverage": int(same_day.sum()),
                    "active_rows_without_horizon_coverage": int(len(positions) - same_day.sum()),
                }
            )

    summary = pd.DataFrame(summary_rows)
    grouped = pd.DataFrame(grouped_rows)
    horizons = pd.DataFrame(horizon_rows)
    identity_summary = pd.DataFrame(identity_summary_rows)
    identity_grouped = pd.DataFrame(identity_grouped_rows)
    alignment_rows: list[dict[str, Any]] = []
    supported_candidates = [
        candidate
        for candidate in TRADE_SETUP_CANDIDATES[1:]
        if candidate.candidate_id in supported_candidate_streams
    ]
    for left_position, left in enumerate(supported_candidates):
        assert left.idea is not None and left.setup_timeframe is not None
        for right in supported_candidates[left_position + 1 :]:
            assert right.idea is not None and right.setup_timeframe is not None
            if (
                left.idea != right.idea
                or left.direction != right.direction
                or left.setup_timeframe == right.setup_timeframe
            ):
                continue
            left_active, left_identity = supported_candidate_streams[left.candidate_id]
            right_active, right_identity = supported_candidate_streams[right.candidate_id]
            alignment_rows.append(
                {
                    "idea": left.idea,
                    "direction": "long" if left.direction > 0 else "short",
                    "left_candidate_id": left.candidate_id,
                    "left_timeframe": left.setup_timeframe,
                    "right_candidate_id": right.candidate_id,
                    "right_timeframe": right.setup_timeframe,
                    **_cross_timeframe_alignment_metrics(
                        left_identity, left_active, right_identity, right_active
                    ),
                }
            )
    cross_timeframe_alignment = pd.DataFrame(alignment_rows)
    source_time_tuple_clusters = _source_time_tuple_clusters(supported_candidate_streams)
    if len(summary) != 108:
        raise AssertionError(f"expected 108 candidates, found {len(summary)}")

    output_dir.mkdir(parents=True, exist_ok=True)
    resolved_config = OmegaConf.to_yaml(cfg, resolve=True)
    (output_dir / "resolved_config.yaml").write_text(resolved_config, encoding="utf-8")
    summary.to_csv(output_dir / "candidate_summary.csv", index=False)
    grouped.to_csv(output_dir / "candidate_month_regime.csv", index=False)
    horizons.to_csv(output_dir / "candidate_horizon_coverage.csv", index=False)
    identity_summary.to_csv(output_dir / "candidate_event_identity_summary.csv", index=False)
    identity_grouped.to_csv(output_dir / "candidate_event_identity_month_regime.csv", index=False)
    cross_timeframe_alignment.to_csv(
        output_dir / "candidate_event_cross_timeframe_alignment.csv", index=False
    )
    source_time_tuple_clusters.to_csv(
        output_dir / "candidate_source_time_tuple_clusters.csv", index=False
    )
    fvg_events.to_csv(output_dir / "fvg_retest_zone_event_ledger.csv", index=False)
    fvg_collisions.to_csv(output_dir / "fvg_retest_collisions.csv", index=False)
    fvg_monthly.to_csv(output_dir / "fvg_retest_monthly_collision_summary.csv", index=False)
    supported_timeframes = {
        idea: ", ".join(timeframes) if timeframes else "none"
        for idea, timeframes in support.items()
    }
    readme_lines = [
        "# Training-only trade-setup opportunity census",
        "",
        "This audit counts feature eligibility contexts under the registered trade-setup overlay. It does not simulate orders, fills, positions, P&L, or policy choices.",
        "",
        f"- Training dates: {train_start} through {train_end} inclusive.",
        f"- Primary instrument: `{primary_symbol}`; secondary input: `{secondary_symbol}`.",
        f"- M1 training rows: {len(primary):,}; feature-ready rows: {len(features):,}.",
        f"- Candidate catalog: {len(summary)} setup tuples; {int(summary['family_enabled_by_audit_config'].sum())} supported by the selected config and {int((~summary['family_enabled_by_audit_config']).sum())} unsupported by it.",
        f"- Source-event identity: {int(identity_summary['identified_source_event_rows'].sum()):,} active candidate rows resolve across {int(identity_summary['distinct_source_event_ids'].sum()):,} candidate-scoped event IDs; missing source times are counted separately.",
        "- Identity lifecycle counts measure contiguous source-time tuple episodes, adjacent tuple changes while a candidate remains active, and IDs reused across separate active-mask intervals; they do not establish logical event cardinality.",
        f"- Event identity contract: `{TRADE_SETUP_EVENT_IDENTITY_VERSION}` keys each selected candidate zone by its formation/confirmation source time where applicable; same-row nonselected overlapping zones are not separate category actions.",
        "- Ambiguous timestamp vectors are not represented in this scalar feature matrix; the row-level resolver tests that state separately.",
        "- Event-time encoding: source columns are nullable numeric features; epoch nanoseconds pass through float64 and can round at subsecond precision. Integer keys preserve bar-time identity at the configured minute resolution but are not exact nanosecond instants or publication timestamps.",
        "- Cross-timeframe alignment compares matching normalized integer source-time keys only for jointly active, configured candidates in the same idea and direction. Alignment is descriptive key evidence, not proof of shared logical event identity or event cardinality.",
        f"- Source-time key clusters: {len(source_time_tuple_clusters):,} family/direction/ordered-key groups across configured candidate streams; {(source_time_tuple_clusters['timeframe_count'] > 1).sum():,} occur on more than one timeframe and {(source_time_tuple_clusters['rows_with_multiple_timeframes'] > 0).sum():,} have simultaneous multi-timeframe rows. Candidate memberships sum to {int(source_time_tuple_clusters['candidate_count'].sum()):,}; {(source_time_tuple_clusters['candidate_count'] != source_time_tuple_clusters['timeframe_count']).sum():,} groups have a candidate/timeframe count mismatch. Key equality is a conservative linkage relation, not a validated ground-truth event ontology or complete logical-event count.",
        "- FVG retest event rows retain every M1 zone confirmation, including overlapping zones; the scalar-selection marker identifies the source zone projected by the existing feature. These detector confirmations are not candidate actions, orders, fills, or trades.",
        "- Source config: `config/base/default.yaml` plus `config/research/trade_setup_mtf_reasoning_2m.yaml`.",
        "- Volatility: trailing 20-M1 true range divided by close; tercile cutoffs fitted only on the in-sample rows.",
        "- Horizon coverage: later M1 rows on the same date-derived `session_id`, not a claim of quote availability or executable trades.",
        "- Session counts use configured `ny` labels emitted by the local data pipeline.",
        "",
        "## Source families enabled by config",
        "",
        "| Idea | Enabled source timeframes |",
        "|---|---|",
    ]
    readme_lines.extend(
        f"| `{idea}` | {timeframes} |" for idea, timeframes in supported_timeframes.items()
    )
    readme_lines.extend(
        [
            "",
            "The heatmap sums active candidate rows across supported timeframes and directions. Contexts can overlap, so it is not a count of unique decisions, orders, or trades. `warmup_unknown` rows are retained in the CSVs and omitted from the plot.",
            "The `fvg_retest_zone_event_ledger.csv`, `fvg_retest_collisions.csv`, and `fvg_retest_monthly_collision_summary.csv` files report per-zone M1 detector confirmations and scalar overlap selection by month/regime. They do not represent policy choices or trades.",
            "",
            "![Supported setup-context M1 rows by training month and volatility regime](candidate_month_regime_heatmap.png)",
            "",
            "Vector version: [candidate_month_regime_heatmap.pdf](candidate_month_regime_heatmap.pdf).",
            "",
            "## Reproduction",
            "",
            "Run from the repository root on an x86 CPU allocation with the matching environment:",
            "",
            "```bash",
            ".venv-x86/bin/python -m scripts.research.analysis.features.entry_idea_opportunity_census",
            "```",
            "",
            "The CSV files contain one row per candidate, month/regime cell, candidate/horizon pair, candidate event-identity summary, supported same-family cross-timeframe candidate pair, and family/direction/source-time key cluster. `candidate_source_time_tuple_clusters.csv` reports normalized key linkage and candidate/timeframe overlap; float-backed epoch nanoseconds can round at subsecond precision. It is not a complete ground-truth event ontology. IDs are candidate-scoped selected-source identities, not orders or trades. Identity lifecycle counters remain descriptive key/mask transitions. `resolved_config.yaml` and `census.json` record the config and source/data identities.",
            "The FVG event files contain per-zone detector confirmations only. They record training month and volatility regime for collision rows but do not represent additional policy actions or economic opportunities.",
            "",
            "Rebuild the heatmap from the census tables with:",
            "",
            "```bash",
            ".venv-x86/bin/python -m scripts.research.analysis.features.plot_entry_idea_opportunity_census",
            "```",
            "",
        ]
    )
    (output_dir / "README.md").write_text("\n".join(readme_lines), encoding="utf-8")
    raw_manifest = (
        ROOT
        / "evidence/research/releases/negative-evidence-readiness/RAW_DATA_SHA256_MANIFEST.json"
    )
    manifest_data = json.loads(raw_manifest.read_text(encoding="utf-8"))
    source_file_hashes: dict[str, str] = {}
    manifest_files = {entry["path"]: entry for entry in manifest_data["files"]}
    for symbol in (primary_symbol, secondary_symbol):
        spec = cfg.data.datasets.training
        files = [spec.m1_files[symbol]]
        files.extend(
            timeframe_files[symbol]
            for timeframe_files in spec.timeframe_files.values()
            if symbol in timeframe_files
        )
        for relative in files:
            relative_path = (Path(str(spec.raw_dir)) / str(relative)).as_posix()
            if relative_path not in manifest_files:
                raise ValueError(
                    f"training input absent from pinned local data manifest: {relative_path}"
                )
            entry = manifest_files[relative_path]
            input_path = ROOT / relative_path
            stat = input_path.stat()
            if stat.st_size != int(entry["size_bytes"]):
                raise ValueError(
                    f"training input size differs from pinned manifest: {relative_path}"
                )
            manifest_mtime = pd.Timestamp(entry["mtime_utc"]).timestamp()
            if abs(stat.st_mtime - manifest_mtime) > 1.0:
                raise ValueError(
                    f"training input mtime differs from pinned manifest: {relative_path}"
                )
            source_file_hashes[relative_path] = str(entry["sha256"])

    metadata = {
        "status": "descriptive_training_context_only",
        "interpretation": "Feature eligibility contexts only; not orders, fills, positions, or trades.",
        "source_commit": _git_commit(),
        "source_hashes": _source_hashes(),
        "config_path": (
            config_path.resolve().relative_to(ROOT.resolve()).as_posix()
            if config_path.resolve().is_relative_to(ROOT.resolve())
            else str(config_path.resolve())
        ),
        "resolved_config_sha256": hashlib.sha256(resolved_config.encode("utf-8")).hexdigest(),
        "training_period": {"start": train_start, "end_inclusive": train_end},
        "training_m1_rows": int(len(primary)),
        "feature_rows": int(len(features)),
        "source_timeframes": list(TIMEFRAMES),
        "candidate_count": int(len(summary)),
        "supported_candidate_count": int(summary["family_enabled_by_audit_config"].sum()),
        "unsupported_candidate_count": int((~summary["family_enabled_by_audit_config"]).sum()),
        "family_supported_timeframes": support,
        "regime_definition": "Trailing 20-M1 true range divided by close; tercile thresholds fitted on training-only rows.",
        "regime_thresholds": regime_thresholds,
        "horizon_definition": "Coverage means the specified number of later M1 rows exists on the same date-derived session_id; it is not execution or return evidence.",
        "source_event_identity_version": TRADE_SETUP_EVENT_IDENTITY_VERSION,
        "source_event_identity_definition": "A row resolves only when every family-required source timestamp is present; identity is deterministic within candidate and selected source-time key tuple, including the selected zone origin for FVG/IFVG/PO3. Same-row nonselected overlapping zones are not separate category actions. It is not linked to historical actions or trades unless captured in a shared rollout decision record.",
        "source_event_timestamp_encoding": "Feature event timestamps are normalized to integer nanosecond keys from nullable numeric columns. Current feature paths store epoch nanoseconds through float64, so keys can inherit subsecond rounding and are not exact nanosecond instants. The configured M1 bar-time keys remain separated at minute resolution; this representation does not establish feed publication time.",
        "source_event_lifecycle_counters": "The candidate summary counts contiguous identified-tuple episodes, adjacent tuple changes while active, and distinct tuple IDs appearing in multiple active-mask intervals. These are descriptive observed transitions, not ground-truth logical event cardinality.",
        "ambiguous_source_event_time_coverage": "Timestamp-vector ambiguity is tested at the row-level resolver. Same-row overlapping zones select one scalar source event and retain that selected origin; other colliding zones remain unrepresented.",
        "cross_timeframe_alignment_definition": "For supported candidates with the same idea and direction but different timeframes, counts rows where both are active, both source-time key tuples resolve, and their normalized integer keys match exactly. Float-backed epoch nanoseconds may be rounded at subsecond precision. This is descriptive alignment evidence, not proof of shared logical event identity or event cardinality.",
        "source_time_tuple_cluster_definition": "Across supported candidates, groups identified rows by family, direction, and ordered normalized source-time key tuple, ignoring candidate timeframe. The ledger reports candidate/timeframe multiplicity and row overlap. Integer key equality is a strict linkage audit over serialized feature values, not a complete ground-truth logical event ontology or complete logical-event count.",
        "source_time_tuple_cluster_counts": {
            "exact_family_direction_tuple_groups": int(len(source_time_tuple_clusters)),
            "candidate_memberships": int(source_time_tuple_clusters["candidate_count"].sum()),
            "groups_represented_on_multiple_timeframes": int(
                (source_time_tuple_clusters["timeframe_count"] > 1).sum()
            ),
            "groups_with_simultaneous_multitimeframe_rows": int(
                (source_time_tuple_clusters["rows_with_multiple_timeframes"] > 0).sum()
            ),
            "groups_with_candidate_timeframe_count_mismatch": int(
                (
                    source_time_tuple_clusters["candidate_count"]
                    != source_time_tuple_clusters["timeframe_count"]
                ).sum()
            ),
        },
        "fvg_retest_event_scope": "Configured M1 FVG detection and retest-buffer semantics on local primary-symbol training bars. Every per-zone confirmation is retained and reconciled to the unchanged scalar M1 feature. These are detector events, not policy proposals, orders, fills, or trades. Other timeframes and FVG configurations are not represented.",
        "fvg_retest_event_counts": {
            "per_zone_confirmations": int(len(fvg_events)),
            "scalar_confirmation_pulses": int(fvg_events["selected_by_scalar"].sum())
            if not fvg_events.empty
            else 0,
            "same_row_side_collision_groups": int(len(fvg_collisions)),
            "suppressed_per_zone_confirmations": int(
                fvg_collisions["suppressed_per_zone_confirmations"].sum()
            )
            if not fvg_collisions.empty
            else 0,
        },
        "fvg_config": {
            "reaction_buffer_fraction": _configured_fvg_config(cfg).reaction_buffer_fraction,
            "reaction_buffer_enabled": _configured_fvg_config(cfg).reaction_buffer_enabled,
        },
        "session_definition": "Configured session labels emitted by the local data pipeline.",
        "local_data_manifest": str(raw_manifest.relative_to(ROOT)),
        "local_data_manifest_sha256": hashlib.sha256(raw_manifest.read_bytes()).hexdigest(),
        "training_input_sha256": source_file_hashes,
        "output_files": [
            "candidate_summary.csv",
            "candidate_month_regime.csv",
            "candidate_horizon_coverage.csv",
            "candidate_event_identity_summary.csv",
            "candidate_event_identity_month_regime.csv",
            "candidate_event_cross_timeframe_alignment.csv",
            "candidate_source_time_tuple_clusters.csv",
            "fvg_retest_zone_event_ledger.csv",
            "fvg_retest_collisions.csv",
            "fvg_retest_monthly_collision_summary.csv",
            "resolved_config.yaml",
            "README.md",
        ],
    }
    (output_dir / "census.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _write_output_checksums(output_dir)
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    config_path = args.config if args.config.is_absolute() else ROOT / args.config
    cfg = load_config(config_path=config_path)
    cfg.features.entry_ideas.enabled = True
    result = build_census(cfg, args.output_dir, config_path=config_path)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
