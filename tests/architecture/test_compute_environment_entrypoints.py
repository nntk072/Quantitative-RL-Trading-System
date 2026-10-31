from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_quality_gate_selects_the_architecture_matched_project_python() -> None:
    check = (ROOT / "tools/check").read_text(encoding="utf-8")

    assert "aarch64|arm64)" in check
    assert '"$ROOT/.venv/bin/python"' in check
    assert '"$ROOT/.venv-x86/bin/python"' in check
    assert '"$PYTHON_BIN" -m "$@"' in check
    assert '"$PYTHON_BIN" -m build --outdir "$build_dir"' in check
    assert 'uv build --python "$PYTHON_BIN"' not in check
    assert 'UV_BIN="${QRL_UV:-${THESIS_UV:-}}"' in check
    assert 'PROJECT_UV="$(dirname "$PYTHON_BIN")/uv"' in check
    assert 'UV="$UV_BIN" UV_PYTHON="$PYTHON_BIN"' in check
    assert '"$UV_BIN" run python -c "$smoke"' in check
    assert "if uv run python" not in check
    assert (
        "UV ?= $(if $(strip $(QRL_UV)),$(QRL_UV),$(if $(strip $(THESIS_UV)),$(THESIS_UV),uv))"
        in (ROOT / "Makefile").read_text(encoding="utf-8")
    )
    assert '"$UV_BIN" sync --extra dev' in check
    assert '[[ -z "$PYTHON_BIN"' in check
    result = subprocess.run(["bash", "-n", str(ROOT / "tools/check")], check=False)
    assert result.returncode == 0


def test_generic_environment_helpers_default_to_the_current_checkout() -> None:
    paths = (
        ROOT / "tools/setup-venv",
        ROOT / "tools/setup-venv-x86",
        ROOT / "tools/setup-venv-v100",
        ROOT / "tools/setup-venv-mi210",
        ROOT / "tools/uv-install",
    )
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert 'UV_BIN="${QRL_UV:-${THESIS_UV:-uv}}"' in text
        if path.name != "uv-install":
            assert 'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"' in text
            assert 'REPO="${TRITON_REPO:-$(cd "$SCRIPT_DIR/.." && pwd)}"' in text
        result = subprocess.run(["bash", "-n", str(path)], check=False)
        assert result.returncode == 0, path


def test_current_tree_gpu_gate_uses_its_checkout_unless_overridden() -> None:
    script = ROOT / "scripts/compute/slurm/run_current_tree_gpu_ci.sh"
    text = script.read_text(encoding="utf-8")

    assert 'ROOT="${TRITON_REPO:-$(cd "$SCRIPT_DIR/../../.." && pwd)}"' in text
    result = subprocess.run(["bash", "-n", str(script)], check=False)
    assert result.returncode == 0
