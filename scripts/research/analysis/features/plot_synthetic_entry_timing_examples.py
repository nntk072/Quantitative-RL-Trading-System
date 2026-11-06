#!/usr/bin/env python3
"""Render synthetic entry-timing and session-gating examples as SVG."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from configuration.paths import repository_root

ROOT = repository_root(__file__)
DEFAULT_FIXTURE = ROOT / "tests/fixtures/research/idea12/synthetic_examples.json"
DEFAULT_OUTPUT_DIR = ROOT / "outputs/research/feature_examples/entry_timing"


def _svg(body: str, title: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="560" viewBox="0 0 1000 560">
<title>{title}</title><rect width="1000" height="560" fill="#fbfcfe"/>
<style>text{{font:14px sans-serif;fill:#152536}} .small{{font-size:12px}} .axis{{stroke:#8091a0;stroke-width:1}} .bull{{stroke:#18794e;fill:#18794e}} .bear{{stroke:#b42318;fill:#b42318}} .ref{{stroke:#7a5af8;stroke-dasharray:6 5}} .zone{{fill:#fdb022;fill-opacity:.19;stroke:#dc6803}} .gate{{stroke:#175cd3;stroke-dasharray:7 5}}</style>
<text x="44" y="34" font-size="20" font-weight="bold">{title}</text>
<text x="44" y="54" class="small">SYNTHETIC EXPLANATORY EXAMPLE — not historical data or a strategy result</text>
{body}</svg>"""


def render_fixture_a(data: dict[str, object]) -> str:
    fixture = data["fixture_a_confirmed_long"]
    assert isinstance(fixture, dict)
    bars = fixture["bars"]
    assert isinstance(bars, list)
    x_positions = [210, 390, 570, 750]
    low_y, high_y = 440, 110
    pmin, pmax = 90.0, 155.0

    def y(price: float) -> float:
        return high_y + (pmax - price) / (pmax - pmin) * (low_y - high_y)

    marks: list[str] = []
    for i, bar in enumerate(bars):
        assert isinstance(bar, dict)
        x = x_positions[i]
        marks.append(
            f'<line class="axis" x1="{x}" y1="{y(bar["high"]):.1f}" x2="{x}" y2="{y(bar["low"]):.1f}"/>'
        )
        color = "bull" if bar["close"] >= bar["open"] else "bear"
        top = y(max(bar["open"], bar["close"]))
        height = max(4, abs(y(float(bar["open"])) - y(float(bar["close"]))))
        marks.append(
            f'<rect class="{color}" x="{x - 22}" y="{top:.1f}" width="44" height="{height:.1f}" opacity=".78"/>'
        )
        marks.append(f'<text x="{x - 5}" y="462">{bar["bar"]}</text>')
        marks.append(f'<text x="{x - 58}" y="480" class="small">{bar["timestamp"]}</text>')
    stop, target = float(fixture["stop"]), float(fixture["target"])
    zone_top, zone_bottom = y(116), y(112)
    marks.extend(
        [
            f'<rect class="zone" x="120" y="{zone_top:.1f}" width="720" height="{zone_bottom - zone_top:.1f}"/>',
            f'<line class="ref" x1="100" y1="{y(100):.1f}" x2="850" y2="{y(100):.1f}"/>',
            f'<line x1="110" y1="{y(stop):.1f}" x2="850" y2="{y(stop):.1f}" stroke="#b42318"/>',
            f'<line x1="110" y1="{y(target):.1f}" x2="850" y2="{y(target):.1f}" stroke="#18794e"/>',
            f'<text x="860" y="{y(100) + 4:.1f}">confirmed M5 low 100</text>',
            f'<text x="860" y="{y(114) + 4:.1f}">bearish FVG [112,116]</text>',
            f'<text x="860" y="{y(stop) + 4:.1f}">SL 97</text>',
            f'<text x="860" y="{y(target) + 4:.1f}">TP 150</text>',
            '<text x="520" y="90" fill="#175cd3">IFVG confirmation close</text>',
            '<line class="gate" x1="600" y1="96" x2="600" y2="485"/>',
            '<text x="710" y="500">next bar open: earliest fill 118</text>',
            f'<text x="75" y="520" class="small">Causal order: pivot {fixture["pivot_confirmed_at"]} → reclaim {fixture["sweep_reclaim_confirmed_at"]} → IFVG close {fixture["ifvg_confirmed_at"]} → fill {fixture["earliest_fill_at"]}</text>',
        ]
    )
    return _svg("\n".join(marks), "Confirmed PO3–IFVG entry timing")


def render_incorrect_same_bar_entry(data: dict[str, object]) -> str:
    fixture = data["fixture_a_confirmed_long"]
    assert isinstance(fixture, dict)
    bars = fixture["bars"]
    assert isinstance(bars, list)
    confirmation_open = bars[2]
    assert isinstance(confirmation_open, dict)
    body = [
        '<line class="axis" x1="140" y1="300" x2="870" y2="300"/>',
        '<line class="gate" x1="460" y1="115" x2="460" y2="365"/>',
        '<line x1="650" y1="115" x2="650" y2="365" stroke="#18794e" stroke-dasharray="6 5"/>',
        '<circle cx="350" cy="300" r="11" fill="#b42318"/>',
        '<text x="210" y="250" fill="#b42318" font-weight="bold">INVALID FILL</text>',
        f'<text x="210" y="278">bar 21 open {confirmation_open["timestamp"]}</text>',
        '<text x="400" y="95" fill="#175cd3">bar 21 close: IFVG becomes confirmed</text>',
        '<text x="590" y="250" fill="#18794e" font-weight="bold">VALID EARLIEST FILL</text>',
        f'<text x="590" y="278">bar 22 open {fixture["earliest_fill_at"]}</text>',
        '<text x="145" y="410" fill="#b42318">A fill at the confirmation bar open uses information not yet available.</text>',
        '<text x="145" y="438">Submission can occur only after the confirmation close; next-bar open is earliest.</text>',
        '<text x="145" y="490" class="small">Synthetic explanatory timing; timestamps are illustrative UTC labels, not market observations.</text>',
    ]
    return _svg("\n".join(body), "Incorrect same-bar IFVG entry timing")


def render_fixture_b(data: dict[str, object]) -> str:
    fixture = data["fixture_b_idea2_gate"]
    assert isinstance(fixture, dict)
    session = fixture["previous_completed_session"]
    assert isinstance(session, dict)
    hi, lo, mid = (float(session[k]) for k in ("high", "low", "midpoint"))
    close = float(fixture["decision_close"])
    x0, x1 = 220, 790
    y_top, y_bottom = 120, 420

    def y(price: float) -> float:
        return y_bottom - (price - lo) / (hi - lo) * (y_bottom - y_top)

    body = [
        f'<rect x="{x0}" y="{y(hi):.1f}" width="{x1 - x0}" height="{y(lo) - y(hi):.1f}" fill="#d1e9ff" stroke="#175cd3"/>',
        f'<line class="gate" x1="{x0}" y1="{y(mid):.1f}" x2="{x1}" y2="{y(mid):.1f}"/>',
        f'<line x1="{x0}" y1="{y(close):.1f}" x2="{x1}" y2="{y(close):.1f}" stroke="#b42318" stroke-width="3"/>',
        f'<text x="810" y="{y(hi) + 4:.1f}">previous completed {session["label"]} high 120</text>',
        f'<text x="810" y="{y(mid) + 4:.1f}">midpoint 108</text>',
        f'<text x="810" y="{y(close) + 4:.1f}">decision close 112</text>',
        f'<text x="810" y="{y(lo) + 4:.1f}">low 96</text>',
        '<text x="230" y="470" fill="#b42318">New long blocked: close is at premium</text>',
        '<text x="230" y="495">An already open long continues under its existing exit rules.</text>',
        '<text x="65" y="535" class="small">Synthetic configured session labels only; this example makes no external schedule claim.</text>',
    ]
    return _svg("\n".join(body), "Previous completed-session premium gate")


def render_retest(data: dict[str, object]) -> str:
    fixture = data["fixture_a_confirmed_long"]
    assert isinstance(fixture, dict)
    retest = fixture["optional_retest_example"]
    assert isinstance(retest, dict)
    body = [
        '<rect x="110" y="160" width="780" height="105" rx="8" fill="#eef4ff" stroke="#175cd3"/>',
        '<rect x="110" y="315" width="780" height="105" rx="8" fill="#ecfdf3" stroke="#18794e"/>',
        '<text x="140" y="195" font-weight="bold">Main: confirmed first eligible</text>',
        '<text x="140" y="230">IFVG confirmed at bar 21 close → submit → earliest fill at bar 22 open.</text>',
        '<text x="140" y="350" font-weight="bold">Optional: confirmed retest</text>',
        f'<text x="140" y="385">Later touch at {retest["touch_price"]} inside [112,116] on bar {retest["touch_bar"]} → submit after close → fill bar {retest["earliest_fill_bar"]}.</text>',
        '<text x="110" y="470" class="small">The interior touch is one synthetic example. The retest mode accepts any touch in the zone within its expiry.</text>',
        '<text x="110" y="495" class="small">The early exploratory variant is unconfirmed and is not depicted or labeled as an IFVG confirmation.</text>',
    ]
    return _svg("\n".join(body), "Optional confirmed retest variant — separate from main entry")


def render_swing_confirmation(data: dict[str, object]) -> str:
    fixture = data["swing_confirmation"]
    assert isinstance(fixture, dict)
    bars = fixture["bars"]
    assert isinstance(bars, list)
    x_positions = [190, 345, 500, 655, 810]
    marks = [
        '<line class="axis" x1="110" y1="390" x2="890" y2="390"/>',
        '<line class="ref" x1="135" y1="130" x2="880" y2="130"/>',
        '<text x="140" y="114">candidate pivot high 105</text>',
    ]
    for x, bar in zip(x_positions, bars, strict=True):
        assert isinstance(bar, dict)
        high = float(bar["high"])
        y = 340 - (high - 98.0) * 30.0
        marks.extend(
            [
                f'<line class="axis" x1="{x}" y1="{y:.1f}" x2="{x}" y2="390"/>',
                f'<circle cx="{x}" cy="{y:.1f}" r="5" fill="#175cd3"/>',
                f'<text x="{x - 52}" y="420" class="small">{bar["time"]}</text>',
            ]
        )
    marks.extend(
        [
            '<line x1="500" y1="112" x2="500" y2="395" stroke="#b42318" stroke-dasharray="6 5"/>',
            '<text x="365" y="92" fill="#b42318" font-weight="bold">INVALID: pivot candle is not yet confirmed</text>',
            '<line class="gate" x1="810" y1="112" x2="810" y2="395"/>',
            '<text x="610" y="92" fill="#175cd3" font-weight="bold">VALID: two right bars complete</text>',
            f'<text x="130" y="475">Pivot bar {fixture["pivot_time"]}; confirmed at its right-window close {fixture["confirmed_at"]}.</text>',
            f'<text x="130" y="505" class="small">A decision at {fixture["incorrect_visible_at"]} is premature; earliest next-bar time is {fixture["earliest_decision_at"]}.</text>',
        ]
    )
    return _svg("\n".join(marks), "Swing pivot becomes visible after right-bar confirmation")


def render_order_block_retest(data: dict[str, object]) -> str:
    fixture = data["order_block_retest"]
    assert isinstance(fixture, dict)
    bars = fixture["bars"]
    assert isinstance(bars, list)
    xs = [240, 440, 640, 840]
    marks = [
        '<rect class="zone" x="165" y="230" width="730" height="115"/>',
        '<text x="175" y="218">active order-block zone [100,102]</text>',
        '<line class="axis" x1="145" y1="390" x2="910" y2="390"/>',
    ]
    for x, bar in zip(xs, bars, strict=True):
        assert isinstance(bar, dict)
        marks.extend(
            [
                f'<line class="axis" x1="{x}" y1="145" x2="{x}" y2="395"/>',
                f'<text x="{x - 70}" y="420" class="small">{bar["time"]}</text>',
            ]
        )
    marks.extend(
        [
            '<line x1="440" y1="120" x2="440" y2="395" stroke="#b42318" stroke-dasharray="6 5"/>',
            '<text x="275" y="92" fill="#b42318" font-weight="bold">Overlap alone: not confirmed</text>',
            '<line class="gate" x1="640" y1="120" x2="640" y2="395"/>',
            '<text x="535" y="92" fill="#175cd3" font-weight="bold">Later close confirms retest</text>',
            f'<text x="155" y="475">Zone available {fixture["zone_created_at"]} → overlap bar {fixture["first_overlap_bar_time"]} → close confirmation {fixture["confirmed_at"]}.</text>',
            f'<text x="155" y="505" class="small">Earliest next-bar action: {fixture["earliest_next_bar_at"]}; no fill at overlap-bar time {fixture["incorrect_same_overlap_fill_at"]}.</text>',
        ]
    )
    return _svg("\n".join(marks), "Order-block retest requires later close confirmation")


def render_smt_missing_secondary_bar(data: dict[str, object]) -> str:
    fixture = data["smt_missing_secondary_bar"]
    assert isinstance(fixture, dict)
    body = [
        '<line class="axis" x1="170" y1="280" x2="840" y2="280"/>',
        '<circle cx="290" cy="280" r="10" fill="#18794e"/>',
        '<circle cx="720" cy="280" r="10" fill="#18794e"/>',
        '<line x1="505" y1="115" x2="505" y2="365" stroke="#b42318" stroke-dasharray="6 5"/>',
        '<circle cx="505" cy="280" r="10" fill="#b42318"/>',
        '<text x="210" y="225">last completed secondary close = 200</text>',
        '<text x="390" y="330" fill="#b42318">no secondary bar at primary decision time</text>',
        '<text x="650" y="225">later secondary close = 204</text>',
        '<line class="gate" x1="505" y1="115" x2="505" y2="155"/>',
        '<text x="400" y="95" fill="#175cd3" font-weight="bold">forward-fill 200</text>',
        '<text x="610" y="400" fill="#b42318">Backward-fill 204 here would use a future bar.</text>',
        f'<text x="160" y="455">Previous source {fixture["secondary_previous_time"]} → decision {fixture["primary_time"]} → next source {fixture["secondary_next_time"]}.</text>',
        f'<text x="160" y="490" class="small">At the decision, use {fixture["secondary_previous_close"]}; do not expose {fixture["incorrect_future_value"]} until the next source bar closes.</text>',
    ]
    return _svg("\n".join(body), "SMT secondary bars use the last available observation")


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    if not args.fixture.is_file():
        parser.error(f"synthetic fixture does not exist: {args.fixture}")

    data = json.loads(args.fixture.read_text(encoding="utf-8"))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs = (
        args.output_dir / "confirmed_po3_ifvg_entry_timing.svg",
        args.output_dir / "incorrect_same_bar_ifvg_entry.svg",
        args.output_dir / "previous_session_premium_gate.svg",
        args.output_dir / "confirmed_ifvg_retest_timing.svg",
        args.output_dir / "swing_confirmation_timing.svg",
        args.output_dir / "order_block_retest_timing.svg",
        args.output_dir / "smt_secondary_bar_availability.svg",
    )
    outputs[0].write_text(render_fixture_a(data), encoding="utf-8")
    outputs[1].write_text(render_incorrect_same_bar_entry(data), encoding="utf-8")
    outputs[2].write_text(render_fixture_b(data), encoding="utf-8")
    outputs[3].write_text(render_retest(data), encoding="utf-8")
    outputs[4].write_text(render_swing_confirmation(data), encoding="utf-8")
    outputs[5].write_text(render_order_block_retest(data), encoding="utf-8")
    outputs[6].write_text(render_smt_missing_secondary_bar(data), encoding="utf-8")
    for path in outputs:
        print(path)


if __name__ == "__main__":
    main()
