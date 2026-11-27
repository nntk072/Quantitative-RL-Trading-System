from __future__ import annotations

import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

_RUNTIME_EXPORTS = {
    "action_intent_runtime": ("entries.action_intent", ("ActionIntentRuntimeMixin",)),
    "action_runtime": ("actions.decoding", ("ActionDecodingMixin",)),
    "diagnostics_runtime": ("diagnostics.runtime", ("DiagnosticsRuntimeMixin",)),
    "ema_exit_runtime": ("exits.ema", ("EmaExitRuntimeMixin",)),
    "entry_execution_runtime": ("entries.execution", ("EntryExecutionRuntimeMixin",)),
    "entry_funnel_runtime": ("entries.funnel", ("EntryFunnelRuntimeMixin",)),
    "entry_order_runtime": ("entries.orders", ("EntryOrderRuntimeMixin",)),
    "entry_runtime": ("entries.lifecycle", ("EntryRuntimeMixin",)),
    "episode_runtime": ("episode.lifecycle", ("EpisodeRuntimeMixin",)),
    "execution_runtime": ("exits.execution", ("ExecutionRuntimeMixin",)),
    "fill_quote_runtime": ("quotes.fills", ("FillQuoteRuntimeMixin",)),
    "initialization_runtime": ("episode.initialization", ("InitializationRuntimeMixin",)),
    "observation_runtime": ("observations.runtime", ("ObservationRuntimeMixin",)),
    "position_open_runtime": ("positions.opening", ("PositionOpenRuntimeMixin",)),
    "position_runtime": ("positions.lifecycle", ("PositionRuntimeMixin",)),
    "protective_level_runtime": (
        "exits.protective_levels",
        ("ProtectiveLevelRuntimeMixin", "_level_reached", "_pending_tp_sl_quotes"),
    ),
    "risk_runtime": ("risk.runtime", ("RiskRuntimeMixin",)),
    "step_accounting_runtime": ("accounting.step", ("StepAccountingRuntimeMixin",)),
    "step_constraints_runtime": ("episode.constraints", ("StepConstraintsRuntimeMixin",)),
    "step_end_runtime": ("episode.end", ("StepEndRuntimeMixin",)),
    "step_info_runtime": ("episode.info", ("StepInfoRuntimeMixin",)),
    "step_runtime": ("episode.step", ("StepRuntimeMixin",)),
    "tick_quote_runtime": ("quotes.ticks", ("TickQuoteRuntimeMixin",)),
    "trade_accounting_runtime": ("accounting.trades", ("TradeAccountingRuntimeMixin",)),
    "trade_entry_record_runtime": (
        "positions.entry_record",
        ("TradeEntryRecordRuntimeMixin",),
    ),
}


def test_legacy_package_directories_are_removed() -> None:
    for rel in ("quant_rl", "mt5_trading", "evaluation/analysis", "training/train"):
        path = ROOT / rel
        python_files = list(path.rglob("*.py")) if path.exists() else []
        assert not python_files, f"legacy Python modules remain under {rel}: {python_files[:5]}"


def test_environment_runtime_modules_reexport_concept_modules() -> None:
    for legacy_name, (concept_name, symbols) in _RUNTIME_EXPORTS.items():
        legacy = importlib.import_module(f"simulation.environment.{legacy_name}")
        concept = importlib.import_module(f"simulation.environment.{concept_name}")
        for symbol in symbols:
            assert getattr(legacy, symbol) is getattr(concept, symbol), (
                f"{legacy_name}.{symbol} must re-export {concept_name}.{symbol}"
            )
