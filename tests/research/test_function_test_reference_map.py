"""Focused tests for the static function-to-test reference inventory."""

from __future__ import annotations

import hashlib
from pathlib import Path

from scripts.research.analysis.evidence.build_function_test_reference_map import (
    build_rows,
    write_csv,
    write_readme,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_build_rows_maps_only_static_symbol_references(tmp_path: Path) -> None:
    """Imported symbols map to a test path without implying execution coverage."""
    _write(
        tmp_path / "features" / "causal.py",
        """def build_signal(value: int) -> int:
    return value

def _internal_helper() -> int:
    return 1

class Envelope:
    @staticmethod
    def create() -> 'Envelope':
        return Envelope()
""",
    )
    _write(
        tmp_path / "trading" / "execution" / "broker.py",
        """def place_order() -> None:
    pass
""",
    )
    _write(
        tmp_path / "trading" / "execution" / "service.py",
        """from trading.execution.broker import place_order

def execute() -> None:
    place_order()
""",
    )
    _write(
        tmp_path / "tests" / "test_causal.py",
        """from features.causal import build_signal, Envelope

def test_symbols():
    build_signal(1)
    Envelope.create()
""",
    )
    _write(
        tmp_path / "tests" / "test_broker.py",
        """import trading.execution.broker as broker

def test_broker():
    broker.place_order()
""",
    )
    _write(tmp_path / "orchestra" / "pipeline.py", "def hidden() -> None:\n    pass\n")
    _write(tmp_path / ".venv-x86" / "lib.py", "def hidden() -> None:\n    pass\n")
    _write(tmp_path / "build" / "generated.py", "def hidden() -> None:\n    pass\n")

    rows = build_rows(tmp_path)
    by_symbol = {(row["module"], row["symbol"]): row for row in rows}

    signal = by_symbol[("features.causal", "build_signal")]
    assert signal["direct_static_test_references"] == "tests/test_causal.py"
    assert signal["risk_tier"] == "P0"
    assert signal["api_visibility_by_name"] == "public_by_name"
    assert signal["direct_static_production_references"] == ""
    assert signal["evidence_status"] == "static_reference_only"
    assert (
        hashlib.sha256((tmp_path / signal["source_path"]).read_bytes()).hexdigest()
        == signal["source_sha256"]
    )
    assert signal["test_sha256s"].endswith(
        hashlib.sha256((tmp_path / "tests/test_causal.py").read_bytes()).hexdigest()
    )

    method = by_symbol[("features.causal", "Envelope.create")]
    assert method["direct_static_test_references"] == "tests/test_causal.py"
    order = by_symbol[("trading.execution.broker", "place_order")]
    assert order["direct_static_test_references"] == "tests/test_broker.py"
    assert order["direct_static_production_references"] == "trading/execution/service.py"
    internal = by_symbol[("features.causal", "_internal_helper")]
    assert internal["api_visibility_by_name"] == "internal_by_name"
    assert by_symbol[("features.causal", "build_signal")]["direct_static_test_references"]
    assert all("hidden" not in row["symbol"] for row in rows)


def test_csv_and_readme_are_stable_and_scope_honest(tmp_path: Path) -> None:
    """Generated artifacts state that static imports are not execution evidence."""
    _write(tmp_path / "features" / "sample.py", "def sample() -> None:\n    pass\n")
    _write(tmp_path / "tests" / "test_sample.py", "from features.sample import sample\n")
    rows = build_rows(tmp_path)
    csv_path = tmp_path / "packet" / "map.csv"
    readme_path = tmp_path / "packet" / "README.md"

    write_csv(csv_path, rows)
    first = csv_path.read_bytes()
    write_csv(csv_path, rows)
    write_readme(readme_path, rows, source_file_count=1)

    assert csv_path.read_bytes() == first
    assert "static_reference_only" in first.decode()
    assert "direct_static_production_references" in first.decode().splitlines()[0]
    readme = " ".join(readme_path.read_text(encoding="utf-8").split())
    assert "does not claim that a test was run" in readme
    assert "neither is a call graph" in readme
