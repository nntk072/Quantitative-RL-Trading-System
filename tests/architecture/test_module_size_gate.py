from __future__ import annotations

from pathlib import Path

from tools.quality.module_size import find_oversized_modules


def _write_module(path: Path, line_count: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join("pass" for _ in range(line_count)), encoding="utf-8")


def test_module_size_gate_reports_product_modules_over_limit(tmp_path: Path) -> None:
    _write_module(tmp_path / "training" / "large.py", 1001)
    _write_module(tmp_path / "training" / "small.py", 1000)

    assert find_oversized_modules(tmp_path) == [("training/large.py", 1001)]


def test_module_size_gate_accepts_specific_reason_in_nearest_readme(tmp_path: Path) -> None:
    package = tmp_path / "training"
    _write_module(package / "runner" / "large.py", 1001)
    (package / "runner" / "README.md").write_text(
        "## Module size exceptions\n\n"
        "| Module | Reason |\n"
        "| --- | --- |\n"
        "| `large.py` | Generated protocol adapter retained for a stable external API. |\n",
        encoding="utf-8",
    )

    assert find_oversized_modules(tmp_path, packages=("training",)) == []


def test_module_size_gate_rejects_generic_or_unscoped_readme_text(tmp_path: Path) -> None:
    package = tmp_path / "training"
    _write_module(package / "large.py", 1001)
    (package / "README.md").write_text(
        "Large files are sometimes needed.\n\n"
        "## Module size exceptions\n\n"
        "| Module | Reason |\n"
        "| --- | --- |\n"
        "| `large.py` | TODO: explain later. |\n",
        encoding="utf-8",
    )

    assert find_oversized_modules(tmp_path, packages=("training",)) == [("training/large.py", 1001)]
