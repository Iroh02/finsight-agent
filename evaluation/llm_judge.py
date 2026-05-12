"""LLM-as-Judge evaluation (Zheng et al., 2023).

Asks the configured LLM (Gemini / OpenAI / Anthropic, via src.llm_client) to
score every (question, answer) pair from the three result CSVs on three
dimensions: correctness, helpfulness, citation_accuracy (1-10 each).

Outputs:
- evaluation/llm_judge_scores.csv   one row per (mode, question_id)
- prints per-mode averages to stdout

Usage:
    python evaluation/llm_judge.py --resume        # continue an interrupted run
    python evaluation/llm_judge.py                 # judge all 3 modes from scratch
    python evaluation/llm_judge.py --modes naive   # just one mode
    python evaluation/llm_judge.py --force         # ignore existing cache
    python evaluation/llm_judge.py --limit 1       # smoke test (1 question per mode)
    python evaluation/llm_judge.py --delay 10      # seconds between requests (free-tier friendly)

Status & resume instructions: docs/llm_judge_notes.md

NOTE on the model: `gemini-1.5-flash` is deprecated. The current free-tier
working model is `gemini-2.5-flash-lite` (20 requests/day on free tier).
Set this via LLM_MODEL in .env.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

# Make src/ importable when this script is run from project root or evaluation/.
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from src.llm_client import get_llm_client, load_prompt  # noqa: E402


MODES = ["naive", "agentic", "multi_agent"]
RESULTS_DIR = ROOT / "evaluation"
OUT_PATH = RESULTS_DIR / "llm_judge_scores.csv"
PROMPT_NAME = "llm_judge"


def load_test_questions() -> Dict[str, Dict[str, str]]:
    """question_id -> {expected_answer, should_refuse}."""
    path = RESULTS_DIR / "test_questions.csv"
    lookup: Dict[str, Dict[str, str]] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            lookup[row["question_id"]] = {
                "expected_answer": row.get("expected_answer_summary", ""),
                "should_refuse": str(row.get("should_refuse", "False")),
            }
    return lookup


def load_results(mode: str) -> List[Dict[str, str]]:
    """Load one mode's result CSV as list of dicts."""
    path = RESULTS_DIR / f"results_{mode}.csv"
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build_prompt(template: str, question: str, expected: str, should_refuse: str, answer: str) -> str:
    """Fill prompt template. Uses str.replace so we don't choke on JSON braces in the prompt."""
    return (
        template
        .replace("{question}", question)
        .replace("{expected_answer}", expected)
        .replace("{should_refuse}", should_refuse)
        .replace("{answer}", answer)
    )


_JSON_RE = re.compile(r"\{[^{}]*\}", re.DOTALL)


def parse_judge_response(text: str) -> Optional[Dict]:
    """Extract the JSON object from the LLM response. Tolerant to leading/trailing prose."""
    candidate = text.strip()
    # Try whole-string first.
    try:
        return json.loads(candidate)
    except Exception:
        pass
    # Fall back: find the first {...} block.
    m = _JSON_RE.search(candidate)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def clamp_score(v) -> Optional[int]:
    """Coerce to int 1-10, else None."""
    try:
        i = int(round(float(v)))
        if 1 <= i <= 10:
            return i
        return max(1, min(10, i))
    except Exception:
        return None


def judge_one(client, prompt_template: str, mode: str, row: Dict, test_lookup: Dict, max_retries: int = 3) -> Dict:
    """Run the judge on a single (mode, question) and return a row for the output CSV."""
    qid = row["question_id"]
    test_meta = test_lookup.get(qid, {})
    prompt = build_prompt(
        prompt_template,
        question=row.get("question", ""),
        expected=test_meta.get("expected_answer", ""),
        should_refuse=test_meta.get("should_refuse", "False"),
        answer=row.get("answer", ""),
    )

    last_err = ""
    for attempt in range(max_retries + 1):
        try:
            raw = client.generate(
                prompt=prompt,
                system="You are a strict, impartial RAG evaluator. Reply with JSON only.",
                temperature=0.0,
                max_tokens=300,
            )
            parsed = parse_judge_response(raw)
            if parsed is None:
                last_err = f"unparseable response: {raw[:120]}"
                continue
            return {
                "mode": mode,
                "question_id": qid,
                "category": row.get("category", ""),
                "question": row.get("question", ""),
                "correctness": clamp_score(parsed.get("correctness")),
                "helpfulness": clamp_score(parsed.get("helpfulness")),
                "citation_accuracy": clamp_score(parsed.get("citation_accuracy")),
                "justification": str(parsed.get("justification", ""))[:300],
                "raw_response": raw[:500],
                "error": "",
            }
        except Exception as e:
            last_err = str(e)
            err_str = last_err
            if "429" in err_str or "quota" in err_str.lower() or "rate" in err_str.lower():
                # Per-minute window is 60s — wait > 60s so the window fully clears.
                wait = 70 + attempt * 30
                print(f"      rate-limited, sleeping {wait}s for per-minute window to clear...")
                time.sleep(wait)
            else:
                time.sleep(2)
    # Failed all retries
    return {
        "mode": mode,
        "question_id": qid,
        "category": row.get("category", ""),
        "question": row.get("question", ""),
        "correctness": None,
        "helpfulness": None,
        "citation_accuracy": None,
        "justification": "",
        "raw_response": "",
        "error": last_err,
    }


def load_existing_scores() -> Dict:
    """Load already-scored rows so we can skip them. Returns dict keyed by (mode, question_id)."""
    if not OUT_PATH.exists():
        return {}
    existing = {}
    with open(OUT_PATH, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            # Only treat as 'done' if it has a real correctness score
            if r.get("correctness") and r["correctness"] not in ("", "None"):
                existing[(r["mode"], r["question_id"])] = r
    return existing


def print_summary(rows: List[Dict]) -> None:
    """Print per-mode averages."""
    print("\n" + "=" * 70)
    print("LLM-AS-JUDGE SUMMARY (1-10 scale, higher is better)")
    print("=" * 70)
    by_mode: Dict[str, List[Dict]] = {}
    for r in rows:
        by_mode.setdefault(r["mode"], []).append(r)

    metrics = ["correctness", "helpfulness", "citation_accuracy"]
    header = f"{'Metric':<22}" + "".join(f"{m:^18}" for m in MODES)
    print(header)
    print("-" * len(header))
    for metric in metrics:
        line = f"{metric:<22}"
        for m in MODES:
            vals = [r[metric] for r in by_mode.get(m, []) if r.get(metric) is not None]
            avg = sum(vals) / len(vals) if vals else 0.0
            line += f"{avg:^18.2f}"
        print(line)

    print("\nValid rows per mode:")
    for m in MODES:
        valid = sum(1 for r in by_mode.get(m, []) if r.get("correctness") is not None)
        total = len(by_mode.get(m, []))
        print(f"  {m:<14}  {valid}/{total}")


def main() -> int:
    parser = argparse.ArgumentParser(description="LLM-as-Judge evaluation")
    parser.add_argument("--modes", nargs="+", default=MODES, choices=MODES,
                        help="Subset of modes to judge")
    parser.add_argument("--force", action="store_true",
                        help="Wipe llm_judge_scores.csv and re-judge everything")
    parser.add_argument("--resume", action="store_true",
                        help="Keep existing scored rows; only re-judge failures and missing rows")
    parser.add_argument("--limit", type=int, default=0,
                        help="Optional cap on questions per mode (for smoke tests)")
    parser.add_argument("--delay", type=float, default=5.0,
                        help="Seconds to sleep between successful requests (default 5s for free-tier RPM)")
    args = parser.parse_args()

    if OUT_PATH.exists() and not args.force and not args.resume:
        print(f"[skip] {OUT_PATH} already exists.")
        print(f"       Use --resume to re-judge only failed rows, or --force to wipe and restart.")
        return 0

    existing = {} if args.force else load_existing_scores()
    if existing:
        print(f"[resume] Found {len(existing)} already-scored rows; will skip those.")

    print(f"Loading LLM client (provider auto-detected from .env)...")
    client = get_llm_client()
    print(f"  provider={client.provider}  model={client.model}")

    prompt_template = load_prompt(PROMPT_NAME)
    test_lookup = load_test_questions()

    fieldnames = [
        "mode", "question_id", "category", "question",
        "correctness", "helpfulness", "citation_accuracy",
        "justification", "raw_response", "error",
    ]

    def flush(rows: List[Dict]) -> None:
        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    all_rows: List[Dict] = []
    for mode in args.modes:
        results = load_results(mode)
        if args.limit:
            results = results[: args.limit]
        print(f"\nJudging {len(results)} responses for mode={mode}")
        for i, row in enumerate(results, 1):
            key = (mode, row.get("question_id", ""))
            if key in existing:
                scored = existing[key]
                for k in ("correctness", "helpfulness", "citation_accuracy"):
                    scored[k] = clamp_score(scored.get(k)) if scored.get(k) not in ("", "None", None) else None
                print(f"  [{i:>2}/{len(results)}] {key[1]:<3} (cached) corr={scored.get('correctness')}")
                all_rows.append(scored)
            else:
                scored = judge_one(client, prompt_template, mode, row, test_lookup)
                ok = scored.get("correctness") is not None
                print(
                    f"  [{i:>2}/{len(results)}] {row.get('question_id'):<3} "
                    f"corr={scored.get('correctness')} help={scored.get('helpfulness')} "
                    f"cite={scored.get('citation_accuracy')}  {'' if ok else '(failed)'}"
                )
                all_rows.append(scored)
                flush(all_rows)  # incremental save in case we get rate-limited mid-run
                if ok and args.delay > 0:
                    time.sleep(args.delay)

    flush(all_rows)
    print(f"\nWrote {len(all_rows)} judge rows to {OUT_PATH}")

    print_summary(all_rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
