from __future__ import annotations

import sys as _sys
from importlib import import_module as _import_module
from pathlib import Path as _Path
from runpy import run_module as _run_module
from typing import Any as _Any

_ROOT = _Path(__file__).resolve().parents[4]
if str(_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_ROOT))

_TARGET = "research_tools.features.features.build_feature_causality_matrix"
if __name__ == "__main__":
    _run_module(_TARGET, run_name="__main__", alter_sys=True)
else:
    _module = _import_module(_TARGET)
    __all__ = [name for name in vars(_module) if not name.startswith("_")]
    globals().update({name: getattr(_module, name) for name in __all__})

    def __getattr__(name: str) -> _Any:
        return getattr(_module, name)

    def __dir__() -> list[str]:
        return sorted(set(globals()) | set(dir(_module)))
