"""Feature build pipeline: indicators + SMT + normalisation → feature matrix.

Chain A: per-timeframe technical features. For every timeframe listed in
``cfg.features.htf_timeframes`` the same ``build_indicators()`` call used
for M1 is run on that timeframe's own bars, then causally forward-filled
onto the M1 spine via :func:`market_data.transforms.align.align_timeframes` with
``{TF}_{indicator}`` column names.

MTF extensions (mtf_feature_expansion_plan.md §§4.1-4.6): SMT divergence
(§4.1), structure levels + BOS (§4.2) and liquidity sweeps (§4.3) follow the
same resample → per-TF compute → ``align_timeframes`` pattern; FVG zones
(§4.5) run over the full ladder (M1 + HTFs); PO3 manipulation/distribution
state (§4.4) and IFVG active zones (§4.6) are independently computed on
configured standard timeframes, including M10, then aligned to the M1 spine.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from omegaconf import DictConfig, OmegaConf

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
    feature_cache_content_hash,
)
from features.pipeline.normalization import rolling_zscore
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

# Bump whenever build_features() output schema changes so stale caches are
# not silently reused by the {symbol}_features.parquet call sites.
# v4: Chain F + causal PO3 mapping — detect_htf_fvg/detect_ltf_ifvg now shift
# signals one HTF/primary period forward (no within-period lookahead).
# v5: Idea 1 strategy state — liquidity sweeps, PO3 manipulation/distribution
# state and IFVG active zones (include_strategy_state opt-in block).
# v6: CT-anchored session levels — session OHLC, yesterday/last-week H/L,
# range quadrants and raw vwap (include_session_ohlc opt-in block).
# v7: MTF expansion (plan §§4.1-4.6) — per-TF SMT divergence (§4.1),
# structure/BOS (§4.2) and liquidity sweeps (§4.3) via the Chain-A
# resample → per-TF compute → align_timeframes pattern; FVG zones over the
# full M1+HTF ladder (§4.5); PO3 state (§4.4) and IFVG zones (§4.6) use
# configured supported timeframes and align onto the M1 spine.
# v8: full-day M1 spine, completed-bar HTF ffill, confirmed ATR swings.
# v10: PD context, VWAP off.
# v11: content-hash cache key (config + data identity + optional train_mask).
# v12: trader-context columns (htf_day_bias, manip_reverses_htf, context_trade_direction).
# v13: tick-count VWAP / activity (ignore CFD vol=0).
# v14: swing age in [0, 1], London ATR distances, NY session clock.
# v15: swing confirmation pulses and the distribution-after-IFVG latch.
# v16: SL modes (state machine + agent veto), prev-NY session H/L, swing
#      history columns (swing_high_{1..3}/swing_low_{1..3}), TF-SMT enablement.
# v22: causal completed prior-NY levels use the configured NY session window.
# v25: context-qualified order-block zones across the configured timeframe ladder.
# v26: separate, overlapping PO3, Order Block, FVG-retest, and swing-retracement ideas.
# v31: a confirmed IFVG body-close is a directional entry idea; cache identity
#      also includes strategy.ifvg settings, including its close-through buffer.
# v32: expose FVG retest, IFVG retest, and unretested IFVG as separate ideas.
# v33: retain per-timeframe idea and same-timeframe overlap flags for the policy.


_DEFAULT_HTF_TIMEFRAMES = DEFAULT_MTF_CONTEXT_TIMEFRAMES
# Capped normalised FVG distance: value used when no zone is active nearby.
_FVG_DIST_CAP = 5.0
# Kept off the z-score path: prices for the stop ladder, and the 0/1 retest
# and active flags the entry gate reads on any timeframe prefix.

# Numeric encoding of detect_po3_entries' entry_trigger_type string column so
# the feature matrix stays homogeneous float (TradingEnv casts to float32).
_PO3_TRIGGER_CODE = {"": 0, "retest": 1, "close_through": 2, "ltf_fvg": 3}

# Default MTF subset for SMT divergence (§4.1), structure/BOS (§4.2), and
# liquidity sweeps (§4.3). Each block accepts an explicit list of any standard
# resampled timeframe; the bounded default keeps column growth predictable.


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
) -> pd.DataFrame:
    """Build the full feature matrix for the primary instrument.

    Parameters
    ----------
    primary:
        Cleaned, session-filtered M1 DataFrame (US100).
    secondary:
        US500 M1 DataFrame for SMT divergence (optional but recommended).
    cfg:
        Full OmegaConf config; ``cfg.features`` sub-node is used.
    train_mask:
        Boolean Series aligned to primary index; True = training bar.
    cache_path:
        If given, save/load feature parquet here.
    force:
        Ignore existing cache.
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
    requested_reference_mode = str(
        (OmegaConf.select(cfg, "features.po3_reference_mode") if cfg is not None else None)
        or "m1_legacy"
    )
    sweep_audit_path = Path(str(cache_path) + ".htf_sweeps.parquet") if cache_path else None
    if cache_path and Path(cache_path).exists() and not force:
        meta_path = Path(str(cache_path) + ".hash")
        audit_ready = requested_reference_mode != "htf_confirmed" or (
            sweep_audit_path is not None and sweep_audit_path.exists()
        )
        if (
            audit_ready
            and meta_path.exists()
            and meta_path.read_text(encoding="utf-8").strip() == expected_hash
        ):
            return pd.read_parquet(cache_path)
            # Stale or pre-hash cache: rebuild rather than silently reuse.

    feat_cfg = cfg.features if cfg is not None else None
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

    # --- base indicators ---
    if feat_cfg is not None:
        feat = build_indicators(primary, feat_cfg)
    else:
        # fallback: basic returns only
        feat = pd.DataFrame(
            {"ret_1": np.log(primary["close"]).diff()},
            index=primary.index,
        )

        # --- SMT divergence (M1 always; MTF optional §4.1) ---
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

                # --- Higher-timeframe technical features (Chain A) ---
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
                    block = rolling_zscore(
                        block,
                        window=window,
                        train_mask=daily_train_mask,
                        mode=normalization_mode,
                    )
                    d1_source_normalized_columns = [f"D1_{column}" for column in block.columns]
                htf_blocks[tf_name] = block
            feat = align_blocks(feat, htf_blocks)

            # --- Chain B variant blocks (opt-in via config flags) ---
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

            # FVG zone features (plan §4.5): full M1+HTF ladder, not HTFs only.
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

            # --- normalisation ---
    window = feat_cfg.zscore_window if feat_cfg is not None else 252
    if feat_cfg is not None and d1_source_normalized_columns:
        source_normalized_columns = [
            column for column in d1_source_normalized_columns if column in feat
        ]
        original_columns = list(feat.columns)
        source_normalized = feat[source_normalized_columns]
        feat = rolling_zscore(
            feat.drop(columns=source_normalized_columns),
            window=window,
            train_mask=train_mask,
            mode=normalization_mode,
        )
        feat = pd.concat([feat, source_normalized], axis=1).reindex(columns=original_columns)
    else:
        feat = rolling_zscore(feat, window=window, train_mask=train_mask, mode=normalization_mode)
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

            # --- Full PO3 pipeline (Chain F): HTF FVG -> LTF IFVG -> entry triggers ---
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

        # --- Liquidity Levels + Volume Spike + ATR - add AFTER normalization ---
    levels = detect_session_levels(primary)
    feat = pd.concat([feat, levels], axis=1)
    from market_data.transforms.activity import activity_series

    vol_s = activity_series(primary)
    if vol_s is not None:
        feat["volume_spike"] = volume_spike(vol_s, window=20)
    feat["atr_5"] = atr(primary, period=5)

    # --- Session-conditional PD context (opt-in) ---
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

        # HTF swing / session-range PD distances onto M1 (beyond indicator copies).
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

            # --- Sweep Velocity and Wick Ratio - for PLAN 3 ---
            # Add sweep velocity (uses liquidity levels from levels)
    sweep_vel = sweep_velocity(
        primary,
        london_high=levels.get("london_high"),
        london_low=levels.get("london_low"),
        asian_high=levels.get("asian_high"),
        asian_low=levels.get("asian_low"),
        atr_period=5,
    )
    feat = pd.concat([feat, sweep_vel], axis=1)

    # Add wick ratio
    feat["wick_ratio"] = wick_ratio(primary)

    # --- Liquidity sweep MTF (plan §4.3) ---
    # True per-TF sweeps on genuinely resampled OHLC (not M1 proxies with
    # wider windows). Opt-in; follows the structure/BOS placement rule.
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

            # --- MTF structure/BOS ATR distances (plan §4.2, second half) ---
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

    # --- LTF BOS + MSS decision stack ---
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

    # --- Trader-context HTF bias / manip reverse / trade direction ---
    # Wired when PD context or strategy state is on (Idea 1/2).
    need_trader_ctx = feat_cfg is not None and (
        bool(getattr(feat_cfg, "include_strategy_state", False))
        or bool(getattr(feat_cfg, "include_pd_context", False))
    )
    if need_trader_ctx:
        trader_ctx = build_trader_context_features(feat)
        for col in trader_ctx.columns:
            feat[col] = trader_ctx[col]

    feat = ensure_london_atr_distances(feat, primary["close"])
    # Raw decision price is retained only for the opt-in Idea 2 entry gate
    # and excluded from the model observation sequence.
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

            # Add explicit directional multi-hot flags after all source families
            # exist. Concurrent ideas stay visible together; none gates another.
        feat = pd.concat([feat, build_entry_idea_features(feat)], axis=1)

        # Drop leading NaNs from warmup
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

    return feat
