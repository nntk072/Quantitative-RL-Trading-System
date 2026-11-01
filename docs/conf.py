"""Sphinx configuration for the framework documentation website."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

project = "Quantitative RL Trading System"
copyright = "2026, Long Nguyen"
author = "Long Nguyen"
release = "0.1.0"
version = release

extensions = [
    "myst_nb",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "autoapi.extension",
    "sphinxcontrib.mermaid",
    "sphinx_design",
]

root_doc = "index"
source_suffix = {".md": "myst-nb", ".rst": "restructuredtext"}
master_doc = root_doc
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

myst_heading_anchors = 3
myst_fence_as_directive = ["mermaid"]
myst_enable_extensions = ["colon_fence"]
nb_execution_mode = "off"
nb_execution_raise_on_error = True
nb_execution_allow_errors = False
nb_execution_timeout = 120
nb_output_stderr = "warn"
napoleon_google_docstring = True
napoleon_numpy_docstring = False
autodoc_typehints = "description"
autodoc_typehints_format = "short"
autosummary_generate = True

autoapi_type = "python"
autoapi_dirs = [
    str(ROOT / package)
    for package in (
        "configuration",
        "artifacts",
        "market_data",
        "features",
        "trading",
        "decisioning",
        "simulation",
        "models",
        "learning",
        "training",
        "evaluation",
        "experiments",
        "live",
        "integrations",
        "compute",
        "orchestra",
    )
]
autoapi_root = "api/generated"
autoapi_add_toctree_entry = False
autoapi_keep_files = True
autoapi_python_class_content = "class"
autoapi_python_use_implicit_namespaces = True
autoapi_options = ["members", "show-inheritance", "show-module-summary"]

html_theme = "pydata_sphinx_theme"
html_title = project
html_baseurl = "https://nntk072.github.io/Quantitative-RL-Trading-System/"
html_theme_options = {
    "show_nav_level": 2,
    "navigation_depth": 4,
}
html_static_path = ["_static"]

# AutoAPI parses valid re-exports statically but cannot resolve some imported
# names through the repository's module split. Keep other AutoAPI warnings,
# especially unreadable source and broken toctree entries, visible to the gate.
suppress_warnings = ["autoapi.python_import_resolution"]
