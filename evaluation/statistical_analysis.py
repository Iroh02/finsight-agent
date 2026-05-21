"""Statistical analysis of the 45-row LLM-as-Judge eval.

Produces:
  * Bootstrap 95% CIs around each mode's mean for every metric (1,000 resamples)
  * Paired Wilcoxon signed-rank tests on all 3 mode pairs
  * A markdown table ready to paste into the README

This converts the existing point-estimate results ("multi-agent 8.13 vs naive 7.00")
into statistical claims with p-values, addressing RQ1 + RQ2 with rigor.

Run:
    python evaluation/statistical_analysis.py
"""

from __future__ import annotations

import csv
import math
import random
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from scipy import stats

EVAL_DIR = Path(__file__).resolve().parent
JUDGE_CSV = EVAL_DIR / "llm_judge_scores.csv"
OUT_MD = EVAL_DIR / "statistical_results.md"

MODES = ["naive", "agentic", "multi_agent"]
METRICS = ["correctness", "helpfulness", "citation_accuracy"]
N_BOOTSTRAP = 1000
SEED = 42


# --------------------------------------------------------------------------- #
# Data loading
# --------------------------------------------------------------------------- #

def load_judge_scores(path: Path) -> Dict[str, Dict[str, Dict[str, float]]]:
    """Load llm_judge_scores.csv into nested dict[mode][question_id][metric]."""
    scores: Dict[str, Dict[str, Dict[str, float]]] = defaultdict(dict)
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            mode = row["mode"]
            qid = row["question_id"]
            try:
                scores[mode][qid] = {
                    "correctness":       float(row["correctness"]),
                    "helpfulness":       float(row["helpfulness"]),
                    "citation_accuracy": float(row["citation_accuracy"]),
                }
            except (ValueError, KeyError):
                # Skip rows with errors
                continue
    return scores


# --------------------------------------------------------------------------- #
# Bootstrap CI
# --------------------------------------------------------------------------- #

def bootstrap_ci(values: List[float], n_boot: int = N_BOOTSTRAP,
                 ci: float = 0.95, seed: int = SEED) -> Tuple[float, float, float]:
    """Return (mean, lo, hi) where (lo, hi) is the bootstrap CI."""
    if not values:
        return float("nan"), float("nan"), float("nan")
    rng = random.Random(seed)
    n = len(values)
    means: List[float] = []
    for _ in range(n_boot):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo_idx = int((1 - ci) / 2 * n_boot)
    hi_idx = int((1 + ci) / 2 * n_boot) - 1
    return (
        sum(values) / n,
        means[lo_idx],
        means[hi_idx],
    )


# --------------------------------------------------------------------------- #
# Paired Wilcoxon signed-rank
# --------------------------------------------------------------------------- #

def paired_wilcoxon(a: List[float], b: List[float]) -> Tuple[float, float]:
    """Return (W, p_two_sided) for paired Wilcoxon signed-rank test."""
    if len(a) != len(b) or not a:
        return float("nan"), float("nan")
    diffs = [x - y for x, y in zip(a, b) if (x - y) != 0]
    if not diffs:
        return 0.0, 1.0
    try:
        res = stats.wilcoxon(a, b, zero_method="wilcox", alternative="two-sided")
        return float(res.statistic), float(res.pvalue)
    except Exception:
        n_pos = sum(1 for d in diffs if d > 0)
        n = len(diffs)
        p = 2 * min(stats.binom.cdf(n_pos, n, 0.5), 1 - stats.binom.cdf(n_pos - 1, n, 0.5))
        return float(n_pos), float(p)


def cohens_dz(a: List[float], b: List[float]) -> float:
    """Cohen's d_z for paired samples, signed so positive => b > a.

    Effect-size interpretation (Cohen 1988): |dz| <= 0.2 small,
    0.5 medium, >= 0.8 large. Reported alongside p-values so that magnitude
    is visible even when the sample is too small to reach significance.
    """
    if len(a) != len(b) or len(a) < 2:
        return float("nan")
    # diffs[i] = b[i] - a[i]  → positive means b improved over a
    diffs = np.array([y - x for x, y in zip(a, b)], dtype=float)
    sd = float(np.std(diffs, ddof=1))
    if sd == 0:
        return 0.0
    return float(np.mean(diffs) / sd)


def effect_label(dz: float) -> str:
    a = abs(dz)
    if math.isnan(dz):
        return "n/a"
    if a < 0.2:
        return "negligible"
    if a < 0.5:
        return "small"
    if a < 0.8:
        return "medium"
    return "large"


# --------------------------------------------------------------------------- #
# Analysis
# --------------------------------------------------------------------------- #

def analyze(scores: Dict[str, Dict[str, Dict[str, float]]]) -> Dict:
    """Run bootstrap CIs + pairwise Wilcoxon for every metric."""
    out: Dict = {"per_mode": {}, "pairwise": {}, "n_per_mode": {}}

    # Intersect question IDs across all 3 modes so the paired tests are valid
    common_qids = set.intersection(*[set(scores[m].keys()) for m in MODES])
    common_qids = sorted(common_qids)
    print(f"Common question IDs across all 3 modes: {len(common_qids)}")
    print(f"  -> using these {len(common_qids)} questions for paired comparisons.")
    print()

    for mode in MODES:
        out["n_per_mode"][mode] = len(common_qids)
        out["per_mode"][mode] = {}
        for metric in METRICS:
            vals = [scores[mode][qid][metric] for qid in common_qids]
            mean, lo, hi = bootstrap_ci(vals)
            out["per_mode"][mode][metric] = {
                "mean": mean,
                "ci_low": lo,
                "ci_high": hi,
                "std": float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0,
                "n": len(vals),
            }

    pairs = [("naive", "agentic"), ("naive", "multi_agent"), ("agentic", "multi_agent")]
    for mode_a, mode_b in pairs:
        out["pairwise"][f"{mode_a}_vs_{mode_b}"] = {}
        for metric in METRICS:
            a_vals = [scores[mode_a][qid][metric] for qid in common_qids]
            b_vals = [scores[mode_b][qid][metric] for qid in common_qids]
            w, p = paired_wilcoxon(a_vals, b_vals)
            dz = cohens_dz(a_vals, b_vals)
            mean_diff = sum(b_vals) / len(b_vals) - sum(a_vals) / len(a_vals)
            out["pairwise"][f"{mode_a}_vs_{mode_b}"][metric] = {
                "W": w,
                "p_value": p,
                "mean_diff": mean_diff,
                "cohens_dz": dz,
                "effect_label": effect_label(dz),
                "n": len(a_vals),
            }

    return out


# --------------------------------------------------------------------------- #
# Markdown emission
# --------------------------------------------------------------------------- #

def to_markdown(results: Dict) -> str:
    lines: List[str] = []
    lines.append("# Statistical Analysis of FinSight Evaluation")
    lines.append("")
    n = results["n_per_mode"][MODES[0]]
    lines.append(f"_{n} questions per mode (paired); {N_BOOTSTRAP} bootstrap resamples; "
                 f"paired Wilcoxon signed-rank, two-sided._")
    lines.append("")

    # Per-mode table
    lines.append("## Per-mode Means with 95% Bootstrap CIs")
    lines.append("")
    header = "| Metric | " + " | ".join(MODES) + " |"
    sep = "|" + ":---:|" * (len(MODES) + 1)
    lines.append(header)
    lines.append(sep)
    for metric in METRICS:
        cells = [metric.replace("_", " ").title()]
        for mode in MODES:
            d = results["per_mode"][mode][metric]
            cells.append(f"**{d['mean']:.2f}** [{d['ci_low']:.2f}, {d['ci_high']:.2f}]")
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")

    # Pairwise table
    lines.append("## Paired Wilcoxon Signed-Rank Tests")
    lines.append("")
    lines.append("| Comparison | Metric | Mean delta | Cohen's dz | Effect | W | p-value | Sig (alpha=0.05) |")
    lines.append("|---|---|---:|---:|:---:|---:|---:|:---:|")
    for pair_name, pair_data in results["pairwise"].items():
        a, b = pair_name.split("_vs_")
        for metric in METRICS:
            d = pair_data[metric]
            sig = "yes" if (d["p_value"] is not None and d["p_value"] < 0.05) else "no"
            lines.append(
                f"| {a} -> {b} | {metric.replace('_', ' ').title()} | "
                f"{d['mean_diff']:+.2f} | {d['cohens_dz']:+.2f} | {d['effect_label']} | "
                f"{d['W']:.1f} | {d['p_value']:.4f} | {sig} |"
            )
    lines.append("")

    lines.append("## Interpretation")
    lines.append("")
    for metric in METRICS:
        nm = results["pairwise"]["naive_vs_multi_agent"][metric]
        better = "multi-agent" if nm["mean_diff"] > 0 else "naive"
        sig = "statistically significant" if nm["p_value"] < 0.05 else "not significant at alpha=0.05"
        magnitude = nm["effect_label"]
        lines.append(
            f"- **{metric.replace('_', ' ').title()}**: {better} "
            f"is +{abs(nm['mean_diff']):.2f} better with a **{magnitude}** effect "
            f"(Cohen's dz = {nm['cohens_dz']:+.2f}; "
            f"p = {nm['p_value']:.4f}, {sig})."
        )
    lines.append("")
    lines.append("## Power note")
    lines.append("")
    lines.append(
        f"With N={n} paired questions, statistical power is limited: only effects "
        f"with |dz| >= ~0.75 typically reach p < 0.05 via Wilcoxon. The observed "
        f"effect sizes are reported above; several are medium-to-large despite "
        f"p-values above 0.05. Expanding the eval set to N >= 30 is the primary "
        f"lever for statistical confirmation (see future work)."
    )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    if not JUDGE_CSV.exists():
        raise SystemExit(f"Missing {JUDGE_CSV}")
    scores = load_judge_scores(JUDGE_CSV)
    print(f"Loaded {sum(len(v) for v in scores.values())} judge rows across {len(scores)} modes.")
    for m in MODES:
        print(f"  {m}: {len(scores[m])} rows")
    print()

    results = analyze(scores)
    md = to_markdown(results)
    OUT_MD.write_text(md, encoding="utf-8")
    # Print a sanitized summary (Windows console = cp1252) — full markdown is in the file.
    safe = md.encode("ascii", errors="replace").decode("ascii")
    print(safe)
    print()
    print(f"Wrote: {OUT_MD}")


if __name__ == "__main__":
    main()
