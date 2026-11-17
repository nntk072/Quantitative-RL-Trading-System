"""Source-backed identities for one persisted representation-study evaluation."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import pandas as pd
from omegaconf import OmegaConf

from artifacts.identity import file_sha256
from decisioning.actions import build_action_schema_from_config
from decisioning.trade_setup import NO_TRADE_ID, TRADE_SETUP_CATEGORY_COUNT
from evaluation.reporting.policy_decision_reconciliation import reconcile_policy_decisions
from training.artifacts.manifests import build_effective_policy_input_schema
from training.configuration.representation_study import (
    EXPECTED_TIMEFRAMES,
    LOCAL_OFFSET,
    parse_local_row_timestamp,
)


def _json_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid JSON artifact: {path}") from error
    if not isinstance(value, dict):
        raise ValueError(f"JSON artifact must contain an object: {path}")
    return value


def _parse_local_timestamp(value: str, name: str) -> pd.Timestamp:
    canonical = value.replace(" ", "T", 1) if "T" not in value else value
    try:
        timestamp = pd.Timestamp(canonical)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be an ISO-8601 timestamp") from error
    if (
        timestamp.tzinfo is None
        or timestamp.utcoffset() != LOCAL_OFFSET
        or timestamp.isoformat() != canonical
    ):
        raise ValueError(f"{name} must use canonical Etc/GMT-3 time")
    return timestamp


def _artifact(root: Path, manifest: Mapping[str, Any], relative_path: str) -> Path:
    rows = manifest.get("numerical_artifacts")
    if not isinstance(rows, list):
        raise ValueError("evaluation manifest numerical_artifacts must be a list")
    matches = [row for row in rows if isinstance(row, dict) and row.get("path") == relative_path]
    if len(matches) != 1:
        raise ValueError(f"evaluation manifest must list exactly one {relative_path}")
    expected_hash = matches[0].get("sha256")
    if not isinstance(expected_hash, str) or len(expected_hash) != 64:
        raise ValueError(f"evaluation manifest hash is invalid for {relative_path}")
    path = (root / relative_path).resolve()
    if root.resolve() not in path.parents:
        raise ValueError("evaluation artifact path escapes the run directory")
    if not path.is_file() or file_sha256(path) != expected_hash:
        raise ValueError(f"evaluation artifact hash mismatch: {relative_path}")
    return path


def _equity_index(path: Path) -> dict[str, Any]:
    timestamps = hashlib.sha256()
    step_timestamps = hashlib.sha256()
    first: str | None = None
    last: str | None = None
    previous = None
    first_equity: float | None = None
    last_equity: float | None = None
    rows = 0
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.reader(stream)
        header = next(reader, None)
        if header is None or len(header) != 2 or header[1].strip() != "equity":
            raise ValueError("equity.csv must contain a timestamp index and equity column")
        for row in reader:
            if len(row) != 2:
                raise ValueError("equity.csv contains a malformed row")
            timestamp = _parse_local_timestamp(row[0].strip(), "equity index")
            if previous is not None and timestamp <= previous:
                raise ValueError("equity timestamp index must be strictly increasing")
            try:
                equity = float(row[1])
            except (TypeError, ValueError) as error:
                raise ValueError("equity.csv contains a nonnumeric value") from error
            if not math.isfinite(equity):
                raise ValueError("equity.csv contains a nonfinite value")
            canonical = timestamp.isoformat()
            timestamps.update(canonical.encode("ascii") + b"\n")
            if rows > 0:
                step_timestamps.update(canonical.encode("ascii") + b"\n")
            if first is None:
                first = canonical
                first_equity = equity
            last = canonical
            last_equity = equity
            previous = timestamp
            rows += 1
    if rows < 2 or first is None or last is None or first_equity is None or last_equity is None:
        raise ValueError("equity.csv must contain at least two timestamped values")
    return {
        "observed_evaluation_start": first,
        "observed_evaluation_end": last,
        "evaluation_cohort_sha256": timestamps.hexdigest(),
        "step_timestamp_sha256": step_timestamps.hexdigest(),
        "row_count": rows,
        "initial_equity": first_equity,
        "ending_equity": last_equity,
    }


def _decision_hashes(path: Path) -> dict[str, Any]:
    opportunities = hashlib.sha256()
    masks = hashlib.sha256()
    cohort = hashlib.sha256()
    decision_timestamps = hashlib.sha256()
    previous_time = None
    previous_decision_id: str | None = None
    rows = 0
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        required = {
            "decision_id",
            "decision_bar_time",
            "eligible_trade_setup_ids",
            "eligible_candidate_count",
        }
        if not required.issubset(reader.fieldnames or ()):
            raise ValueError(f"{path.name} is missing policy-facing candidate fields")
        for record in reader:
            decision_id = str(record.get("decision_id", "")).strip()
            raw_time = str(record.get("decision_bar_time", "")).strip()
            timestamp = parse_local_row_timestamp(raw_time.replace(" ", "T", 1), "decision time")
            if not decision_id or (previous_time is not None and timestamp <= previous_time):
                raise ValueError("decision ledger identity/time must be nonempty and increasing")
            if decision_id == previous_decision_id:
                raise ValueError("decision ledger contains duplicate adjacent decision IDs")
            try:
                candidate_ids = json.loads(record["eligible_trade_setup_ids"])
            except (json.JSONDecodeError, TypeError) as error:
                raise ValueError(
                    "decision ledger eligible IDs must be a JSON integer list"
                ) from error
            if (
                not isinstance(candidate_ids, list)
                or any(type(candidate_id) is not int for candidate_id in candidate_ids)
                or candidate_ids != sorted(set(candidate_ids))
                or NO_TRADE_ID not in candidate_ids
                or any(
                    not 0 <= candidate_id < TRADE_SETUP_CATEGORY_COUNT
                    for candidate_id in candidate_ids
                )
            ):
                raise ValueError("decision ledger contains an invalid legal candidate mask")
            try:
                count = int(record["eligible_candidate_count"])
            except (TypeError, ValueError) as error:
                raise ValueError("decision ledger candidate count must be an integer") from error
            if count != len(candidate_ids):
                raise ValueError("decision ledger candidate count differs from its ID mask")
            time_text = timestamp.isoformat(timespec="seconds")
            setup_ids = [
                candidate_id for candidate_id in candidate_ids if candidate_id != NO_TRADE_ID
            ]
            opportunities.update(
                json.dumps([decision_id, time_text, setup_ids], separators=(",", ":")).encode()
                + b"\n"
            )
            mask = [
                candidate_id in candidate_ids for candidate_id in range(TRADE_SETUP_CATEGORY_COUNT)
            ]
            masks.update(
                json.dumps([decision_id, time_text, mask], separators=(",", ":")).encode() + b"\n"
            )
            cohort.update(
                json.dumps([decision_id, time_text], separators=(",", ":")).encode() + b"\n"
            )
            decision_timestamps.update(time_text.encode("ascii") + b"\n")
            previous_time = timestamp
            previous_decision_id = decision_id
            rows += 1
    if rows == 0:
        raise ValueError("decision ledger is empty")
    return {
        "candidate_opportunities_sha256": opportunities.hexdigest(),
        "legal_masks_sha256": masks.hexdigest(),
        "decision_cohort_sha256": cohort.hexdigest(),
        "decision_timestamp_sha256": decision_timestamps.hexdigest(),
        "decision_rows": rows,
    }


def _verify_setup_decisions(path: Path, expected: Mapping[str, Any]) -> None:
    actual = _decision_hashes(path)
    for field in (
        "candidate_opportunities_sha256",
        "legal_masks_sha256",
        "decision_cohort_sha256",
        "decision_timestamp_sha256",
        "decision_rows",
    ):
        if actual[field] != expected[field]:
            raise ValueError(
                f"trade_setup_decisions.csv differs from policy_decisions.csv: {field}"
            )


def _validate_actions_and_execution(policy_path: Path, trades_path: Path) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    previous_index: int | None = None
    previous_session: str | None = None
    first_timestamp: str | None = None
    last_timestamp: str | None = None
    first_index: int | None = None
    last_index: int | None = None
    with policy_path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        required = {
            "schema_version",
            "decision_id",
            "action",
            "trade_setup_candidate_id",
            "trade_setup_eligible",
            "eligible_trade_setup_ids",
            "eligible_candidate_count",
            "decision_bar_index",
            "session_id",
            "decision_bar_time",
            "position_direction_at_decision",
            "position_id_at_decision",
            "pending_order_id_at_decision",
        }
        if not required.issubset(reader.fieldnames or ()):
            raise ValueError("policy decision ledger lacks action/execution reconciliation fields")
        for row in reader:
            try:
                eligible_ids = json.loads(row["eligible_trade_setup_ids"])
                action = int(row["action"])
                candidate_id = int(row["trade_setup_candidate_id"])
                bar_index = int(row["decision_bar_index"])
                eligible_flag = row["trade_setup_eligible"]
            except (json.JSONDecodeError, TypeError, ValueError) as error:
                raise ValueError("policy decision action/candidate fields are malformed") from error
            if eligible_flag not in {"True", "False"}:
                raise ValueError("policy decision eligibility must be an explicit boolean")
            eligible = eligible_flag == "True"
            if action not in {-1, 0, 1}:
                raise ValueError("policy decision action is outside the supported contract")
            if candidate_id not in eligible_ids and eligible:
                raise ValueError("policy decision marks a candidate eligible outside its mask")
            if (candidate_id in eligible_ids) != eligible:
                raise ValueError("policy decision candidate eligibility differs from its mask")
            if action != 0 and (candidate_id == NO_TRADE_ID or not eligible):
                raise ValueError("directional policy action selects an ineligible candidate")
            timestamp = parse_local_row_timestamp(
                row["decision_bar_time"].replace(" ", "T", 1), "decision time"
            )
            session_id = row["session_id"]
            if previous_index is not None:
                if bar_index <= previous_index:
                    raise ValueError("policy decision bar indexes must increase")
                if session_id == previous_session and bar_index != previous_index + 1:
                    raise ValueError("policy decision ledger omits a bar inside one session")
            canonical_time = timestamp.isoformat(timespec="seconds")
            if first_index is None:
                first_index = bar_index
                first_timestamp = canonical_time
            last_index = bar_index
            last_timestamp = canonical_time
            previous_index = bar_index
            previous_session = session_id
            records.append(
                {
                    **{key: None if value == "" else value for key, value in row.items()},
                    "action": action,
                    "trade_setup_candidate_id": candidate_id,
                    "trade_setup_eligible": eligible,
                    "eligible_trade_setup_ids": eligible_ids,
                }
            )
    if not records:
        raise ValueError("policy decision ledger is empty")
    events = pd.read_csv(trades_path, keep_default_na=True)
    report = reconcile_policy_decisions(pd.DataFrame.from_records(records), events, [])
    if report.get("status") != "matched" or report.get("failure_count") != 0:
        raise ValueError(
            "policy decisions do not reconcile with candidate masks and execution ledger: "
            f"status={report.get('status')}, failures={report.get('failure_count')}, "
            f"incomplete={report.get('incomplete_reasons')}"
        )
    return {
        "decision_rows": len(records),
        "first_decision_index": first_index,
        "last_decision_index": last_index,
        "first_decision_time": first_timestamp,
        "last_decision_time": last_timestamp,
    }


def _account_trace(path: Path, equity_rows: int) -> dict[str, Any]:
    initial_balance: float | None = None
    final_equity: float | None = None
    cumulative_payouts: float | None = None
    breach = False
    rows = 0
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        required = {"initial_balance", "equity", "cumulative_payouts", "breach_reason"}
        if not required.issubset(reader.fieldnames or ()):
            raise ValueError("account_state_trace.csv lacks outcome reconciliation fields")
        for record in reader:
            try:
                initial = float(record["initial_balance"])
                equity = float(record["equity"])
                payouts = float(record["cumulative_payouts"])
            except (TypeError, ValueError) as error:
                raise ValueError("account trace has nonnumeric account values") from error
            if not all(math.isfinite(value) for value in (initial, equity, payouts)):
                raise ValueError("account trace has nonfinite account values")
            if initial_balance is not None and not math.isclose(
                initial, initial_balance, rel_tol=1e-10
            ):
                raise ValueError("account trace initial balance changed")
            initial_balance = initial
            final_equity = equity
            cumulative_payouts = payouts
            breach = breach or bool(str(record.get("breach_reason", "")).strip())
            rows += 1
    if (
        rows != equity_rows - 1
        or initial_balance is None
        or final_equity is None
        or cumulative_payouts is None
    ):
        raise ValueError("account trace rows do not match persisted equity decisions")
    return {
        "initial_balance": initial_balance,
        "final_equity": final_equity,
        "cumulative_payouts": cumulative_payouts,
        "hard_risk_gate_passed": not breach,
        "trace_rows": rows,
    }


def _csv_row_count(path: Path) -> int:
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.reader(stream)
        if next(reader, None) is None:
            raise ValueError(f"CSV artifact has no header: {path.name}")
        return sum(1 for _ in reader)


def _liquidated_at_data_end(path: Path) -> bool:
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if "exit_reason" not in (reader.fieldnames or ()):
            raise ValueError("positions.csv lacks the exit_reason field")
        return any(str(row.get("exit_reason", "")).strip() == "data_end" for row in reader)


def _validate_account_config(config: Mapping[str, Any], arm_name: str) -> dict[str, Any]:
    env = config.get("env")
    if not isinstance(env, Mapping):
        raise ValueError("resolved config env section is missing")
    expected_history = arm_name == "C"
    if env.get("completed_htf_history_enabled") is not expected_history:
        raise ValueError(f"resolved config has wrong HTF history setting for arm {arm_name}")
    if tuple(env.get("trade_setup_candidate_timeframes", ())) != EXPECTED_TIMEFRAMES:
        raise ValueError("resolved config candidate timeframe set differs from registration")
    if env.get("trade_setup_actions") is not True:
        raise ValueError("representation arms require trade setup actions")
    if isinstance(env.get("obs_window"), bool) or not isinstance(env.get("obs_window"), int):
        raise ValueError("resolved config obs_window must be an integer")
    return dict(config)


def _dataset_datetime(record: Mapping[str, Any], field: str, name: str) -> Any:
    return parse_local_row_timestamp(record.get(field), name)


def _validate_dataset_cohort(
    bar_record: Mapping[str, Any],
    feature_record: Mapping[str, Any],
    *,
    allowed_start: Any,
    allowed_end: Any,
) -> tuple[Any, Any, int]:
    rows = bar_record.get("rows")
    feature_rows = feature_record.get("rows")
    if isinstance(rows, bool) or not isinstance(rows, int) or rows <= 0 or feature_rows != rows:
        raise ValueError("selected bar and feature row counts must agree and be positive")
    for record, name in ((bar_record, "bars"), (feature_record, "features")):
        digest = record.get("sha256")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest.lower())
        ):
            raise ValueError(f"selected {name} dataset identity is invalid")
    bar_start = _dataset_datetime(bar_record, "start", "partition bar start")
    bar_end = _dataset_datetime(bar_record, "end", "partition bar end")
    feature_start = _dataset_datetime(feature_record, "start", "partition feature start")
    feature_end = _dataset_datetime(feature_record, "end", "partition feature end")
    if bar_start != feature_start or bar_end != feature_end:
        raise ValueError("selected bar and feature dataset bounds differ")
    if not (allowed_start.date() <= bar_start.date() <= bar_end.date() <= allowed_end.date()):
        raise ValueError("selected dataset rows fall outside the registered local-calendar period")
    return bar_start, bar_end, rows


def _source_identity(source: Any) -> str:
    if not isinstance(source, dict) or source.get("available") is not True:
        raise ValueError("run manifest source state is unavailable")
    head = source.get("head")
    dirty_files = source.get("dirty_files")
    if (
        not isinstance(head, str)
        or len(head) != 40
        or any(char not in "0123456789abcdef" for char in head.lower())
        or not isinstance(dirty_files, list)
    ):
        raise ValueError("run manifest source state is incomplete")
    for record in dirty_files:
        if not isinstance(record, dict) or not isinstance(record.get("path"), str):
            raise ValueError("run manifest dirty source record is invalid")
        digest = record.get("sha256")
        if digest is not None and (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest.lower())
        ):
            raise ValueError("run manifest dirty source hash is invalid")
    return _json_sha256(source)


def load_source_backed_arm(
    *,
    run_dir: str | Path,
    partition: str,
    arm_name: str,
    seed: int,
    declared_interval: tuple[str, str],
    allowed_interval: tuple[str, str],
) -> dict[str, Any]:
    """Verify persisted artifacts and derive policy/outcome identities from them."""
    root = Path(run_dir).expanduser().resolve()
    evaluation_path = root / "evaluation_manifest.json"
    run_manifest_path = root / "run_manifest.json"
    config_path = root / "config.yaml"
    evaluation_manifest = _read_json(evaluation_path)
    run_bytes_sha = file_sha256(run_manifest_path) if run_manifest_path.is_file() else None
    run_manifest = _read_json(run_manifest_path)
    if evaluation_manifest.get("schema_version") != "evaluation-artifacts-v1":
        raise ValueError("unsupported evaluation manifest")
    parent = evaluation_manifest.get("parent_manifests", {}).get("run_manifest")
    if (
        not isinstance(parent, dict)
        or parent.get("path") != "run_manifest.json"
        or parent.get("sha256") != run_bytes_sha
    ):
        raise ValueError("evaluation manifest does not checksum-link run_manifest.json")
    if run_manifest.get("seed") != seed:
        raise ValueError(f"run manifest seed mismatch for arm {arm_name}")
    partitions = evaluation_manifest.get("partitions")
    if (
        partition not in {"training", "testing"}
        or not isinstance(partitions, list)
        or partition not in partitions
    ):
        raise ValueError("requested evaluation partition is not listed in the manifest")
    if not config_path.is_file():
        raise FileNotFoundError(config_path)
    config_digest = file_sha256(config_path)
    config_manifest = run_manifest.get("config")
    if not isinstance(config_manifest, dict) or config_manifest.get("sha256") != config_digest:
        raise ValueError("run manifest config checksum differs from config.yaml")
    if evaluation_manifest.get("config_sha256") != config_digest:
        raise ValueError("evaluation manifest config checksum differs from config.yaml")
    config_value = OmegaConf.to_container(OmegaConf.load(config_path), resolve=True)
    if not isinstance(config_value, Mapping):
        raise ValueError("resolved config snapshot must be a mapping")
    config = _validate_account_config(cast(Mapping[str, Any], config_value), arm_name)

    allowed_start = parse_local_row_timestamp(allowed_interval[0], "registered period start")
    allowed_end = parse_local_row_timestamp(allowed_interval[1], "registered period end")
    if declared_interval != allowed_interval:
        raise ValueError("declared evaluation interval differs from the registered exposure")

    equity_path = _artifact(root, evaluation_manifest, f"{partition}/equity.csv")
    metrics_path = _artifact(root, evaluation_manifest, f"{partition}/metrics.json")
    diagnostics_path = _artifact(
        root, evaluation_manifest, f"{partition}/evaluation_diagnostics.json"
    )
    trace_path = _artifact(root, evaluation_manifest, f"{partition}/account_state_trace.csv")
    reconciliation_path = _artifact(
        root, evaluation_manifest, f"{partition}/account_state_reconciliation.json"
    )
    policy_path = _artifact(root, evaluation_manifest, f"{partition}/policy_decisions.csv")
    setup_path = _artifact(root, evaluation_manifest, f"{partition}/trade_setup_decisions.csv")
    positions_path = _artifact(root, evaluation_manifest, f"{partition}/positions.csv")
    trades_path = _artifact(root, evaluation_manifest, f"{partition}/trades.csv")
    equity = _equity_index(equity_path)
    observed_start = _parse_local_timestamp(equity["observed_evaluation_start"], "observed start")
    observed_end = _parse_local_timestamp(equity["observed_evaluation_end"], "observed end")
    metrics = _read_json(metrics_path)
    diagnostics = _read_json(diagnostics_path)
    trace = _account_trace(trace_path, equity["row_count"])
    reconciliation = _read_json(reconciliation_path)
    if reconciliation.get("status") != "matched" or reconciliation.get("failure_count") != 0:
        raise ValueError("account state reconciliation is not matched")
    if reconciliation.get("trace_rows") != trace["trace_rows"]:
        raise ValueError("account state reconciliation row count differs from trace")
    policy_decisions = _decision_hashes(policy_path)
    _verify_setup_decisions(setup_path, policy_decisions)
    action_evidence = _validate_actions_and_execution(policy_path, trades_path)
    if action_evidence["decision_rows"] != policy_decisions["decision_rows"]:
        raise ValueError("policy decision row count differs across parsed ledgers")
    reported_decision_rows = diagnostics.get("policy_decisions_rows")
    reported_reconciliation_failures = diagnostics.get("policy_decision_reconciliation_failures")
    if (
        diagnostics.get("policy_decisions_complete") is not True
        or isinstance(reported_decision_rows, bool)
        or not isinstance(reported_decision_rows, int)
        or reported_decision_rows != action_evidence["decision_rows"]
        or diagnostics.get("policy_decision_reconciliation_status") != "matched"
        or isinstance(reported_reconciliation_failures, bool)
        or not isinstance(reported_reconciliation_failures, int)
        or reported_reconciliation_failures != 0
    ):
        raise ValueError("policy decision diagnostics differ from the checksummed decision ledger")
    if policy_decisions["decision_rows"] != equity["row_count"] - 1:
        raise ValueError("policy decision count differs from persisted equity path")
    initial = metrics.get("initial_balance")
    final = metrics.get("final_equity")
    total_return = metrics.get("total_return_pct")
    trade_count = metrics.get("n_trades")
    if (
        isinstance(initial, bool)
        or not isinstance(initial, (int, float))
        or isinstance(final, bool)
        or not isinstance(final, (int, float))
        or isinstance(total_return, bool)
        or not isinstance(total_return, (int, float))
    ):
        raise ValueError("metrics.json lacks canonical account endpoints and return")
    initial_value = float(initial)
    final_value = float(final)
    total_return_value = float(total_return)
    if isinstance(trade_count, bool) or not isinstance(trade_count, int) or trade_count < 0:
        raise ValueError("metrics.json trade count must be a nonnegative integer")
    if _csv_row_count(trades_path) != trade_count:
        raise ValueError("metrics trade count does not reconcile to persisted trades.csv")
    if not (
        math.isclose(initial_value, equity["initial_equity"], rel_tol=1e-10, abs_tol=1e-7)
        and math.isclose(final_value, equity["ending_equity"], rel_tol=1e-10, abs_tol=1e-7)
        and math.isclose(final_value, trace["final_equity"], rel_tol=1e-10, abs_tol=1e-7)
        and math.isclose(initial_value, trace["initial_balance"], rel_tol=1e-10, abs_tol=1e-7)
    ):
        raise ValueError("metrics, equity, and account trace endpoints do not reconcile")
    expected_metric_return = 100.0 * (final_value - initial_value) / initial_value
    if not math.isclose(expected_metric_return, total_return_value, rel_tol=1e-9, abs_tol=1e-7):
        raise ValueError("metrics return does not reconcile to retained equity")
    net_return = 100.0 * (final_value + trace["cumulative_payouts"] - initial_value) / initial_value

    dataset_records = run_manifest.get("datasets")
    if not isinstance(dataset_records, dict):
        raise ValueError("run manifest dataset records are missing")
    bar_record = dataset_records.get("train_bars" if partition == "training" else "test_bars")
    feature_record = dataset_records.get(
        "train_features" if partition == "training" else "test_features"
    )
    if not isinstance(bar_record, dict) or not isinstance(feature_record, dict):
        raise ValueError("run manifest lacks selected partition data identities")
    bar_start, bar_end, bar_rows = _validate_dataset_cohort(
        bar_record, feature_record, allowed_start=allowed_start, allowed_end=allowed_end
    )
    obs_window = config["env"]["obs_window"]
    first_index = action_evidence["first_decision_index"]
    last_index = action_evidence["last_decision_index"]
    if (
        not isinstance(first_index, int)
        or not isinstance(last_index, int)
        or first_index < obs_window
        or last_index >= bar_rows
    ):
        raise ValueError("policy decision indexes fall outside the selected bar rows")
    first_decision = parse_local_row_timestamp(
        action_evidence["first_decision_time"], "first decision timestamp"
    )
    last_decision = parse_local_row_timestamp(
        action_evidence["last_decision_time"], "last decision timestamp"
    )
    if not (
        bar_start <= first_decision <= last_decision <= bar_end
        and observed_start == first_decision
        and observed_end == last_decision + pd.Timedelta(minutes=1)
    ):
        raise ValueError("equity and policy rows do not match the selected source row cohort")
    action_schema = run_manifest.get("action_schema")
    if not isinstance(action_schema, dict):
        raise ValueError("run manifest action schema is missing")
    expected_action_schema = build_action_schema_from_config(config["env"]).to_dict()
    if action_schema != expected_action_schema:
        raise ValueError("run manifest action schema differs from resolved config")
    observation_schema = run_manifest.get("observation_schema")
    sequence_schema = run_manifest.get("sequence_feature_schema")
    architecture = run_manifest.get("training_architecture")
    if not isinstance(observation_schema, dict) or not isinstance(sequence_schema, dict):
        raise ValueError("run manifest observation and sequence schemas are required")
    if not isinstance(architecture, dict) or not isinstance(architecture.get("arch"), str):
        raise ValueError("run manifest runtime architecture is required")
    sequence_columns = sequence_schema.get("columns")
    if not isinstance(sequence_columns, list) or any(
        not isinstance(item, str) for item in sequence_columns
    ):
        raise ValueError("run manifest sequence feature columns are invalid")
    env_config = config["env"]
    expected_policy_schema = build_effective_policy_input_schema(
        sequence_columns,
        trade_setup_actions=env_config.get("trade_setup_actions") is True,
        completed_htf_history_enabled=env_config["completed_htf_history_enabled"],
        validity_channels=env_config.get("feature_validity_channels") is True,
        runtime_arch=architecture["arch"],
    )
    if observation_schema.get("effective_policy_input_schema") != expected_policy_schema:
        raise ValueError(
            "run manifest effective policy schema differs from config and runtime arch"
        )
    history_enabled = config["env"]["completed_htf_history_enabled"]
    environment_schema = {
        "observation": observation_schema,
        "sequence": run_manifest.get("sequence_feature_schema"),
        "history_availability": "completed_htf" if history_enabled else "masked",
    }
    normalized_config = json.loads(json.dumps(config))
    normalized_config["env"].pop("completed_htf_history_enabled", None)
    split = run_manifest.get("split", {})
    provenance = {
        "dataset_sha256": bar_record.get("sha256"),
        "split_id": _json_sha256({"partition": partition, "split": split}),
        "features_sha256": feature_record.get("sha256"),
        "reward_sha256": _json_sha256(
            {key: value for key, value in config.get("env", {}).items() if "reward" in key}
        ),
        "risk_sha256": _json_sha256({key: config.get(key) for key in ("account", "ftmo", "risk")}),
        "costs_sha256": _json_sha256(config.get("costs", {})),
        "execution_sha256": _json_sha256(run_manifest.get("execution_protocol")),
        "timesteps": run_manifest.get("completed_steps"),
        "seed": seed,
        "initial_capital": initial_value,
        "model_settings_sha256": _json_sha256(
            {
                "agent": config.get("agent"),
                "architecture": run_manifest.get("training_architecture"),
            }
        ),
        "evaluation_cohort_sha256": _json_sha256(
            {
                "bars": {key: bar_record[key] for key in ("sha256", "rows", "start", "end")},
                "features": {
                    key: feature_record[key] for key in ("sha256", "rows", "start", "end")
                },
            }
        ),
        "evaluation_index_sha256": equity["evaluation_cohort_sha256"],
        "evaluation_start": bar_start.isoformat(timespec="seconds"),
        "evaluation_end": bar_end.isoformat(timespec="seconds"),
        "decision_cohort_sha256": policy_decisions["decision_cohort_sha256"],
        "candidate_opportunities_sha256": policy_decisions["candidate_opportunities_sha256"],
        "legal_masks_sha256": policy_decisions["legal_masks_sha256"],
        "action_schema_sha256": _json_sha256(action_schema),
        "common_policy_contract_sha256": _json_sha256(normalized_config),
        "environment_sha256": _json_sha256(environment_schema),
        "source_identity_sha256": _source_identity(run_manifest.get("source")),
    }
    complete_cohort = last_decision == bar_end and last_index == bar_rows - 1
    outcome = (
        "completed_after_hard_breach"
        if not trace["hard_risk_gate_passed"]
        else "completed_without_breach"
        if complete_cohort
        else None
    )
    liquidation_at_end = _liquidated_at_data_end(positions_path)
    if outcome is None:
        scientific_status = "invalid"
        invalid_reason = "incomplete_evaluation"
    else:
        scientific_status = "valid"
        invalid_reason = None
        if outcome == "completed_without_breach" and liquidation_at_end:
            outcome = "completed_after_liquidation"
    source_artifacts = [
        {"path": str(path), "sha256": file_sha256(path)}
        for path in (
            evaluation_path,
            run_manifest_path,
            config_path,
            equity_path,
            metrics_path,
            trace_path,
            reconciliation_path,
            diagnostics_path,
            policy_path,
            setup_path,
            positions_path,
            trades_path,
        )
    ]
    result: dict[str, Any] = {
        "run_id": root.name,
        "run_dir": str(root),
        "partition": partition,
        "scientific_status": scientific_status,
        "invalid_reason": invalid_reason,
        "history_availability": "completed_htf" if history_enabled else "masked",
        "observed_evaluation_start": equity["observed_evaluation_start"],
        "observed_evaluation_end": equity["observed_evaluation_end"],
        "source_identity_sha256": provenance["source_identity_sha256"],
        "provenance": provenance,
        "source_artifacts": source_artifacts,
    }
    if scientific_status == "valid":
        result.update(
            {
                "outcome": outcome,
                "evaluation_complete": True,
                "hard_risk_gate_passed": trace["hard_risk_gate_passed"],
                "initial_operating_equity": initial_value,
                "ending_retained_equity": final_value,
                "cumulative_payouts": trace["cumulative_payouts"],
                "trade_count": trade_count,
                "net_return_initial_equity_pct": net_return,
            }
        )
    return result


__all__ = ["load_source_backed_arm"]
