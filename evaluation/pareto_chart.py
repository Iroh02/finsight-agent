"""Pareto cost/latency vs accuracy chart for the 3 operating modes.

Plots each mode (naive, agentic, multi_agent) as a point on:
    x-axis: median per-query latency (seconds)
    y-axis: mean LLM-judge correctness (1-10)

The accompanying error bars show the latency interquartile range and the
bootstrap-95% CI on correctness. Output: evaluation/pareto_chart.png.

This visually defends the 3-mode architecture: each mode sits on a different
point of the cost/quality frontier, and the analyst can pick the mode that
matches the question's budget.

Run:
    python evaluation/pareto_chart.py
"""

from __future__ import annotations

import csv
import random
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib
matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt
import numpy as np

EVAL_DIR = Path(__file__).resolve().parent
JUDGE_CSV = EVAL_DIR / "llm_judge_scores.csv"
OUT_PNG = EVAL_DIR / "pareto_chart.png"

MODES = ["naive", "agentic", "multi_agent"]
MODE_LABELS = {"naive": "Naive RAG", "agentic": "Agentic (4-state)", "multi_agent": "Multi-Agent (6 agents)"}
MODE_COLORS = {"naive": "#94a3b8", "agentic": "#2563eb", "multi_agent": "#10b981"}

# Rough cost ($/query) estimated from token-counts × gpt-4o-mini pricing.
# Used for the secondary x-axis. Update if you swap models.
COST_PER_QUERY_USD = {"naive": 0.003, "agentic": 0.012, "multi_agent": 0.045}


# --------------------------------------------------------------------------- #
# Loaders
# --------------------------------------------------------------------------- #

def load_results_csv(mode: str) -> List[Dict]:
    """Load one of the results_{mode}.csv files."""
    path = EVAL_DIR / f"results_{mode}.csv"
    rows: List[Dict] = []
    if not path.exists():
        return rows
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append(row)
    return rows


def load_judge_scores() -> Dict[str, Dict[str, float]]:
    """Return {mode: {qid: correctness}}."""
    out: Dict[str, Dict[str, float]] = {m: {} for m in MODES}
    with open(JUDGE_CSV, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            try:
                out[r["mode"]][r["question_id"]] = float(r["correctness"])
            except (ValueError, KeyError):
                continue
    return out


def latencies_by_mode() -> Dict[str, List[float]]:
    """Return {mode: [latency_seconds, ...]} from the per-mode results CSVs."""
    out: Dict[str, List[float]] = {}
    for mode in MODES:
        rows = load_results_csv(mode)
        vals: List[float] = []
        for r in rows:
            t = r.get("execution_time_s") or r.get("execution_time_ms")
            if not t:
                continue
            try:
                seconds = float(t)
                # Heuristic — if value > 200 the field was probably milliseconds
                if seconds > 200:
                    seconds /= 1000.0
                vals.append(seconds)
            except ValueError:
                continue
        out[mode] = vals
    return out


# --------------------------------------------------------------------------- #
# Stats helpers
# --------------------------------------------------------------------------- #

def bootstrap_ci(vals: List[float], n: int = 1000, ci: float = 0.95,
                 seed: int = 42) -> Tuple[float, float, float]:
    if not vals:
        return float("nan"), float("nan"), float("nan")
    rng = random.Random(seed)
    k = len(vals)
    means = []
    for _ in range(n):
        sample = [vals[rng.randrange(k)] for _ in range(k)]
        means.append(sum(sample) / k)
    means.sort()
    lo = means[int((1 - ci) / 2 * n)]
    hi = means[int((1 + ci) / 2 * n) - 1]
    return sum(vals) / k, lo, hi


# --------------------------------------------------------------------------- #
# Plot
# --------------------------------------------------------------------------- #

def main() -> None:
    judge = load_judge_scores()
    latencies = latencies_by_mode()

    fig, ax = plt.subplots(figsize=(9.5, 6.5))

    points: List[Dict] = []
    for mode in MODES:
        lats = latencies.get(mode, [])
        corr_vals = list(judge.get(mode, {}).values())
        if not lats or not corr_vals:
            continue

        # Median latency + IQR (latencies have heavier tails than means)
        lats_sorted = sorted(lats)
        median_lat = float(np.median(lats_sorted))
        q1 = float(np.percentile(lats_sorted, 25))
        q3 = float(np.percentile(lats_sorted, 75))

        mean_corr, lo, hi = bootstrap_ci(corr_vals)
        points.append({
            "mode": mode, "median_lat": median_lat, "q1": q1, "q3": q3,
            "mean_corr": mean_corr, "lo": lo, "hi": hi,
            "n_lat": len(lats), "n_corr": len(corr_vals),
        })

    # Scatter
    for p in points:
        ax.errorbar(
            p["median_lat"], p["mean_corr"],
            xerr=[[p["median_lat"] - p["q1"]], [p["q3"] - p["median_lat"]]],
            yerr=[[p["mean_corr"] - p["lo"]], [p["hi"] - p["mean_corr"]]],
            fmt="o", markersize=18,
            color=MODE_COLORS[p["mode"]],
            ecolor=MODE_COLORS[p["mode"]], alpha=0.85,
            elinewidth=1.5, capsize=6, capthick=1.5,
            label=f"{MODE_LABELS[p['mode']]}  (n={p['n_corr']})",
        )
        ax.annotate(
            f"{MODE_LABELS[p['mode']]}\ncost ≈ ${COST_PER_QUERY_USD[p['mode']]:.3f}/q",
            xy=(p["median_lat"], p["mean_corr"]),
            xytext=(15, 12), textcoords="offset points",
            fontsize=10, fontweight="bold",
            color=MODE_COLORS[p["mode"]],
        )

    # Frontier line (visual aid — connect the modes in latency order)
    points_sorted = sorted(points, key=lambda d: d["median_lat"])
    ax.plot(
        [p["median_lat"] for p in points_sorted],
        [p["mean_corr"] for p in points_sorted],
        linestyle="--", color="#9ca3af", alpha=0.5, linewidth=1.2, zorder=1,
    )

    ax.set_xlabel("Median latency per query (seconds, log scale)", fontsize=12)
    ax.set_ylabel("Mean LLM-Judge correctness (1–10)", fontsize=12)
    ax.set_title(
        "FinSight Cost/Quality Frontier\n"
        "Each mode trades latency + LLM cost for answer quality",
        fontsize=13, fontweight="bold",
    )
    ax.set_xscale("log")
    ax.grid(alpha=0.3, which="both")
    ax.set_axisbelow(True)
    ax.legend(loc="lower right", framealpha=0.95, fontsize=10)

    # Footer
    fig.text(
        0.5, 0.01,
        "Error bars: x = latency IQR (Q1–Q3); y = 95% bootstrap CI on correctness. "
        "Cost = est. gpt-4o-mini USD per query.",
        ha="center", fontsize=9, style="italic", color="#6b7280",
    )

    fig.tight_layout(rect=[0, 0.03, 1, 1])
    fig.savefig(OUT_PNG, dpi=150, bbox_inches="tight")
    print(f"Wrote: {OUT_PNG}")

    # Console summary
    print()
    print("Frontier summary:")
    print(f"{'Mode':<14} {'Median Lat':>12} {'Mean Corr':>11} {'Cost/q':>10}")
    for p in points_sorted:
        print(f"{p['mode']:<14} {p['median_lat']:>10.2f}s "
              f"{p['mean_corr']:>11.2f} "
              f"{'$' + format(COST_PER_QUERY_USD[p['mode']], '.4f'):>10}")


if __name__ == "__main__":
    main()
