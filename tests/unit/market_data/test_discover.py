"""Behavior tests for broker-neutral symbol discovery utilities."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pandas as pd
import pytest
import yaml

# MT5 is a Windows-only runtime dependency. Keep this CLI importable on CPU CI;
# augment any test-provided stub and replace every MT5 call before use.
_mt5_stub = sys.modules.get("MetaTrader5")
if _mt5_stub is None:
    _mt5_stub = ModuleType("MetaTrader5")
    sys.modules["MetaTrader5"] = _mt5_stub
for _name in ("initialize", "login", "symbols_get", "shutdown", "last_error"):
    if not hasattr(_mt5_stub, _name):
        setattr(_mt5_stub, _name, lambda *args, **kwargs: None)

from market_data import cli as market_data_cli  # noqa: E402
from market_data.commands import (  # noqa: E402
    discover,
    prepare,
)

mt5: Any = vars(discover)["mt5"]


@pytest.mark.parametrize(
    ("symbol", "expected"),
    [
        ("BTCUSD", "crypto"),
        ("XAUUSD", "commodities"),
        ("BRENT", "commodities"),
        ("COPPER", "commodities"),
        ("EURUSD", "forex"),
        ("USDSGD", "forex"),
        ("SPY", "etf"),
        ("BRK.B", "stocks"),
        ("US100IDX", "other"),
    ],
)
def test_categorize_symbol_uses_symbol_name_rules(symbol: str, expected: str) -> None:
    assert discover.categorize_symbol(symbol, "ignored description") == expected


def _symbol(
    name: str,
    *,
    description: str | None = "description",
    visible: bool = True,
) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        description=description,
        visible=visible,
        currency_base="USD",
        currency_profit="EUR",
        trade_mode=4,
        digits=2,
        point=0.01,
        volume_min=0.1,
        volume_max=10.0,
        volume_step=0.1,
    )


def test_discover_symbols_categorizes_visible_symbols_and_shuts_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    records = [
        _symbol("BTCUSD", description=None),
        _symbol("EURUSD"),
        _symbol("US100IDX", visible=False),
        _symbol("GBPUSD"),
    ]

    def initialize(**kwargs: Any) -> bool:
        del kwargs
        calls.append("initialize")
        return True

    def login(**kwargs: Any) -> bool:
        del kwargs
        calls.append("login")
        return True

    monkeypatch.setattr(mt5, "initialize", initialize)
    monkeypatch.setattr(mt5, "login", login)
    monkeypatch.setattr(mt5, "symbols_get", lambda: records)
    monkeypatch.setattr(mt5, "shutdown", lambda: calls.append("shutdown"))

    result = discover.discover_symbols()

    assert [item["symbol"] for item in result["forex"]] == ["EURUSD", "GBPUSD"]
    assert result["crypto"] == [
        {
            "symbol": "BTCUSD",
            "description": "",
            "currency_base": "USD",
            "currency_profit": "EUR",
            "trade_mode": 4,
            "digits": 2,
            "point": 0.01,
            "volume_min": 0.1,
            "volume_max": 10.0,
            "volume_step": 0.1,
        }
    ]
    assert result["other"] == []
    assert calls == ["initialize", "login", "shutdown"]


@pytest.mark.parametrize(
    ("initialize_ok", "login_ok", "symbols", "expected_calls"),
    [
        (False, True, [], ["initialize"]),
        (True, False, [], ["initialize", "login", "shutdown"]),
        (True, True, None, ["initialize", "login", "shutdown"]),
    ],
)
def test_discover_symbols_fails_closed_and_shuts_down_when_initialized(
    monkeypatch: pytest.MonkeyPatch,
    initialize_ok: bool,
    login_ok: bool,
    symbols: list[Any] | None,
    expected_calls: list[str],
) -> None:
    calls: list[str] = []

    def initialize(**kwargs: Any) -> bool:
        del kwargs
        calls.append("initialize")
        return initialize_ok

    def login(**kwargs: Any) -> bool:
        del kwargs
        calls.append("login")
        return login_ok

    monkeypatch.setattr(mt5, "initialize", initialize)
    monkeypatch.setattr(mt5, "login", login)
    monkeypatch.setattr(mt5, "symbols_get", lambda: symbols)
    monkeypatch.setattr(mt5, "last_error", lambda: (1, "test error"))
    monkeypatch.setattr(mt5, "shutdown", lambda: calls.append("shutdown"))

    assert discover.discover_symbols() == {}
    assert calls == expected_calls


def test_print_symbols_shows_first_twenty_and_omits_empty_categories(
    capsys: pytest.CaptureFixture[str],
) -> None:
    symbols = [{"symbol": f"S{index:02d}", "description": "example"} for index in range(21)]

    discover.print_symbols(
        {"crypto": symbols, "forex": [{"symbol": "EURUSD", "description": "FX"}], "other": []}
    )

    output = capsys.readouterr().out
    assert "CRYPTO (21 symbols)" in output
    assert "S19" in output
    assert "S20" not in output
    assert "... and 1 more" in output
    assert "FOREX (1 symbols)" in output
    assert "OTHER (" not in output


def test_save_symbols_to_config_merges_nonempty_categories_and_creates_parent(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "nested" / "symbols.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        "symbol_categories:\n  forex: [OLD]\n  crypto: [BTCUSD]\nsettings:\n  enabled: true\n",
        encoding="utf-8",
    )

    discover.save_symbols_to_config(
        {
            "forex": [{"symbol": "EURUSD"}],
            "crypto": [],
            "etf": [{"symbol": "SPY"}],
        },
        str(config_path),
    )

    saved = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert saved == {
        "symbol_categories": {"forex": ["EURUSD"], "crypto": ["BTCUSD"], "etf": ["SPY"]},
        "settings": {"enabled": True},
    }


def test_save_symbols_to_config_handles_empty_yaml_file(tmp_path: Path) -> None:
    config_path = tmp_path / "symbols.yaml"
    config_path.write_text("", encoding="utf-8")

    discover.save_symbols_to_config(
        {"forex": [{"symbol": "EURUSD"}], "crypto": []}, str(config_path)
    )

    assert yaml.safe_load(config_path.read_text(encoding="utf-8")) == {
        "symbol_categories": {"forex": ["EURUSD"]}
    }


def test_main_returns_when_credentials_are_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(discover, "LOGIN", None)
    monkeypatch.setattr(discover, "PASSWORD", "password")
    monkeypatch.setattr(discover, "SERVER", "server")
    was_called = False

    def fail_connect() -> dict[str, list[dict[str, Any]]]:
        nonlocal was_called
        was_called = True
        return {}

    monkeypatch.setattr(discover, "discover_symbols", fail_connect)

    discover.main()

    assert not was_called


def test_main_returns_when_discovery_has_no_symbols(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(discover, "LOGIN", "login")
    monkeypatch.setattr(discover, "PASSWORD", "password")
    monkeypatch.setattr(discover, "SERVER", "server")
    monkeypatch.setattr(discover, "discover_symbols", lambda: {})
    monkeypatch.setattr(discover, "repository_root", lambda _file: tmp_path)

    discover.main()

    assert not (tmp_path / "config" / "symbols_config.yaml").exists()


def test_main_persists_discovery_and_reports_summary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    symbols = {
        "forex": [{"symbol": "EURUSD", "description": "Euro"}],
        "crypto": [{"symbol": "BTCUSD", "description": "Bitcoin"}],
        "commodities": [],
        "etf": [],
        "stocks": [],
        "other": [],
    }
    monkeypatch.setattr(discover, "LOGIN", "login")
    monkeypatch.setattr(discover, "PASSWORD", "password")
    monkeypatch.setattr(discover, "SERVER", "server")
    monkeypatch.setattr(discover, "discover_symbols", lambda: symbols)
    monkeypatch.setattr(discover, "repository_root", lambda _file: tmp_path)

    discover.main()

    output = capsys.readouterr().out
    assert "SUMMARY: Discovered 2 tradeable symbols" in output
    assert "forex: 1 symbols" in output
    assert "crypto: 1 symbols" in output
    config = yaml.safe_load(
        (tmp_path / "config" / "symbols_config.yaml").read_text(encoding="utf-8")
    )
    assert config["symbol_categories"] == {"forex": ["EURUSD"], "crypto": ["BTCUSD"]}


def test_module_entrypoint_returns_without_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("LOGIN", "PASSWORD", "SERVER"):
        monkeypatch.setenv(name, "")
    monkeypatch.setitem(sys.modules, "MetaTrader5", mt5)
    module_path = discover.__file__
    assert module_path is not None

    namespace = runpy.run_path(module_path, run_name="__main__")

    assert namespace["__name__"] == "__main__"


@pytest.mark.parametrize("command", ["prepare", "discover", "prebuild-experiment-run-cache"])
def test_market_data_cli_forwards_arguments_and_restores_argv(
    monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    from market_data.commands import prebuild_experiment_run_cache

    modules = {
        "prepare": prepare,
        "discover": discover,
        "prebuild-experiment-run-cache": prebuild_experiment_run_cache,
    }
    target = modules[command]
    observed: list[list[str]] = []

    def capture_args() -> None:
        observed.append(sys.argv[1:])

    monkeypatch.setattr(target, "main", capture_args)
    original_argv = ["qrl-data", command, "--sample", "value"]
    monkeypatch.setattr(sys, "argv", original_argv)

    market_data_cli.main()

    assert observed == [["--sample", "value"]]
    assert sys.argv is original_argv


def test_prebuild_cache_uses_one_merged_data_policy_for_all_run_workers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from market_data.commands import prebuild_experiment_run_cache

    (tmp_path / "config/data_modes").mkdir(parents=True)
    (tmp_path / "config/data_modes/session.yaml").write_text(
        "data:\n  timezone: UTC\n  session:\n    start: '08:30'\n",
        encoding="utf-8",
    )
    (tmp_path / "config/experiments.yaml").write_text(
        "defaults: {}\nvariants:\n  - name: baseline\n    config_overrides: ['data.timezone=Europe/Helsinki']\n",
        encoding="utf-8",
    )
    spec = tmp_path / "run.yaml"
    spec.write_text(
        "variants: [baseline]\ndata_profile: config/data_modes/session.yaml\n"
        "config_overrides:\n  data.cache_dir: cache/shared\n  model.seed: 42\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(prebuild_experiment_run_cache, "ROOT", tmp_path)
    monkeypatch.setenv("EXPERIMENT_RUN_SPEC", str(spec))

    overrides = prebuild_experiment_run_cache._experiment_run_data_overrides()

    assert overrides == [
        "data.cache_dir=cache/shared",
        "data.session.start=08:30",
        "data.timezone=Europe/Helsinki",
    ]


def test_prebuild_cache_flattens_scalar_profile_settings_and_rejects_sequences() -> None:
    from market_data.commands import prebuild_experiment_run_cache

    assert prebuild_experiment_run_cache._flatten_data(
        {"timezone": "UTC", "session": {"start": "08:30", "enabled": True}}
    ) == {
        "data.timezone": "UTC",
        "data.session.start": "08:30",
        "data.session.enabled": True,
    }
    with pytest.raises(ValueError, match="mappings"):
        prebuild_experiment_run_cache._flatten_data(["not", "a", "mapping"])
    with pytest.raises(ValueError, match="unsupported experiment run data setting data.timeframes"):
        prebuild_experiment_run_cache._flatten_data({"timeframes": ["M1", "M5"]})


@pytest.mark.parametrize(
    ("increment", "cache_dir"),
    [(0.0, "cache/grid"), (0.25, "../cache/grid"), (0.25, "/tmp/grid")],
)
def test_prebuild_cache_rejects_invalid_price_grid_variant_identity(
    increment: float, cache_dir: str
) -> None:
    from market_data.commands import prebuild_experiment_run_cache

    experiments = {
        "defaults": {"price_grid_increment": increment, "price_grid_cache_dir": cache_dir},
        "variants": [{"name": "grid"}],
    }

    with pytest.raises(ValueError, match="positive increment and relative cache dir"):
        prebuild_experiment_run_cache._variant_data_overrides("grid", experiments)


def test_prebuild_cache_rejects_run_variants_with_different_data_policies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from market_data.commands import prebuild_experiment_run_cache

    (tmp_path / "config").mkdir()
    (tmp_path / "config/experiments.yaml").write_text(
        "defaults: {}\nvariants:\n"
        "  - name: utc\n    config_overrides: ['data.timezone=UTC']\n"
        "  - name: helsinki\n    config_overrides: ['data.timezone=Europe/Helsinki']\n",
        encoding="utf-8",
    )
    spec = tmp_path / "run.yaml"
    spec.write_text("variants: [utc, helsinki]\n", encoding="utf-8")
    monkeypatch.setattr(prebuild_experiment_run_cache, "ROOT", tmp_path)
    monkeypatch.setenv("EXPERIMENT_RUN_SPEC", str(spec))

    with pytest.raises(ValueError, match="variants must share one data transform"):
        prebuild_experiment_run_cache._experiment_run_data_overrides()


def test_prebuild_cache_reports_only_complete_bar_and_tick_cache_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from omegaconf import OmegaConf

    from market_data.commands import prebuild_experiment_run_cache

    symbol = "US100.cash"
    cache_dir = tmp_path / "cache"
    config = OmegaConf.create(
        {
            "data": {
                "cache_dir": str(cache_dir),
                "symbols": [symbol],
                "timeframes": ["M1"],
                "price_discretization": {"enabled": False},
            }
        }
    )
    bars = pd.DataFrame({"close": [100.0]})
    calls: list[tuple[object, bool]] = []

    def run_pipeline(actual_config: object, *, force: bool) -> dict[str, dict[str, pd.DataFrame]]:
        calls.append((actual_config, force))
        return {symbol: {"M1": bars}}

    monkeypatch.setattr(prebuild_experiment_run_cache, "load_config", lambda **_kwargs: config)
    monkeypatch.setattr(prebuild_experiment_run_cache, "run_pipeline", run_pipeline)
    monkeypatch.setattr(
        prebuild_experiment_run_cache, "build_tick_books", lambda *_args, **_kwargs: {}
    )
    monkeypatch.setattr(prebuild_experiment_run_cache, "bar_cache_is_complete", lambda _path: True)
    monkeypatch.setattr(prebuild_experiment_run_cache, "tick_cache_is_complete", lambda _path: True)
    monkeypatch.setattr(
        prebuild_experiment_run_cache, "configured_price_grid_increment", lambda _cfg: None
    )

    prebuild_experiment_run_cache.main()

    summary = yaml.safe_load(capsys.readouterr().out)
    assert calls == [(config, True)]
    assert summary["cache_files"] == 1
    assert summary["tick_cache_files"] == 1
    assert summary["bars"] == {symbol: {"M1": 1}}
    assert summary["ticks"] == {}


def test_prebuild_cache_fails_when_tick_cache_output_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from omegaconf import OmegaConf

    from market_data.commands import prebuild_experiment_run_cache

    config = OmegaConf.create(
        {
            "data": {
                "cache_dir": str(tmp_path / "cache"),
                "symbols": ["US100.cash"],
                "timeframes": ["M1"],
                "price_discretization": {"enabled": False},
            }
        }
    )
    monkeypatch.setattr(prebuild_experiment_run_cache, "load_config", lambda **_kwargs: config)
    monkeypatch.setattr(
        prebuild_experiment_run_cache,
        "run_pipeline",
        lambda *_args, **_kwargs: {"US100.cash": {"M1": pd.DataFrame({"close": [100.0]})}},
    )
    monkeypatch.setattr(
        prebuild_experiment_run_cache, "build_tick_books", lambda *_args, **_kwargs: {}
    )
    monkeypatch.setattr(prebuild_experiment_run_cache, "bar_cache_is_complete", lambda _path: True)
    monkeypatch.setattr(
        prebuild_experiment_run_cache, "tick_cache_is_complete", lambda _path: False
    )
    monkeypatch.setattr(
        prebuild_experiment_run_cache, "configured_price_grid_increment", lambda _cfg: None
    )

    with pytest.raises(RuntimeError, match="tick cache build left missing/empty outputs"):
        prebuild_experiment_run_cache.main()


def test_prepare_command_applies_overrides_and_force_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = SimpleNamespace(data=SimpleNamespace(raw_dir="raw", cache_dir="cache"))
    received: list[tuple[object, bool]] = []

    def run_pipeline(actual_cfg: object, *, force: bool) -> dict[str, dict[str, list[int]]]:
        received.append((actual_cfg, force))
        return {"US100.cash": {"M1": [1, 2]}}

    monkeypatch.setattr(prepare, "load_config", lambda overrides: (cfg, overrides)[0])
    monkeypatch.setattr(prepare, "run_pipeline", run_pipeline)
    monkeypatch.setattr(sys, "argv", ["qrl-data", "--force", "data.tz=UTC"])

    prepare.main()

    assert received == [(cfg, True)]
