"""Optional HTML chart dependencies do not block CSV/PNG reporting."""

from __future__ import annotations

import builtins
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from training.reporting import training_curves


def test_training_html_helpers_skip_cleanly_when_plotly_is_unavailable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    real_import = builtins.__import__

    def import_without_plotly(name: str, *args: Any, **kwargs: Any) -> Any:
        if name.startswith("plotly"):
            raise ImportError("optional plotly dependency unavailable")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_without_plotly)
    frame = pd.DataFrame({"timestep": [1, 2], "reward": [0.1, 0.2]})
    output = tmp_path / "plots"
    output.mkdir()

    training_curves._save_training_html(frame, output)
    training_curves._html_lines(
        frame,
        (("reward", "Reward"),),
        "Reward history",
        output / "reward.html",
    )

    assert list(output.iterdir()) == []
