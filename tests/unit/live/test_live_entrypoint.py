"""Headless tests for the ``live_trading_rl.py`` entrypoint helpers (Stage 8).

Covers the pieces of the live entrypoint that can be verified without MT5 or a
model checkpoint: SMT/secondary-symbol wiring decisions, live-risk extraction
(parity with the repo config), run-config resolution, and CLI/env defaults.
MetaTrader5 (Windows-only) is stubbed the same additive way as
``test_rl_robot.py`` so the module-level imports resolve on Linux.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from omegaconf import OmegaConf

# --- additive headless MetaTrader5 stub (mirror of test_rl_robot.py) --------
if "MetaTrader5" not in sys.modules:
    try:  # pragma: no cover - depends on platform
        import MetaTrader5  # noqa: F401
    except ImportError:
        sys.modules["MetaTrader5"] = ModuleType("MetaTrader5")

_mt5_stub = sys.modules["MetaTrader5"]
for _attr in (
    "TIMEFRAME_M1",
    "TIMEFRAME_M5",
    "TIMEFRAME_M15",
    "TIMEFRAME_M30",
    "TIMEFRAME_H1",
    "TIMEFRAME_H4",
    "TIMEFRAME_D1",
):
    if not hasattr(_mt5_stub, _attr):
        setattr(_mt5_stub, _attr, 1)  # all timeframes equal is fine headless
if not hasattr(_mt5_stub, "ORDER_TYPE_BUY"):
    setattr(_mt5_stub, "ORDER_TYPE_BUY", 0)
if not hasattr(_mt5_stub, "ORDER_TYPE_SELL"):
    setattr(_mt5_stub, "ORDER_TYPE_SELL", 1)

import live_trading_rl  # noqa: E402


# --- _use_secondary_symbol: SMT wiring decision ----------------------------
def test_secondary_symbol_wired_when_mtf_training() -> None:
    """Mtf-trained runs (use_m1_only=False, primary_only=False) need SMT data."""
    cfg = OmegaConf.create({"training": {"use_m1_only": False, "primary_only": False}})
    assert live_trading_rl._use_secondary_symbol(cfg) is True


def test_secondary_symbol_skipped_when_m1_only() -> None:
    cfg = OmegaConf.create({"training": {"use_m1_only": True, "primary_only": False}})
    assert live_trading_rl._use_secondary_symbol(cfg) is False


def test_secondary_symbol_skipped_when_primary_only() -> None:
    cfg = OmegaConf.create({"training": {"use_m1_only": False, "primary_only": True}})
    assert live_trading_rl._use_secondary_symbol(cfg) is False


def test_secondary_symbol_defaults_true_without_training_block() -> None:
    """A config without a training block must not silently drop SMT features."""
    assert live_trading_rl._use_secondary_symbol(OmegaConf.create({})) is True


# --- load_risk_overrides: live risk parity ---------------------------------
def test_load_risk_overrides_reads_repo_default_yaml() -> None:
    """The repo default.yaml block must round-trip into the RiskManager dict."""
    cfg = OmegaConf.load("config/base/default.yaml")
    risk = live_trading_rl.load_risk_overrides(cfg)
    block = cfg.live_risk_overrides
    assert risk["risk_per_symbol"] == float(block.risk_per_symbol)
    assert risk["max_total_risk"] == float(block.max_total_risk)
    assert risk["risk_per_symbol_usd_cap"] == float(cfg.ftmo.risk_sizing_limit_usd)
    assert risk["stop_loss_pips"] == float(block.stop_loss_pips)
    assert risk["interval_minutes"] == float(block.interval_minutes)
    assert risk["execution_slippage_points"] == float(cfg.costs.slippage_points)
    assert risk["commission_per_lot"] == float(cfg.costs.commission_per_lot)
    assert "default_lot_size" not in risk


def test_load_risk_overrides_missing_block_falls_back_with_defaults() -> None:
    class NoBlock:
        pass

    risk = live_trading_rl.load_risk_overrides(NoBlock())
    assert risk == live_trading_rl._LIVE_RISK_DEFAULTS


def test_load_risk_overrides_keeps_training_cap_when_live_block_is_missing() -> None:
    cfg = OmegaConf.create({"ftmo": {"risk_sizing_limit_usd": 900.0}})

    risk = live_trading_rl.load_risk_overrides(cfg)

    assert risk["risk_per_symbol"] == live_trading_rl._LIVE_RISK_DEFAULTS["risk_per_symbol"]
    assert risk["risk_per_symbol_usd_cap"] == 900.0


@pytest.mark.parametrize("invalid", [0.0, -1.0, float("nan"), float("inf"), True, "bad"])
def test_load_risk_overrides_rejects_invalid_training_sizing_cap(invalid: object) -> None:
    cfg = OmegaConf.create({"ftmo": {"risk_sizing_limit_usd": invalid}})

    with pytest.raises(ValueError, match="ftmo.risk_sizing_limit_usd"):
        live_trading_rl.load_risk_overrides(cfg)


def test_load_risk_overrides_partial_block_warns_and_fills(monkeypatch: pytest.MonkeyPatch) -> None:
    """A dropped key must fall back explicitly, not silently shrink live risk."""
    warnings: list[str] = []
    monkeypatch.setattr(
        getattr(live_trading_rl, "logger"),
        "warning",
        lambda msg, *a: warnings.append(str(msg)),
    )
    cfg = OmegaConf.create({"live_risk_overrides": {"risk_per_symbol": 0.005}})
    risk = live_trading_rl.load_risk_overrides(cfg)
    assert risk["risk_per_symbol"] == 0.005
    assert risk["max_total_risk"] == live_trading_rl._LIVE_RISK_DEFAULTS["max_total_risk"]
    assert len(warnings) == len(live_trading_rl._LIVE_RISK_DEFAULTS) - 2


@pytest.mark.parametrize("invalid", [0.0, -0.1, float("nan"), float("inf"), True, "bad"])
def test_load_risk_overrides_rejects_invalid_values(invalid: object) -> None:
    cfg = OmegaConf.create({"live_risk_overrides": {"risk_per_symbol": invalid}})

    with pytest.raises(ValueError, match="risk_per_symbol must be a finite positive number"):
        live_trading_rl.load_risk_overrides(cfg)


@pytest.mark.parametrize(
    "key, invalid",
    [
        ("slippage_points", -0.1),
        ("slippage_points", float("nan")),
        ("commission_per_lot", -0.1),
        ("commission_per_lot", float("inf")),
        ("commission_per_lot", True),
    ],
)
def test_load_risk_overrides_rejects_invalid_execution_costs(key: str, invalid: object) -> None:
    cfg = OmegaConf.create({"costs": {key: invalid}})

    with pytest.raises(ValueError, match=f"costs.{key}"):
        live_trading_rl.load_risk_overrides(cfg)


# --- resolve_run_config: train/live parity ---------------------------------
def test_resolve_run_config_prefers_saved_run_config(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    (run_dir / "model").mkdir(parents=True)
    (run_dir / "config.yaml").write_text("features:\n  window: 30\n", encoding="utf-8")
    model_path = run_dir / "model" / "ppo_final.zip"
    model_path.write_bytes(b"x")
    assert live_trading_rl.resolve_run_config(model_path) == run_dir / "config.yaml"


def test_resolve_run_config_rejects_checkpoint_without_saved_config(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    (run_dir / "model").mkdir(parents=True)
    model_path = run_dir / "model" / "ppo_final.zip"
    model_path.write_bytes(b"x")
    with pytest.raises(FileNotFoundError, match="no saved config.yaml"):
        live_trading_rl.resolve_run_config(model_path)


def test_live_normalization_state_requires_manifest_hash_link(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    config_path = run_dir / "config.yaml"
    config_path.write_text("features: {}\n", encoding="utf-8")
    state_path = run_dir / "feature_normalization_state.json"
    state = {
        "schema": "feature-normalization-v1",
        "feature_cache_hash": "feature-cache-identity",
    }
    state_path.write_text(json.dumps(state), encoding="utf-8")
    manifest = {
        "feature_cache": {"sha256": "feature-cache-identity"},
        "feature_normalization": {
            "schema": "feature-normalization-v1",
            "path": state_path.name,
            "sha256": hashlib.sha256(state_path.read_bytes()).hexdigest(),
            "feature_cache_hash": "feature-cache-identity",
        },
    }
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    manifest["config"] = {
        "sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
    }
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    assert live_trading_rl.resolve_feature_normalization_state(config_path) == state_path

    state["feature_cache_hash"] = "different-cache-identity"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    with pytest.raises(ValueError, match="missing or mismatched"):
        live_trading_rl.resolve_feature_normalization_state(config_path)

    state["feature_cache_hash"] = "feature-cache-identity"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    config_path.write_text("features: {window: 3}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="config differs from its manifest identity"):
        live_trading_rl.resolve_feature_normalization_state(config_path)


# --- parse_args: CLI/env contract ------------------------------------------
def test_parse_args_model_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RL_MODEL_PATH", "outputs/some_run/model/ppo_final")
    monkeypatch.setattr(sys, "argv", ["live_trading_rl.py"])
    args = live_trading_rl.parse_args()
    assert args.model == "outputs/some_run/model/ppo_final"
    assert args.symbol == "US100"
    assert args.secondary_symbol == "US500"
    assert args.once is False
    assert args.interval_minutes is None


def test_parse_args_cli_overrides_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RL_MODEL_PATH", "from_env")
    monkeypatch.setattr(
        sys,
        "argv",
        ["live_trading_rl.py", "--model", "from_cli", "--once", "--symbol", "US500"],
    )
    args = live_trading_rl.parse_args()
    assert args.model == "from_cli"
    assert args.symbol == "US500"
    assert args.once is True


def test_parse_args_model_defaults_to_none_without_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With no env/CLI model the entrypoint's guard must produce a clean exit."""
    monkeypatch.delenv("RL_MODEL_PATH", raising=False)
    monkeypatch.setattr(sys, "argv", ["live_trading_rl.py"])
    args = live_trading_rl.parse_args()
    assert SimpleNamespace(model=args.model).model is None
