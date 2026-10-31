"""Focused simulation initialization service."""

from __future__ import annotations

from typing import Any, cast

import numpy as np
import pandas as pd

from decisioning.regime_observations import REGIME_FEATURES, regime_observation_schema
from decisioning.trade_setup import (
    TRADE_SETUP_CATEGORY_COUNT,
    legacy_thesis_observation_schema,
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
    def _initialize_observation_arrays(
        self,
        bundle_data: Any | None,
        bars: pd.DataFrame | None,
        features: pd.DataFrame | None,
        legacy_sequence_columns: bool | None,
        episodic: bool,
        obs_features_mmap: str | None,
        mtf: bool,
        mtf_windows: dict[str, int] | None,
        target_timeframes: tuple[str, ...],
        scheduled_session_closes: dict[str, str] | None,
        session_start: str,
        regime_observation: bool,
        trade_setup_actions: bool,
    ) -> None:
        # Model-facing observation frame: the strategy's raw price-level
        # columns stay in ``features`` for execution/risk but must not enter
        # the normalised ``seq`` tensor (Agent.md §11). MTF blocks reuse the
        # same stems with a ``{TF}_`` prefix (e.g. ``M5_last_swing_high``),
        # matched via MTF_RAW_SUFFIXES so unnormalised HTF price magnitudes
        # never reach the encoder.
        # Drop non-numeric columns (e.g. string ``session`` labels) — they cannot
        # be cast to float32 and are not part of the model's normalized observation.
        if self._bundle_arrays is None:
            assert bars is not None and features is not None
            self._legacy_sequence_columns = bool(legacy_sequence_columns)
            select_columns = (
                select_legacy_obs_columns if self._legacy_sequence_columns else select_obs_columns
            )
            self._obs_features: pd.DataFrame = attach_reachable_r(
                select_columns(features, self.strategy.raw_columns),
                bars,
                features,
            )
            self._obs_columns = list(self._obs_features.columns)
        else:
            assert bundle_data is not None
            self._obs_features = cast(pd.DataFrame, None)
            self._obs_columns = list(bundle_data.manifest["column_names"]["obs_features"])
            saved_legacy_columns = bool(
                bundle_data.manifest.get("config", {}).get("legacy_sequence_columns", False)
            )
            if legacy_sequence_columns is not None and bool(legacy_sequence_columns) != (
                saved_legacy_columns
            ):
                raise ValueError(
                    "requested legacy sequence-column mode differs from the saved env bundle"
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
        self.trade_setup_observation_schema = (
            trade_setup_observation_schema() if self.trade_setup_actions else None
        )
        self.thesis_observation_schema = (
            legacy_thesis_observation_schema()
            if self.trade_setup_actions and self.legacy_thesis_contract
            else None
        )
        self._trade_setup_mask_key = (
            "thesis_mask" if self.legacy_thesis_contract else "trade_setup_mask"
        )
        self._trade_setup_candidate_ids: np.ndarray[Any, Any] = np.empty(0, dtype=np.int64)
        self._trade_setup_feature_indices: np.ndarray[Any, Any] = np.empty(0, dtype=np.int64)
        if self.trade_setup_actions:
            columns = trade_setup_candidate_feature_columns()
            column_indices = {name: index for index, name in enumerate(self._obs_columns)}
            missing_setup_features = [name for _, name in columns if name not in column_indices]
            if missing_setup_features:
                contract_label = (
                    "legacy thesis actions"
                    if self.legacy_thesis_contract
                    else "trade setup actions"
                )
                raise ValueError(
                    f"{contract_label} require all per-timeframe entry-idea observation features; "
                    f"missing {missing_setup_features[:5]}"
                )
            self._trade_setup_candidate_ids = np.asarray(
                [candidate_id for candidate_id, _ in columns], dtype=np.int64
            )
            self._trade_setup_feature_indices = np.asarray(
                [column_indices[name] for _, name in columns], dtype=np.int64
            )
            if self._trade_setup_candidate_ids.size != TRADE_SETUP_CATEGORY_COUNT - 1:
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
