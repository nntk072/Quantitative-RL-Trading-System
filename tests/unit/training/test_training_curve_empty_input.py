from __future__ import annotations

from pathlib import Path

from training.reporting.training_curves import save_dashboard_plots


def test_dashboard_plot_export_skips_csv_with_no_columns(tmp_path: Path) -> None:
    log_path = tmp_path / "empty-dashboard.csv"
    log_path.write_text("\n", encoding="utf-8")
    output_dir = tmp_path / "plots"

    save_dashboard_plots(log_path, output_dir)

    assert output_dir.is_dir()
    assert list(output_dir.iterdir()) == []
