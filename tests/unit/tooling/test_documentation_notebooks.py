"""Tests for documentation notebook execution limits."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from tools.documentation import check_notebooks


def test_notebook_metadata_requires_subject_data_and_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Require the subject, fixture source, and owning role in notebook metadata."""
    path = tmp_path / "example.ipynb"
    notebook = {
        "metadata": {
            "title": "Example",
            "kernelspec": {"name": "python3"},
            "mystnb": {"execution_mode": "force"},
            "qrl": {"tier": "A", "hardware": "CPU", "runtime": "under 60 seconds"},
        },
        "cells": [
            {"cell_type": "markdown", "source": "# Example"},
            {"cell_type": "code", "source": "print('ok')"},
        ],
    }
    path.write_text(json.dumps(notebook), encoding="utf-8")
    monkeypatch.setattr(check_notebooks, "ROOT", tmp_path)

    errors = check_notebooks.validate_notebook(path)

    assert any("qrl.data" in error for error in errors)
    assert any("qrl.subject" in error for error in errors)
    assert any("qrl.owner" in error for error in errors)


def test_tier_a_notebook_over_runtime_limit_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reject a Tier A notebook whose total execution exceeds 60 seconds."""
    docs = tmp_path / "docs"
    docs.mkdir()
    path = docs / "example.ipynb"
    notebook = {
        "metadata": {"qrl": {"tier": "A"}},
        "cells": [{"cell_type": "code", "source": "print('ok')"}],
    }
    path.write_text(json.dumps(notebook), encoding="utf-8")

    class FastNotebookClient:
        def __init__(self, value: object, **_: object) -> None:
            self.notebook = value

        def execute(self) -> dict[str, object]:
            return {"cells": [{"cell_type": "code", "outputs": ["ok"]}]}

    original_import = importlib.import_module

    def import_module(name: str) -> object:
        if name == "nbclient":
            return SimpleNamespace(NotebookClient=FastNotebookClient)
        return original_import(name)

    monkeypatch.setattr(check_notebooks, "ROOT", tmp_path)
    monkeypatch.setattr(importlib, "import_module", import_module)
    elapsed = iter((0.0, 60.1))
    monkeypatch.setattr(check_notebooks, "perf_counter", lambda: next(elapsed), raising=False)

    errors = check_notebooks.execute_tier_a((path,))

    assert errors == ["docs/example.ipynb: execution took 60.10s; limit is 60s"]
