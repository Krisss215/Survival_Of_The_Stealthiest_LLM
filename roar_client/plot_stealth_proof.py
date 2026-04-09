#!/usr/bin/env python3
"""
Safe benchmarking plot from a single CSV file.

First figure:
  - Distance from threshold = server_threshold - anomaly_score.
  - y=0 is the detection threshold reference line.

Second figure:
  - Cumulative progress from cumulative_throughput (saved as its own PNG).
"""

import argparse
import csv
import os
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np


def _as_float(value: str) -> Optional[float]:
    try:
        if value is None:
            return None
        value = str(value).strip()
        if not value:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _pick_first_present(row: Dict[str, str], candidates: List[str]) -> Optional[float]:
    for key in candidates:
        if key in row:
            v = _as_float(row.get(key))
            if v is not None:
                return v
    return None


def _load_delta_series_single_csv(path: str) -> Tuple[np.ndarray, np.ndarray, Optional[np.ndarray], np.ndarray]:
    """
    Return (x_seconds, distance_from_threshold, cumulative_or_none, anomaly_score) sorted by x.
    """
    xs: List[float] = []
    distances: List[float] = []
    scores: List[float] = []
    cumulatives: List[float] = []
    has_cumulative = False

    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Exact required columns from attack_research_data_ga.csv
            t = _pick_first_present(row, ["seconds_since_start"])
            score = _pick_first_present(row, ["anomaly_score"])
            threshold = _pick_first_present(row, ["server_threshold"])
            if t is None or score is None or threshold is None:
                continue

            xs.append(t)
            distances.append(threshold - score)
            scores.append(score)

            c = _pick_first_present(row, ["cumulative_throughput"])
            if c is not None:
                has_cumulative = True
                cumulatives.append(c)
            else:
                cumulatives.append(np.nan)

    if not xs:
        raise ValueError(f"No valid rows with time/score/threshold in {path}")

    order = np.argsort(np.asarray(xs))
    x_sorted = np.asarray(xs, dtype=float)[order]
    distance_sorted = np.asarray(distances, dtype=float)[order]

    if has_cumulative:
        c_sorted = np.asarray(cumulatives, dtype=float)[order]
        # Fill missing cumulative values forward for continuity.
        for i in range(1, len(c_sorted)):
            if np.isnan(c_sorted[i]):
                c_sorted[i] = c_sorted[i - 1]
        if np.isnan(c_sorted[0]):
            c_sorted[0] = 0.0
        score_sorted = np.asarray(scores, dtype=float)[order]
        return x_sorted, distance_sorted, c_sorted, score_sorted

    score_sorted = np.asarray(scores, dtype=float)[order]
    return x_sorted, distance_sorted, None, score_sorted


def plot_stealth_proof(
    workload_csv: str,
    output_dir: str,
    y_min: Optional[float],
    y_max: Optional[float],
    invert_y: bool,
) -> None:
    x_vals, dist_vals, cumulative_vals, score_vals = _load_delta_series_single_csv(workload_csv)

    os.makedirs(output_dir, exist_ok=True)
    distance_path = os.path.join(output_dir, "distance_plot.pdf")
    cumulative_path = os.path.join(output_dir, "cumulative_plot.pdf")

    # --- Figure 1: distance from threshold ---
    fig1, ax_top = plt.subplots(figsize=(12, 5))
    fig1.suptitle(
        "Distance from Threshold Over Time",
        fontsize=15,
        fontweight="bold",
    )

    ax_top.plot(
        x_vals,
        dist_vals,
        color="#1f77b4",
        linewidth=1.0,
        label="Distance from Threshold",
    )
    ax_top.axhline(0.0, color="black", linewidth=2.4, label="Detection Threshold")

    top_y_min = -0.6 if y_min is None else y_min
    top_y_max = 0.4 if y_max is None else y_max
    ax_top.set_ylim(top_y_min, top_y_max)
    ax_top.set_yticks(np.arange(top_y_min, top_y_max + 1e-9, 0.1))

    _ = invert_y

    ax_top.set_xlabel("Time (Seconds)")
    ax_top.set_ylabel("Distance from Threshold")
    ax_top.set_title("Proximity to Detection Threshold")
    ax_top.grid(True, linestyle="--", alpha=0.45)
    ax_top.legend(loc="best")

    fig1.tight_layout()
    fig1.subplots_adjust(top=0.88)
    fig1.savefig(distance_path,format='pdf', dpi=300)
    plt.close(fig1)
    print(f"Saved figure to: {distance_path}")

    # --- Figure 2: cumulative progress ---
    if cumulative_vals is None:
        cumulative_vals = np.zeros_like(x_vals)

    fig2, ax_bottom = plt.subplots(figsize=(12, 5))
    fig2.suptitle(
        "Cumulative Progress Over Time",
        fontsize=15,
        fontweight="bold",
    )

    ax_bottom.plot(
        x_vals,
        cumulative_vals,
        color="#9467bd",
        linewidth=2.0,
        label="Cumulative Attack Progress",
    )
    ax_bottom.fill_between(x_vals, 0, cumulative_vals, color="#9467bd", alpha=0.18)
    ax_bottom.set_xlabel("Time (Seconds)")
    ax_bottom.set_ylabel("Total Damage / Work")
    ax_bottom.set_title("Cumulative Attack Impact")
    ax_bottom.grid(True, linestyle="--", alpha=0.45)
    ax_bottom.legend(loc="best")

    fig2.tight_layout()
    fig2.subplots_adjust(top=0.88)
    fig2.savefig(cumulative_path, format='pdf',dpi=300)
    plt.close(fig2)
    print(f"Saved figure to: {cumulative_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plot distance from threshold and cumulative progress as two separate PNG files."
    )
    parser.add_argument(
        "--workload",
        default="attack_research_data_ga.csv",
        help="Input CSV containing seconds_since_start, anomaly_score, server_threshold, cumulative_throughput.",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help='Directory for distance_plot.png and cumulative_plot.png (default: current directory).',
    )
    parser.add_argument("--y-min", type=float, default=None, help="Optional fixed Y min for top subplot.")
    parser.add_argument("--y-max", type=float, default=None, help="Optional fixed Y max for top subplot.")
    parser.add_argument(
        "--invert-y",
        action="store_true",
        help="Invert Y axis on the top subplot.",
    )
    args = parser.parse_args()

    if not os.path.exists(args.workload):
        raise SystemExit(f"Missing workload CSV: {args.workload}")

    plot_stealth_proof(
        workload_csv=args.workload,
        output_dir=os.path.abspath(args.output_dir),
        y_min=args.y_min,
        y_max=args.y_max,
        invert_y=args.invert_y,
    )


if __name__ == "__main__":
    main()
