from __future__ import annotations

import os
import subprocess
import sys
import sysconfig
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.integration
def test_installed_wheel_loads_default_config_outside_checkout(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--outdir",
            str(dist_dir),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    wheel = next(dist_dir.glob("*.whl"))
    venv_dir = tmp_path / "venv"
    subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
    venv_python = venv_dir / "bin" / "python"
    subprocess.run(
        [
            str(venv_python),
            "-m",
            "pip",
            "install",
            "--no-index",
            "--no-deps",
            str(wheel),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    script = """
import sys
from pathlib import Path

install_site = Path(sys.argv[1]).resolve()
dependency_site = Path(sys.argv[2]).resolve()
sys.path[:] = [
    str(install_site),
    *(path for path in sys.path if path and not Path(path).resolve().is_relative_to(Path.cwd())),
    str(dependency_site),
]
import configuration
from configuration import load_config

assert Path(configuration.__file__).resolve().is_relative_to(install_site)
assert len(load_config()) > 0
"""
    env = os.environ.copy()
    install_site = subprocess.run(
        [str(venv_python), "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    result = subprocess.run(
        [str(venv_python), "-c", script, install_site, sysconfig.get_paths()["purelib"]],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    env["PYTHONPATH"] = sysconfig.get_paths()["purelib"]
    for entrypoint in (
        "qrl-data",
        "qrl-train",
        "qrl-evaluate",
        "qrl-experiment",
        "qrl-compute",
    ):
        command = subprocess.run(
            [str(venv_dir / "bin" / entrypoint), "--help"],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
        )
        assert command.returncode == 0, f"{entrypoint}: {command.stderr}"
        assert "usage:" in command.stdout.lower(), entrypoint

    train_command = subprocess.run(
        [str(venv_dir / "bin" / "qrl-train"), "train", "--installed-command-probe"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )
    assert train_command.returncode == 2
    assert "unrecognized arguments: --installed-command-probe" in train_command.stderr
    assert "pyproject.toml" not in train_command.stderr
