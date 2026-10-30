"""Focused campaign execution state store services."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
from typing import Any, cast

from artifacts.atomic import write_json_atomic


def utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()  # noqa: UP017


def atomic_json(path: pathlib.Path, value: object) -> None:
    write_json_atomic(path, value, default=None)


def record(path: pathlib.Path, value: dict[str, object]) -> None:
    with path.open("a", encoding="utf-8") as out:
        out.write(json.dumps({"timestamp": utc(), **value}, sort_keys=True) + "\n")
        out.flush()


def read_manifest(path: pathlib.Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def validate_inputs(args: argparse.Namespace) -> list[dict[str, Any]]:
    variants = [
        v.strip()
        for v in args.variant_file.read_text().splitlines()
        if v.strip() and not v.lstrip().startswith("#")
    ]
    for variant in variants:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", variant):
            raise ValueError(f"unsafe variant name: {variant}")
    if len(variants) != len(set(variants)):
        raise ValueError("duplicate variants in variant file")
    if not variants:
        raise ValueError("variant list empty")
    seeds = [int(s) for s in args.seeds.replace(",", " ").split()]
    if not seeds or len(seeds) != len(set(seeds)):
        raise ValueError("seeds empty or duplicate")
    if args.timesteps <= 0 or args.workers <= 0 or args.n_envs <= 0:
        raise ValueError("timesteps/workers/n-envs must be positive")
    jobs = [
        {"key": f"{v}__seed{s}", "variant": v, "seed": s, "status": "pending", "attempts": 0}
        for v in variants
        for s in seeds
    ]
    if len(jobs) != len({j["key"] for j in jobs}):
        raise ValueError("duplicate run keys")
    return jobs
