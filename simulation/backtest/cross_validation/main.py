"""Compatibility entry point; retire after the legacy invocation window ends.

The standalone Backtrader implementation lives in ``backtrader_runner``.
"""

from .backtrader_runner import main

__all__ = ["main"]


if __name__ == "__main__":
    raise SystemExit(main())
