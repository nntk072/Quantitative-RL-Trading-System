"""Join measured observation missingness to reviewed feature producer contracts.

The generated table is a source-and-missingness crosswalk. It does not claim
that a validity signal is consumed by a policy or that a feature has economic
value.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import tempfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypedDict

DEFAULT_TRIAGE = Path(
    "evidence/research/feature_causality/observation_validity_priorities/"
    "feature_validity_priorities.csv"
)
DEFAULT_MATRIX = Path("evidence/research/feature_causality/feature_causality_matrix.csv")
DEFAULT_OUTPUT = Path("evidence/research/feature_causality/observation_validity_semantics")

STREAM_PREFIXES = ("M1_", "M3_", "M5_", "M10_", "M15_", "M30_", "H1_", "H4_", "D1_")


class FeatureContract(TypedDict):
    normalized_feature: str
    producer_function: str
    source_path: str | None
    reviewed_missingness_semantics: str
    validity_signal: str


# Ordered, reviewed mappings from emitted observation columns to their producer
# contract. Dynamic names are resolved by family, then retain their exact output
# name in the generated table.
FEATURE_RULES: tuple[tuple[str, str, str | None, str, str], ...] = (
    (
        r"^entry_idea_",
        "build_entry_idea_features",
        "features/context/entry_ideas.py",
        "Candidate eligibility flag or count; values are finite in the measured packet.",
        "No per-feature validity mask is needed for the observed rows.",
    ),
    (
        r"^(entry_long|entry_short|entry_trigger_type)$",
        "detect_entry_trigger",
        "features/po3/trigger_rules.py",
        "Trigger output is unavailable until a confirmed source zone exists.",
        "The paired trigger flags and type encode whether a trigger fired.",
    ),
    (
        r"^ema_",
        "ema_features",
        "features/technical/indicators.py",
        "EMA values begin from the available history; slope and normalized distance require prior rows or valid denominators.",
        "Leading-only missingness in the profile audit; no per-feature mask is added.",
    ),
    (
        r"^macd",
        "macd",
        "features/technical/indicators.py",
        "EWM values inherit upstream missing rows; finite zero is a valid value.",
        "Leading-only missingness in the profile audit; no per-feature mask is added.",
    ),
    (
        r"^(adx|plus_di|minus_di)$",
        "adx",
        "features/technical/indicators.py",
        "Initial differences and zero denominators can produce missing values.",
        "Leading-only missingness in the profile audit; no per-feature mask is added.",
    ),
    (
        r"^(atr|atr_5|atr_norm_price)$",
        "atr",
        "features/technical/indicators.py",
        "ATR is causal; normalized forms can be missing when a required denominator is unavailable.",
        "Leading-only missingness in the profile audit; no per-feature mask is added.",
    ),
    (
        r"^bb_",
        "bollinger",
        "features/technical/indicators.py",
        "Rolling bands require a complete lookback; invalid denominators remain missing.",
        "Leading-only missingness in the profile audit; no per-feature mask is added.",
    ),
    (
        r"^ret_",
        "returns",
        "features/technical/indicators.py",
        "The first rows at each return horizon and nonpositive closes are missing.",
        "Leading-only missingness in the profile audit; no per-feature mask is added.",
    ),
    (
        r"^realized_vol$",
        "realized_vol",
        "features/technical/indicators.py",
        "Rolling volatility is missing until its return window is populated.",
        "Leading-only missingness in the profile audit; no per-feature mask is added.",
    ),
    (
        r"^rsi$",
        "rsi",
        "features/technical/indicators.py",
        "Initial differences and zero-loss denominators can produce missing values.",
        "Leading-only missingness in the profile audit; no per-feature mask is added.",
    ),
    (
        r"^stoch_[kd]$",
        "stochastic",
        "features/technical/indicators.py",
        "K and D remain missing until their rolling windows are populated.",
        "Leading-only missingness in the profile audit; no per-feature mask is added.",
    ),
    (
        r"^(tod|dow)_(sin|cos)$",
        "time_features",
        "features/technical/indicators.py",
        "Time coordinates are finite for valid timestamps; remaining leading missingness is introduced downstream by rolling normalization.",
        "Zero-variance normalization now maps finite values to zero; source-missing and unavailable fit rows remain missing.",
    ),
    (
        r"^smt_",
        "smt_divergence",
        "features/context/smt.py",
        "Correlation needs a complete paired rolling window; spread and divergence also depend on aligned secondary bars.",
        "No dedicated per-feature pair-availability mask is present; the selected historical overlay disables SMT.",
    ),
    (
        r"^ob_",
        "build_order_block_features",
        "features/context/order_blocks.py",
        "Age and distance are missing while the corresponding order-block zone is inactive.",
        "The matching ob_*_active feature is the explicit state companion.",
    ),
    (
        r"^sweep_velocity_",
        "sweep_velocity",
        "features/technical/indicators.py",
        "Values require London levels and a positive ATR.",
        "Leading-only missingness in the profile audit; no per-feature mask is added.",
    ),
    (
        r"^sweep_",
        "detect_liquidity_sweeps",
        "features/context/liquidity.py",
        "Sweep ages and levels are missing when no matching sweep is active.",
        "The corresponding sweep event and reclaimed flags identify event state; they are sequence features, not a separate tensor mask.",
    ),
    (
        r"^mss_",
        "detect_mss",
        "features/context/liquidity.py",
        "MSS distance values require a BOS direction change and a crossed structure level.",
        "The corresponding mss_* event flags are finite companions.",
    ),
    (
        r"^bos_",
        "detect_bos",
        "features/context/liquidity.py",
        "BOS distance values require a confirmed prior structure level or event.",
        "The corresponding bos_* event flags are finite companions.",
    ),
    (
        r"^(hh|hl|lh|ll)$",
        "classify_structure",
        "features/technical/swings.py",
        "A structure class is unavailable until a prior accepted same-side swing exists.",
        "Finite one-hot structure flags represent emitted classes.",
    ),
    (
        r"^(standard_deviation_|bars_since_last_swing|last_swing_|dist_to_)",
        "build_swing_retracement_features",
        "features/context/swing_retracement.py",
        "Retracement distances are masked without a valid confirmed swing leg; swing distances require an accepted swing and valid ATR.",
        "standard_deviation_leg_valid accompanies retracement distances; it does not mask every generic swing-distance column.",
    ),
    (
        r"^swing_",
        "swing_features",
        "features/technical/swings.py",
        "Swing event flags are finite; candidate levels remain missing until accepted swings populate the available history slots.",
        "Accepted-event flags and finite history slots indicate available swing state.",
    ),
    (
        r"^fvg_",
        "build_fvg_zone_features",
        "features/po3/fvg.py",
        "FVG bounds and distances depend on a confirmed source zone; first source rows may lack zone history.",
        "Finite active, in-zone, and retest flags accompany scalar zone values.",
    ),
    (
        r"^(ifvg_|price_in_ifvg_)",
        "build_ifvg_zone_features",
        "features/po3/po3_phase_state.py",
        "IFVG zone state uses explicit inactive sentinels and nullable source metadata; measured numeric state columns are finite in this packet.",
        "Active, confirmed, in-zone, and retest flags represent the state.",
    ),
    (
        r"^po3_phase$",
        "build_po3_phase_features",
        "features/po3/entries.py",
        "Phase is missing outside the configured session; phase zero is a valid accumulation value.",
        "No explicit session-validity feature distinguishes outside-session NaN from accumulation zero.",
    ),
    (
        r"^po3_",
        "append_po3_state_features",
        "features/pipeline/po3_stage.py",
        "Idle state is zero; unavailable event timestamps and levels remain missing in source metadata.",
        "Finite state, event, and reference-code columns encode emitted lifecycle state.",
    ),
    (
        r"^manipulation_",
        "build_po3_state",
        "features/po3/po3_phase_state.py",
        "Manipulation levels require a qualifying causal sweep.",
        "The manipulation-active and direction fields accompany the levels.",
    ),
    (
        r"^(asian_ct_|london_ct_|ny_ct_)",
        "session_ohlc",
        "features/context/session_levels.py",
        "Session OHLC remains missing until the first configured session window is observed.",
        "No per-feature mask; values are held after a session completes.",
    ),
    (
        r"^(yesterday_|lastweek_)",
        "append_session_features",
        "features/pipeline/session_stage.py",
        "Prior-period levels are missing until a completed prior calendar period exists.",
        "No per-feature mask; missing values are converted to zero by observation construction.",
    ),
    (
        r"^previous_session_code$",
        "previous_labeled_session_ohlc",
        "features/context/session_levels.py",
        "The label code starts at zero; completed session prices are missing until a qualifying close.",
        "The code is finite and does not itself validate the associated price fields.",
    ),
    (
        r"^prev_ny_",
        "prev_ny_high_low",
        "features/context/session_levels.py",
        "Prior NY levels are missing until the configured session completes.",
        "No per-feature mask; missing values are converted to zero by observation construction.",
    ),
    (
        r"^pd_(asia|london)_(mid_dist_atr|in_discount|in_premium)$",
        "build_htf_pd_distance_features",
        "features/context/premium_discount.py",
        "Midpoint distances require intraday session levels and positive ATR; daily bars may not contain qualifying intraday session rows.",
        "D1 Asian/London midpoint distances are fully nonfinite in all measured groups and are unsupported on daily bars.",
    ),
    (
        r"^pd_(swing_high|swing_low)_dist_atr$",
        "build_htf_pd_distance_features",
        "features/context/premium_discount.py",
        "Swing distances require a confirmed swing and positive ATR.",
        "No separate per-feature mask beyond the corresponding swing/context values.",
    ),
    (
        r"^ctx_",
        "build_pd_context_features",
        "features/context/premium_discount.py",
        "Context distances require the relevant session or prior-period reference; flags default to inactive without a reference.",
        "Finite context flags accompany the normalized distances.",
    ),
    (
        r"^(price_to_asian_|price_to_london_|asian_range$)",
        "append_po3_state_features",
        "features/pipeline/po3_stage.py",
        "Distances require the session levels and ATR inputs used by the PO3 stage.",
        "No separate validity mask for all reference-distance columns.",
    ),
    (
        r"^(htf_day_bias|manip_reverses_htf|context_trade_direction)$",
        "build_trader_context_features",
        "features/context/premium_discount.py",
        "Optional or unavailable context defaults to a neutral code.",
        "The neutral code does not distinguish unavailable optional context from valid neutrality.",
    ),
    (
        r"^reachable_r$",
        "attach_reachable_r",
        "features/context/reachability.py",
        "The legacy value maps unavailable distance/risk to zero.",
        "reachable_r_valid is an opt-in companion and is disabled in the selected historical configuration.",
    ),
    (
        r"^active_session_",
        "session_mask",
        "features/context/session_levels.py",
        "Boolean session membership is finite for valid timestamps.",
        "The finite activity flags identify session membership.",
    ),
    (
        r"^session_progress$",
        "build_po3_phase_features",
        "features/po3/entries.py",
        "Progress clips to zero before session start and to one after session end.",
        "No explicit session-validity distinction between pre-session zero and the first accumulation row.",
    ),
    (
        r"^ny_(session_sin|session_cos|minutes_to_close)$",
        "ny_session_clock",
        "features/technical/indicators.py",
        "Clock coordinates are finite for valid timestamps and configured session boundaries.",
        "Finite scheduled-session features provide the clock state.",
    ),
    (
        r"^ny_(minutes_to_scheduled_close|scheduled_close_fraction|scheduled_short)$",
        "build_policy_market_context",
        "features/context/policy_market.py",
        "Scheduled-close features are computed from configured local session schedules.",
        "Finite schedule features; this does not establish an external calendar source.",
    ),
    (
        r"^tick_",
        "build_policy_market_context",
        "features/context/policy_market.py",
        "Quote offsets, spread, and age are missing when no usable quote is available.",
        "tick_quote_available is the explicit quote-validity companion.",
    ),
    (
        r"^vwap$",
        "vwap_level",
        "features/technical/indicators.py",
        "VWAP requires session identity and usable activity weights.",
        "No per-feature mask beyond source inputs and activity values.",
    ),
    (
        r"^vwap_dist$",
        "vwap_from_session",
        "features/technical/indicators.py",
        "Distance is missing when VWAP inputs or a positive denominator are unavailable.",
        "No per-feature mask beyond source inputs.",
    ),
    (
        r"^wick_ratio$",
        "wick_ratio",
        "features/technical/indicators.py",
        "The ratio is undefined for zero-range candles.",
        "No explicit zero-range validity feature; the observation layer maps missing values to zero.",
    ),
    (
        r"^volume_spike$",
        "volume_spike",
        "features/technical/indicators.py",
        "The ratio requires usable activity and a nonzero trailing median.",
        "No per-feature mask beyond source activity values.",
    ),
    (
        r"^ny_session_",
        "ny_session_clock",
        "features/context/policy_market.py",
        "Clock phase is finite for valid session boundaries.",
        "Finite clock features encode the scheduled session state.",
    ),
)


def _load_csv(path: Path) -> tuple[list[dict[str, str]], bytes]:
    content = path.read_bytes()
    with io.StringIO(content.decode("utf-8"), newline="") as stream:
        return list(csv.DictReader(stream)), content


def normalize_feature_name(feature: str) -> str:
    for prefix in STREAM_PREFIXES:
        if feature.startswith(prefix):
            return feature[len(prefix) :]
    return feature


def resolve_feature_contract(feature: str) -> FeatureContract | None:
    normalized = normalize_feature_name(feature)
    for pattern, function, source_path, missingness, validity_signal in FEATURE_RULES:
        if re.search(pattern, normalized):
            return {
                "normalized_feature": normalized,
                "producer_function": function,
                "source_path": source_path,
                "reviewed_missingness_semantics": missingness,
                "validity_signal": validity_signal,
            }
    return None


def _parse_matrix(matrix_rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for row in matrix_rows:
        if row.get("record_type") != "public_feature_function_candidate":
            continue
        function = row.get("function", "").strip()
        if function:
            if function in result:
                raise ValueError(f"duplicate feature-source function in matrix: {function}")
            result[function] = row
    return result


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def build_report(
    triage_path: Path = DEFAULT_TRIAGE,
    matrix_path: Path = DEFAULT_MATRIX,
    output_dir: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    triage_rows, triage_bytes = _load_csv(triage_path)
    matrix_rows, matrix_bytes = _load_csv(matrix_path)
    source_contracts = _parse_matrix(matrix_rows)
    reconciled: list[dict[str, str | None]] = []
    unmapped: list[str] = []
    missing_source_contracts: set[str] = set()
    source_path_mismatches: set[str] = set()
    for raw in triage_rows:
        contract = resolve_feature_contract(raw["feature"])
        if contract is None:
            unmapped.append(raw["feature"])
            continue
        producer = source_contracts.get(contract["producer_function"])
        if producer is None:
            missing_source_contracts.add(contract["producer_function"])
            continue
        if producer.get("source_path") != contract["source_path"]:
            source_path_mismatches.add(contract["producer_function"])
            continue
        try:
            nonfinite = int(raw["nonfinite_rows"])
            leading = int(raw["leading_nonfinite_rows"])
            interior = int(raw["interior_nonfinite_rows"])
            sampled = int(raw["sampled_rows"])
            zero_rows = int(raw["finite_zero_rows"])
        except (KeyError, ValueError) as exc:
            raise ValueError(f"invalid triage counts for {raw.get('feature')!r}") from exc
        flags = raw.get("triage_flags", "")
        if sampled <= 0 or nonfinite != leading + interior or nonfinite > sampled:
            raise ValueError(f"inconsistent triage counts for {raw['feature']!r}")
        if nonfinite == 0:
            measured_class = "no_missing_values_observed"
        elif "fully_nonfinite_in_every_group" in flags:
            measured_class = "unavailable_in_every_profile_group"
        elif interior:
            measured_class = "interior_missing_values_observed"
        else:
            measured_class = "leading_missing_values_only"
        reconciled.append(
            {
                "timeframe": raw["timeframe"],
                "feature": raw["feature"],
                "normalized_feature": contract["normalized_feature"],
                "profile_group_count": raw["profile_group_count"],
                "sampled_rows": str(sampled),
                "nonfinite_rows": str(nonfinite),
                "leading_nonfinite_rows": str(leading),
                "interior_nonfinite_rows": str(interior),
                "finite_zero_rows": str(zero_rows),
                "triage_flags": flags,
                "measured_missingness_class": measured_class,
                "producer_function": contract["producer_function"],
                "source_path": contract["source_path"],
                "producer_missingness_contract": producer.get("warmup_missingness", ""),
                "producer_evidence_status": producer.get("evidence_status", ""),
                "reviewed_missingness_semantics": contract["reviewed_missingness_semantics"],
                "validity_signal_and_limit": contract["validity_signal"],
                "observation_conversion": (
                    "Nonfinite sequence values are converted to zero; the sequence mask marks rows, not per-feature validity."
                ),
            }
        )
    if unmapped or missing_source_contracts or source_path_mismatches:
        raise ValueError(
            "validity crosswalk is incomplete: "
            f"unmapped_features={sorted(set(unmapped))}; "
            f"missing_source_contracts={sorted(missing_source_contracts)}; "
            f"source_path_mismatches={sorted(source_path_mismatches)}"
        )

    report: dict[str, Any] = {
        "schema": "qrl.observation_validity_semantics.v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "triage_path": str(triage_path.resolve()),
        "triage_sha256": hashlib.sha256(triage_bytes).hexdigest(),
        "feature_matrix_path": str(matrix_path.resolve()),
        "feature_matrix_sha256": hashlib.sha256(matrix_bytes).hexdigest(),
        "analyzer_path": str(Path(__file__).resolve()),
        "analyzer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "feature_timeframe_rows": len(reconciled),
        "producer_function_count": len({row["producer_function"] for row in reconciled}),
        "measured_missingness_classes": dict(
            sorted(Counter(row["measured_missingness_class"] for row in reconciled).items())
        ),
        "review_limit": (
            "The crosswalk links measured aggregate missingness to source-reviewed producer contracts. "
            "It does not prove a policy consumes a companion validity signal, establish economic value, "
            "or turn an unavailable feature into a valid zero."
        ),
        "rows": reconciled,
    }
    fields = list(reconciled[0]) if reconciled else []
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(reconciled)
    csv_payload = stream.getvalue().encode("utf-8")
    json_payload = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
    readme_payload = (
        "# Observation validity semantics\n\n"
        "This generated crosswalk joins every measured feature/timeframe validity row to a reviewed "
        "producer contract in the feature causality matrix. It preserves measured leading/interior "
        "counts, source functions, and the declared validity signal or limitation. It is not evidence "
        "that a policy consumes those signals or that a feature has economic value.\n\n"
        f"Rows: {len(reconciled)}. Producer functions: {report['producer_function_count']}.\n\n"
        f"Triage SHA-256: `{report['triage_sha256']}`. Feature matrix SHA-256: "
        f"`{report['feature_matrix_sha256']}`. Analyzer SHA-256: `{report['analyzer_sha256']}`.\n\n"
        "Regenerate with:\n\n```bash\n"
        ".venv/bin/python scripts/research/analysis/features/"
        "reconcile_observation_validity_semantics.py\n```\n"
    ).encode()
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "observation_validity_semantics.csv"
    json_path = output_dir / "observation_validity_semantics.json"
    readme_path = output_dir / "README.md"
    _atomic_write(csv_path, csv_payload)
    _atomic_write(json_path, json_payload)
    _atomic_write(readme_path, readme_payload)
    checksum_payload = "".join(
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n"
        for path in (csv_path, json_path, readme_path)
    ).encode("utf-8")
    _atomic_write(output_dir / "SHA256SUMS", checksum_payload)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--triage", type=Path, default=DEFAULT_TRIAGE)
    parser.add_argument("--feature-matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = build_report(args.triage, args.feature_matrix, args.output_dir)
    print(
        json.dumps(
            {
                "feature_timeframe_rows": report["feature_timeframe_rows"],
                "producer_function_count": report["producer_function_count"],
                "measured_missingness_classes": report["measured_missingness_classes"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
