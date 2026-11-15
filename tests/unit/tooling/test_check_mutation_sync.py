from __future__ import annotations

import os
import subprocess
from pathlib import Path


def test_mutation_sync_keeps_documentation_dependencies(tmp_path: Path) -> None:
    environment = tmp_path / ".venv-x86"
    bin_dir = environment / "bin"
    bin_dir.mkdir(parents=True)
    python = bin_dir / "python"
    python.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    python.chmod(0o755)

    sync_record = tmp_path / "uv-arguments.txt"
    uv = tmp_path / "uv"
    uv.write_text(
        "#!/bin/sh\n"
        'printf "%s\\n" "$@" > "$QRL_TEST_UV_ARGUMENTS"\n'
        'mkdir -p "$UV_PROJECT_ENVIRONMENT/bin"\n'
        'printf "#!/bin/sh\\nexit 0\\n" > "$UV_PROJECT_ENVIRONMENT/bin/mutmut"\n'
        'chmod +x "$UV_PROJECT_ENVIRONMENT/bin/mutmut"\n',
        encoding="utf-8",
    )
    uv.chmod(0o755)

    environment_vars = os.environ.copy()
    environment_vars.pop("QRL_CHECK_NO_SYNC", None)
    environment_vars.update(
        {
            "QRL_PYTHON": str(python),
            "QRL_UV": str(uv),
            "QRL_MUTATION_MAX_CHILDREN": "4",
            "QRL_TEST_UV_ARGUMENTS": str(sync_record),
        }
    )
    repository_root = Path(__file__).resolve().parents[3]
    result = subprocess.run(
        ["bash", str(repository_root / "tools/check"), "mutation-critical"],
        check=False,
        capture_output=True,
        text=True,
        env=environment_vars,
    )

    assert result.returncode == 0, result.stderr
    assert sync_record.read_text(encoding="utf-8").splitlines() == [
        "sync",
        "--extra",
        "dev",
        "--extra",
        "docs",
        "--extra",
        "mutation",
    ]
