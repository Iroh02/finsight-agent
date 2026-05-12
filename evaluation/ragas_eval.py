"""RAGAS evaluation for FinSight Agent.

Runs the research-standard RAGAS metrics on the three mode-specific result CSVs:
    - faithfulness          (does the answer rely on the contexts?)
    - answer_relevancy      (does the answer address the question?)
    - context_precision     (are retrieved chunks actually relevant?)
    - context_recall        (was the needed info retrieved?)

Two modes:

    --dry-run    Build the RAGAS dataset from the result CSVs and print a sample.
                 NO LLM calls. NO API key required. Use this to validate the
                 dataset shape before burning quota.

    --run        Actually call ragas.evaluate(). Requires:
                   * ragas + datasets installed (already in requirements.txt)
                   * a live LLM API key in .env (Gemini / OpenAI / Anthropic)
                   * enough quota for ~60 LLM calls per metric per row

The result CSVs from eval_script.py only store `num_chunks`, not the actual
retrieved chunk text. We do a best-effort reconstruction of contexts by
extracting the inline "(Source: ..., Page: ...)" citations from each answer.
This is good enough for faithfulness on the answer-side and gives RAGAS
something to compute context_precision/recall against, but it under-reports
context-side metrics compared to a run where chunks are preserved end-to-end.

Outputs:
    evaluation/ragas_scores.csv         per-(mode, question) metric scores
    evaluation/ragas_dataset_dry.json   dataset preview (dry-run only)

Usage:
    python evaluation/ragas_eval.py --dry-run             # safe, no API
    python evaluation/ragas_eval.py --run                 # full run (needs API)
    python evaluation/ragas_eval.py --run --modes naive   # one mode only
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional


# --------------------------------------------------------------------------- #
# Paths & constants
# --------------------------------------------------------------------------- #

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
EVAL_DIR = HERE
sys.path.insert(0, str(ROOT))  # for src.* imports when --run is used

MODES = ["naive", "agentic", "multi_agent"]
RESULTS_PATTERN = "results_{mode}.csv"
TEST_QUESTIONS = "test_questions.csv"
SCORES_OUT = "ragas_scores.csv"
DATASET_PREVIEW_OUT = "ragas_dataset_dry.json"

# Citation pattern from the generator's output, e.g.
#   "(Source: Apple_10K_2025.pdf, Page: 32)"
_CITE_RE = re.compile(
    r"\(\s*Source:\s*([^,]+),\s*Page:\s*([^)]+)\)",
    re.IGNORECASE,
)


# --------------------------------------------------------------------------- #
# Data loading
# --------------------------------------------------------------------------- #

def load_test_questions() -> Dict[str, Dict[str, str]]:
    """Return question_id -> {expected_answer_summary, should_refuse, category}."""
    path = EVAL_DIR / TEST_QUESTIONS
    lookup: Dict[str, Dict[str, str]] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            lookup[row["question_id"]] = row
    return lookup


def load_results(mode: str) -> List[Dict[str, str]]:
    path = EVAL_DIR / RESULTS_PATTERN.format(mode=mode)
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# --------------------------------------------------------------------------- #
# Context reconstruction
# --------------------------------------------------------------------------- #

def extract_contexts(answer: str) -> List[str]:
    """
    Best-effort reconstruction of context strings from an answer's inline
    citations. Each unique (Source, Page) pair becomes one context entry.
    Not as informative as real chunk text, but lets RAGAS run.

    Returns at least one element so RAGAS doesn't choke on empty lists.
    """
    if not answer:
        return ["(no context available)"]
    seen = []
    found = set()
    for m in _CITE_RE.finditer(answer):
        source = m.group(1).strip()
        page = m.group(2).strip()
        key = (source.lower(), page.lower())
        if key in found:
            continue
        found.add(key)
        # Include a snippet of nearby answer text so the "context" isn't just
        # a filename — pull ~120 chars before the citation as the supporting
        # passage proxy.
        start = max(0, m.start() - 120)
        snippet = answer[start:m.start()].strip()
        ctx = f"[Reconstructed citation] Source: {source}, Page: {page}. Surrounding text: {snippet}"
        seen.append(ctx)

    if seen:
        return seen
    return ["(no inline citations found in answer)"]


# --------------------------------------------------------------------------- #
# Dataset construction
# --------------------------------------------------------------------------- #

def build_samples(mode: str, test_lookup: Dict[str, Dict[str, str]]) -> List[Dict]:
    """Return one RAGAS-compatible sample dict per response."""
    samples: List[Dict] = []
    for row in load_results(mode):
        qid = row["question_id"]
        meta = test_lookup.get(qid, {})
        sample = {
            "question_id": qid,
            "category": row.get("category", ""),
            "mode": mode,
            "question": row.get("question", ""),
            "answer": row.get("answer", ""),
            "contexts": extract_contexts(row.get("answer", "")),
            "ground_truth": meta.get("expected_answer_summary", ""),
            # Carry over the heuristic scores from eval_script for downstream join
            "heur_relevance": row.get("relevance", ""),
            "heur_faithfulness": row.get("faithfulness", ""),
            "execution_time_s": row.get("execution_time_s", ""),
        }
        samples.append(sample)
    return samples


def to_ragas_dataset(samples: List[Dict]):
    """Lazy-import datasets so dry-run works without it installed."""
    from datasets import Dataset
    # RAGAS expects fields: question, answer, contexts (list[str]), ground_truth
    return Dataset.from_list([
        {
            "question": s["question"],
            "answer": s["answer"],
            "contexts": s["contexts"],
            "ground_truth": s["ground_truth"],
        }
        for s in samples
    ])


# --------------------------------------------------------------------------- #
# Dry-run output
# --------------------------------------------------------------------------- #

def dry_run(modes: List[str], test_lookup: Dict, preview_n: int = 2) -> None:
    print("=" * 72)
    print("RAGAS dataset DRY-RUN (no API calls)")
    print("=" * 72)
    print(f"Source: {EVAL_DIR}")
    print(f"Modes:  {modes}")
    print()

    all_samples: Dict[str, List[Dict]] = {}
    for mode in modes:
        samples = build_samples(mode, test_lookup)
        all_samples[mode] = samples
        ctx_lens = [len(s["contexts"]) for s in samples]
        gt_present = sum(1 for s in samples if s["ground_truth"])
        print(f"[{mode:<11}] {len(samples)} samples  "
              f"contexts/sample(min/avg/max): {min(ctx_lens)}/{sum(ctx_lens)/len(ctx_lens):.1f}/{max(ctx_lens)}  "
              f"ground-truth present: {gt_present}/{len(samples)}")

    # Save full preview JSON
    preview_path = EVAL_DIR / DATASET_PREVIEW_OUT
    preview_payload = {
        "modes": modes,
        "schema": ["question", "answer", "contexts", "ground_truth"],
        "samples": {
            mode: [
                {
                    "question_id": s["question_id"],
                    "question": s["question"],
                    "answer_preview": (s["answer"] or "")[:160],
                    "n_contexts": len(s["contexts"]),
                    "contexts_preview": [c[:120] for c in s["contexts"][:2]],
                    "ground_truth": s["ground_truth"],
                }
                for s in samples[:preview_n]
            ]
            for mode, samples in all_samples.items()
        },
    }
    with open(preview_path, "w", encoding="utf-8") as f:
        json.dump(preview_payload, f, indent=2, ensure_ascii=False)
    print(f"\nWrote dataset preview to {preview_path.name}")

    # Show first sample for the first mode inline
    first_mode = modes[0]
    if all_samples[first_mode]:
        s = all_samples[first_mode][0]
        print("\n--- Sample sample (first row of first mode) ---")
        print(f"  question_id : {s['question_id']}")
        print(f"  question    : {s['question']}")
        print(f"  answer      : {(s['answer'] or '')[:160]}...")
        print(f"  contexts[0] : {s['contexts'][0][:160]}...")
        print(f"  ground_truth: {s['ground_truth']}")

    print("\nNext step:")
    print("  # When you have LLM API quota:")
    print(f"  python evaluation/ragas_eval.py --run --modes {' '.join(modes)}")


# --------------------------------------------------------------------------- #
# Live run
# --------------------------------------------------------------------------- #

DEFAULT_METRICS = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]


def live_run(modes: List[str], test_lookup: Dict, metric_names: List[str]) -> None:
    """Actually call ragas.evaluate() and save the scores."""
    print("=" * 72)
    print("RAGAS LIVE evaluation")
    print("=" * 72)

    # Lazy imports so dry-run works without ragas installed.
    try:
        import ragas
        from ragas import evaluate as ragas_evaluate
        from ragas.metrics import (
            faithfulness as M_faithfulness,
            answer_relevancy as M_answer_relevancy,
            context_precision as M_context_precision,
            context_recall as M_context_recall,
        )
    except ImportError as e:
        print(f"[ERROR] ragas is not installed: {e}")
        print("  Install with: pip install ragas datasets")
        sys.exit(2)

    metric_map = {
        "faithfulness": M_faithfulness,
        "answer_relevancy": M_answer_relevancy,
        "context_precision": M_context_precision,
        "context_recall": M_context_recall,
    }
    selected = [metric_map[m] for m in metric_names if m in metric_map]
    if not selected:
        print(f"[ERROR] No valid metrics; pick from {list(metric_map)}")
        sys.exit(2)

    # RAGAS uses the LLM you configure via langchain. We'll honor whatever the
    # main app uses (Gemini / OpenAI / Anthropic) by configuring through env.
    print(f"  ragas version: {ragas.__version__}")
    print(f"  metrics: {[m.name for m in selected]}")

    all_rows: List[Dict] = []
    for mode in modes:
        samples = build_samples(mode, test_lookup)
        ds = to_ragas_dataset(samples)
        print(f"\n[{mode}] running {len(selected)} metric(s) on {len(samples)} samples...")
        try:
            result = ragas_evaluate(ds, metrics=selected)
        except Exception as e:
            print(f"  [ERROR] ragas_evaluate failed: {e}")
            continue
        # ragas returns a Result wrapping a pandas DataFrame
        df = result.to_pandas()
        for i, sample in enumerate(samples):
            row = {
                "mode": mode,
                "question_id": sample["question_id"],
                "category": sample["category"],
                "question": sample["question"],
            }
            for m in selected:
                col = m.name
                row[col] = float(df.iloc[i][col]) if col in df.columns else None
            all_rows.append(row)

    # Save
    out_path = EVAL_DIR / SCORES_OUT
    fieldnames = ["mode", "question_id", "category", "question"] + [m.name for m in selected]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"\nWrote {len(all_rows)} rows to {out_path}")

    # Per-mode averages
    print("\nPer-mode averages:")
    by_mode: Dict[str, List[Dict]] = {}
    for r in all_rows:
        by_mode.setdefault(r["mode"], []).append(r)
    header = f"{'metric':<22} | " + " | ".join(f"{m:^14}" for m in modes)
    print(header)
    print("-" * len(header))
    for m in [mm.name for mm in selected]:
        line = f"{m:<22}"
        for mode in modes:
            rows = by_mode.get(mode, [])
            vals = [r.get(m) for r in rows if isinstance(r.get(m), (int, float))]
            avg = sum(vals) / len(vals) if vals else 0.0
            line += f" | {avg:^14.3f}"
        print(line)


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="RAGAS evaluation for FinSight Agent")
    group = p.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true",
                       help="Build dataset, print preview, NO API calls (default)")
    group.add_argument("--run", action="store_true",
                       help="Actually run ragas.evaluate() (needs API quota)")
    p.add_argument("--modes", nargs="+", default=MODES, choices=MODES,
                   help="Subset of modes to evaluate")
    p.add_argument("--metrics", nargs="+", default=DEFAULT_METRICS,
                   choices=DEFAULT_METRICS,
                   help="Subset of metrics to run (--run only)")
    args = p.parse_args()
    if not args.dry_run and not args.run:
        args.dry_run = True  # safe default
    return args


def main() -> int:
    args = parse_args()
    test_lookup = load_test_questions()

    if args.dry_run:
        dry_run(args.modes, test_lookup)
        return 0
    live_run(args.modes, test_lookup, args.metrics)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
