#!/usr/bin/env python3
"""
Safe benchmarking plot from a single CSV file.

Top subplot:
  - Safety Margin = server_threshold - anomaly_score.
  - y=0 is the detection threshold reference line.
  - Shaded area between delta and y=0 visualizes margin from threshold.

Bottom subplot:
  - Cumulative progress from cumulative_throughput.
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
    Return (x_seconds, margin, cumulative_or_none, anomaly_score) sorted by x.
    """
    xs: List[float] = []
    margins: List[float] = []
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
            margins.append(threshold - score)
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
    margin_sorted = np.asarray(margins, dtype=float)[order]

    if has_cumulative:
        c_sorted = np.asarray(cumulatives, dtype=float)[order]
        # Fill missing cumulative values forward for continuity.
        for i in range(1, len(c_sorted)):
            if np.isnan(c_sorted[i]):
                c_sorted[i] = c_sorted[i - 1]
        if np.isnan(c_sorted[0]):
            c_sorted[0] = 0.0
        score_sorted = np.asarray(scores, dtype=float)[order]
        return x_sorted, margin_sorted, c_sorted, score_sorted

    score_sorted = np.asarray(scores, dtype=float)[order]
    return x_sorted, margin_sorted, None, score_sorted


def plot_stealth_proof(
    workload_csv: str,
    output_png: str,
    y_min: Optional[float],
    y_max: Optional[float],
    invert_y: bool,
) -> None:
    x_vals, margin_vals, cumulative_vals, score_vals = _load_delta_series_single_csv(workload_csv)

    fig, (ax_top, ax_bottom) = plt.subplots(
        2, 1, figsize=(12, 9), sharex=True, gridspec_kw={"height_ratios": [2.3, 1.2]}
    )
    fig.suptitle(
        "Attack Stealth Analysis: Evasion Margin over Time",
        fontsize=15,
        fontweight="bold",
    )

    # Top: Safety margin from threshold and shaded safe zone to zero-line.
    ax_top.plot(x_vals, margin_vals, color="#1f77b4", linewidth=1.0, label="Attack Evasion Margin")
    ax_top.axhline(0.0, color="black", linewidth=2.4, label="Detection Threshold")
    ax_top.fill_between(
        x_vals,
        margin_vals,
        0.0,
        color="#b7e4c7",
        alpha=0.10,
        label="Stealth Zone (Unobserved)",
    )

    # Fixed top-axis range for consistent reporting.
    top_y_min = -0.6 if y_min is None else y_min
    top_y_max = 0.4 if y_max is None else y_max
    ax_top.set_ylim(top_y_min, top_y_max)
    ax_top.set_yticks(np.arange(top_y_min, top_y_max + 1e-9, 0.1 ))

    # No inversion: positive safety margin naturally appears above the floor.
    _ = invert_y  # keep backward-compatible CLI arg without changing orientation.

    ax_top.set_ylabel("Distance from Radar (Threshold - Score)")
    ax_top.set_title("Stealth Validation: Proximity to Detection Boundary")
    ax_top.grid(True, linestyle="--", alpha=0.45)
    ax_top.legend(loc="best")

    # Bottom: cumulative work progression.
    if cumulative_vals is None:
        # Fall back to cumulative sum of positive throughput deltas if no cumulative column exists.
        # We cannot recover exact throughput per step from delta; this fallback is intentionally simple.
        cumulative_vals = np.zeros_like(x_vals)
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

    plt.tight_layout()
    plt.subplots_adjust(top=0.92)
    plt.savefig(output_png, dpi=300)
    print(f"Saved figure to: {output_png}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plot single-workload proximity to threshold with margin shading."
    )
    parser.add_argument(
        "--workload",
        default="attack_research_data_ga.csv",
        help="Input CSV containing seconds_since_start, anomaly_score, server_threshold, cumulative_throughput.",
    )
    parser.add_argument(
        "--output",
        default="stealth_proof_graph.png",
        help="Output PNG file path.",
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
        output_png=args.output,
        y_min=args.y_min,
        y_max=args.y_max,
        invert_y=args.invert_y,
    )


if __name__ == "__main__":
    main()
