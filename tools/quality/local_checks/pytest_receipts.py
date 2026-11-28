"""Pytest inventory and per-phase evidence hooks for bounded local campaigns."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest


def _write_json(path: Path, value: object) -> None:
    """Write the per-process collection inventory in an isolated file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Apply an exact explicit node-ID selection without command-line length limits."""
    selection = os.environ.get("QRL_LOCAL_SELECTION")
    if selection:
        expected = set(json.loads(Path(selection).read_text()))
        items[:] = [item for item in items if item.nodeid in expected]
        if {item.nodeid for item in items} != expected:
            raise pytest.UsageError("Selected test inventory could not be collected")


def pytest_collection_finish(session: pytest.Session) -> None:
    """Capture exact node IDs after marker and impact selection."""
    target = os.environ.get("QRL_LOCAL_INVENTORY")
    if target:
        worker = os.environ.get("PYTEST_XDIST_WORKER")
        path = Path(target + f".{worker}.json" if worker else target)
        _write_json(
            path,
            [
                {"nodeid": item.nodeid, "markers": sorted(m.name for m in item.iter_markers())}
                for item in session.items
            ],
        )


class _ReceiptWriter:
    """Bind the receipt destination before tests can alter the process environment."""

    def __init__(self, target: Path) -> None:
        self.target = target

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        """Record phase outcomes on the controller for the whole pytest session."""
        with self.target.open("a", encoding="utf-8") as stream:
            stream.write(
                json.dumps(
                    {
                        "nodeid": report.nodeid,
                        "phase": report.when,
                        "outcome": report.outcome,
                        "seconds": report.duration,
                        "xfail": bool(getattr(report, "wasxfail", False)),
                    }
                )
                + "\n"
            )


def pytest_configure(config: pytest.Config) -> None:
    """Register a session-scoped controller writer with a stable destination."""
    target = os.environ.get("QRL_LOCAL_RECEIPTS")
    if target and not os.environ.get("PYTEST_XDIST_WORKER"):
        config.pluginmanager.register(_ReceiptWriter(Path(target).resolve()), "qrl-receipt-writer")
