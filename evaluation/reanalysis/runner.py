"""Compatibility import for the historical checkpoint reanalysis path."""

from __future__ import annotations

import sys

from evaluation.reanalysis import checkpoint_reanalysis as _implementation

if __name__ == "__main__":
    _implementation.main()
else:
    sys.modules[__name__] = _implementation
