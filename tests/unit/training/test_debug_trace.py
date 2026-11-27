"""Flight recorder incidents for exceptions, non-finite values, and checks."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from simulation.environment.diagnostics.errors import DebugStepError
from training.callbacks.debug_trace import (
    FlightRecorder,
    account_weights,
    builtin_checks,
    collect_rollout,
    install_flight_recorder,
    merge_env_stats,
    policy_std,
)

pytestmark = pytest.mark.unit


def _healthy(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "explained_variance": 0.5,
        "std": 0.7,
        "reward_per_1k": {"pnl": -0.01, "strategy": -0.001},
        "shape_on_hold": 0,
        "soft_daily_repeat": 0,
        "soft_year_repeat": 0,
        "corr_val_open_pnl": 0.9,
        "corr_boot_open_pnl": 0.9,
    }
    row.update(overrides)
    return row


def _incidents(directory: Path) -> list[dict[str, object]]:
    path = directory / "debug_incidents.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_exception_writes_traceback_and_previous_snapshots(tmp_path: Path) -> None:
    recorder = FlightRecorder(tmp_path, ring_size=5)
    recorder.record(_healthy(explained_variance=0.4))
    recorder.record(_healthy(explained_variance=0.6))
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        recorder.capture("train exception", _healthy(explained_variance=0.8))
    rows = _incidents(tmp_path)
    assert len(rows) == 1
    assert rows[0]["reason"] == "train exception"
    assert "RuntimeError" in str(rows[0]["traceback"])
    history = rows[0]["history"]
    assert isinstance(history, list)
    assert len(history) == 2
    assert history[0]["explained_variance"] == pytest.approx(0.4)
    assert history[1]["explained_variance"] == pytest.approx(0.6)


def test_nonfinite_value_writes_an_incident(tmp_path: Path) -> None:
    recorder = FlightRecorder(tmp_path)
    recorder.record(_healthy(explained_variance=float("nan")))
    rows = _incidents(tmp_path)
    assert len(rows) == 1
    assert str(rows[0]["reason"]).startswith("non-finite")


def test_extra_check_writes_an_incident(tmp_path: Path) -> None:
    def flag(records: Sequence[Mapping[str, object]]) -> str:
        return "custom" if records and records[-1].get("flag") else ""

    recorder = FlightRecorder(tmp_path, extra_checks=[flag])
    recorder.record(_healthy(flag=1))
    rows = _incidents(tmp_path)
    assert len(rows) == 1
    assert rows[0]["reason"] == "custom"


def test_healthy_record_and_the_first_update_write_no_incident(tmp_path: Path) -> None:
    recorder = FlightRecorder(tmp_path)
    recorder.record(_healthy(explained_variance=0.0, corr_val_open_pnl=0.0, corr_boot_open_pnl=0.0))
    for _ in range(4):
        recorder.record(_healthy(explained_variance=0.1))
    assert _incidents(tmp_path) == []
    assert (tmp_path / "debug.jsonl").exists()


def test_flight_recorder_forwards_off_policy_update_arguments(tmp_path: Path) -> None:
    from types import SimpleNamespace

    calls: list[tuple[int, int]] = []

    def train(*, batch_size: int, gradient_steps: int) -> None:
        calls.append((batch_size, gradient_steps))
        raise RuntimeError("stop after validating forwarded arguments")

    model = SimpleNamespace(
        train=train,
        learn=lambda *args, **kwargs: None,
        get_env=lambda: None,
        num_timesteps=0,
    )
    install_flight_recorder(model, tmp_path)

    with pytest.raises(RuntimeError, match="stop after validating"):
        model.train(batch_size=128, gradient_steps=2)

    assert calls == [(128, 2)]


def test_merge_env_stats_aggregates_counts_and_normalizes_per_step_signals() -> None:
    summary = merge_env_stats(
        [
            {
                "n": 2,
                "parts": {"pnl": 4.0, "strategy": -2.0},
                "opens": 1,
                "shape_on_open": 1,
                "breach_events": 1,
                "entries": 1,
                "risk_sum": 0.2,
                "soft_daily_nz": 1,
                "soft_daily_repeat": 0,
                "closes": 1,
                "structure_sl": 1,
                "spike_share": 0.5,
                "nonzero": 1.0,
            },
            {
                "n": 1,
                "parts": {"pnl": -1.0, "strategy": 3.0},
                "shape_on_hold": 1,
                "entries": 1,
                "risk_sum": 0.4,
                "soft_year_repeat": 1,
                "closes": 1,
                "structure_tp": 1,
                "spike_share": 0.0,
                "nonzero": 0.0,
            },
            {},
        ]
    )

    assert summary["reward_steps"] == 3
    assert summary["reward_per_1k"] == {"pnl": 1000.0, "strategy": pytest.approx(1000.0 / 3)}
    assert summary["breach_events"] == 1
    assert summary["opens"] == 1
    assert summary["shape_on_open"] == 1
    assert summary["shape_on_hold"] == 1
    assert summary["mean_entry_risk"] == pytest.approx(0.3)
    assert summary["soft_daily_nz"] == 1
    assert summary["soft_year_repeat"] == 1
    assert summary["spike_share"] == pytest.approx(1 / 3)
    assert summary["nonzero_frac"] == pytest.approx(2 / 3)
    assert summary["structure_sl_share"] == 0.5
    assert summary["structure_tp_share"] == 0.5


def test_collect_rollout_reports_returns_value_fit_mc_return_and_account_correlations() -> None:
    model = SimpleNamespace(
        num_timesteps=7,
        gamma=0.5,
        rollout_buffer=SimpleNamespace(
            returns=np.array([[1.0], [2.0], [4.0]]),
            values=np.array([[0.0], [1.0], [2.0]]),
            rewards=np.array([[1.0], [1.0], [2.0]]),
            episode_starts=np.array([[1.0], [0.0], [1.0]]),
            observations={
                "account": np.array(
                    [[0.0, 0.0, 0.0, 1.0], [0.0, 0.0, 1.0, 2.0], [0.0, 0.0, 2.0, 4.0]]
                )
            },
        ),
    )

    rollout = collect_rollout(model)

    assert rollout["timesteps"] == 7
    assert rollout["ret_mean"] == pytest.approx(7 / 3)
    assert rollout["val_mean"] == pytest.approx(1.0)
    assert rollout["explained_variance"] == pytest.approx(1 - np.var([1, 1, 2]) / np.var([1, 2, 4]))
    assert rollout["mc_mean"] == pytest.approx(1.5)
    assert rollout["corr_val_open_pnl"] == pytest.approx(1.0)
    assert rollout["corr_boot_open_pnl"] == pytest.approx(
        np.corrcoef([1.0, 2.0, 4.0], [0.0, 1.0, 2.0])[0, 1]
    )
    assert rollout["corr_boot_unrealised_r"] == pytest.approx(1.0)


def test_collect_rollout_handles_empty_buffers_and_policy_weight_diagnostics() -> None:
    empty = collect_rollout(
        SimpleNamespace(num_timesteps=4, rollout_buffer=SimpleNamespace(returns=[], values=[]))
    )
    policy = SimpleNamespace(
        log_std=torch.tensor([0.0, np.log(4.0)]),
        account_value_weight=torch.tensor([[1.5, -0.5, 2.0]]),
    )

    assert empty["timesteps"] == 4
    assert empty["ret_mean"] == 0.0
    assert empty["explained_variance"] == 0.0
    assert policy_std(SimpleNamespace(policy=policy)) == pytest.approx(2.5)
    assert account_weights(SimpleNamespace(policy=policy)) == [1.5, -0.5, 2.0]
    assert policy_std(SimpleNamespace()) is None
    assert account_weights(SimpleNamespace()) == []


def test_builtin_checks_flag_sustained_value_and_policy_wiring_health_signals() -> None:
    checks = builtin_checks({"ev_windows": 2, "corr_windows": 2})
    baseline = _healthy()

    assert checks[0](
        [baseline, _healthy(explained_variance=0.1), _healthy(explained_variance=0.2)]
    ) == ("explained variance")
    assert checks[1]([_healthy(std=1.1)]) == "policy std"
    assert checks[2]([_healthy(reward_per_1k={"pnl": 0.1, "strategy": 2.0})]) == (
        "reward part strategy"
    )
    assert checks[3]([_healthy(shape_on_hold=1)]) == "shaping on hold"
    assert (
        checks[4]([baseline, _healthy(corr_val_open_pnl=0.1), _healthy(corr_val_open_pnl=0.2)])
        == "value ignores open pnl"
    )
    assert checks[5]([_healthy(breach_penalty=-5.0, eval_breach_penalty=-10.0)]) == (
        "train/eval breach penalty mismatch"
    )
    assert (
        checks[5]([_healthy(pnl_dsr_weight=0.1, breach_penalty=0.0, eval_breach_penalty=0.0)])
        == "pnl dsr weight"
    )


def test_train_wrapper_flushes_env_stats_and_records_wiring_health(tmp_path: Path) -> None:
    class VecEnv:
        def env_method(self, method: str) -> list[object]:
            if method == "debug_wiring":
                return [{"breach_penalty": -5.0, "eval_breach_penalty": -10.0}]
            if method == "debug_flush":
                return [{"n": 2, "parts": {"pnl": 0.5}, "entries": 1, "risk_sum": 0.2}]
            return []

    model = SimpleNamespace(
        get_env=VecEnv,
        train=lambda: "trained",
        learn=lambda: None,
        num_timesteps=0,
    )
    recorder = install_flight_recorder(model, tmp_path)

    assert model.train() == "trained"
    trace = json.loads((tmp_path / "debug.jsonl").read_text(encoding="utf-8"))
    wiring = json.loads((tmp_path / "debug_wiring.json").read_text(encoding="utf-8"))

    assert trace["reward_steps"] == 2
    assert trace["reward_per_1k"]["pnl"] == pytest.approx(250.0)
    assert wiring["breach_penalty"] == -5.0
    assert [row["reason"] for row in _incidents(tmp_path)] == ["train/eval breach penalty mismatch"]
    assert recorder.directory == tmp_path


def test_train_wrapper_unwraps_debug_step_error_and_records_incident(tmp_path: Path) -> None:
    original = RuntimeError("environment step failed")

    def train() -> None:
        raise DebugStepError("bad reward", {"step": 4}, original=original)

    model = SimpleNamespace(
        get_env=lambda: object(),
        train=train,
        learn=lambda: None,
        num_timesteps=0,
    )
    install_flight_recorder(model, tmp_path)

    with pytest.raises(RuntimeError, match="environment step failed"):
        model.train()

    incident = _incidents(tmp_path)[0]
    assert incident["reason"] == "bad reward"
    assert incident["snapshot"] == {"step": 4}
    assert "DebugStepError" in str(incident["traceback"])


def test_nested_nonfinite_value_reports_its_full_path(tmp_path: Path) -> None:
    recorder = FlightRecorder(tmp_path)

    recorder.record({"metrics": {"reward_parts": [0.0, float("nan")]}})

    incident = _incidents(tmp_path)[0]
    assert incident["reason"] == "non-finite metrics.reward_parts[1]"


def test_train_wrapper_keeps_working_when_environment_debug_api_is_unavailable(
    tmp_path: Path,
) -> None:
    class VecEnv:
        def env_method(self, method: str) -> list[object]:
            raise TypeError(f"unsupported debug method: {method}")

    model = SimpleNamespace(
        get_env=lambda: VecEnv(),
        train=lambda: "trained",
        learn=lambda: None,
        num_timesteps=0,
    )
    install_flight_recorder(model, tmp_path)

    assert model.train() == "trained"

    trace = json.loads((tmp_path / "debug.jsonl").read_text(encoding="utf-8"))
    assert trace["reward_steps"] == 0
    assert trace["mean_entry_risk"] == 0.0
    assert _incidents(tmp_path) == []


def test_learn_wrapper_records_and_reraises_debug_error_without_original(
    tmp_path: Path,
) -> None:
    error = DebugStepError("invalid step", {"step": 9})
    model = SimpleNamespace(
        get_env=lambda: object(),
        train=lambda: None,
        learn=lambda **_kwargs: (_ for _ in ()).throw(error),
        num_timesteps=0,
    )
    install_flight_recorder(model, tmp_path)

    with pytest.raises(DebugStepError) as raised:
        model.learn(total_timesteps=10)

    assert raised.value is error
    incident = _incidents(tmp_path)[0]
    assert incident["reason"] == "invalid step"
    assert incident["snapshot"] == {"step": 9}
    assert "DebugStepError" in str(incident["traceback"])


def test_learn_wrapper_records_and_reraises_ordinary_failure(tmp_path: Path) -> None:
    model = SimpleNamespace(
        get_env=lambda: object(),
        train=lambda: None,
        learn=lambda: (_ for _ in ()).throw(RuntimeError("learn failed")),
        num_timesteps=0,
    )
    install_flight_recorder(model, tmp_path)

    with pytest.raises(RuntimeError, match="learn failed"):
        model.learn()

    incident = _incidents(tmp_path)[0]
    assert incident["reason"] == "learn exception"
    assert "RuntimeError: learn failed" in str(incident["traceback"])
