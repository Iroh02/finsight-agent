# RAGAS Evaluation — How to Run

This document explains how to run the research-standard [RAGAS](https://docs.ragas.io/) metrics over FinSight Agent's three modes (Naive / Agentic / Multi-Agent).

The script lives at [`evaluation/ragas_eval.py`](../evaluation/ragas_eval.py).

> Full evaluation-track status across all of Anushree's issues: [`ANUSHREE_STATUS.md`](../ANUSHREE_STATUS.md).

---

## Why this is useful

The heuristic metrics in [`eval_script.py`](../evaluation/eval_script.py) (relevance, faithfulness, has_citations) are crude proxies. RAGAS provides four research-standard metrics that are widely cited in RAG papers:

| Metric | What it measures | Needs |
|---|---|---|
| `faithfulness` | Is every claim in the answer supported by the contexts? | question, answer, contexts |
| `answer_relevancy` | Does the answer address the question? | question, answer |
| `context_precision` | Are the retrieved chunks actually relevant to the question? | question, contexts, ground_truth |
| `context_recall` | Did retrieval find the info needed to produce the ground_truth answer? | question, contexts, ground_truth |

Adding RAGAS to the evaluation section moves the writeup from "we measured citation accuracy with a heuristic" to **"we evaluated against the RAGAS benchmark, the de facto standard in RAG literature."**

---

## Two modes of operation

### `--dry-run` (default, no API needed)

```bash
python evaluation/ragas_eval.py --dry-run
```

This:

1. Loads the 3 result CSVs (`results_naive.csv`, etc.)
2. Joins them with `test_questions.csv` to pick up `expected_answer_summary` as `ground_truth`
3. Reconstructs `contexts` by parsing inline `(Source: ..., Page: ...)` citations from each answer
4. Prints per-mode dataset stats and a sample row
5. Saves a JSON preview to `evaluation/ragas_dataset_dry.json`
6. **Does not call any LLM** — safe to run with no API key

Use this to confirm the dataset shape is correct before burning API quota.

### `--run` (full evaluation, requires API)

```bash
python evaluation/ragas_eval.py --run --modes naive agentic multi_agent
```

This actually invokes `ragas.evaluate()`. It will:

- Make many LLM calls per question (RAGAS uses an LLM to compute each metric — typically 3–5 calls per row per metric)
- For 15 questions × 3 modes × 4 metrics, expect roughly **150–250 LLM calls**
- Save scores to `evaluation/ragas_scores.csv` and print per-mode averages

You can narrow scope while debugging:

```bash
# One mode only
python evaluation/ragas_eval.py --run --modes naive

# Subset of metrics (faster, cheaper)
python evaluation/ragas_eval.py --run --metrics faithfulness answer_relevancy
```

---

## Prerequisites

1. **Install deps** (already in `requirements.txt`):
   ```bash
   pip install ragas datasets
   ```
2. **API quota** — RAGAS itself uses an LLM. The configured provider in `.env` (Gemini / OpenAI / Anthropic) needs enough quota for ~250 calls.
   - Gemini free tier (20/day on `gemini-2.5-flash-lite`) is **not sufficient** for a full run.
   - Recommended: use OpenAI (`gpt-4o-mini` is cheap — under $0.50 for the full run) or Gemini paid tier.

---

## Known limitation: degraded contexts

`eval_script.py` saves the response `answer` and `decision`, but **not** the retrieved chunk text. So `ragas_eval.py` reconstructs contexts from the citation strings embedded in each answer (e.g. "Source: Apple_10K_2025.pdf, Page: 32" + the surrounding 120 chars). That's enough for RAGAS to run, but it under-reports `faithfulness` and especially `context_precision` / `context_recall` compared to a run where the real chunk text was preserved.

To get full-fidelity scores, the eval pipeline would need to also persist `chunks: [{"text": ..., "source": ..., "page": ...}, ...]` to the result CSV. That's a one-line change in [`eval_script.py:103`](../evaluation/eval_script.py#L103) (add `"chunks": response.get("chunks", [])[:5]`) and a re-run of the eval. This is tracked as a follow-up.

---

## Interpreting results

RAGAS scores are 0–1, higher is better. Rough rules of thumb from the literature:

| Score range | Meaning |
|---|---|
| 0.9–1.0 | Very strong |
| 0.7–0.9 | Acceptable for production |
| 0.5–0.7 | Mediocre — needs work |
| < 0.5 | Failing — fundamental issues |

When the scores are in, merge them into the comparison table in [`docs/evaluation_results.md`](./evaluation_results.md) — add three columns (one per RAGAS metric) alongside the existing heuristic metrics.

---

## Reference

- RAGAS docs: https://docs.ragas.io/
- RAGAS paper: Es et al., 2024 — *"RAGAS: Automated Evaluation of Retrieval Augmented Generation"*
