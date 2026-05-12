# LLM-as-Judge Evaluation — Status & How to Resume

This document tracks the current state of the LLM-as-Judge evaluation (issue #32) and explains how to finish the remaining runs when API quota is available.

> Full evaluation-track status across all of Anushree's issues: [`ANUSHREE_STATUS.md`](../ANUSHREE_STATUS.md).

Reference: Zheng et al., 2023 — *"Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena."*

Code: [`evaluation/llm_judge.py`](../evaluation/llm_judge.py) · Prompt: [`prompts/llm_judge.txt`](../prompts/llm_judge.txt) · Output: [`evaluation/llm_judge_scores.csv`](../evaluation/llm_judge_scores.csv)

---

## What it does

For every (question, answer) pair across all 3 modes, it asks an LLM judge to score on three dimensions, 1–10:

| Dimension | What it captures |
|---|---|
| `correctness` | Factual alignment with the expected answer |
| `helpfulness` | Whether the answer actually addresses the question |
| `citation_accuracy` | Whether the embedded citations look plausible (and not fabricated) |

The judge is given the question, the expected-answer summary, the `should_refuse` flag, and the actual answer. It returns a one-line JSON object plus a short justification. See [`prompts/llm_judge.txt`](../prompts/llm_judge.txt) for the full rubric.

---

## Current state (as of pause)

| Mode | Scored / Total |
|---|---|
| Naive RAG | **15 / 15** ✅ complete |
| Agentic RAG | **1 / 15** |
| Multi-Agent RAG | **0 / 15** |

29 rows remain. They were not scored because the **Gemini free tier daily limit is 20 requests/day** on `gemini-2.5-flash-lite`, and we exhausted that budget testing + scoring naive mode.

The script preserves all 16 scored rows in [`evaluation/llm_judge_scores.csv`](../evaluation/llm_judge_scores.csv). When quota is available, `--resume` will pick up exactly where we left off.

---

## Highlights from the scored naive rows

Even partial coverage produced striking signal — the judge correctly penalized the failures we already found in [error_analysis.md](../evaluation/error_analysis.md):

| Question | Judge score (corr/help/cite) | What it caught |
|---|---|---|
| N2 — *"Apple's stock price right now?"* | **1 / 1 / 1** | Naive's fake `$234` answer + fabricated citation |
| F3 — *"Amazon Q1 2026 net sales?"* | 1 / 1 / 1 | Judge marks the answer as off-base |
| R3 — *"Apple supply chain risk?"* | 2 / 2 / 1 | Weak / circular answer |
| C2 — *"Apple vs Amazon revenue"* | 2 / 2 / 1 | Cross-doc synthesis fell flat |
| F1, F2, F4, F5, C1, C3 | 10 / 10 / 10 | Clean factual matches |
| N1, N3 — refusals | 10 / 9 / 10 | Refused gracefully, judge rewards it |

This is a much sharper signal than the 100%-everything heuristic citation score. Once agentic + multi-agent are scored, the comparison table in [evaluation_results.md](./evaluation_results.md) gets a real "objective scoring" column trio.

---

## How to resume

### 1. Make sure you have API quota

The script reads `LLM_MODEL` and the matching `*_API_KEY` from `.env`. Three ways to get past the current block:

- **Wait for daily reset** — Gemini's per-day counter resets at midnight (Google's timezone). Then run as below.
- **Use a fresh Gemini key** — 2 minutes at https://aistudio.google.com/apikey on a different Google account. Replace `GOOGLE_API_KEY` in `.env`.
- **Switch provider** — set `OPENAI_API_KEY=sk-...` and `LLM_MODEL=gpt-4o-mini` in `.env`. ~$0.10 covers the full 29 remaining calls.

### 2. Heads-up about the model name

`.env.example` currently suggests `LLM_MODEL=gemini-1.5-flash`, but **Google deprecated all `gemini-1.5-*` models** — they now return 404. Use one of these instead:

| Model | Notes |
|---|---|
| `gemini-2.5-flash-lite` | ✅ Works on free tier (20/day) — used here |
| `gemini-flash-lite-latest` | Alias for the above |
| `gemini-2.0-flash` | Faster, but limit was `0` for this account — likely needs paid tier |

This is worth fixing in `.env.example` for the rest of the team — but it's outside the evaluation scope.

### 3. Run with resume

```bash
# Make sure venv is active
venv\Scripts\activate.bat

# Resume — skips the 16 already-scored rows, re-judges the 29 remaining
python evaluation/llm_judge.py --resume --delay 10
```

Flags worth knowing:

- `--resume` — keep already-scored rows, only re-judge failures and missing rows
- `--force` — wipe the CSV and start fresh
- `--delay N` — seconds between successful requests (default 5). Use **10–12** on Gemini free tier to stay under per-minute rate limits.
- `--modes naive agentic multi_agent` — restrict to a subset of modes
- `--limit 1` — score only the first question per mode (good for smoke tests)

### 4. Verify

After it finishes, check the per-mode averages:

```bash
python -c "
import csv
from collections import defaultdict
rows = list(csv.DictReader(open('evaluation/llm_judge_scores.csv', encoding='utf-8')))
agg = defaultdict(lambda: {'c':[], 'h':[], 'ca':[]})
for r in rows:
    if r['correctness'] not in ('', 'None'):
        agg[r['mode']]['c'].append(int(r['correctness']))
        agg[r['mode']]['h'].append(int(r['helpfulness']))
        agg[r['mode']]['ca'].append(int(r['citation_accuracy']))
for m in ['naive','agentic','multi_agent']:
    v = agg[m]
    if v['c']:
        print(f'{m:<14}  corr={sum(v[\"c\"])/len(v[\"c\"]):.2f}  help={sum(v[\"h\"])/len(v[\"h\"]):.2f}  cite={sum(v[\"ca\"])/len(v[\"ca\"]):.2f}  (n={len(v[\"c\"])})')
"
```

### 5. Merge into the main writeup

Update [`docs/evaluation_results.md`](./evaluation_results.md) — add three columns (LLM-Judge Correctness / Helpfulness / Citation Accuracy) to the comparison table with the per-mode averages from step 4.

---

## Notes on the prompt

The judge prompt is in [`prompts/llm_judge.txt`](../prompts/llm_judge.txt). Key design choices:

- **`temperature=0`** so the judge is deterministic
- **Strict JSON output**, parsed defensively (looks for `{...}` block; tolerates wrapping prose if it slips through)
- **Special handling of `should_refuse=True`** — a correct refusal earns 10 on correctness, an attempted answer earns 1–3
- **Penalty for fabricated citations** — explicitly instructs the judge to score 1–3 if a citation is implausible for the claim

If you change the rubric mid-run, run with `--force` to wipe the cache (otherwise the old scores carry forward as cached).
