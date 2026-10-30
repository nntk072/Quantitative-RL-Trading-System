#!/usr/bin/env python3
"""Export a chronological window of completed training trades for review.

This report uses saved position summaries and fill events. It does not reload a
checkpoint or replay the market. Its purpose is to make the recorded decisions,
risk, fills, and outcomes easy to inspect alongside the experiment run report.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result and abs(result) != float("inf") else None


def _fmt(value: Any, digits: int = 2) -> str:
    number = _number(value)
    if number is not None:
        return f"{number:,.{digits}f}"
    if value is None or str(value).strip() in {"", "nan", "None"}:
        return "—"
    return str(value)


def _cell(value: Any) -> str:
    return str(value if value not in (None, "") else "—").replace("|", "\\|").replace("\n", " ")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _run_dirs(experiment_run_dir: Path, variant: str) -> tuple[Path, Path]:
    candidates = sorted(
        (experiment_run_dir / "runs" / "attempts").glob(
            f"{variant}__seed50/attempt*/{variant}__seed50"
        )
    )
    if len(candidates) != 1:
        raise FileNotFoundError(f"expected one saved run for {variant}; found {len(candidates)}")
    attempt_root = candidates[0]
    run_dirs = sorted(
        path for path in attempt_root.iterdir() if path.is_dir() and (path / "training").is_dir()
    )
    if len(run_dirs) != 1:
        raise FileNotFoundError(
            f"expected one timestamped run for {variant}; found {len(run_dirs)}"
        )
    return attempt_root, run_dirs[0]


def _ordered_positions(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    completed = [row for row in rows if row.get("completed", "").lower() == "true"]
    return sorted(
        completed, key=lambda row: (row.get("entry_time", ""), row.get("position_id", ""))
    )


def _write_report(
    experiment_run_dir: Path,
    variant: str,
    limit: int,
    window: str,
    output_dir: Path,
) -> Path:
    attempt_root, run_dir = _run_dirs(experiment_run_dir, variant)
    split_dir = run_dir / "training"
    positions_path = split_dir / "positions.csv"
    fills_path = split_dir / "fills.csv"
    config_path = attempt_root / "resolved_config.json"
    for path in (positions_path, fills_path, config_path):
        if not path.is_file():
            raise FileNotFoundError(path)

    positions = _ordered_positions(_read_rows(positions_path))
    fills = _read_rows(fills_path)
    by_position: dict[str, list[dict[str, str]]] = {}
    for fill in fills:
        position_id = fill.get("position_id", "")
        if position_id:
            by_position.setdefault(position_id, []).append(fill)
    selected = positions[-limit:] if window == "last" else positions[:limit]
    config = json.loads(config_path.read_text(encoding="utf-8"))
    overrides = config.get("overrides", [])
    override_map = dict(item.split("=", 1) for item in overrides if "=" in item)
    experiment_run = json.loads(
        (experiment_run_dir / "experiment_run.json").read_text(encoding="utf-8")
    )
    fingerprint = experiment_run.get("fingerprint", "not recorded")

    report_path = output_dir / f"{variant}_seed50_training_last{len(selected)}_trades.md"
    output_dir.mkdir(parents=True, exist_ok=True)
    first_time = selected[0].get("entry_time", "—") if selected else "—"
    last_time = selected[-1].get("exit_time", "—") if selected else "—"
    selected_pnl = sum(
        _number(row.get("position_net_pnl") or row.get("net_pnl")) or 0.0 for row in selected
    )

    lines = [
        f"# {variant}: {len(selected)} completed training trades",
        "",
        f"Experiment run: `{experiment_run_dir.name}`  ",
        f"Experiment run fingerprint: `{fingerprint}`  ",
        f"Seed: `{config.get('seed', 'not recorded')}`  ",
        f"Architecture: `{config.get('arch', 'not recorded')}`  ",
        f"Window: `{window}` chronological completed positions from the training split  ",
        f"Selected interval: `{first_time}` through `{last_time}`  ",
        f"Selected-window net PnL: **${selected_pnl:,.2f}** (sum for these rows only).",
        "",
        "## Risk policy actually used",
        "",
        "This MTF experiment run did **not** use a 10% peak trailing drawdown rule. Its resolved settings were:",
        "",
        "| Rule | Resolved setting | Meaning |",
        "|---|---:|---|",
        f"| Daily loss limit | ${_fmt(override_map.get('ftmo.daily_loss_limit'))} | Fixed-dollar daily limit |",
        f"| Maximum loss | ${_fmt(override_map.get('ftmo.max_loss_limit'))} | Fixed-dollar loss from initial equity; $90,000 floor at $100,000 initial equity |",
        f"| Maximum loss as initial-equity share | {_fmt(override_map.get('ftmo.max_loss_limit_initial_pct'), 3)} | 10% of initial equity, not 10% from the running peak |",
        f"| FTMO trailing drawdown | ${_fmt(override_map.get('ftmo.trailing_dd_limit'))} | Disabled |",
        f"| Environment peak trailing drawdown | {_fmt(override_map.get('env.peak_trailing_dd_limit'))} | Disabled |",
        f"| Per-trade sizing ceiling | ${_fmt(override_map.get('ftmo.risk_sizing_limit_usd'))} | Dollar-band cap recorded in the run config |",
        "",
        "The equity could therefore retreat by more than 10% from a local peak while remaining above $90,000. The training gate stopped the run when the fixed maximum-loss floor was reached; it did not enforce a 10% peak-to-trough ceiling.",
        "",
        "## Trade ledger",
        "",
        "One row represents one completed position, joined from `positions.csv` and its recorded opening fill in `fills.csv`. Prices, risk, actions, and outcomes are saved artifacts. Action coordinates are the policy outputs recorded at entry; risk dollars are the environment's requested/approved amounts.",
        "",
        "| # | Entry → exit time (UTC) | Side | Entry → exit | Stop / target | Risk requested / approved | Net PnL / R | Exit reason | SL / TP reference | Setup · session · regime | Equity at entry | Action intensity · risk · exit |",
        "|---:|---|---|---:|---|---:|---:|---|---|---|---:|---|",
    ]

    for index, position in enumerate(selected, start=1):
        events = by_position.get(position.get("position_id", ""), [])
        opens = [row for row in events if row.get("type") == "open"]
        entry = opens[0] if opens else {}
        side = "Long" if _number(position.get("direction")) == 1.0 else "Short"
        entry_exit_time = f"{position.get('entry_time', '—')} → {position.get('exit_time', '—')}"
        prices = f"{_fmt(position.get('entry_price'))} → {_fmt(position.get('exit_price'))}"
        stop_target = f"SL {_fmt(entry.get('sl_price'))} / TP {_fmt(entry.get('tp_price'))}"
        risk = f"${_fmt(entry.get('requested_risk_usd'))} / ${_fmt(entry.get('approved_risk_usd'))}"
        pnl = _number(position.get("position_net_pnl") or position.get("net_pnl"))
        realized_r = _number(entry.get("position_realized_r") or entry.get("realized_r"))
        pnl_r = f"${_fmt(pnl)} / {_fmt(realized_r, 3)}R"
        references = f"SL {entry.get('sl_ref') or '—'} / TP {entry.get('tp_ref') or '—'}"
        setup = ", ".join(
            part
            for part in (
                entry.get("entry_setup_types", ""),
                entry.get("level_type", ""),
                entry.get("session", ""),
                entry.get("volatility_regime", ""),
                entry.get("trend_regime", ""),
            )
            if part and part not in {"[]", "nan"}
        )
        actions = (
            f"I {_fmt(entry.get('action_intensity'), 3)} · R {_fmt(entry.get('action_risk'), 3)} · "
            f"X {_fmt(entry.get('action_exit'), 3)}"
        )
        cells = (
            index,
            entry_exit_time,
            side,
            prices,
            stop_target,
            risk,
            pnl_r,
            position.get("exit_reason", "—"),
            references,
            setup,
            f"${_fmt(entry.get('equity'))}",
            actions,
        )
        lines.append("| " + " | ".join(_cell(item) for item in cells) + " |")

    lines.extend(
        [
            "",
            "## Reading this ledger",
            "",
            "- The run's equity plots and full metrics remain in [the experiment run report](project_results_report.md).",
            "- `Net PnL` is the completed position's recorded net amount. `R` is the recorded realized R value when available; `—` means the source row did not contain it.",
            "- The action columns show selected raw PPO outputs, not a probability or a guarantee of execution. SL/TP values and approved risk are the resolved execution fields.",
            "- This is a training-split observation window, not an independent test sample. It does not claim that its selected-window sum is the experiment run's total return.",
            "",
            "## Source artifact hashes",
            "",
            f"- `positions.csv`: `{_sha256(positions_path)}`",
            f"- `fills.csv`: `{_sha256(fills_path)}`",
            f"- `resolved_config.json`: `{_sha256(config_path)}`",
            "",
            f"Generated from saved artifacts at `{datetime.now().astimezone().isoformat(timespec='seconds')}`. No checkpoint was loaded and no market replay was run.",
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment-run-dir", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--window", choices=("first", "last"), default="last")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if args.limit <= 0:
        parser.error("--limit must be positive")
    experiment_run_dir = args.experiment_run_dir.resolve()
    output_dir = (args.output_dir or experiment_run_dir / "reports" / "trade_observation").resolve()
    for variant in ("rq_mtf_control_tcn", "rq_mtf_treatment_mtf"):
        report = _write_report(experiment_run_dir, variant, args.limit, args.window, output_dir)
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
