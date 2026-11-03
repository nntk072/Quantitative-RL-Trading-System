from __future__ import annotations

import hashlib
import json

import pandas as pd
from scripts.research.analysis.features.plot_entry_idea_opportunity_census import plot_census


def test_plot_census_records_source_and_outputs(tmp_path) -> None:
    rows = []
    for regime in ("low", "middle", "high", "warmup_unknown"):
        rows.append(
            {
                "idea": "standard_deviation",
                "volatility_regime": regime,
                "month": "2025-01",
                "active_m1_rows": 4,
                "support_status": "supported",
            }
        )
    pd.DataFrame(rows).to_csv(tmp_path / "candidate_month_regime.csv", index=False)

    metadata = plot_census(tmp_path)

    assert metadata["included_regimes"] == ["low", "middle", "high"]
    assert metadata["outputs"] == [
        "candidate_month_regime_heatmap.png",
        "candidate_month_regime_heatmap.pdf",
    ]
    assert (tmp_path / metadata["outputs"][0]).is_file()
    assert (tmp_path / metadata["outputs"][1]).is_file()
    assert json.loads((tmp_path / "plot_metadata.json").read_text())["input_csv_sha256"]
    checksum_rows = (tmp_path / "OUTPUT_SHA256SUMS").read_text().splitlines()
    checksum_names = {line.split("  ", maxsplit=1)[1] for line in checksum_rows}
    assert "OUTPUT_SHA256SUMS" not in checksum_names
    assert "plot_metadata.json" in checksum_names
    for filename in metadata["outputs"]:
        digest, _ = next(
            line.split("  ", maxsplit=1) for line in checksum_rows if line.endswith(f"  {filename}")
        )
        assert digest == hashlib.sha256((tmp_path / filename).read_bytes()).hexdigest()
