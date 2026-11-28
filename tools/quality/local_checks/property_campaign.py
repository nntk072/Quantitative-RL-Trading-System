"""Reproducible bounded Hypothesis and Atheris campaigns on actual product contracts."""

from __future__ import annotations

import argparse
import importlib
import os
import sys
from pathlib import Path

from tools.quality.local_checks.product_oracles import ORACLE_MODULES, PRODUCT_ORACLES, exercise_product_oracles

PROPERTY_EXAMPLES = {"dev": 12, "pr": 80, "nightly": 500}


def run_product_properties(target: str, profile: str, seed_value: int, corpus: Path) -> None:
    """Use persistent failure examples with explicit seed and profile."""
    from hypothesis import given, seed, settings, strategies as st
    from hypothesis.database import DirectoryBasedExampleDatabase

    for name in PRODUCT_ORACLES if target == "all" else [target]:
        def check_target(selected: str) -> None:
            """Bind the target to this Hypothesis invocation."""
            @seed(seed_value)
            @settings(max_examples=PROPERTY_EXAMPLES[profile], deadline=None,
                      database=DirectoryBasedExampleDatabase(corpus / selected))
            @given(st.binary(min_size=0, max_size=128))
            def property_check(data: bytes) -> None:
                """Assert the selected independent product contract."""
                exercise_product_oracles(data, selected)
            property_check()
        check_target(name)


def run_product_fuzzer(target: str, seconds: int, corpus: Path, seed_value: int) -> None:
    """Instrument selected product imports and run libFuzzer with a bounded budget."""
    if seconds < 1:
        raise ValueError("Fuzz budget must be positive")
    atheris = importlib.import_module("atheris")
    names = list(PRODUCT_ORACLES) if target == "all" else [target]
    modules = [module for name in names for module in ORACLE_MODULES[name]]
    with atheris.instrument_imports(include=modules):
        for module in modules:
            importlib.import_module(module)
    for name in names:
        atheris.instrument_func(PRODUCT_ORACLES[name])
    corpus.mkdir(parents=True, exist_ok=True)
    @atheris.instrument_func
    def fuzz_input(data: bytes) -> None:
        """Route bounded byte inputs to the registered independent oracle."""
        exercise_product_oracles(data, target)
    atheris.Setup([sys.argv[0], str(corpus), f"-max_total_time={seconds}",
                   f"-seed={seed_value}", "-max_len=128", "-artifact_prefix="+str(corpus)+os.sep], fuzz_input)
    atheris.Fuzz()


def main() -> int:
    """Dispatch the explicitly requested product property or fuzz campaign."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("engine", choices=["hypothesis", "atheris"])
    parser.add_argument("--target", choices=["all", *PRODUCT_ORACLES], default="all")
    parser.add_argument("--profile", choices=list(PROPERTY_EXAMPLES), default="dev")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--seconds", type=int, default=10)
    parser.add_argument("--corpus", type=Path, required=True)
    args = parser.parse_args()
    if args.engine == "hypothesis":
        run_product_properties(args.target, args.profile, args.seed, args.corpus)
    else:
        run_product_fuzzer(args.target, args.seconds, args.corpus, args.seed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
