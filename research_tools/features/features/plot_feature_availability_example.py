"""Plot a synthetic comparison of HTF-open leakage and close-time availability."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from market_data.transforms.align import align_timeframes, timeframe_close_times


def build_synthetic_alignment_example() -> pd.DataFrame:
    """Return one HTF event aligned correctly and with a deliberately naive fill."""
    minute_index = pd.date_range("2025-01-01 00:00", periods=20, freq="1min", tz="UTC")
    m1 = pd.DataFrame(index=minute_index)
    htf_index = pd.date_range("2025-01-01 00:00", periods=4, freq="5min", tz="UTC")
    htf = pd.DataFrame({"event": [0.0, 0.0, 1.0, 0.0]}, index=htf_index)
    close_times = timeframe_close_times(htf, "M5")
    causal = align_timeframes(
        m1,
        {"M5": htf},
        availability_times={"M5": close_times},
    )["M5_event"]
    naive = htf["event"].reindex(minute_index, method="ffill")
    return pd.DataFrame({"causal_close_available": causal, "naive_open_available": naive})


def plot_feature_availability_example(output: Path) -> None:
    """Write a labeled synthetic HTF availability comparison figure."""
    import matplotlib.pyplot as plt

    frame = build_synthetic_alignment_example()
    event_open = 10
    event_close = 15

    fig, ax = plt.subplots(figsize=(10, 4.8), constrained_layout=True)
    ax.axvspan(event_open, event_close, color="#f3c969", alpha=0.22, label="forming M5 source bar")
    ax.step(
        range(len(frame)),
        frame["naive_open_available"],
        where="post",
        color="#c34b42",
        linewidth=2.2,
        label="incorrect: expose at M5 open",
    )
    ax.step(
        range(len(frame)),
        frame["causal_close_available"],
        where="post",
        color="#247a63",
        linewidth=2.6,
        label="causal: expose at configured M5 close",
    )
    ax.axvline(event_open, color="#c34b42", linestyle="--", alpha=0.7)
    ax.axvline(event_close, color="#247a63", linestyle="--", alpha=0.7)
    ax.annotate(
        "source bar opens\n00:10 UTC",
        (event_open, 0.45),
        xytext=(-12, -28),
        textcoords="offset points",
        ha="right",
    )
    ax.annotate(
        "first available\n00:15 UTC",
        (event_close, 1.0),
        xytext=(8, 12),
        textcoords="offset points",
    )
    ax.set(
        title="Synthetic HTF event availability at the configured M5 close",
        xlabel="UTC timestamp (synthetic M1 spine)",
        ylabel="event value",
        ylim=(-0.08, 1.3),
        yticks=[0, 1],
    )
    tick_positions = list(range(0, len(frame), 5))
    ax.set_xticks(tick_positions, [frame.index[pos].strftime("%H:%M") for pos in tick_positions])
    ax.text(
        0.98,
        0.98,
        "Synthetic fixture; no provider-clock evidence",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=8,
        color="#555555",
    )
    ax.grid(axis="y", alpha=0.25)
    ax.legend(loc="upper left", frameon=False)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=160)
    plt.close(fig)


def main() -> None:
    """Parse output path and generate the example figure."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evidence/research/feature_causality/causal_feature_availability_example.png"),
    )
    args = parser.parse_args()
    plot_feature_availability_example(args.output)
    print(args.output)


if __name__ == "__main__":
    main()
