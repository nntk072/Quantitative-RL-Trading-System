import hashlib
import json
from pathlib import Path

from scripts.research.analysis.evidence.build_v3_final_research_outputs import build_outputs
from scripts.research.audits.verify_v3_final_research_outputs import verify_manifest


def test_final_output_builder_requires_contract_columns_and_hashed_sources(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    source.write_text("{}\n", encoding="utf-8")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    src = [{"path": str(source), "sha256": digest}]
    contract = {
        "required_tables": {
            "survival": {"required_columns": ["seed"]},
            "model_baseline": {"required_columns": ["policy"]},
            "cost_execution": {"required_columns": ["scope"]},
            "action_funnel": {"required_columns": ["scope"]},
            "feature_causality": {"required_columns": ["family"]},
            "robustness": {"optional_when_no_finalist": True, "required_columns": ["scenario"]},
        },
        "required_limitations": ["exposed_2026"],
    }
    spec = {
        "schema_version": "v3-final-research-input-v1",
        "source_commit": "a" * 40,
        "readiness_verdict": "BLOCKED / NEGATIVE RESULT",
        "finalist_exists": False,
        "narrative": {
            "primary_result": "negative",
            "secondary_results": "none",
            "robustness": "not applicable",
            "exposed_report_only": "not used for selection",
        },
        "tables": {
            "survival": {"columns": ["seed"], "rows": [{"seed": 42}], "source_artifacts": src},
            "model_baseline": {
                "columns": ["policy"],
                "rows": [{"policy": "no_trade"}],
                "source_artifacts": src,
            },
            "cost_execution": {
                "columns": ["scope"],
                "rows": [{"scope": "dev"}],
                "source_artifacts": src,
            },
            "action_funnel": {
                "columns": ["scope"],
                "rows": [{"scope": "dev"}],
                "source_artifacts": src,
            },
            "feature_causality": {
                "columns": ["family"],
                "rows": [{"family": "x"}],
                "source_artifacts": src,
            },
        },
        "figures": [],
        "limitations": {"exposed_2026": "Previously exposed; report-only."},
    }
    manifest = build_outputs(spec, contract, output_dir=tmp_path / "out")
    assert "CONSOLIDATED_RESEARCH_RESULTS.md" in manifest["outputs"]
    assert "THESIS_FIGURE_TABLE_INDEX.md" in manifest["outputs"]
    manifest_path = tmp_path / "out" / "FINAL_OUTPUT_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert verify_manifest(manifest_path, expected_source_commit="a" * 40)["status"] == "pass"

    source.write_text("changed\n", encoding="utf-8")
    report = verify_manifest(manifest_path, expected_source_commit="a" * 40)
    assert report["status"] == "fail"
    assert any("source artifact hash mismatch" in item for item in report["failures"])
