#!/usr/bin/env python3
"""Compatibility entry point for the canonical campaign execution module."""

from __future__ import annotations

import signal as signal
import sys

from experiments.campaigns import campaign_execution as _implementation

__all__ = [*_implementation.__all__, "signal"]
globals().update({name: getattr(_implementation, name) for name in __all__})


def main() -> int:
    """Forward the legacy module entry point, including patched test/runtime hooks."""
    previous = {name: getattr(_implementation, name) for name in __all__}
    for name in __all__:
        if name != "main":
            setattr(_implementation, name, globals()[name])
    try:
        return _implementation.main()
    finally:
        for name, value in previous.items():
            setattr(_implementation, name, value)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
