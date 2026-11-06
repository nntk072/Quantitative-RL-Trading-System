"""Build configured market features on a causal minute-level time index.

Technical indicators, structure, SMT, liquidity, session, and trade-setup
features are calculated on their configured source timeframes. Higher-timeframe
results are forward-filled onto the primary minute series only after the source
bar closes, preserving causal timing for the simulation and live consumers.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from omegaconf import DictConfig, OmegaConf

from artifacts.atomic import write_json_atomic
from configuration.paths import repository_root
from features.context.entry_ideas import build_entry_idea_features
from features.context.liquidity import detect_bos, detect_liquidity_sweeps, detect_mss
from features.context.order_blocks import build_order_block_features
from features.context.premium_discount import (
    build_htf_pd_distance_features,
    build_pd_context_features,
    build_trader_context_features,
)
from features.context.smt import smt_divergence
from features.context.swing_retracement import SWING_LEVELS, build_swing_retracement_features
from features.pipeline.feature_build_inputs import (
    DEFAULT_MTF_CONTEXT_TIMEFRAMES,
    configured_feature_timeframes,
    feature_block_enabled,
    resample_market_pair,
    source_timeframe_training_mask,
    split_raw_fvg_features,
)
from features.pipeline.feature_cache_identity import (
    FEATURE_CACHE_VERSION,
    feature_cache_content_hash,
)
from features.pipeline.normalization import (
    apply_rolling_zscore_state,
    fit_rolling_zscore_state,
    rolling_zscore,
)
from features.pipeline.po3_stage import append_po3_state_features
from features.pipeline.session_context_features import ensure_london_atr_distances
from features.pipeline.session_stage import append_session_features
from features.pipeline.structure_stage import append_structure_features
from features.po3.entries import build_po3_phase_features
from features.po3.fvg import build_fvg_zone_features
from features.po3.fvg_detection import FVGConfig
from features.po3.trigger_rules import detect_po3_entries
from features.technical.indicators import (
    atr,
    build_indicators,
    ny_session_clock,
    sweep_velocity,
    volume_spike,
    wick_ratio,
)
from features.technical.structure import (
    TIMEFRAME_CONFIG,
    detect_pivots,
    detect_session_levels,
    detect_swings,
)
from market_data.transforms.align import align_timeframes, timeframe_close_times
from market_data.transforms.resample import resample
from market_data.transforms.session_schedule import scheduled_session_close_map

_DEFAULT_HTF_TIMEFRAMES = DEFAULT_MTF_CONTEXT_TIMEFRAMES
# Capped normalised FVG distance: value used when no zone is active nearby.
_FVG_DIST_CAP = 5.0
# Kept off the z-score path: prices for the stop ladder, and the 0/1 retest
# and active flags the entry gate reads on any timeframe prefix.

# Numeric encoding of detect_po3_entries' entry_trigger_type string column so
# the feature matrix stays homogeneous float (TradingEnv casts to float32).
_PO3_TRIGGER_CODE = {"": 0, "retest": 1, "close_through": 2, "ltf_fvg": 3}


def _normalization_configuration_sha256(cfg: DictConfig | None, *, mode: str, window: int) -> str:
    """Hash only configuration that defines feature values and their fit.

    Args:
        cfg: Resolved run config whose feature, strategy, session, and data settings matter.
        mode: Normalization fit mode.
        window: Rolling-statistic lookback in bars.

    Returns:
        SHA-256 digest for the feature and normalization configuration.
    """
    payload: dict[str, Any] = {
        "feature_cache_version": FEATURE_CACHE_VERSION,
        "mode": mode,
        "window": int(window),
    }
    if cfg is not None:
        feature_cfg = OmegaConf.select(cfg, "features", default={})
        strategy_cfg = OmegaConf.select(cfg, "strategy", default={})
        session_cfg = OmegaConf.select(cfg, "session", default={})
        payload["features"] = (
            OmegaConf.to_container(feature_cfg, resolve=True)
            if OmegaConf.is_config(feature_cfg)
            else feature_cfg
        )
        payload["strategy"] = (
            OmegaConf.to_container(strategy_cfg, resolve=True)
            if OmegaConf.is_config(strategy_cfg)
            else strategy_cfg
        )
        payload["session"] = (
            OmegaConf.to_container(session_cfg, resolve=True)
            if OmegaConf.is_config(session_cfg)
            else session_cfg
        )
        data_fields = (
            "data.primary",
            "data.secondary",
            "data.timeframes",
            "data.tz",
            "data.timestamp_clock",
            "data.session_schedule_file",
        )
        payload["data"] = {
            field: OmegaConf.select(cfg, field, default=None) for field in data_fields
        }
        payload["point_size"] = OmegaConf.select(cfg, "costs.point_size", default=None)
        schedule_value = OmegaConf.select(cfg, "data.session_schedule_file", default=None)
        if schedule_value:
            schedule_path = Path(str(schedule_value)).expanduser()
            if not schedule_path.is_absolute():
                schedule_path = repository_root(__file__) / schedule_path
            payload["session_schedule_sha256"] = (
                hashlib.sha256(schedule_path.read_bytes()).hexdigest()
                if schedule_path.is_file()
                else "missing"
            )
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


# Default MTF subset for SMT divergence, structure, and liquidity sweeps. Each
# block accepts an explicit list of standard resampled timeframes; the bounded
# default keeps column growth predictable.


def build_features(
    primary: pd.DataFrame,
    secondary: pd.DataFrame | None = None,
    cfg: DictConfig | None = None,
    train_mask: pd.Series | None = None,
    cache_path: Path | None = None,
    force: bool = False,
    normalization_mode: str = "legacy_masked_window",
    timeframe_bars: dict[str, pd.DataFrame] | None = None,
    secondary_timeframe_bars: dict[str, pd.DataFrame] | None = None,
    fit_state_path: Path | None = None,
    fitted_normalization_state: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """Build the full feature matrix for the primary instrument.

    Args:
        primary: Cleaned, session-filtered M1 DataFrame (US100).
        secondary: US500 M1 DataFrame for SMT divergence (optional but recommended).
        cfg: Full OmegaConf config; ``cfg.features`` sub-node is used.
        train_mask: Boolean Series aligned to primary index; True = training bar.
        cache_path: If given, save/load feature parquet here.
        force: Ignore existing cache.
        normalization_mode: Normalization behavior used for continuous feature columns.
        timeframe_bars: Optional precomputed primary bars indexed by timeframe.
        secondary_timeframe_bars: Optional precomputed correlated-symbol bars by timeframe.
        fit_state_path: Persist the train-only normalization fit state beside this run/cache.
        fitted_normalization_state: Apply a previously captured state without refitting.

    Returns:
        DataFrame returned by ``build_features``.
    """
    expected_hash = feature_cache_content_hash(
        cfg,
        primary,
        train_mask=train_mask,
        secondary=secondary,
        normalization_mode=normalization_mode,
        timeframe_bars=timeframe_bars,
        secondary_timeframe_bars=secondary_timeframe_bars,
    )
    normalization_window = (
        int(cfg.features.zscore_window) if cfg is not None and "features" in cfg else 252
    )
    normalization_config_sha256 = _normalization_configuration_sha256(
        cfg, mode=normalization_mode, window=normalization_window
    )
    if fit_state_path is not None and fitted_normalization_state is not None:
        raise ValueError("fit_state_path and fitted_normalization_state are mutually exclusive")
    if fit_state_path is not None and train_mask is None:
        raise ValueError("persisting a feature normalization state requires a training mask")
    if fitted_normalization_state is not None:
        if fitted_normalization_state.get("schema") != "feature-normalization-v1":
            raise ValueError("unsupported feature normalization state")
        if fitted_normalization_state.get("configuration_sha256") != normalization_config_sha256:
            raise ValueError(
                "feature normalization state does not match the effective configuration"
            )
        if fitted_normalization_state.get("mode") != normalization_mode:
            raise ValueError("feature normalization state mode differs from the requested mode")
        if fitted_normalization_state.get("window") != normalization_window:
            raise ValueError("feature normalization state window differs from the effective config")
        stages = fitted_normalization_state.get("stages")
        if not isinstance(stages, dict):
            raise ValueError("feature normalization state must contain stage fits")
        for stage_name, stage_state in stages.items():
            if not isinstance(stage_state, dict):
                raise ValueError(f"feature normalization stage {stage_name!r} is malformed")
            if (
                stage_state.get("mode") != normalization_mode
                or stage_state.get("window") != normalization_window
            ):
                raise ValueError(
                    f"feature normalization stage {stage_name!r} differs from the run fit contract"
                )
    requested_reference_mode = str(
        (OmegaConf.select(cfg, "features.po3_reference_mode") if cfg is not None else None)
        or "m1_legacy"
    )
    sweep_audit_path = Path(str(cache_path) + ".htf_sweeps.parquet") if cache_path else None
    if cache_path and Path(cache_path).exists() and not force:
        meta_path = Path(str(cache_path) + ".hash")
        state_ready = fit_state_path is None
        if fit_state_path is not None and fit_state_path.is_file():
            try:
                cached_state = json.loads(fit_state_path.read_text(encoding="utf-8"))
                cached_stages = cached_state.get("stages", {})
                matrix_fit = (
                    cached_stages.get("matrix") if isinstance(cached_stages, dict) else None
                )
                source_fit = (
                    cached_stages.get("source:D1") if isinstance(cached_stages, dict) else None
                )
                source_fit_required = bool(
                    cfg is not None
                    and OmegaConf.select(
                        cfg, "features.normalize_d1_technical_on_source", default=False
                    )
                )
                if isinstance(matrix_fit, dict):
                    apply_rolling_zscore_state(
                        pd.DataFrame(columns=matrix_fit.get("columns", [])), matrix_fit
                    )
                if isinstance(source_fit, dict):
                    apply_rolling_zscore_state(
                        pd.DataFrame(columns=source_fit.get("columns", [])), source_fit
                    )
                state_ready = (
                    cached_state.get("schema") == "feature-normalization-v1"
                    and cached_state.get("feature_cache_hash") == expected_hash
                    and cached_state.get("configuration_sha256") == normalization_config_sha256
                    and isinstance(matrix_fit, dict)
                    and (not source_fit_required or isinstance(source_fit, dict))
                )
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                state_ready = False
        audit_ready = requested_reference_mode != "htf_confirmed" or (
            sweep_audit_path is not None and sweep_audit_path.exists()
        )
        if (
            audit_ready
            and state_ready
            and meta_path.exists()
            and meta_path.read_text(encoding="utf-8").strip() == expected_hash
        ):
            return pd.read_parquet(cache_path)
            # Stale or pre-hash cache: rebuild rather than silently reuse.

    feat_cfg = cfg.features if cfg is not None else None
    captured_stages: dict[str, dict[str, Any]] = {}
    secondary_m1: pd.DataFrame | None = secondary  # M1 copy kept for per-TF resampling
    primary_timeframes = {str(tf).upper(): frame for tf, frame in (timeframe_bars or {}).items()}
    primary_timeframes["M1"] = primary
    secondary_timeframe_frames = {
        str(tf).upper(): frame for tf, frame in (secondary_timeframe_bars or {}).items()
    }
    if secondary is not None:
        secondary_timeframe_frames["M1"] = secondary
    scheduled_closes = scheduled_session_close_map(cfg)
    session_start = str(OmegaConf.select(cfg, "session.start") or "16:30") if cfg else "16:30"

    def primary_tf_bars(tf: str) -> pd.DataFrame:
        """Return cached primary bars or derive them for one timeframe.

        Args:
            tf: Target market timeframe label.

        Returns:
            Primary-symbol OHLC bars at the requested timeframe.
        """
        key = str(tf).upper()
        frame = primary_timeframes.get(key)
        if frame is None:
            frame = primary if key == "M1" else resample(primary, key)  # type: ignore[arg-type]
            primary_timeframes[key] = frame
        return frame

    def align_blocks(
        target: pd.DataFrame,
        blocks: dict[str, pd.DataFrame],
        *,
        completed_bars: bool = True,
    ) -> pd.DataFrame:
        """Align feature blocks using their timestamped bar-close availability.

        Args:
            target: Base timeframe index that receives the merged features.
            blocks: Higher-timeframe feature blocks keyed by timeframe.
            completed_bars: Whether to shift blocks that lack close timestamps.

        Returns:
            Target rows with causally aligned feature columns.
        """
        availability = {
            str(tf): timeframe_close_times(
                primary_tf_bars(str(tf)), str(tf), scheduled_closes, session_start
            )
            for tf in blocks
        }
        return align_timeframes(
            target,
            blocks,
            completed_bars=completed_bars,
            availability_times=availability,
        )

    htf_sweep_audit = pd.DataFrame()

    if feat_cfg is not None:
        feat = build_indicators(primary, feat_cfg)
    else:
        # fallback: basic returns only
        feat = pd.DataFrame(
            {"ret_1": np.log(primary["close"]).diff()},
            index=primary.index,
        )

        # M1 block is z-scored with the rest; per-TF blocks join before
        # normalisation for the same treatment. Secondary is resampled from its
        # own M1 bars so each TF compares like-for-like bars.
    if secondary is not None and feat_cfg is not None:
        smt = smt_divergence(
            primary,
            secondary,
            swing_period=int(getattr(feat_cfg, "smt_swing_period", 5)),
            corr_window=int(getattr(feat_cfg, "smt_corr_window", 20)),
        )
        feat = pd.concat([feat, smt], axis=1)
        if feature_block_enabled(feat_cfg, "smt", False):
            smt_tfs = configured_feature_timeframes(feat_cfg, "smt", DEFAULT_MTF_CONTEXT_TIMEFRAMES)
            smt_blocks: dict[str, pd.DataFrame] = {}
            for tf in smt_tfs:
                if str(tf) == "M1":
                    continue  # M1 already present unprefixed
                pri_tf, sec_tf = resample_market_pair(
                    primary,
                    secondary_m1,
                    str(tf),
                    primary_timeframes,
                    secondary_timeframe_frames,
                )
                if sec_tf is None or pri_tf.empty or sec_tf.empty:
                    continue
                smt_blocks[str(tf)] = smt_divergence(
                    pri_tf,
                    sec_tf,
                    swing_period=int(getattr(feat_cfg, "smt_swing_period", 5)),
                    corr_window=int(getattr(feat_cfg, "smt_corr_window", 20)),
                )
            if smt_blocks:
                feat = align_blocks(feat, smt_blocks)

                # Run the same indicator build on each HTF's own bars, then causally
                # forward-fill onto the M1 spine. Done BEFORE normalisation so HTF
                # columns are z-scored like the M1 ones.
    d1_source_normalized_columns: list[str] = []
    if feat_cfg is not None:
        window = int(feat_cfg.zscore_window)
        normalize_d1_on_source = bool(getattr(feat_cfg, "normalize_d1_technical_on_source", False))
        htf_cfg_tfs = getattr(feat_cfg, "htf_timeframes", None)
        htf_tfs = list(htf_cfg_tfs) if htf_cfg_tfs is not None else list(_DEFAULT_HTF_TIMEFRAMES)
        if htf_tfs:
            htf_blocks: dict[str, pd.DataFrame] = {}
            for tf in htf_tfs:
                tf_name = str(tf).upper()
                tf_bars = primary_tf_bars(tf_name)
                block = build_indicators(tf_bars, feat_cfg)
                if tf_name == "D1" and normalize_d1_on_source:
                    daily_train_mask = source_timeframe_training_mask(
                        tf_bars,
                        primary,
                        train_mask,
                        tf_name,
                        scheduled_closes,
                        session_start,
                    )
                    if fitted_normalization_state is not None:
                        source_state = fitted_normalization_state.get("stages", {}).get("source:D1")
                        if not isinstance(source_state, dict):
                            raise ValueError("feature normalization state is missing source:D1 fit")
                        block = apply_rolling_zscore_state(block, source_state)
                    else:
                        if fit_state_path is not None:
                            if train_mask is None:
                                raise ValueError(
                                    "persisting a feature normalization state requires a training mask"
                                )
                            if daily_train_mask is None:
                                raise ValueError(
                                    "persisting D1 source normalization requires a training mask"
                                )
                            captured_stages["source:D1"] = fit_rolling_zscore_state(
                                block,
                                train_mask=daily_train_mask,
                                window=window,
                                mode=normalization_mode,
                            )
                        block = rolling_zscore(
                            block,
                            window=window,
                            train_mask=daily_train_mask,
                            mode=normalization_mode,
                        )
                    d1_source_normalized_columns = [f"D1_{column}" for column in block.columns]
                htf_blocks[tf_name] = block
            feat = align_blocks(feat, htf_blocks)

    _fvg_raw = pd.DataFrame(index=primary.index)
    if feat_cfg is not None:
        # PO3 phase tag: time-derived, identical across TFs once aligned.
        if bool(getattr(feat_cfg, "include_po3", False)):
            session = OmegaConf.select(cfg, "session") if cfg is not None else None
            po3 = build_po3_phase_features(
                pd.DatetimeIndex(primary.index),
                session_start=str(session.get("start", "16:30")) if session else "16:30",
                session_end=str(session.get("end", "23:00")) if session else "23:00",
            )
            feat = pd.concat([feat, po3], axis=1)

            # FVG zones cover the primary timeframe and configured higher timeframes.
            # build_fvg_zone_features is TF-agnostic, so this is purely what goes
            # into the loop: ["M1"] + htf_timeframes (config-overridable via
            # fvg_timeframes), giving M1_fvg_*/M5_fvg_*/... columns.
        if bool(getattr(feat_cfg, "include_fvg_ifvg", False)):
            fvg_cfg_tfs = getattr(feat_cfg, "fvg_timeframes", None)
            if fvg_cfg_tfs is not None:
                fvg_tfs = [str(t) for t in list(fvg_cfg_tfs)]
            else:
                fvg_tfs = ["M1", *[str(t) for t in htf_tfs]]
            fvg_blocks: dict[str, pd.DataFrame] = {}
            configured_buffer_fraction = (
                OmegaConf.select(cfg, "features.gap_reaction_buffer_fraction")
                if cfg is not None
                else None
            )
            configured_buffer_enabled = (
                OmegaConf.select(cfg, "features.gap_reaction_buffer_enabled")
                if cfg is not None
                else None
            )
            buffer_enabled = (
                True if configured_buffer_enabled is None else bool(configured_buffer_enabled)
            )
            reaction_buffer_fraction = (
                (
                    float(configured_buffer_fraction)
                    if configured_buffer_fraction is not None
                    else 0.1
                )
                if buffer_enabled
                else 0.0
            )
            for tf in fvg_tfs:
                tf_bars = primary_tf_bars(str(tf))
                fvg_blocks[str(tf)] = build_fvg_zone_features(
                    tf_bars,
                    fvg_config=FVGConfig(
                        reaction_buffer_fraction=reaction_buffer_fraction,
                        reaction_buffer_enabled=buffer_enabled,
                    ),
                )
            feat = align_blocks(feat, fvg_blocks)
            # Zone prices and the retest flag must stay raw. The distance
            # columns above are normalised with the rest of the matrix.
            feat, _fvg_raw = split_raw_fvg_features(feat)

    window = feat_cfg.zscore_window if feat_cfg is not None else 252
    if feat_cfg is not None and d1_source_normalized_columns:
        source_normalized_columns = [
            column for column in d1_source_normalized_columns if column in feat
        ]
        original_columns = list(feat.columns)
        source_normalized = feat[source_normalized_columns]
        matrix_to_normalize = feat.drop(columns=source_normalized_columns)
        if fitted_normalization_state is not None:
            matrix_state = fitted_normalization_state.get("stages", {}).get("matrix")
            if not isinstance(matrix_state, dict):
                raise ValueError("feature normalization state is missing matrix fit")
            feat = apply_rolling_zscore_state(matrix_to_normalize, matrix_state)
        else:
            if fit_state_path is not None:
                if train_mask is None:
                    raise ValueError(
                        "persisting a feature normalization state requires a training mask"
                    )
                captured_stages["matrix"] = fit_rolling_zscore_state(
                    matrix_to_normalize,
                    train_mask=train_mask,
                    window=window,
                    mode=normalization_mode,
                )
            feat = rolling_zscore(
                matrix_to_normalize,
                window=window,
                train_mask=train_mask,
                mode=normalization_mode,
            )
        feat = pd.concat([feat, source_normalized], axis=1).reindex(columns=original_columns)
    else:
        if fitted_normalization_state is not None:
            matrix_state = fitted_normalization_state.get("stages", {}).get("matrix")
            if not isinstance(matrix_state, dict):
                raise ValueError("feature normalization state is missing matrix fit")
            feat = apply_rolling_zscore_state(feat, matrix_state)
        else:
            if fit_state_path is not None:
                if train_mask is None:
                    raise ValueError(
                        "persisting a feature normalization state requires a training mask"
                    )
                captured_stages["matrix"] = fit_rolling_zscore_state(
                    feat,
                    train_mask=train_mask,
                    window=window,
                    mode=normalization_mode,
                )
            feat = rolling_zscore(
                feat, window=window, train_mask=train_mask, mode=normalization_mode
            )
    if len(_fvg_raw.columns) > 0:
        feat = pd.concat([feat, _fvg_raw], axis=1)

    feat, structure, _mtf_struct_levels = append_structure_features(
        primary,
        feat,
        feature_config=feat_cfg,
        cfg=cfg,
        resample_pair=lambda timeframe: resample_market_pair(
            primary, None, timeframe, primary_timeframes
        ),
        align_blocks=align_blocks,
        timeframe_list=configured_feature_timeframes,
        enabled=feature_block_enabled,
        default_timeframes=DEFAULT_MTF_CONTEXT_TIMEFRAMES,
    )

    # Context-qualified order blocks are calculated on each source timeframe,
    # then aligned only after that source candle is complete. Price boundaries
    # remain raw metadata for stop/target selection; flags and ATR distances are
    # available to the policy as features.
    if feat_cfg is not None and feature_block_enabled(feat_cfg, "order_blocks", False):
        ob_cfg = getattr(feat_cfg, "order_blocks", None)
        ob_blocks: dict[str, pd.DataFrame] = {}
        ob_tfs = configured_feature_timeframes(
            feat_cfg, "order_blocks", ("M1", *_DEFAULT_HTF_TIMEFRAMES)
        )
        swing_period = int(getattr(ob_cfg, "swing_period", 5))
        impulse_atr = float(getattr(ob_cfg, "impulse_atr", 0.5))
        search_bars = int(getattr(ob_cfg, "search_bars", 10))
        max_age_bars = int(getattr(ob_cfg, "max_age_bars", 240))
        if "M1" in {str(tf).upper() for tf in ob_tfs}:
            feat = pd.concat(
                [
                    feat,
                    build_order_block_features(
                        primary,
                        swing_period=swing_period,
                        impulse_atr=impulse_atr,
                        search_bars=search_bars,
                        max_age_bars=max_age_bars,
                    ),
                ],
                axis=1,
            )
        for timeframe in ob_tfs:
            tf_name = str(timeframe).upper()
            if tf_name == "M1":
                continue
            tf_bars = primary_tf_bars(tf_name)
            if tf_bars.empty:
                continue
            ob_blocks[tf_name] = build_order_block_features(
                tf_bars,
                swing_period=swing_period,
                impulse_atr=impulse_atr,
                search_bars=search_bars,
                max_age_bars=max_age_bars,
            )
        if ob_blocks:
            feat = align_blocks(feat, ob_blocks)

            # Added AFTER normalization so the 0/1 entry signals and the numeric
            # trigger code keep their raw meaning (exactly like structure levels).
    if feat_cfg is not None and bool(getattr(feat_cfg, "include_po3_full", False)):
        po3_htf = str(getattr(feat_cfg, "po3_htf", "M15")).upper()
        po3_ltf = str(getattr(feat_cfg, "po3_ltf", "M5")).upper()
        po3_signals = detect_po3_entries(
            primary,
            htf=po3_htf,
            primary_tf=po3_ltf,
            timeframe_bars=primary_timeframes,
            availability_times={
                po3_htf: timeframe_close_times(
                    primary_tf_bars(po3_htf), po3_htf, scheduled_closes, session_start
                ),
                po3_ltf: timeframe_close_times(
                    primary_tf_bars(po3_ltf), po3_ltf, scheduled_closes, session_start
                ),
            },
        )
        po3_feats = po3_signals[["entry_long", "entry_short", "entry_trigger_type"]].copy()
        # entry_trigger_type is a string column; encode numerically so the
        # matrix stays homogeneous float for TradingEnv's float32 cast.
        po3_feats["entry_trigger_type"] = (
            po3_feats["entry_trigger_type"].map(_PO3_TRIGGER_CODE).fillna(0.0).astype("float64")
        )
        feat = pd.concat([feat, po3_feats], axis=1)

    levels = detect_session_levels(primary)
    feat = pd.concat([feat, levels], axis=1)
    from market_data.transforms.activity import activity_series

    vol_s = activity_series(primary)
    if vol_s is not None:
        feat["volume_spike"] = volume_spike(vol_s, window=20)
    feat["atr_5"] = atr(primary, period=5)

    include_pd = feat_cfg is not None and bool(getattr(feat_cfg, "include_pd_context", False))
    if include_pd:
        sess_tz = "Etc/GMT-3"
        if cfg is not None:
            sess_tz = str(
                OmegaConf.select(cfg, "strategy.session.timezone")
                or OmegaConf.select(cfg, "session.tz")
                or OmegaConf.select(cfg, "data.tz")
                or sess_tz
            )
        pd_ctx = build_pd_context_features(primary, feat["atr_5"], tz=sess_tz)
        feat = pd.concat([feat, pd_ctx], axis=1)

        # Align higher-timeframe swing and session-range distances separately
        # from the copied technical indicators.
        htf_cfg_tfs = getattr(feat_cfg, "htf_timeframes", None)
        htf_tfs = list(htf_cfg_tfs) if htf_cfg_tfs is not None else list(_DEFAULT_HTF_TIMEFRAMES)
        pd_htf_blocks: dict[str, pd.DataFrame] = {}
        for tf in htf_tfs:
            pri_tf, _ = resample_market_pair(primary, None, str(tf), primary_timeframes)
            if pri_tf.empty:
                continue
            tf_cfg = TIMEFRAME_CONFIG.get(str(tf), TIMEFRAME_CONFIG["M1"])
            pd_htf_blocks[str(tf)] = build_htf_pd_distance_features(
                pri_tf,
                feat["atr_5"],
                swing_period=int(tf_cfg["left"]),
                atr_mult=float(tf_cfg["atr_mult"]),
            )
        if pd_htf_blocks:
            feat = align_blocks(feat, pd_htf_blocks)

    sweep_vel = sweep_velocity(
        primary,
        london_high=levels.get("london_high"),
        london_low=levels.get("london_low"),
        asian_high=levels.get("asian_high"),
        asian_low=levels.get("asian_low"),
        atr_period=5,
    )
    feat = pd.concat([feat, sweep_vel], axis=1)

    feat["wick_ratio"] = wick_ratio(primary)

    # Build sweeps on each resampled timeframe to preserve source-bar timing;
    # widened M1 windows would change their meaning.
    _mtf_sweep_levels: dict[str, pd.DataFrame] = {}
    if feat_cfg is not None and feature_block_enabled(feat_cfg, "liquidity", False):
        swing = int(getattr(feat_cfg, "smt_swing_period", 5))
        sweep_blocks: dict[str, pd.DataFrame] = {}
        for tf in configured_feature_timeframes(
            feat_cfg, "liquidity", DEFAULT_MTF_CONTEXT_TIMEFRAMES
        ):
            if str(tf) == "M1":
                continue
            pri_tf, _ = resample_market_pair(primary, None, str(tf), primary_timeframes)
            if pri_tf.empty:
                continue
            sweeps_tf = detect_liquidity_sweeps(pri_tf, swing_period=swing)
            tf_cfg = TIMEFRAME_CONFIG.get(str(tf), TIMEFRAME_CONFIG["M1"])
            pivots_tf = detect_pivots(pri_tf, left=int(tf_cfg["left"]), right=int(tf_cfg["right"]))
            swings_tf = detect_swings(pri_tf, pivots_tf, atr_mult=float(tf_cfg["atr_mult"]))
            events_tf = swings_tf[["swing_high_event", "swing_low_event"]].astype(float)
            sweep_blocks[str(tf)] = pd.concat([sweeps_tf, events_tf], axis=1)
            _mtf_sweep_levels[str(tf)] = detect_session_levels(pri_tf)
        if sweep_blocks:
            feat = align_blocks(feat, sweep_blocks)

            # Needs atr_5 (computed above) + aligned {TF}_swing levels via ffill.
    if (
        feat_cfg is not None
        and feature_block_enabled(feat_cfg, "structure", False)
        and _mtf_struct_levels
    ):
        atr5_m1 = feat["atr_5"].where(feat["atr_5"] > 0)
        for tf, lv_tf in _mtf_struct_levels.items():
            hi = lv_tf["last_swing_high"].reindex(feat.index, method="ffill")
            lo = lv_tf["last_swing_low"].reindex(feat.index, method="ffill")
            feat[f"{tf}_dist_to_swing_high_atr"] = (hi - primary["close"]) / atr5_m1
            feat[f"{tf}_dist_to_swing_low_atr"] = (primary["close"] - lo) / atr5_m1

    feat, htf_sweep_audit = append_po3_state_features(
        primary,
        feat,
        feature_config=feat_cfg,
        cfg=cfg,
        primary_timeframes=primary_timeframes,
        scheduled_closes=scheduled_closes,
        session_start=session_start,
        levels=levels,
        structure=structure,
        mtf_sweep_levels=_mtf_sweep_levels,
        align_blocks=align_blocks,
    )

    # With include_strategy_state, BOS is already present; with include_pd_context
    # alone we add BOS here. MSS is always paired when either flag is on.
    need_ltf_stack = feat_cfg is not None and (
        bool(getattr(feat_cfg, "include_strategy_state", False))
        or bool(getattr(feat_cfg, "include_pd_context", False))
    )
    if need_ltf_stack and structure is not None:
        atr5_ltf = feat["atr_5"].where(feat["atr_5"] > 0)
        if "bos_up" not in feat.columns:
            bos_m1 = detect_bos(primary, structure)
            feat = pd.concat([feat, bos_m1], axis=1)
        if "bos_up_dist_atr" not in feat.columns:
            feat["bos_up_dist_atr"] = (feat["bos_up_level"] - primary["close"]) / atr5_ltf
            feat["bos_down_dist_atr"] = (primary["close"] - feat["bos_down_level"]) / atr5_ltf
        if "mss_up" not in feat.columns:
            bos_for_mss = feat[["bos_up", "bos_down", "bos_up_level", "bos_down_level"]]
            mss_m1 = detect_mss(primary, structure, bos_for_mss)
            feat = pd.concat([feat, mss_m1], axis=1)
        if "mss_up_dist_atr" not in feat.columns:
            feat["mss_up_dist_atr"] = (feat["mss_up_level"] - primary["close"]) / atr5_ltf
            feat["mss_down_dist_atr"] = (primary["close"] - feat["mss_down_level"]) / atr5_ltf

    feat = append_session_features(primary, feat, cfg, feat_cfg)

    # Trader-context columns depend on premium/discount context or strategy-state features.
    need_trader_ctx = feat_cfg is not None and (
        bool(getattr(feat_cfg, "include_strategy_state", False))
        or bool(getattr(feat_cfg, "include_pd_context", False))
    )
    if need_trader_ctx:
        trader_ctx = build_trader_context_features(feat)
        for col in trader_ctx.columns:
            feat[col] = trader_ctx[col]

    feat = ensure_london_atr_distances(feat, primary["close"])
    # Retain decision price for opt-in setup-entry gating but exclude it from
    # the model observation sequence.
    if feat_cfg is not None and bool(getattr(feat_cfg, "include_previous_session_pd", False)):
        feat["decision_close"] = primary["close"].reindex(feat.index)
    session = OmegaConf.select(cfg, "session") if cfg is not None else None
    session_start = str(session.get("start", "16:30")) if session else "16:30"
    session_end = str(session.get("end", "23:00")) if session else "23:00"
    clock = ny_session_clock(pd.DatetimeIndex(feat.index), session_start, session_end)
    feat = pd.concat([feat, clock], axis=1)

    # The fib-like swing retracement idea is calculated independently on each
    # configured timeframe. Higher-timeframe signals are visible only after
    # that source candle closes.
    if feat_cfg is not None and feature_block_enabled(feat_cfg, "entry_ideas", False):
        idea_timeframes = configured_feature_timeframes(
            feat_cfg,
            "entry_ideas",
            ("M1", *_DEFAULT_HTF_TIMEFRAMES),
        )
        retracement_low = float(getattr(feat_cfg.entry_ideas, "retracement_low", 0.5))
        retracement_high = float(getattr(feat_cfg.entry_ideas, "retracement_high", 0.786))
        raw_levels = getattr(feat_cfg.entry_ideas, "levels", SWING_LEVELS)
        retracement_levels = tuple(float(value) for value in raw_levels)
        if not 0.0 <= retracement_low < retracement_high <= 1.0:
            raise ValueError("entry-idea retracement bounds must satisfy 0 <= low < high <= 1")
        retracement_blocks: dict[str, pd.DataFrame] = {}
        for timeframe in idea_timeframes:
            tf_name = str(timeframe).upper()
            if tf_name not in TIMEFRAME_CONFIG:
                raise ValueError(f"unsupported entry-idea timeframe: {tf_name}")
            tf_bars = primary_tf_bars(tf_name)
            if tf_bars.empty:
                continue
            tf_config = TIMEFRAME_CONFIG[tf_name]
            block = build_swing_retracement_features(
                tf_bars,
                swing_period=int(tf_config["left"]),
                atr_mult=float(tf_config["atr_mult"]),
                retracement_low=retracement_low,
                retracement_high=retracement_high,
                level_values=retracement_levels,
            )
            if tf_name == "M1":
                feat = pd.concat([feat, block], axis=1)
            elif not tf_bars.empty:
                retracement_blocks[tf_name] = block
        if retracement_blocks:
            feat = align_blocks(feat, retracement_blocks)

            # Preserve concurrent ideas as independent flags; one candidate
            # must not suppress another.
        feat = pd.concat([feat, build_entry_idea_features(feat)], axis=1)

    feat = feat.dropna(how="all")
    feat.columns = feat.columns.map(str)
    duplicate_columns = feat.columns[feat.columns.duplicated()].unique().tolist()
    if duplicate_columns:
        sample = duplicate_columns[:20]
        raise ValueError(
            "feature builder produced duplicate column names "
            f"({len(duplicate_columns)} unique duplicates): {sample}"
        )

    if cache_path:
        path = Path(cache_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        feat.to_parquet(path)
        if requested_reference_mode == "htf_confirmed" and sweep_audit_path is not None:
            htf_sweep_audit.to_parquet(sweep_audit_path)
        path.with_name(path.name + ".hash").write_text(expected_hash + "\n", encoding="utf-8")

    if fit_state_path is not None:
        final_state = {
            "schema": "feature-normalization-v1",
            "configuration_sha256": normalization_config_sha256,
            "feature_cache_hash": expected_hash,
            "mode": normalization_mode,
            "window": normalization_window,
            "stages": captured_stages,
        }
        if "matrix" not in captured_stages:
            raise RuntimeError("feature builder did not capture its matrix normalization fit")
        write_json_atomic(fit_state_path, final_state, default=None)

    return feat
