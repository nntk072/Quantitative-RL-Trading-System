from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree

from scripts.research.analysis.features.plot_synthetic_entry_timing_examples import main

from configuration.paths import repository_root


def test_synthetic_entry_timing_generator_writes_concept_named_svg_files(
    tmp_path: Path,
) -> None:
    fixture = repository_root(__file__) / "tests/fixtures/research/idea12/synthetic_examples.json"
    main(["--fixture", str(fixture), "--output-dir", str(tmp_path)])

    expected_names = {
        "confirmed_po3_ifvg_entry_timing.svg",
        "incorrect_same_bar_ifvg_entry.svg",
        "previous_session_premium_gate.svg",
        "confirmed_ifvg_retest_timing.svg",
    }
    assert {path.name for path in tmp_path.iterdir()} == expected_names

    contents: dict[str, str] = {}
    for name in expected_names:
        root = ElementTree.parse(tmp_path / name).getroot()
        assert root.tag == "{http://www.w3.org/2000/svg}svg"
        contents[name] = " ".join(root.itertext())

    assert "SYNTHETIC EXPLANATORY EXAMPLE" in contents["confirmed_po3_ifvg_entry_timing.svg"]
    assert "next bar open: earliest fill 118" in contents["confirmed_po3_ifvg_entry_timing.svg"]
    assert "2025-01-06T14:51:59.999Z" in contents["confirmed_po3_ifvg_entry_timing.svg"]
    assert "2025-01-06T14:52:00Z" in contents["confirmed_po3_ifvg_entry_timing.svg"]
    assert "INVALID FILL" in contents["incorrect_same_bar_ifvg_entry.svg"]
    assert "2025-01-06T14:51:00Z" in contents["incorrect_same_bar_ifvg_entry.svg"]
    assert "2025-01-06T14:52:00Z" in contents["incorrect_same_bar_ifvg_entry.svg"]
    assert (
        "Previous completed-session premium gate" in contents["previous_session_premium_gate.svg"]
    )
    assert "no external schedule claim" in contents["previous_session_premium_gate.svg"]
    assert "Figure 17" not in contents["confirmed_po3_ifvg_entry_timing.svg"]
