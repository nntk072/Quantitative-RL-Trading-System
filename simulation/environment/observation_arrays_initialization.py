"""Focused simulation initialization service."""

from __future__ import annotations

from typing import Any, cast

import numpy as np
import pandas as pd

from decisioning.regime_observations import REGIME_FEATURES, regime_observation_schema
from decisioning.trade_setup import (
    candidate_geometry_observation_schema,
    trade_setup_candidate,
    trade_setup_observation_schema,
)
from features import attach_reachable_r, select_legacy_obs_columns, select_obs_columns
from features.context.trade_setup_candidates import trade_setup_candidate_feature_columns

from .mixin_base import RuntimeMixinBase
from .observations import (
    DEFAULT_HTF_WINDOWS,
    HTF_BRANCHES,
    split_obs_columns,
    timeframe_starts,
)


class ObservationArraysInitializationMixin(RuntimeMixinBase):
    """Build cached market and feature arrays used by observations and steps."""

    def _initialize_observation_arrays(
        self,
        bundle_data: Any | None,
        bars: pd.DataFrame | None,
        features: pd.DataFrame | None,
        legacy_sequence_columns: bool | None,
        sequence_columns_override: tuple[str, ...] | None,
        episodic: bool,
        obs_features_mmap: str | None,
        mtf: bool,
        mtf_windows: dict[str, int] | None,
        target_timeframes: tuple[str, ...],
        scheduled_session_closes: dict[str, str] | None,
        session_start: str,
        regime_observation: bool,
        trade_setup_actions: bool,
        trade_setup_candidate_timeframes: tuple[str, ...],
        completed_htf_history_enabled: bool,
        reachable_r_validity_mask: bool,
        feature_validity_channels: bool,
    ) -> None:
        """Build the cached inputs used by policy observations and decisions.

        Args:
            bundle_data: Optional memory-mapped or bundled market-data source.
            bars: Frame-backed market bars when no bundle is selected.
            features: Frame-backed engineered features when no bundle is selected.
            legacy_sequence_columns: Whether to use the legacy sequence-column selection.
            sequence_columns_override: Exact saved sequence columns for replay.
            episodic: Whether environment episodes may terminate on account failure.
            obs_features_mmap: Optional path for memory-mapped observation features.
            mtf: Whether to construct multi-timeframe observation arrays.
            mtf_windows: Configured lookback windows for higher timeframes.
            target_timeframes: Timeframes considered for target selection.
            scheduled_session_closes: Known close timestamps keyed by date.
            session_start: Local session start used for session identifiers.
            regime_observation: Whether regime fields are included in observations.
            trade_setup_actions: Whether setup masks are included in observations.
            trade_setup_candidate_timeframes: Timeframes allowed to contribute candidates.
            completed_htf_history_enabled: Whether completed HTF windows are policy inputs.
            reachable_r_validity_mask: Whether to add the reachability-validity feature.
            feature_validity_channels: Whether to append finite-value masks.
        """
        if sequence_columns_override is not None and (
            bundle_data is not None or mtf or obs_features_mmap is not None
        ):
            raise ValueError(
                "recorded sequence coordinates require a frame-backed single-sequence environment"
            )
        # Model-facing observation frame: the strategy's raw price-level
        # columns stay in ``features`` for execution/risk but must not enter
        # the normalised ``seq`` tensor (Agent.md §11). MTF blocks reuse the
        # same stems with a ``{TF}_`` prefix (e.g. ``M5_last_swing_high``),
        # matched via MTF_RAW_SUFFIXES so unnormalised HTF price magnitudes
        # never reach the encoder.
        # Drop non-numeric columns (e.g. string ``session`` labels) — they cannot
        # be cast to float32 and are not part of the model's normalized observation.
        self._reachable_r_validity_mask = bool(reachable_r_validity_mask)
        self.feature_validity_channels = bool(feature_validity_channels)
        self.completed_htf_history_enabled = bool(completed_htf_history_enabled)
        setup_feature_names = {name for _, name in trade_setup_candidate_feature_columns()}
        if self._bundle_arrays is None:
            assert bars is not None and features is not None
            self._legacy_sequence_columns = bool(legacy_sequence_columns)
            if sequence_columns_override is not None:
                if self._legacy_sequence_columns:
                    raise ValueError(
                        "recorded sequence coordinates cannot be combined with legacy selection"
                    )
                if not sequence_columns_override or len(sequence_columns_override) != len(
                    set(sequence_columns_override)
                ):
                    raise ValueError("sequence_columns_override must be non-empty and unique")
                generated_columns = {"reachable_r"}
                if self._reachable_r_validity_mask:
                    generated_columns.add("reachable_r_valid")
                missing = set(sequence_columns_override) - set(features.columns) - generated_columns
                if missing:
                    raise ValueError(
                        "sequence_columns_override contains columns missing from features: "
                        f"{sorted(missing)[:10]}"
                    )
                non_numeric = [
                    name
                    for name in sequence_columns_override
                    if name in features.columns
                    and not pd.api.types.is_numeric_dtype(features[name].dtype)
                ]
                if non_numeric:
                    raise ValueError(
                        "sequence_columns_override must contain numeric feature columns: "
                        f"{non_numeric[:10]}"
                    )
                if trade_setup_actions and setup_feature_names.intersection(
                    sequence_columns_override
                ):
                    raise ValueError(
                        "recorded sequence coordinates cannot include trade setup candidate features"
                    )
                selected = features.loc[
                    :, [name for name in sequence_columns_override if name in features.columns]
                ]
                self._obs_features = attach_reachable_r(
                    selected,
                    bars,
                    features,
                    include_validity_mask=self._reachable_r_validity_mask,
                ).loc[:, list(sequence_columns_override)]
            else:
                select_columns = (
                    select_legacy_obs_columns
                    if self._legacy_sequence_columns
                    else select_obs_columns
                )
                self._obs_features = attach_reachable_r(
                    select_columns(features, self.strategy.raw_columns),
                    bars,
                    features,
                    include_validity_mask=self._reachable_r_validity_mask,
                )
            if trade_setup_actions:
                self._obs_features = self._obs_features.drop(
                    columns=[
                        name for name in self._obs_features.columns if name in setup_feature_names
                    ]
                )
            self._obs_columns = list(self._obs_features.columns)
        else:
            assert bundle_data is not None
            if sequence_columns_override is not None:
                raise ValueError("recorded sequence coordinates are unsupported for bundled envs")
            self._obs_features = cast(pd.DataFrame, None)
            self._obs_columns = list(bundle_data.manifest["column_names"]["obs_features"])
            if trade_setup_actions and setup_feature_names.intersection(self._obs_columns):
                raise ValueError(
                    "env bundle observation columns contain trade setup candidate features; "
                    "rebuild the bundle for the versioned candidate-history contract"
                )
            saved_legacy_columns = bool(
                bundle_data.manifest.get("config", {}).get("legacy_sequence_columns", False)
            )
            saved_reachable_r_validity_mask = bool(
                bundle_data.manifest.get("config", {})
                .get("env", {})
                .get("reachable_r_validity_mask", False)
            )
            if legacy_sequence_columns is not None and bool(legacy_sequence_columns) != (
                saved_legacy_columns
            ):
                raise ValueError(
                    "requested legacy sequence-column mode differs from the saved env bundle"
                )
            if self._reachable_r_validity_mask != saved_reachable_r_validity_mask:
                raise ValueError(
                    "requested reachable-r validity-mask mode differs from the saved env bundle"
                )
            saved_completed_history = bool(
                bundle_data.manifest.get("config", {})
                .get("env", {})
                .get("completed_htf_history_enabled", True)
            )
            if self.completed_htf_history_enabled != saved_completed_history:
                raise ValueError(
                    "requested completed HTF history mode differs from the saved env bundle"
                )
            if trade_setup_actions:
                all_candidate_timeframes = (
                    "M1",
                    "M3",
                    "M5",
                    "M10",
                    "M15",
                    "M30",
                    "H1",
                    "H4",
                    "D1",
                )
                saved_candidate_timeframes = tuple(
                    str(tf).upper()
                    for tf in bundle_data.manifest.get("config", {})
                    .get("env", {})
                    .get("trade_setup_candidate_timeframes", all_candidate_timeframes)
                )
                requested_candidate_timeframes = tuple(
                    str(tf).upper() for tf in trade_setup_candidate_timeframes
                )
                if set(requested_candidate_timeframes) != set(saved_candidate_timeframes):
                    raise ValueError(
                        "requested trade setup candidate timeframes "
                        f"{sorted(set(requested_candidate_timeframes))} differ from the saved "
                        "env bundle contract "
                        f"{sorted(set(saved_candidate_timeframes))}"
                    )
            self._legacy_sequence_columns = saved_legacy_columns
        if self._legacy_sequence_columns and episodic:
            raise ValueError("legacy sequence columns are restricted to non-episodic replay")
        self._obs_features_mmap = obs_features_mmap

        # Cache numpy arrays for hot-path env stepping — avoids per-step pandas
        # iloc/Series-creation overhead that starves the GPU.
        #   - _obs_features / _features_arr: immutable post-construction
        #   - OHLC/spread bar caches: rebuilt via ``_sync_bar_arrays()`` (call
        #     again after in-place ``env.bars`` mutations in tests)
        # A read-only memmap is one shared copy for every SubprocVecEnv worker.
        if self._bundle_arrays is not None:
            self._obs_features_arr = self._bundle_arrays["obs_features"]
        elif obs_features_mmap:
            assert self._obs_features is not None
            shared = np.load(obs_features_mmap, mmap_mode="r")
            assert self._obs_features is not None
            if shared.shape != self._obs_features.shape:
                raise ValueError(
                    f"obs memmap shape {shared.shape} != obs columns {self._obs_features.shape}"
                )
            self._obs_features_arr = shared
        else:
            assert self._obs_features is not None
            self._obs_features_arr = self._obs_features.to_numpy(dtype=np.float32)
        self.mtf = bool(mtf)
        self._mtf_windows = dict(DEFAULT_HTF_WINDOWS)
        if mtf_windows:
            self._mtf_windows.update({str(k): int(v) for k, v in mtf_windows.items()})
            # Keep structural TP candidate sources fixed while the encoder gains
            # additional observation streams; these are separate experiment factors.
        self._target_timeframes = tuple(str(tf).upper() for tf in target_timeframes)
        if self._bundle_arrays is not None:
            assert bundle_data is not None
            self._features_cols = list(bundle_data.manifest["column_names"]["features_num"])
            self._features_arr = self._bundle_arrays["features_num"]
            self._bar_times = self._bundle_arrays["bar_time_ns"].view("datetime64[ns]")
            self._bar_time_index = pd.to_datetime(self._bundle_arrays["bar_time_ns"], utc=True)
            bundle_timezone = bundle_data.manifest.get("labels", {}).get("bar_timezone")
            if bundle_timezone:
                self._bar_time_index = self._bar_time_index.tz_convert(str(bundle_timezone))
            self._session_ids_arr = (
                self._bundle_arrays["bar_session_id"] if self._bundle_has_session_id else None
            )
        else:
            assert bars is not None and features is not None
            _feat_numeric = features.select_dtypes(include="number")
            self._features_cols = list(_feat_numeric.columns)
            self._features_arr = _feat_numeric.to_numpy()
            self._bar_times = bars.index.to_numpy()
            self._bar_time_index = pd.DatetimeIndex(bars.index)
            self._session_ids_arr = (
                bars["session_id"].to_numpy(dtype=np.int64)
                if "session_id" in bars.columns
                else None
            )
        self._m1_idx, self._htf_idx = split_obs_columns(self._obs_columns)
        self.regime_observation = bool(regime_observation)
        self.regime_observation_schema = regime_observation_schema() if regime_observation else None
        self.trade_setup_actions = bool(trade_setup_actions)
        allowed_timeframes = set(trade_setup_candidate_timeframes)
        unknown_timeframes = allowed_timeframes - set(
            ("M1", "M3", "M5", "M10", "M15", "M30", "H1", "H4", "D1")
        )
        if unknown_timeframes or not allowed_timeframes:
            raise ValueError(
                f"invalid trade setup candidate timeframes: {sorted(allowed_timeframes)}"
            )
        self._trade_setup_candidate_timeframes = tuple(
            tf
            for tf in ("M1", "M3", "M5", "M10", "M15", "M30", "H1", "H4", "D1")
            if tf in allowed_timeframes
        )
        self.trade_setup_observation_schema = (
            trade_setup_observation_schema(
                self._trade_setup_candidate_timeframes,
                completed_htf_history_enabled=self.completed_htf_history_enabled,
            )
            if self.trade_setup_actions
            else None
        )
        self.candidate_geometry_observation_schema = (
            candidate_geometry_observation_schema(
                self._trade_setup_candidate_timeframes,
                completed_htf_history_enabled=self.completed_htf_history_enabled,
            )
            if bool(getattr(self, "candidate_geometry_actions", False))
            else None
        )
        self._scheduled_session_closes = dict(scheduled_session_closes or {})
        self._session_start = str(session_start)
        self._trade_setup_mask_key = "trade_setup_mask"
        self._trade_setup_candidate_ids: np.ndarray[Any, Any] = np.empty(0, dtype=np.int64)
        self._trade_setup_feature_indices: np.ndarray[Any, Any] = np.empty(0, dtype=np.int64)
        if self.trade_setup_actions:
            columns = [
                (candidate_id, name)
                for candidate_id, name in trade_setup_candidate_feature_columns()
                if trade_setup_candidate(int(candidate_id)).setup_timeframe in allowed_timeframes
            ]
            column_indices = {name: index for index, name in enumerate(self._features_cols)}
            missing_setup_features = [name for _, name in columns if name not in column_indices]
            if missing_setup_features:
                raise ValueError(
                    "trade setup actions require all per-timeframe entry-idea feature columns; "
                    f"missing {missing_setup_features[:5]}"
                )
            self._trade_setup_candidate_ids = np.asarray(
                [candidate_id for candidate_id, _ in columns], dtype=np.int64
            )
            self._trade_setup_feature_indices = np.asarray(
                [column_indices[name] for _, name in columns], dtype=np.int64
            )
            if not self._trade_setup_candidate_ids.size:
                raise RuntimeError("trade setup candidate feature mapping is incomplete")
        missing_regime = [name for name in REGIME_FEATURES if name not in self._obs_columns]
        self._regime_idx = np.asarray(
            [
                self._obs_columns.index(name)
                for name in REGIME_FEATURES
                if name in self._obs_columns
            ],
            dtype=np.int64,
        )
        if self.regime_observation and missing_regime:
            raise ValueError(
                f"regime observation is missing required D1 features: {missing_regime}"
            )
        self._htf_starts: dict[str, np.ndarray[Any, Any]] = {}
        if self.mtf:
            for key, _, _ in HTF_BRANCHES:
                self._htf_starts[key] = timeframe_starts(
                    self._bar_time_index,
                    key.upper(),
                    scheduled_session_closes,
                    session_start,
                )
        self._features_col_to_idx = {c: i for i, c in enumerate(self._features_cols)}
        self._sync_bar_arrays()


__all__ = ["ObservationArraysInitializationMixin"]
