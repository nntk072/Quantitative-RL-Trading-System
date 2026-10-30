#!/usr/bin/env python3
"""Apply a reviewed experiment run preflight migration through the package API."""

from experiments.runs.preflight_migration import main

if __name__ == "__main__":
    raise SystemExit(main())
