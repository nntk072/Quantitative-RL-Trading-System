"""Record the native build inputs and outputs (NATIVE-TOOLCHAIN).

Builds the release CPython wheel for native/python with maturin into <repo>/target/wheels,
then writes planning/native_modernization/native_toolchain/build_manifest.json with:
rustc/cargo versions, the host target triple, the build profile and flags, maturin and
Python versions, sha256 of Cargo.lock and of the source inputs, and sha256 of the wheel.

Usage (from the repository root):
    .venv/bin/python planning/native_modernization/native_toolchain/build_manifest.py \
        --python .venv/bin/python [--skip-build]

Standard library only. Fails closed: a failing recorded tool aborts with an error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
MANIFEST_PATH = Path(__file__).resolve().parent / "build_manifest.json"
PY_CRATE_DIR = REPO / "native" / "python"
WHEEL_DIR = REPO / "target" / "wheels"
SOURCE_INPUTS = ["Cargo.toml", "Cargo.lock", "rust-toolchain.toml"]
SOURCE_DIRS = ["native/domain", "native/python"]
SOURCE_SUFFIXES = {".rs", ".toml"}
# Pins zip entry timestamps so identical inputs give a byte-identical wheel (2026-01-01T00:00:00Z).
SOURCE_DATE_EPOCH = "1767225600"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_tree_sha256() -> str:
    """Hash of the build inputs (manifests and Rust/TOML sources), independent of commit id."""
    digest = hashlib.sha256()
    files = [REPO / name for name in SOURCE_INPUTS]
    for directory in SOURCE_DIRS:
        files.extend(
            sorted(
                path
                for path in (REPO / directory).rglob("*")
                if path.is_file() and path.suffix in SOURCE_SUFFIXES
            )
        )
    for path in files:
        digest.update(path.relative_to(REPO).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def run(command: list[str], extra_env: dict[str, str] | None = None) -> str:
    env = {**os.environ, **extra_env} if extra_env else None
    result = subprocess.run(command, cwd=REPO, capture_output=True, text=True, check=False, env=env)
    if result.returncode != 0:
        raise SystemExit(
            f"command failed ({result.returncode}): {' '.join(command)}\n{result.stderr}"
        )
    return result.stdout.strip()


def resolve_maturin(python: str) -> str:
    """Prefer the maturin installed beside the interpreter, then PATH; fail if neither exists."""
    found = shutil.which("maturin", path=str(Path(os.path.abspath(python)).parent))
    if found is None:
        found = shutil.which("maturin")
    if found is None:
        raise SystemExit("maturin not found beside the interpreter or on PATH")
    return found


def host_triple() -> str:
    for line in run(["rustc", "-vV"]).splitlines():
        if line.startswith("host:"):
            return line.split(":", 1)[1].strip()
    raise SystemExit("rustc -vV did not report a host triple")


def build_wheel(python: str) -> Path:
    WHEEL_DIR.mkdir(parents=True, exist_ok=True)
    for stale in WHEEL_DIR.glob("qrl_native-*.whl"):
        stale.unlink()  # regenerated output under the ignored target/ tree
    run(
        [
            resolve_maturin(python),
            "build",
            "--release",
            "-i",
            python,
            "--out",
            str(WHEEL_DIR),
            "-m",
            str(PY_CRATE_DIR / "Cargo.toml"),
        ],
        extra_env={"SOURCE_DATE_EPOCH": SOURCE_DATE_EPOCH},
    )
    created = sorted(WHEEL_DIR.glob("qrl_native-*.whl"))
    if len(created) != 1:
        raise SystemExit(f"expected exactly one qrl_native wheel after build, found {len(created)}")
    return created[0]


def newest_wheel() -> Path:
    wheels = sorted(WHEEL_DIR.glob("qrl_native-*.whl"), key=lambda p: p.stat().st_mtime)
    if not wheels:
        raise SystemExit(f"no qrl_native wheel in {WHEEL_DIR}")
    return wheels[-1]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--python", default=sys.executable, help="CPython interpreter for the wheel tag"
    )
    parser.add_argument("--skip-build", action="store_true", help="hash the newest existing wheel")
    args = parser.parse_args()

    python_version = run([args.python, "-c", "import sys;print(sys.version.split()[0])"])
    python_tag = run(
        [args.python, "-c", "import sys;print(f'cp{sys.version_info[0]}{sys.version_info[1]}')"]
    )
    wheel = newest_wheel() if args.skip_build else build_wheel(args.python)
    if f"-{python_tag}-" not in wheel.name:
        raise SystemExit(f"wheel {wheel.name} does not match interpreter tag {python_tag}")

    manifest = {
        "schema": "qrl.native.build_manifest.v1",
        "work_package": "NATIVE-TOOLCHAIN",
        "repository_head": run(["git", "rev-parse", "HEAD"]),
        "repository_dirty_at_build": bool(run(["git", "status", "--porcelain"])),
        "toolchain": {
            "rustc": run(["rustc", "--version"]),
            "cargo": run(["cargo", "--version"]),
            "rust_toolchain_file": (REPO / "rust-toolchain.toml")
            .read_text(encoding="utf-8")
            .strip(),
        },
        "target_triple": host_triple(),
        "build": {
            "profile": "release",
            "source_date_epoch": SOURCE_DATE_EPOCH,
            "maturin_command": "maturin build --release -i <python> --out target/wheels -m native/python/Cargo.toml",
            "rustflags_env": {
                name: os.environ.get(name, "") for name in ("RUSTFLAGS", "CARGO_ENCODED_RUSTFLAGS")
            },
            "workspace_lints": {"rust.unsafe_code": "forbid", "clippy.all": "deny"},
            "platform": platform.platform(),
        },
        "tools": {
            "maturin_path": resolve_maturin(args.python),
            "maturin": run([resolve_maturin(args.python), "--version"]),
            "python": python_version,
            "python_tag": python_tag,
        },
        "inputs": {
            "cargo_lock_sha256": sha256_file(REPO / "Cargo.lock"),
            "source_tree_sha256": source_tree_sha256(),
        },
        "wheel": {
            "path": wheel.relative_to(REPO).as_posix(),
            "name": wheel.name,
            "bytes": wheel.stat().st_size,
            "sha256": sha256_file(wheel),
        },
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
