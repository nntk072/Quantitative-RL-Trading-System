"""Check assembled-feature prefix invariance across resolved feature profiles.

This audit uses deterministic synthetic M1 and secondary-symbol bars. It checks
whether recomputing each resolved feature tree on a truncated input changes any
feature values that were already available at the cutoff. It does not inspect
market outcomes, establish feed-clock authority, or validate economic results.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from omegaconf import OmegaConf

from configuration.configuration_loader import load_config
from configuration.paths import repository_root
from features import build_features
from market_data.transforms.sessions import add_session_id, add_session_labels

ROOT = repository_root(__file__)
DEFAULT_INVENTORY = (
    ROOT / "evidence" / "research" / "feature_causality" / ("feature_configuration_inventory.json")
)
DEFAULT_OUTPUT = (
    ROOT
    / "evidence"
    / "research"
    / "feature_causality"
    / ("feature_profile_prefix_invariance.json")
)
SYNTHETIC_TIMEZONE = "Etc/GMT-3"


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _feature_fingerprint(features: dict[str, Any]) -> str:
    encoded = json.dumps(features, sort_keys=True, separators=(",", ":")).encode()
    return _sha256_bytes(encoded)


def _resolved_feature_groups(
    inventory_path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, str]]:
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    profiles = inventory.get("profiles")
    if not isinstance(profiles, list) or not profiles:
        raise ValueError("feature configuration inventory has no profiles")
    profile_by_id = {str(profile["profile_id"]): profile for profile in profiles}
    groups = inventory.get("distinct_feature_configs")
    if not isinstance(groups, list) or not groups:
        raise ValueError("feature configuration inventory has no distinct feature configs")

    seen: set[str] = set()
    resolved: list[dict[str, Any]] = []
    for group in groups:
        fingerprint = str(group["feature_config_sha256"])
        if fingerprint in seen:
            raise ValueError(f"duplicate feature configuration fingerprint: {fingerprint}")
        seen.add(fingerprint)
        profile_ids = [str(value) for value in group["profile_ids"]]
        if not profile_ids:
            raise ValueError(f"feature configuration {fingerprint} has no profile IDs")
        missing_ids = [profile_id for profile_id in profile_ids if profile_id not in profile_by_id]
        if missing_ids:
            raise ValueError(f"inventory group references missing profiles: {missing_ids}")

        members = [profile_by_id[profile_id] for profile_id in profile_ids]
        for profile in members:
            features = profile.get("features")
            if not isinstance(features, dict) or _feature_fingerprint(features) != fingerprint:
                raise ValueError(
                    "feature profile fingerprint does not match its recorded configuration: "
                    f"{profile['profile_id']}"
                )
        representative = members[0]
        source_hashes: dict[str, str] = {}
        for profile in members:
            for source in profile.get("source_paths", []):
                relative_path = str(source["path"])
                path = (ROOT / relative_path).resolve()
                if not path.is_file():
                    raise FileNotFoundError(f"inventory source is missing: {relative_path}")
                actual_hash = _sha256_file(path)
                if actual_hash != source["sha256"]:
                    raise ValueError(f"inventory source hash changed: {relative_path}")
                source_hashes[relative_path] = actual_hash
        resolved.append(
            {
                "fingerprint": fingerprint,
                "profile_ids": profile_ids,
                "features": representative["features"],
                "source_hashes": source_hashes,
            }
        )

    observed_fingerprints = {_feature_fingerprint(profile["features"]) for profile in profiles}
    if observed_fingerprints != seen:
        raise ValueError("inventory distinct-feature groups do not cover its profile list")
    resolver_hashes: dict[str, str] = {}
    for source in inventory.get("resolver_sources", []):
        relative_path = str(source["path"])
        path = (ROOT / relative_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"inventory resolver source is missing: {relative_path}")
        actual_hash = _sha256_file(path)
        if actual_hash != source["sha256"]:
            raise ValueError(f"inventory resolver source hash changed: {relative_path}")
        resolver_hashes[relative_path] = actual_hash
    return inventory, resolved, resolver_hashes


def _synthetic_bars(
    rows: int, seed: int, timezone: str, ny_end: str, offset: float = 0.0
) -> pd.DataFrame:
    index = pd.date_range("2025-01-06 00:00", periods=rows, freq="1min", tz=timezone)
    rng = np.random.default_rng(seed)
    close = 20_000.0 + offset + np.cumsum(rng.normal(0.0, 1.5, rows))
    volume = rng.integers(100, 5_000, rows)
    bars = pd.DataFrame(
        {
            "open": close - 0.4,
            "high": close + 1.2,
            "low": close - 1.2,
            "close": close,
            "tickvol": rng.integers(10, 200, rows),
            "volume": volume,
            "vol": np.zeros(rows, dtype=np.int64),
            "spread": np.full(rows, 0.6),
            "gap_flag": False,
        },
        index=index,
    )
    return add_session_id(add_session_labels(bars, tz=timezone, ny_end=ny_end))


def _set_synthetic_clock(cfg: Any, timezone: str) -> None:
    OmegaConf.update(cfg, "data.tz", timezone, force_add=True)
    OmegaConf.update(cfg, "session.tz", timezone, force_add=True)
    OmegaConf.update(cfg, "strategy.session.timezone", timezone, force_add=True)


def _compare_prefix(
    full: pd.DataFrame, prefix: pd.DataFrame, cutoff: pd.Timestamp
) -> dict[str, Any]:
    if not prefix.index.equals(full.index[: len(prefix)]):
        return {"passed": False, "reason": "prefix indexes differ", "cutoff": cutoff.isoformat()}
    if list(prefix.columns) != list(full.columns):
        return {
            "passed": False,
            "reason": "feature columns differ",
            "cutoff": cutoff.isoformat(),
        }

    changed: list[dict[str, Any]] = []
    compared_values = 0
    max_abs_delta = 0.0
    reference = full.iloc[: len(prefix)]
    for column in prefix.columns:
        expected = pd.to_numeric(reference[column], errors="coerce").to_numpy(dtype=np.float64)
        actual = pd.to_numeric(prefix[column], errors="coerce").to_numpy(dtype=np.float64)
        expected_nan = np.isnan(expected)
        actual_nan = np.isnan(actual)
        finite = np.isfinite(expected) & np.isfinite(actual)
        equal = np.zeros(len(expected), dtype=bool)
        equal[finite] = np.isclose(expected[finite], actual[finite], rtol=1e-10, atol=1e-12)
        nonfinite = ~finite & ~expected_nan & ~actual_nan
        equal[nonfinite] = expected[nonfinite] == actual[nonfinite]
        equal[expected_nan & actual_nan] = True
        compared_values += len(expected)
        mismatch = np.flatnonzero(~equal)
        column_delta = (
            float(np.abs(expected[finite] - actual[finite]).max(initial=0.0))
            if finite.any()
            else 0.0
        )
        max_abs_delta = max(max_abs_delta, column_delta)
        if len(mismatch):
            first = int(mismatch[0])
            changed.append(
                {
                    "feature": str(column),
                    "mismatch_rows": len(mismatch),
                    "first_timestamp": prefix.index[first].isoformat(),
                    "max_abs_delta": column_delta,
                    "nan_mask_mismatches": int((expected_nan != actual_nan).sum()),
                }
            )
    return {
        "passed": not changed,
        "cutoff": cutoff.isoformat(),
        "rows": len(prefix),
        "feature_count": len(prefix.columns),
        "compared_values": compared_values,
        "max_abs_delta": max_abs_delta,
        "changed_feature_count": len(changed),
        "changed_features": changed[:100],
    }


def run_audit(*, inventory_path: Path, rows: int, cutoff_row: int) -> dict[str, Any]:
    if rows < 10 or not 1 <= cutoff_row < rows:
        raise ValueError("require rows >= 10 and cutoff_row in [1, rows)")
    inventory, groups, resolver_hashes = _resolved_feature_groups(inventory_path)
    session_end = str(load_config().session.end)
    report_groups: list[dict[str, Any]] = []

    for group_index, group in enumerate(groups, start=1):
        session_config = group["features"].get("sessions", {})
        timezone = str(session_config.get("tz", SYNTHETIC_TIMEZONE))
        primary = _synthetic_bars(rows, seed=1, timezone=timezone, ny_end=session_end)
        secondary = _synthetic_bars(
            rows, seed=2, timezone=timezone, ny_end=session_end, offset=400.0
        )
        cutoff = pd.Timestamp(primary.index[cutoff_row])
        print(
            f"checking feature profile {group_index}/{len(groups)} "
            f"{group['profile_ids'][0]} rows={rows} cutoff={cutoff.isoformat()}",
            flush=True,
        )
        try:
            cfg = load_config()
            OmegaConf.update(cfg, "features", group["features"], merge=False)
            _set_synthetic_clock(cfg, timezone)
            full = build_features(primary, secondary=secondary, cfg=cfg, force=True)
            prefix_primary = primary.iloc[: cutoff_row + 1]
            prefix_secondary = secondary.iloc[: cutoff_row + 1]
            prefix_cfg = load_config()
            OmegaConf.update(prefix_cfg, "features", group["features"], merge=False)
            _set_synthetic_clock(prefix_cfg, timezone)
            prefix = build_features(
                prefix_primary, secondary=prefix_secondary, cfg=prefix_cfg, force=True
            )
            result = _compare_prefix(full, prefix, cutoff)
            del full, prefix, prefix_cfg, cfg
        except Exception as exc:
            result = {
                "passed": False,
                "error": {"type": type(exc).__name__, "message": str(exc)},
            }
        report_groups.append(
            {
                "feature_config_sha256": group["fingerprint"],
                "representative_profile": group["profile_ids"][0],
                "profile_count": len(group["profile_ids"]),
                "profile_ids": group["profile_ids"],
                "feature_session_timezone": timezone,
                "source_hashes": group["source_hashes"],
                "result": result,
            }
        )
        print(
            f"profile result={group_index}/{len(groups)} passed={bool(result['passed'])}",
            flush=True,
        )

    feature_sources = sorted(
        path
        for directory in (ROOT / "features", ROOT / "market_data")
        for path in directory.rglob("*.py")
        if path.is_file()
    )
    return {
        "audit": "assembled_feature_profile_prefix_invariance",
        "inventory_path": _relative(inventory_path),
        "inventory_sha256": _sha256_file(inventory_path),
        "inventory_profile_count": inventory["profile_count"],
        "distinct_feature_config_count": len(groups),
        "inventory_resolver_source_hashes": resolver_hashes,
        "synthetic_input": {
            "primary_symbol_role": "synthetic_primary",
            "secondary_symbol_role": "synthetic_secondary",
            "timezone": "declared per feature profile",
            "rows": rows,
            "cutoff_row": cutoff_row,
            "cutoff": cutoff.isoformat(),
            "seed_primary": 1,
            "seed_secondary": 2,
        },
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "packages": {
                name: importlib.metadata.version(name) for name in ("numpy", "pandas", "omegaconf")
            },
            "slurm_job_id": os.getenv("SLURM_JOB_ID"),
        },
        "source_hashes": {
            _relative(path): _sha256_file(path)
            for path in [*feature_sources, Path(__file__).resolve()]
        },
        "feature_profiles": report_groups,
        "summary": {
            "passed": sum(bool(group["result"]["passed"]) for group in report_groups),
            "failed": sum(not bool(group["result"]["passed"]) for group in report_groups),
            "profiles": len(report_groups),
        },
        "scope_note": (
            "Synthetic assembled-matrix prefix evidence across every distinct feature tree "
            "in the resolved repository inventory. This does not establish real-market "
            "availability, feed publication timing, external calendar authority, or economic value."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--rows", type=int, default=3600)
    parser.add_argument("--cutoff-row", type=int, default=2400)
    args = parser.parse_args()
    inventory_path = args.inventory if args.inventory.is_absolute() else ROOT / args.inventory
    output = args.out if args.out.is_absolute() else ROOT / args.out
    report = run_audit(
        inventory_path=inventory_path,
        rows=args.rows,
        cutoff_row=args.cutoff_row,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"report={output} summary={report['summary']}", flush=True)
    return 0 if report["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
