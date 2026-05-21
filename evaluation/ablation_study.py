"""Ablation study — measure the contribution of each FinSight component.

Builds the multi-agent pipeline IN-PROCESS (the HTTP endpoint always runs the
full stack, so component toggles must be set here) and re-runs the test set
under each ablation variant:

    full          everything on  (reranker + temporal + verifier + conflict)
    no_reranker   cross-encoder reranking OFF (vector-only retrieval)
    no_temporal   plain Retriever, no metadata filtering
    no_verifier   Chain-of-Verification OFF
    no_conflict   cross-document conflict detection OFF

For each variant it records LLM-free metrics (no judge needed, so this is fast
and reproducible): heuristic faithfulness, latency, FinSight Trust Score,
answer rate, and correct-abstention rate.

Addresses RQ3 (reranker) and RQ4 (temporal); also quantifies the verifier and
conflict detector.

Run (no server needed — builds the pipeline directly):
    python evaluation/ablation_study.py
    python evaluation/ablation_study.py --questions 8     # faster subset
    python evaluation/ablation_study.py --variants full no_reranker
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path
from typing import Dict, List

EVAL_DIR = Path(__file__).resolve().parent
ROOT = EVAL_DIR.parent
sys.path.insert(0, str(ROOT))

TEST_Q_CSV = EVAL_DIR / "test_questions.csv"
OUT_CSV = EVAL_DIR / "ablation_results.csv"
OUT_MD = EVAL_DIR / "ablation_results.md"

VARIANTS = ["full", "no_reranker", "no_temporal", "no_verifier", "no_conflict"]
VARIANT_DESC = {
    "full":        "All components on (reranker + temporal + verifier + conflict)",
    "no_reranker": "Cross-encoder reranking OFF (vector-only retrieval)",
    "no_temporal": "Temporal metadata filtering OFF (plain retriever)",
    "no_verifier": "Chain-of-Verification OFF",
    "no_conflict": "Cross-document conflict detection OFF",
}


# --------------------------------------------------------------------------- #
# Pipeline construction
# --------------------------------------------------------------------------- #

def build_orchestrator(variant: str, vectorstore, llm):
    """Construct a MultiAgentOrchestrator configured for one ablation variant."""
    from src.retriever import Retriever
    from src.temporal import TemporalAwareRetriever
    from src.agent import AgenticRouter
    from src.multi_agent import MultiAgentOrchestrator

    use_reranker = variant != "no_reranker"
    use_temporal = variant != "no_temporal"

    if use_temporal:
        retriever = TemporalAwareRetriever(
            vectorstore, use_reranker=use_reranker, retrieve_multiplier=4
        )
    else:
        retriever = Retriever(
            vectorstore, use_reranker=use_reranker, retrieve_multiplier=4
        )

    agentic = AgenticRouter(retriever, llm)
    orch = MultiAgentOrchestrator(
        retriever, llm,
        single_agent_fallback=agentic,
        enable_verifier=(variant != "no_verifier"),
        enable_conflict_detection=(variant != "no_conflict"),
    )
    return orch, retriever


# --------------------------------------------------------------------------- #
# Metrics (LLM-judge-free)
# --------------------------------------------------------------------------- #

def heuristic_faithfulness(result: Dict, expected_refuse: bool) -> float:
    """Heuristic faithfulness, consistent with eval_script.score_response."""
    decision = result.get("decision", "")
    citations = result.get("citations", []) or []
    if decision == "ANSWER" and len(citations) > 0:
        return min(1.0, 0.5 + 0.1 * len(citations))
    if decision == "REFUSE":
        return 1.0 if expected_refuse else 0.5
    return 0.5


def score_one(result: Dict, trust_composite: int, expected_refuse: bool,
              latency_s: float) -> Dict:
    answer = result.get("answer", "") or ""
    decision = result.get("decision", "")
    chunks = result.get("chunks", []) or []
    correct_abstention = (
        1 if (expected_refuse and decision == "REFUSE")
        or (not expected_refuse and decision != "REFUSE")
        else 0
    )
    return {
        "faithfulness": round(heuristic_faithfulness(result, expected_refuse), 3),
        "trust_score": trust_composite,
        "latency_s": round(latency_s, 2),
        "decision": decision,
        "answered": 1 if decision == "ANSWER" else 0,
        "correct_abstention": correct_abstention,
        "n_chunks": len(chunks),
        "answer_len": len(answer),
    }


# --------------------------------------------------------------------------- #
# Run
# --------------------------------------------------------------------------- #

def run_variant(variant: str, questions: List[Dict], vectorstore, llm,
                trust_calc) -> List[Dict]:
    print(f"\n=== Variant: {variant} — {VARIANT_DESC[variant]} ===")
    orch, _ = build_orchestrator(variant, vectorstore, llm)
    rows: List[Dict] = []

    for i, q in enumerate(questions, 1):
        qid = q["question_id"]
        expected_refuse = str(q.get("should_refuse", "")).strip().lower() == "true"
        print(f"  [{i}/{len(questions)}] {qid} ...", end="", flush=True)

        t0 = time.time()
        try:
            result = orch.query(q["question"], k=5)
        except Exception as e:
            print(f" ERROR: {e}")
            continue
        latency = time.time() - t0

        raw_trace = result.get("multi_agent_trace", {}) or {}
        trust = trust_calc.compute(
            chunks=result.get("chunks", []),
            verification=raw_trace.get("verification_report"),
            validation=raw_trace.get("validation_report"),
            conflict_report=result.get("conflict_report"),
            temporal_context=result.get("temporal_context"),
            mode="multi_agent",
        )
        scored = score_one(result, trust.composite, expected_refuse, latency)
        scored.update({"variant": variant, "question_id": qid,
                       "category": q.get("category", "")})
        rows.append(scored)
        print(f" {scored['decision']:7s} faith={scored['faithfulness']:.2f} "
              f"trust={scored['trust_score']:3d} {latency:.1f}s")

    return rows


def aggregate(rows: List[Dict]) -> Dict[str, Dict]:
    """Aggregate per-variant means."""
    agg: Dict[str, Dict] = {}
    for variant in VARIANTS:
        vr = [r for r in rows if r["variant"] == variant]
        if not vr:
            continue
        n = len(vr)
        agg[variant] = {
            "n": n,
            "faithfulness": sum(r["faithfulness"] for r in vr) / n,
            "trust_score": sum(r["trust_score"] for r in vr) / n,
            "latency_s": sum(r["latency_s"] for r in vr) / n,
            "answer_rate": sum(r["answered"] for r in vr) / n,
            "correct_abstention": sum(r["correct_abstention"] for r in vr) / n,
            "avg_chunks": sum(r["n_chunks"] for r in vr) / n,
        }
    return agg


def write_outputs(rows: List[Dict], agg: Dict[str, Dict]) -> None:
    # Per-question CSV
    if rows:
        fields = ["variant", "question_id", "category", "decision", "faithfulness",
                  "trust_score", "latency_s", "answered", "correct_abstention",
                  "n_chunks", "answer_len"]
        with open(OUT_CSV, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k, "") for k in fields})

    # Markdown summary
    lines = ["# FinSight Ablation Study", ""]
    full = agg.get("full", {})
    n = full.get("n", "?")
    lines.append(f"_Each variant re-runs the multi-agent pipeline over {n} test "
                 f"questions with one component disabled. Metrics are LLM-judge-free "
                 f"(heuristic faithfulness, Trust Score, latency) for reproducibility._")
    lines.append("")
    lines.append("## Per-variant Means")
    lines.append("")
    lines.append("| Variant | Faithfulness | Trust Score | Latency (s) | Answer rate | Correct abstention |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for variant in VARIANTS:
        if variant not in agg:
            continue
        a = agg[variant]
        lines.append(
            f"| {variant} | {a['faithfulness']:.3f} | {a['trust_score']:.1f} | "
            f"{a['latency_s']:.1f} | {a['answer_rate']:.0%} | {a['correct_abstention']:.0%} |"
        )
    lines.append("")

    # Deltas vs full
    if full:
        lines.append("## Delta vs Full Pipeline (removing each component)")
        lines.append("")
        lines.append("| Removed component | Faithfulness Δ | Trust Score Δ | Latency Δ |")
        lines.append("|---|---:|---:|---:|")
        for variant in VARIANTS:
            if variant == "full" or variant not in agg:
                continue
            a = agg[variant]
            lines.append(
                f"| {variant.replace('no_', '')} | "
                f"{a['faithfulness'] - full['faithfulness']:+.3f} | "
                f"{a['trust_score'] - full['trust_score']:+.1f} | "
                f"{a['latency_s'] - full['latency_s']:+.1f}s |"
            )
        lines.append("")
        lines.append("## Interpretation")
        lines.append("")
        lines.append("A negative faithfulness / trust delta means **removing that "
                     "component hurt quality** — i.e. the component was contributing. "
                     "A negative latency delta means that component **costs time**; "
                     "the trade-off is the value it adds against the seconds it spends.")
        lines.append("")

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote: {OUT_CSV}")
    print(f"Wrote: {OUT_MD}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", type=int, default=0,
                    help="Limit to first N questions (0 = all)")
    ap.add_argument("--variants", nargs="+", default=VARIANTS, choices=VARIANTS)
    args = ap.parse_args()

    from src.vectorstore import get_vectorstore
    from src.llm_client import get_llm_client
    from src.trust_score import TrustScoreCalculator

    questions: List[Dict] = []
    with open(TEST_Q_CSV, newline="", encoding="utf-8") as fh:
        questions = list(csv.DictReader(fh))
    if args.questions > 0:
        questions = questions[:args.questions]

    print(f"Ablation study: {len(args.variants)} variants x {len(questions)} questions")
    vectorstore = get_vectorstore()
    llm = get_llm_client()
    trust_calc = TrustScoreCalculator()

    all_rows: List[Dict] = []
    for variant in args.variants:
        rows = run_variant(variant, questions, vectorstore, llm, trust_calc)
        all_rows.extend(rows)
        # Write incrementally so a crash keeps partial results
        write_outputs(all_rows, aggregate(all_rows))

    print("\nDone.")


if __name__ == "__main__":
    main()
