# 📋 Anushree — Evaluation Track Status

**Branch (planned):** `feature/anushree-evaluation` — not yet pushed
**Issues covered:** #28, #38, #32, #31, #36

---

## TL;DR

| # | Issue | Status | Needs API to finish? |
|---|---|---|---|
| **#28** | Compile 3-way evaluation results | ✅ **DONE** | No |
| **#38** | Error analysis dashboard | ✅ **DONE** | No |
| **#36** | Chain-of-Verification (CoVe) 5th agent | 🟡 **Code complete + 13 tests pass** | Yes (live demo + re-eval) |
| **#31** | RAGAS evaluation | 🟡 **Code complete + dry-run validated** | Yes (live `--run`) |
| **#32** | LLM-as-Judge | 🟡 **Code complete + 15/45 rows scored** | Yes (29 rows remaining) |

The 3 yellow items are fully built and tested. They just need an LLM API key with enough quota to flip the switch — see [§ Pending API work](#-pending-api-work-flip-the-switch-when-quota-is-back) below for the exact one-line commands.

---

## ✅ Issue #28 — Compile 3-way evaluation results

**Files:**
- `evaluation/analysis.ipynb` — pandas analysis, outputs embedded
- `evaluation/comparison_chart.png` — quality + latency dashboard
- `docs/evaluation_results.md` — comparison table + writeup + caveats

**Headline numbers:**

| Metric | Naive | Agentic | Multi-Agent |
|---|---|---|---|
| Avg Relevance | 0.835 | **0.920** | 0.917 |
| Avg Faithfulness | **0.947** | 0.753 | 0.893 |
| Correct Abstention % | **80.0** | 53.3 | 73.3 |
| Avg Latency (s) | **2.96** | 6.88 | 16.38 |

Most striking finding: agentic mode **over-refuses** (10 of 15 questions), which deflates the abstention score below Naive's. Full analysis in `docs/evaluation_results.md`.

---

## ✅ Issue #38 — Error analysis dashboard

**Files:**
- `evaluation/error_analysis.ipynb` — 3-panel dashboard
- `evaluation/error_analysis_chart.png` — stacked breakdown + counts + latency boxplot
- `evaluation/error_analysis.md` — categorized failures with examples

**Headline finding:** each mode has a distinctive failure signature.
- 🔴 **Naive:** 3 hallucinations, including **the fake `$234` Apple stock price with a fabricated citation**
- 🟠 **Agentic:** 7 wrong refusals on legitimate questions (F4, C2–C4, R1–R3)
- 🟢 **Multi-Agent:** 10/15 correct but 2 pathological-latency cases (36 s, 72 s) on out-of-scope questions

---

## 🟡 Issue #36 — Chain-of-Verification (CoVe) 5th agent

Implements Dhuliawala et al., 2023 — directly attacks the Naive hallucination mode.

**Files created:**
- `prompts/verifier_claim_extract.txt`
- `prompts/verifier_question_gen.txt`
- `prompts/verifier_check.txt`
- `src/agents/verifier.py` — full `VerifierAgent` (extract → generate questions → re-retrieve → check → revise)
- `src/test_verifier.py` — **13 unit tests, all passing**, run without any LLM call

**Files modified:**
- `src/agents/__init__.py` — exports `VerifierAgent`
- `src/multi_agent.py` — wired between Synthesizer and Validator; new `enable_verifier=True` flag; response includes `multi_agent_trace.verification_report`

**Tests cover** the actual hallucination from error analysis: the verifier extracts the `$234` claim, asks "What is Apple's stock price?", gets no support, returns `CONTRADICTED`, and drops the sentence. **Logic is validated end-to-end with mocks.**

**To verify locally:**
```cmd
venv\Scripts\activate.bat
python -m src.test_verifier
```
Expected: `All 13 tests passed.`

---

## 🟡 Issue #31 — RAGAS evaluation

**Files created:**
- `evaluation/ragas_eval.py` — dual-mode script (`--dry-run` / `--run`)
- `evaluation/ragas_dataset_dry.json` — preview of the constructed dataset
- `docs/ragas_eval_notes.md` — full usage + limits doc

**Files modified:**
- `requirements.txt` — added `ragas>=0.2.0`, `datasets>=2.18.0`

**Dry-run already validated:** all 45 samples (15 × 3 modes) have a question, answer, ground_truth, and reconstructed contexts. RAGAS would accept the dataset as-is.

**Known limitation:** result CSVs don't store the actual chunk text (only `num_chunks`), so contexts are reconstructed from inline citations. Documented in `docs/ragas_eval_notes.md`.

---

## 🟡 Issue #32 — LLM-as-Judge

**Files created:**
- `prompts/llm_judge.txt` — 3-dimension rubric (correctness, helpfulness, citation_accuracy on 1–10)
- `evaluation/llm_judge.py` — full script with `--resume`, `--force`, `--delay`, `--limit`
- `evaluation/llm_judge_scores.csv` — **16 rows scored** (15/15 naive ✅, 1/15 agentic)
- `docs/llm_judge_notes.md` — current state + resume instructions + early findings

**Partial findings (from the 15 naive rows scored):** the judge correctly flagged:
- N2 (fake `$234` stock price): **1 / 1 / 1**
- F3 (Amazon Q1 2026 wrong): **1 / 1 / 1**
- C2 (cross-doc synthesis weak): **2 / 2 / 1**
- F1, F2, F4, F5, C1, C3 (clean factuals): **10 / 10 / 10**

This is much sharper signal than the 100%-everything heuristic citation score — the judge agrees with our error analysis.

---

## ⚠️ Pending API work — flip the switch when quota is back

All three remaining items just need an LLM API key with enough quota. Pick whichever is easiest:

- **Wait for Gemini daily reset** — 20/day on `gemini-2.5-flash-lite` resets at midnight (Google TZ)
- **Fresh Gemini key** — https://aistudio.google.com/apikey on a different Google account = fresh 20/day
- **Switch to OpenAI** — set `OPENAI_API_KEY=sk-...` and `LLM_MODEL=gpt-4o-mini` in `.env`. ~$0.50 covers everything.

> ⚠️ **Heads-up:** `gemini-1.5-flash` (current `.env.example` default) is **deprecated and returns 404**. The team should update `.env.example` to `gemini-2.5-flash-lite`.

### Commands to finish each issue

```cmd
:: 1. Finish LLM-as-Judge (29 remaining rows; --resume keeps the 16 already scored)
python evaluation/llm_judge.py --resume --delay 10

:: 2. Run RAGAS for real (45 samples × ~4 metrics ≈ 150–250 LLM calls)
python evaluation/ragas_eval.py --run

:: 3. Test the new CoVe agent live in the multi-agent flow
uvicorn app.main:app --host 127.0.0.1 --port 8001
:: then ask any multi-agent question in the UI; "verification_report" appears in the trace

:: 4. (Optional) Re-run multi-agent eval with CoVe enabled to measure improvement
python evaluation/eval_script.py --modes multi_agent
:: Then re-run the analysis notebooks to refresh the charts
```

### Once the runs finish — merge the new numbers into `docs/evaluation_results.md`

Add three new column trios to the main comparison table:
1. **LLM-Judge** — correctness / helpfulness / citation_accuracy (from `llm_judge_scores.csv`)
2. **RAGAS** — faithfulness / answer_relevancy / context_precision / context_recall (from `ragas_scores.csv`)
3. **Post-CoVe multi-agent** — recompute the existing metrics after re-running eval

The per-mode averages can be computed with the snippet at the bottom of [`docs/llm_judge_notes.md`](docs/llm_judge_notes.md#4-verify).

---

## 📁 Full file index

```
NEW files:
  ANUSHREE_STATUS.md                       ← this file
  prompts/verifier_claim_extract.txt
  prompts/verifier_question_gen.txt
  prompts/verifier_check.txt
  prompts/llm_judge.txt
  src/agents/verifier.py
  src/test_verifier.py
  evaluation/analysis.ipynb
  evaluation/comparison_chart.png
  evaluation/error_analysis.ipynb
  evaluation/error_analysis_chart.png
  evaluation/error_analysis.md
  evaluation/llm_judge.py
  evaluation/llm_judge_scores.csv
  evaluation/ragas_eval.py
  evaluation/ragas_dataset_dry.json
  docs/evaluation_results.md
  docs/llm_judge_notes.md
  docs/ragas_eval_notes.md

MODIFIED files:
  requirements.txt                  (+ matplotlib, ragas, datasets)
  src/agents/__init__.py            (export VerifierAgent)
  src/multi_agent.py                (wire VerifierAgent between Synthesizer and Validator)
  .env                              (local-only — model name updated to gemini-2.5-flash-lite)
```

---

## For Nandita / Jillian

- **Want to take over the API runs?** Step-by-step commands above. Each script is self-documenting via `--help`.
- **Code review:** all the changes are in `src/agents/verifier.py`, `src/multi_agent.py`, and the `evaluation/` directory. Nothing touches `src/retriever.py`, `src/chunker.py`, `src/multi_agent.py`'s sub-agent files, or `app/`.
- **The one shared-file change worth a second look** is `src/multi_agent.py` — I inserted the Verifier between Synthesizer and Validator, and added the `enable_verifier=True` constructor flag. If you'd rather disable CoVe for the demo, instantiate with `MultiAgentOrchestrator(retriever, enable_verifier=False)` and the pipeline reverts to the previous behavior exactly.

If anything is unclear, the doc closest to the code is usually the right reference:
- CoVe details → `src/agents/verifier.py` docstring
- LLM-Judge details → `docs/llm_judge_notes.md`
- RAGAS details → `docs/ragas_eval_notes.md`
- Main evaluation results → `docs/evaluation_results.md`
- Error analysis → `evaluation/error_analysis.md`
