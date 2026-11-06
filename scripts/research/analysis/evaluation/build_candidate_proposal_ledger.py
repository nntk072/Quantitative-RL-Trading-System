#!/usr/bin/env python3
"""Build a training-only ledger of causal setup and price-level proposals.

The ledger records bounded market and source-zone midpoint proposals and the
production structural stop/target menus available at each decision. It does not
replay proposal outcomes or estimate policy value.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from omegaconf import DictConfig, OmegaConf
from scripts.research.analysis.features.training_context import (
    DEFAULT_CONFIG,
    candidate_supported,
    training_slice,
)

from configuration.configuration_loader import load_config
from configuration.paths import repository_root
from decisioning.trade_setup import NO_TRADE_ID, TRADE_SETUP_CANDIDATES
from evaluation.candidate_eligibility import CandidateActionEligibilityIndex
from evaluation.candidate_proposals import build_decision_proposals
from features import build_features
from features.context.entry_ideas import entry_idea_context
from features.context.reachability import max_tp_distance
from features.context.trade_setup_candidates import (
    trade_setup_candidate_event_identities,
    trade_setup_candidate_feature_columns,
)
from features.technical.indicators import atr as calculate_atr
from market_data.loading import build_tick_books
from market_data.loading.market_data_ingestion import run_pipeline
from simulation.environment.trading_environment_factory import strategy_from_cfg
from trading.orders import place_strategy_order

ROOT = repository_root(__file__)
DEFAULT_OUTPUT = ROOT / "evidence/research/candidate_proposals"
PROPOSAL_TTL_MINUTES = 60
SOURCE_FILES = (
    "scripts/research/analysis/evaluation/build_candidate_proposal_ledger.py",
    "evaluation/candidate_proposals.py",
    "evaluation/candidate_eligibility.py",
    "decisioning/trade_setup.py",
    "features/context/entry_ideas.py",
    "features/context/reachability.py",
    "features/context/trade_setup_candidates.py",
    "features/pipeline/feature_matrix_builder.py",
    "features/pipeline/feature_cache_identity.py",
    "market_data/loading/ticks.py",
    "trading/orders/entries.py",
    "trading/orders/stops.py",
    "trading/orders/targets.py",
    "simulation/environment/trading_environment_factory.py",
    "simulation/environment/episode_runtime.py",
    "simulation/environment/action_intent_runtime.py",
    "simulation/environment/diagnostics_runtime.py",
    "simulation/environment/step_action_execution.py",
)
DATA_MANIFEST = (
    ROOT / "evidence/research/releases/negative-evidence-readiness/RAW_DATA_SHA256_MANIFEST.json"
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _training_input_hashes(cfg: DictConfig) -> dict[str, str]:
    manifest = json.loads(DATA_MANIFEST.read_text(encoding="utf-8"))
    by_path = {str(item["path"]): item for item in manifest["files"]}
    spec = cfg.data.datasets.training
    raw_dir = Path(str(spec.raw_dir))
    paths: set[str] = set()
    for symbol in (str(cfg.data.primary), str(cfg.data.secondary)):
        paths.add(str(spec.m1_files[symbol]))
        paths.add(str(spec.tick_files[symbol]))
        for timeframe_files in spec.timeframe_files.values():
            if symbol in timeframe_files:
                paths.add(str(timeframe_files[symbol]))
    hashes: dict[str, str] = {}
    for relative in sorted(paths):
        relative_path = (raw_dir / relative).as_posix()
        expected = by_path.get(relative_path)
        if expected is None:
            raise ValueError(f"training input absent from local data manifest: {relative_path}")
        path = ROOT / relative_path
        stat = path.stat()
        if stat.st_size != int(expected["size_bytes"]):
            raise ValueError(f"training input size differs from manifest: {relative_path}")
        if _sha256_file(path) != str(expected["sha256"]):
            raise ValueError(f"training input SHA-256 differs from manifest: {relative_path}")
        hashes[relative_path] = str(expected["sha256"])
    return hashes


def _active_mask(
    features: pd.DataFrame, candidate_id: int, column: str | None
) -> np.ndarray[Any, Any]:
    if column is None or column not in features.columns:
        return np.zeros(len(features), dtype=bool)
    values = pd.to_numeric(features[column], errors="coerce").to_numpy(dtype=float)
    return np.asarray(np.isfinite(values) & (values > 0.0), dtype=bool)


def _timestamp_ns(value: str | int) -> pd.Timestamp:
    if isinstance(value, (int, np.integer)):
        return pd.Timestamp(int(value), unit="ns", tz="UTC")
    return pd.Timestamp(value)


def _candidate_zone(
    row: pd.Series,
    candidate: Any,
    *,
    standard_deviation_timeframes: tuple[str, ...],
) -> tuple[tuple[float, float], str] | None:
    """Choose one deterministic source zone relevant to the active category."""
    if candidate.idea == "standard_deviation":
        timeframe = str(candidate.setup_timeframe).upper()
        prefix = "" if timeframe == "M1" else f"{timeframe}_"
        low_name = f"{prefix}standard_deviation_band_low"
        high_name = f"{prefix}standard_deviation_band_high"
        if low_name not in row or high_name not in row:
            return None
        low = pd.to_numeric(pd.Series([row[low_name]]), errors="coerce").iloc[0]
        high = pd.to_numeric(pd.Series([row[high_name]]), errors="coerce").iloc[0]
        if not np.isfinite(low) or not np.isfinite(high) or low > high:
            return None
        start = row.get("standard_deviation_leg_start_time_ns", "")
        end = row.get("standard_deviation_leg_end_time_ns", "")
        identity = f"standard_deviation:{timeframe}:{start}:{end}:{low:.12g}:{high:.12g}"
        return (float(low), float(high)), identity

    context = entry_idea_context(row, int(candidate.direction), include_zones=True)
    matches = [
        zone
        for zone in context["zones"]
        if zone["idea"] == candidate.idea
        and str(zone["timeframe"]).upper() == str(candidate.setup_timeframe).upper()
    ]
    # Prefer an IFVG reference for PO3 when both projections share the same zone.
    matches.sort(
        key=lambda zone: (
            0 if candidate.idea == "po3" and zone["family"] == "ifvg" else 1,
            str(zone["family"]),
            int(zone.get("start_time_ns") or 0),
            float(zone["low"]),
            float(zone["high"]),
        )
    )
    if not matches:
        return None
    zone = matches[0]
    start = zone.get("start_time_ns")
    identity = (
        f"{candidate.idea}:{zone['family']}:{zone['timeframe']}:{start}:"
        f"{float(zone['low']):.12g}:{float(zone['high']):.12g}"
    )
    return (float(zone["low"]), float(zone["high"])), identity


def _production_menus(
    *,
    cfg: DictConfig,
    strategy: Any,
    candidate: Any,
    row: pd.Series,
    entry_price: float,
    reachable_distance: float,
) -> tuple[tuple[tuple[str, float], ...], tuple[tuple[str, float], ...]] | None:
    atr_value = pd.to_numeric(pd.Series([row.get("atr_5", np.nan)]), errors="coerce").iloc[0]
    atr = float(atr_value) if np.isfinite(atr_value) and atr_value > 0.0 else 0.0
    min_distance = max(
        float(cfg.risk.get("min_sl_points", 0.0)),
        float(cfg.risk.get("min_sl_atr_mult", 0.5)) * atr,
    )
    max_tp_distance = float(reachable_distance)
    rr_values = tuple(float(value) for value in cfg.risk.get("rr_range", (1.5, 5.0)))
    if len(rr_values) != 2:
        raise ValueError("risk.rr_range must contain exactly two values")
    rr_bounds = (rr_values[0], rr_values[1])
    geometry = place_strategy_order(
        strategy,
        direction=int(candidate.direction),
        entry_price=float(entry_price),
        feat_row=row,
        min_dist=min_distance,
        sl_fraction=0.5,
        tp_fraction=0.5,
        exit_mode="structural",
        buffer_pts=float(cfg.env.get("sl_buffer_pts", 0.0)),
        max_tp_distance=max_tp_distance,
        rr_bounds=rr_bounds,
        htf=tuple(str(value) for value in cfg.risk.get("target_timeframes", ("M5", "M15", "H1"))),
        entry_timeframe_floor=str(candidate.setup_timeframe),
        standard_deviation_timeframes=(
            (str(candidate.setup_timeframe),) if candidate.idea == "standard_deviation" else None
        ),
        allow_multi_tp=False,
        allow_simplex=False,
        target_front_run_pts=float(cfg.risk.get("target_front_run_pts", 0.0)),
        price_increment=float(cfg.costs.point_size),
        trade_setup=candidate,
    )
    if not geometry.sl_menu or not geometry.tp_menu:
        return None
    return tuple(geometry.sl_menu), tuple(geometry.tp_menu)


def build_ledger(
    cfg: DictConfig,
    output_dir: Path,
    *,
    config_path: Path,
    ttl_minutes: int = PROPOSAL_TTL_MINUTES,
) -> dict[str, Any]:
    """Generate training-only candidate proposals and a coverage/refusal census."""
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite existing proposal packet: {output_dir}")
    if ttl_minutes <= 0:
        raise ValueError("ttl_minutes must be positive")
    if not bool(cfg.env.get("strategy_actions", False)):
        raise ValueError("candidate geometry audit config must enable strategy_actions")
    cfg.features.entry_ideas.enabled = True
    training_inputs = _training_input_hashes(cfg)
    cfg.data.cache_dir = str(ROOT / "cache/trade_setup_opportunity_census")
    data = run_pipeline(cfg, datasets=["training"])
    primary_symbol = str(cfg.data.primary)
    secondary_symbol = str(cfg.data.secondary)
    train_start, train_end = str(cfg.data.split.train_start), str(cfg.data.split.train_end)
    primary_frames = training_slice(data[primary_symbol], train_start, train_end)
    secondary_frames = training_slice(data[secondary_symbol], train_start, train_end)
    bars = primary_frames["M1"]
    if bars.empty or not bars.index.is_unique:
        raise ValueError("configured training M1 bars must be non-empty and unique")
    if not {"session", "session_id"}.issubset(bars.columns):
        raise ValueError("training M1 bars must preserve environment session labels and IDs")
    features = build_features(
        bars,
        secondary_frames["M1"],
        cfg=cfg,
        train_mask=pd.Series(True, index=bars.index, dtype=bool),
        timeframe_bars=primary_frames,
        secondary_timeframe_bars=secondary_frames,
    )
    if not features.index.equals(bars.index) or not features.columns.is_unique:
        raise ValueError("training feature matrix must uniquely align to the M1 index")
    features = features.copy()
    features["close"] = pd.to_numeric(bars["close"], errors="coerce")
    features["atr"] = calculate_atr(bars, int(cfg.features.atr_period))
    if "atr_5" not in features:
        raise ValueError("production structural order geometry requires atr_5")
    reachable = max_tp_distance(bars, features["atr_5"]).reindex(bars.index)

    tickbook = build_tick_books(
        cfg,
        symbols=[primary_symbol],
        datasets=["training"],
    ).get(primary_symbol)
    if tickbook is None:
        raise ValueError("candidate proposal ledger requires the configured training TickBook")
    strategy, _strategy_reward, _strategy_weight = strategy_from_cfg(cfg)
    feature_columns = dict(trade_setup_candidate_feature_columns())
    candidate_stats: dict[int, Counter[str]] = defaultdict(Counter)
    proposals: list[dict[str, Any]] = []
    identified_events: set[tuple[int, str]] = set()
    eligible_events: set[tuple[int, str]] = set()
    proposal_events: set[tuple[int, str]] = set()
    quote_cache: dict[int, tuple[pd.Timestamp, float, float] | None] = {}
    ttl = pd.Timedelta(minutes=ttl_minutes)
    price_increment = float(cfg.costs.point_size)
    session_values = bars["session"].astype(str)
    eligibility = CandidateActionEligibilityIndex(
        pd.DatetimeIndex(bars.index),
        session_values,
        session_ids=bars["session_id"],
        fill_latency_bars=int(cfg.execution.get("fill_latency_bars", 0)),
        open_manipulation_bars=int(cfg.env.get("open_manipulation_bars", 0)),
        block_overnight=bool(cfg.env.get("block_overnight", True)),
    )
    latency_ms_raw = float(cfg.execution.get("randomized_fill_latency_ms", 0.0))
    for candidate in TRADE_SETUP_CANDIDATES:
        if candidate.candidate_id == NO_TRADE_ID:
            continue
        if candidate.idea is None or candidate.setup_timeframe is None:
            raise AssertionError("nonzero catalog candidates require semantic metadata")
        stats = candidate_stats[candidate.candidate_id]
        if not candidate_supported(cfg, candidate.idea, candidate.setup_timeframe):
            stats["unsupported_by_config"] += 1
            continue
        active = _active_mask(
            features, candidate.candidate_id, feature_columns.get(candidate.candidate_id)
        )
        stats["active_rows"] = int(active.sum())
        for position in np.flatnonzero(active):
            row = features.iloc[int(position)]
            stats["active_event_rows_seen"] += 1
            identity_values = trade_setup_candidate_event_identities(row, [candidate.candidate_id])
            if not identity_values:
                stats["missing_identity"] += 1
                continue
            identity = identity_values[0]
            if identity.status != "identified" or identity.source_event_id is None:
                stats[f"identity_{identity.status}"] += 1
                continue
            event_key = (candidate.candidate_id, identity.source_event_id)
            if event_key in proposal_events:
                continue
            if event_key not in identified_events:
                identified_events.add(event_key)
                stats["unique_identified_events"] += 1
            bar_start = pd.Timestamp(bars.index[int(position)])
            decision_time = bar_start + pd.Timedelta(minutes=1)
            action_eligibility = eligibility.classify(int(position))
            if not action_eligibility.eligible:
                stats[f"policy_ineligible_{action_eligibility.reason}_rows"] += 1
                continue
            if event_key not in eligible_events:
                eligible_events.add(event_key)
                stats["unique_policy_eligible_events"] += 1
            stats["eligible_candidate_rows_examined"] += 1
            event_times = [stamp for _field, stamp in identity.source_event_times_ns]
            confirmation_time = _timestamp_ns(max(event_times))
            if confirmation_time > decision_time:
                stats["source_event_after_decision_rows"] += 1
                continue
            if int(position) not in quote_cache:
                quotes = tickbook.bar_quotes(bar_start, bar_minutes=1)
                last_quote = None
                for last_quote in quotes:
                    pass
                quote_cache[int(position)] = last_quote
            quote = quote_cache[int(position)]
            if quote is None:
                stats["missing_closed_bar_quote_rows"] += 1
                continue
            quote_time, bid, ask = quote
            if quote_time > decision_time:
                stats["quote_after_decision_rows"] += 1
                continue
            atr_value = pd.to_numeric(pd.Series([row["atr_5"]]), errors="coerce").iloc[0]
            atr_scale = float(atr_value) if np.isfinite(atr_value) and atr_value > 0 else None
            session = str(session_values.iloc[int(position)])
            feature_availability = [
                "eligible_setup_flag",
                "identified_source_event",
                "closed_bar_tick_quote",
                "atr_5" if atr_scale is not None else "atr_5_unavailable",
            ]

            def geometry_for_entry(
                price: float,
                _candidate: Any = candidate,
                _row: pd.Series = row,
                _position: int = int(position),
            ) -> tuple[tuple[tuple[str, float], ...], tuple[tuple[str, float], ...]] | None:
                geometry = _production_menus(
                    cfg=cfg,
                    strategy=strategy,
                    candidate=_candidate,
                    row=_row,
                    entry_price=price,
                    reachable_distance=float(reachable.iloc[_position]),
                )
                if geometry is None:
                    return None
                return geometry

            common: dict[str, Any] = {
                "source_event_id": identity.source_event_id,
                "signal_confirmed_at": confirmation_time.isoformat(),
                "quote_observed_at": quote_time.isoformat(),
                "valid_from": decision_time.isoformat(),
                "expires_at": (decision_time + ttl).isoformat(),
                "bid": bid,
                "ask": ask,
                "price_increment": price_increment,
                "max_wait_seconds": ttl.total_seconds(),
                "geometry_for_entry": geometry_for_entry,
                "atr_scale": atr_scale,
                "current_session": session,
                "current_regime": "unknown",
                "policy_eligibility": "eligible",
                "eligible_action_fill_time": action_eligibility.fill_time,
                "session_close_time": action_eligibility.session_close_time,
                "latency_estimate_ms": latency_ms_raw,
                "estimated_round_trip_cost_points": (ask - bid)
                + 2.0 * float(cfg.costs.get("slippage_points", 0.0)),
                "evidence_quality_flags": (
                    "training_only",
                    "market_close_quote_from_current_m1_bar",
                    f"configured_fill_latency_bars:{int(cfg.execution.get('fill_latency_bars', 0))}",
                    "session_label_from_m1_bar",
                    "static_policy_action_eligibility_passed",
                    "account_state_not_evaluated",
                    "regime_unavailable",
                ),
                "causal_feature_availability": tuple(feature_availability),
            }
            proposal_count_before = len(proposals)
            market = build_decision_proposals(
                candidate,
                **common,
                source_geometry_id=f"market_quote:{quote_time.value}",
            )
            if market:
                proposals.extend(proposal.to_record() for proposal in market)
                stats["market_proposals"] += len(market)
            else:
                stats["market_geometry_unavailable_rows"] += 1

            context = entry_idea_context(row, int(candidate.direction), include_zones=True)
            zones: list[tuple[tuple[float, float], str]] = []
            if candidate.idea == "standard_deviation":
                timeframe = str(candidate.setup_timeframe).upper()
                prefix = "" if timeframe == "M1" else f"{timeframe}_"
                low_name = f"{prefix}standard_deviation_band_low"
                high_name = f"{prefix}standard_deviation_band_high"
                if low_name in row and high_name in row:
                    low = pd.to_numeric(pd.Series([row[low_name]]), errors="coerce").iloc[0]
                    high = pd.to_numeric(pd.Series([row[high_name]]), errors="coerce").iloc[0]
                    if np.isfinite(low) and np.isfinite(high) and low <= high:
                        start = row.get("standard_deviation_leg_start_time_ns", "")
                        end = row.get("standard_deviation_leg_end_time_ns", "")
                        zone_id = (
                            f"standard_deviation:{timeframe}:{start}:{end}:{low:.12g}:{high:.12g}"
                        )
                        zones.append(((float(low), float(high)), zone_id))
            else:
                matching = [
                    zone
                    for zone in context["zones"]
                    if zone["idea"] == candidate.idea
                    and (
                        candidate.idea == "po3"
                        or str(zone["timeframe"]).upper() == str(candidate.setup_timeframe).upper()
                    )
                ]
                matching.sort(
                    key=lambda zone: (
                        0 if candidate.idea == "po3" and zone["family"] == "ifvg" else 1,
                        str(zone["family"]),
                        int(zone.get("start_time_ns") or 0),
                        float(zone["low"]),
                        float(zone["high"]),
                    )
                )
                if matching:
                    zone = matching[0]
                    zone_id = (
                        f"{candidate.idea}:{zone['family']}:{zone['timeframe']}:"
                        f"{zone.get('start_time_ns')}:{float(zone['low']):.12g}:"
                        f"{float(zone['high']):.12g}"
                    )
                    zones.append(((float(zone["low"]), float(zone["high"])), zone_id))
            if not zones:
                stats["no_candidate_zone_rows"] += 1
            for source_zone, source_geometry_id in zones:
                limit_proposals = build_decision_proposals(
                    candidate,
                    **common,
                    source_zone=source_zone,
                    source_geometry_id=source_geometry_id,
                    include_market=False,
                )
                if limit_proposals:
                    proposals.extend(proposal.to_record() for proposal in limit_proposals)
                    stats["limit_proposals"] += len(limit_proposals)
                else:
                    stats["limit_not_eligible_or_geometry_unavailable_rows"] += 1
            if len(proposals) > proposal_count_before:
                proposal_events.add(event_key)

    output_dir.mkdir(parents=True)
    for column in (
        "permissible_stop_choices",
        "permissible_target_choices",
        "evidence_quality_flags",
        "causal_feature_availability",
    ):
        for record in proposals:
            record[column] = json.dumps(record[column], separators=(",", ":"))
    proposal_frame = pd.DataFrame.from_records(proposals)
    proposal_path = output_dir / "candidate_proposals.parquet"
    proposal_frame.to_parquet(proposal_path, index=False)
    summary_rows = []
    for candidate in TRADE_SETUP_CANDIDATES[1:]:
        assert candidate.idea is not None and candidate.setup_timeframe is not None
        stats = candidate_stats[candidate.candidate_id]
        summary_rows.append(
            {
                "candidate_id": candidate.candidate_id,
                "idea_family": candidate.idea,
                "source_timeframe": candidate.setup_timeframe,
                "direction": "long" if candidate.direction > 0 else "short",
                "support_status": (
                    "supported"
                    if candidate_supported(cfg, candidate.idea, candidate.setup_timeframe)
                    else "unsupported_by_config"
                ),
                **dict(stats),
            }
        )
    summary_path = output_dir / "candidate_proposal_coverage.csv"
    pd.DataFrame.from_records(summary_rows).to_csv(summary_path, index=False)
    config_text = OmegaConf.to_yaml(cfg, resolve=True)
    manifest_path = DATA_MANIFEST
    manifest: dict[str, Any] = {
        "status": "training_candidate_proposals_static_policy_eligibility_no_outcome_replay",
        "schema_version": "training-candidate-proposal-ledger-v2",
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "config": str(config_path.resolve().relative_to(ROOT.resolve())),
        "resolved_config_sha256": hashlib.sha256(config_text.encode()).hexdigest(),
        "local_data_manifest": str(manifest_path.relative_to(ROOT)),
        "local_data_manifest_sha256": _sha256_file(manifest_path),
        "training_input_sha256": training_inputs,
        "tickbook_sha256": tickbook.content_sha256(),
        "training_window": {"start": train_start, "end_inclusive": train_end},
        "decision_time_contract": "M1 bar open timestamp plus one minute after its close",
        "action_eligibility_contract": {
            "session_source": "configured M1 session and session_id labels",
            "open_blackout_bars": int(cfg.env.get("open_manipulation_bars", 0)),
            "fill_latency_bars": int(cfg.execution.get("fill_latency_bars", 0)),
            "block_overnight": bool(cfg.env.get("block_overnight", True)),
            "eligibility_scope": "static environment session/fill rules; no account state",
        },
        "quote_contract": "last source-ordered TickBook quote in the decision M1 half-open bar",
        "proposal_ttl_minutes": ttl_minutes,
        "proposal_bound": "one market quote plus at most one zone-midpoint limit per candidate event",
        "candidate_event_identity": "candidate catalog ID plus existing identified source_event_id",
        "candidate_event_count": len(identified_events),
        "policy_eligible_candidate_event_count": len(eligible_events),
        "proposal_event_count": len(proposal_events),
        "proposal_count": len(proposals),
        "outcome_replay": "not_run",
        "source_sha256": {relative: _sha256_file(ROOT / relative) for relative in SOURCE_FILES},
        "outputs": {
            proposal_path.name: _sha256_file(proposal_path),
            summary_path.name: _sha256_file(summary_path),
        },
    }
    manifest_out = output_dir / "proposal_ledger_manifest.json"
    manifest_out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    readme = (
        "# Candidate proposals\n\n"
        "This training-only packet includes source-identified candidate events with a causal decision quote, production structural stop/target menus, and a pass through the environment's static NY-session, open-blackout, fill-bar, and same-session rules. It retains the eligible action fill-bar time and local session-close deadline. The 60-minute proposal TTL is an analysis parameter.\n\n"
        "The eligibility pass does not evaluate account-state constraints, policy selection, order contention, or realized actions. Market proposals use the last quote in the completed decision M1 bar; pending-limit proposals use one deterministic source-zone midpoint. The packet does not contain fills, outcomes, returns, or policy value, and includes no report-period rows.\n\n"
        "See `candidate_proposal_coverage.csv` for event and rejection counts, and `proposal_ledger_manifest.json` for source, config, local-input, TickBook, and output identities.\n"
    )
    readme_path = output_dir / "README.md"
    readme_path.write_text(readme, encoding="utf-8")
    checksum_files = (proposal_path, summary_path, manifest_out, readme_path)
    sums = "\n".join(f"{_sha256_file(path)}  {path.name}" for path in checksum_files) + "\n"
    (output_dir / "OUTPUT_SHA256SUMS").write_text(sums, encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--ttl-minutes", type=int, default=PROPOSAL_TTL_MINUTES)
    args = parser.parse_args()
    config_path = args.config if args.config.is_absolute() else ROOT / args.config
    output_dir = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir
    cfg = load_config(config_path=config_path)
    print(
        json.dumps(
            build_ledger(
                cfg,
                output_dir,
                config_path=config_path,
                ttl_minutes=args.ttl_minutes,
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
