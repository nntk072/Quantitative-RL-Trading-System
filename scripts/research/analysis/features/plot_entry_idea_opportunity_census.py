#!/usr/bin/env python3
"""Plot monthly supported-candidate context counts from a census CSV."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from configuration.paths import repository_root

ROOT = repository_root(__file__)
DEFAULT_CENSUS = ROOT / "evidence/research/trade_setup_opportunity_census"
REGIMES = ("low", "middle", "high")


def _write_output_checksums(census_dir: Path) -> None:
    """Refresh hashes for all files in the generated census packet."""
    rows = []
    for path in sorted(census_dir.iterdir(), key=lambda item: item.name):
        if path.is_file() and path.name != "OUTPUT_SHA256SUMS":
            rows.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}")
    (census_dir / "OUTPUT_SHA256SUMS").write_text("\n".join(rows) + "\n", encoding="utf-8")


def plot_census(census_dir: Path) -> dict[str, Any]:
    """Render a monthly family/regime heatmap and record its input identity."""
    grouped_path = census_dir / "candidate_month_regime.csv"
    grouped = pd.read_csv(grouped_path)
    selected = grouped.loc[
        grouped["support_status"].eq("supported") & grouped["volatility_regime"].isin(REGIMES)
    ]
    matrix_series = selected.groupby(["idea", "volatility_regime", "month"], observed=True)[
        "active_m1_rows"
    ].sum()
    matrix_frame = matrix_series.unstack("month", fill_value=0)
    months = list(matrix_frame.columns)
    row_labels: list[str] = []
    matrix: list[np.ndarray[Any, np.dtype[np.int64]]] = []
    ideas = list(selected["idea"].drop_duplicates())
    for idea in ideas:
        for regime in REGIMES:
            key = (idea, regime)
            row_labels.append(f"{idea.replace('_', ' ')} · {regime}")
            if key in matrix_frame.index:
                row = matrix_frame.loc[key].reindex(months, fill_value=0)
                matrix.append(row.to_numpy(dtype=np.int64))
            else:
                matrix.append(np.zeros(len(months), dtype=np.int64))
    values = np.vstack(matrix) if matrix else np.zeros((0, len(months)), dtype=np.int64)
    if not values.size:
        raise ValueError("no supported candidate rows are available to plot")

    figure, axis = plt.subplots(figsize=(13.0, 6.2), constrained_layout=True)
    image = axis.imshow(values, aspect="auto", interpolation="nearest", cmap="viridis")
    axis.set_xticks(np.arange(len(months)), labels=months, rotation=45, ha="right")
    axis.set_yticks(np.arange(len(row_labels)), labels=row_labels)
    axis.set_xlabel("Training month")
    axis.set_ylabel("Supported idea and training-fitted volatility tercile")
    axis.set_title(
        "Supported setup-context rows by month and volatility regime\n"
        "2024-12-30 to 2025-12-31 · overlapping M1 contexts, not trades"
    )
    colorbar = figure.colorbar(image, ax=axis, shrink=0.82)
    colorbar.set_label("Active candidate M1 rows (overlap allowed)")
    png_path = census_dir / "candidate_month_regime_heatmap.png"
    pdf_path = census_dir / "candidate_month_regime_heatmap.pdf"
    figure.savefig(png_path, dpi=300)
    figure.savefig(pdf_path)
    plt.close(figure)

    metadata = {
        "status": "descriptive_training_context_only",
        "input_csv": (
            grouped_path.relative_to(ROOT).as_posix()
            if grouped_path.is_relative_to(ROOT)
            else grouped_path.name
        ),
        "input_csv_sha256": hashlib.sha256(grouped_path.read_bytes()).hexdigest(),
        "plot_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "included_regimes": list(REGIMES),
        "omitted_regime": "warmup_unknown; its counts remain in the CSV tables",
        "unit": "sum of active candidate M1 rows; timeframe/direction contexts can overlap",
        "outputs": [png_path.name, pdf_path.name],
    }
    (census_dir / "plot_metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _write_output_checksums(census_dir)
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--census-dir", type=Path, default=DEFAULT_CENSUS)
    args = parser.parse_args()
    print(json.dumps(plot_census(args.census_dir), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
