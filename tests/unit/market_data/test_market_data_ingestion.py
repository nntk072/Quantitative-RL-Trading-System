from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from market_data.loading import market_data_ingestion


def test_stable_bar_load_rejects_source_changed_while_parsing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "bars.csv"
    source.write_text("original", encoding="utf-8")

    def replace_during_parse(path: Path, **_kwargs: object) -> pd.DataFrame:
        path.write_text("replacement", encoding="utf-8")
        return pd.DataFrame({"close": [1.0]})

    monkeypatch.setattr(market_data_ingestion, "load_bars", replace_during_parse)

    with pytest.raises(RuntimeError, match="changed while being parsed"):
        market_data_ingestion._load_stable_bars(source)


def test_stable_bar_load_rejects_identity_mismatch_before_parsing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "bars.csv"
    source.write_text("current", encoding="utf-8")
    called = False

    def unexpected_parse(*_args: object, **_kwargs: object) -> pd.DataFrame:
        nonlocal called
        called = True
        return pd.DataFrame({"close": [1.0]})

    monkeypatch.setattr(market_data_ingestion, "load_bars", unexpected_parse)

    with pytest.raises(RuntimeError, match="does not match cache identity"):
        market_data_ingestion._load_stable_bars(source, expected_sha256="wrong")

    assert not called
