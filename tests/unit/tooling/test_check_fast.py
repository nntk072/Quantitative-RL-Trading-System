from __future__ import annotations

from pathlib import Path

from tools.check_fast import registration_failures, unit_tests_for

PROFILE_DIR = "config/studies/profiles"


def _write(root: Path, rel: str, text: str) -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def test_registration_names_exact_missing_entry_and_profile_file(tmp_path: Path) -> None:
    _write(tmp_path, "integrations/mt5/new_module.py", "value = 1\n")
    _write(tmp_path, f"{PROFILE_DIR}/integrations.yaml", "api_paths:\n- integrations/mt5/old.py\n")

    failures = registration_failures(tmp_path, ["integrations/mt5/new_module.py"])

    assert len(failures) == 1
    assert "integrations/mt5/new_module.py not registered" in failures[0]
    assert "'- integrations/mt5/new_module.py' under api_paths" in failures[0]
    assert f"{PROFILE_DIR}/integrations.yaml" in failures[0]


def test_registration_accepts_api_path_and_directory_scope(tmp_path: Path) -> None:
    _write(tmp_path, "integrations/mt5/new_module.py", "value = 1\n")
    _write(tmp_path, "integrations/mt5/other.py", "value = 2\n")
    _write(
        tmp_path,
        f"{PROFILE_DIR}/integrations.yaml",
        "api_paths:\n- integrations/mt5/new_module.py\n"
        "source_scopes:\n- {path: integrations/mt5, study_ids: [integrations.x]}\n",
    )

    assert registration_failures(tmp_path, ["integrations/mt5/new_module.py"]) == []
    assert registration_failures(tmp_path, ["integrations/mt5/other.py"]) == []


def test_registration_ignores_tests_tools_and_non_python_files(tmp_path: Path) -> None:
    changed = ["tests/unit/x/test_a.py", "tools/check_fast.py", "integrations/mt5/notes.md"]

    assert registration_failures(tmp_path, changed) == []


def test_registration_reports_missing_profile(tmp_path: Path) -> None:
    _write(tmp_path, "live/paper/new.py", "value = 1\n")

    failures = registration_failures(tmp_path, ["live/paper/new.py"])

    assert failures and "no profile" in failures[0]
    assert f"{PROFILE_DIR}/live.yaml" in failures[0]


def test_unit_tests_select_changed_tests_and_importers(tmp_path: Path) -> None:
    _write(tmp_path, "pkg/mod.py", "value = 1\n")
    _write(tmp_path, "tests/unit/a/test_direct.py", "import pkg.mod\n")
    _write(tmp_path, "tests/unit/a/test_from.py", "from pkg import mod\n")
    _write(tmp_path, "tests/unit/a/test_unrelated.py", "import pkg.other\n")

    selected = unit_tests_for(tmp_path, ["pkg/mod.py"])

    assert selected == ["tests/unit/a/test_direct.py", "tests/unit/a/test_from.py"]
