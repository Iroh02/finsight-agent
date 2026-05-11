"""3-way evaluation script: Naive RAG vs Agentic RAG vs Multi-Agent RAG.

Runs all test questions through all 3 modes and produces a comparison.
"""

import csv
import time
import argparse
from pathlib import Path
from typing import Dict, List


def load_test_questions(csv_path: str = "./evaluation/test_questions.csv") -> List[Dict]:
    """Load test questions from CSV."""
    questions = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        questions = list(reader)
    return questions


def query_endpoint(question: str, mode: str, api_url: str = "http://127.0.0.1:8001") -> Dict:
    """Query the FastAPI endpoint."""
    import requests

    response = requests.post(
        f"{api_url}/query",
        json={"question": question, "mode": mode},
        timeout=180,
    )
    response.raise_for_status()
    return response.json()


def score_response(response: Dict, expected_refuse: bool) -> Dict:
    """
    Score a single response.

    Returns rubric scores (0-1 scale for most):
    - relevance: did it address the question
    - faithfulness: was it grounded in retrieved chunks
    - has_citations: 1 if citations present, 0 otherwise
    - correct_abstention: 1 if should-refuse and did refuse, else 0
    """
    answer = response.get("answer", "")
    decision = response.get("decision", "")
    confidence = response.get("confidence", 0.0)
    citations = response.get("citations", [])
    chunks = response.get("chunks", [])

    # Heuristic scoring (manual scoring would be better but this gives a baseline)

    # 1. Relevance: does the answer mention key entities from the question
    relevance = min(1.0, len(answer) / 300) if answer else 0.0  # Length-based proxy

    # 2. Faithfulness: heuristic - if has citations and decision is ANSWER, high
    if decision == "ANSWER" and len(citations) > 0:
        faithfulness = min(1.0, 0.5 + 0.1 * len(citations))
    elif decision == "REFUSE":
        faithfulness = 1.0 if expected_refuse else 0.5
    else:
        faithfulness = 0.5

    # 3. Has citations
    has_citations = 1 if len(citations) > 0 else 0

    # 4. Correct abstention
    if expected_refuse:
        correct_abstention = 1 if decision == "REFUSE" else 0
    else:
        correct_abstention = 1 if decision != "REFUSE" else 0

    return {
        "relevance": round(relevance, 3),
        "faithfulness": round(faithfulness, 3),
        "has_citations": has_citations,
        "correct_abstention": correct_abstention,
        "confidence": round(confidence, 3),
        "decision": decision,
        "num_chunks": len(chunks),
        "answer_length": len(answer),
    }


def evaluate_single(question_row: Dict, mode: str, api_url: str) -> Dict:
    """Evaluate a single question in a single mode."""
    q_id = question_row["question_id"]
    q_text = question_row["question"]
    should_refuse = question_row.get("should_refuse", "False").lower() == "true"

    start = time.time()
    try:
        response = query_endpoint(q_text, mode, api_url)
        elapsed = time.time() - start

        scores = score_response(response, should_refuse)

        return {
            "question_id": q_id,
            "category": question_row.get("category", ""),
            "question": q_text,
            "mode": mode,
            "answer": response.get("answer", "")[:200],
            "decision": response.get("decision", ""),
            "execution_time_s": round(elapsed, 2),
            **scores,
            "error": "",
        }
    except Exception as e:
        elapsed = time.time() - start
        return {
            "question_id": q_id,
            "category": question_row.get("category", ""),
            "question": q_text,
            "mode": mode,
            "answer": f"ERROR: {e}",
            "decision": "ERROR",
            "execution_time_s": round(elapsed, 2),
            "relevance": 0,
            "faithfulness": 0,
            "has_citations": 0,
            "correct_abstention": 0,
            "confidence": 0,
            "num_chunks": 0,
            "answer_length": 0,
            "error": str(e),
        }


def run_evaluation(
    modes: List[str],
    questions_csv: str = "./evaluation/test_questions.csv",
    output_dir: str = "./evaluation",
    api_url: str = "http://127.0.0.1:8001",
):
    """Run full evaluation across all modes."""
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    questions = load_test_questions(questions_csv)
    print(f"\nLoaded {len(questions)} test questions")
    print(f"Running modes: {modes}\n")

    all_results = {mode: [] for mode in modes}

    for i, q in enumerate(questions, 1):
        print(f"\n[{i}/{len(questions)}] {q['question'][:70]}")
        for mode in modes:
            print(f"  {mode}...", end=" ", flush=True)
            result = evaluate_single(q, mode, api_url)
            all_results[mode].append(result)
            print(f"[{result['decision']}] {result['execution_time_s']}s")

    # Save per-mode CSVs
    print("\n" + "=" * 70)
    print("SAVING RESULTS")
    print("=" * 70)
    for mode, results in all_results.items():
        out_file = output_path / f"results_{mode}.csv"
        if results:
            keys = results[0].keys()
            with open(out_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                writer.writerows(results)
            print(f"  Saved: {out_file}")

    # Print summary
    print("\n" + "=" * 70)
    print("SUMMARY (averages across all questions)")
    print("=" * 70)
    print(f"{'Metric':<25} | " + " | ".join(f"{m:^16}" for m in modes))
    print("-" * (28 + 19 * len(modes)))

    metrics = ["relevance", "faithfulness", "has_citations", "correct_abstention", "confidence", "execution_time_s"]
    for metric in metrics:
        row = [f"{metric:<25}"]
        for mode in modes:
            results = all_results[mode]
            if not results:
                row.append(f"{'N/A':^16}")
                continue
            avg = sum(r.get(metric, 0) for r in results) / len(results)
            row.append(f"{avg:^16.3f}")
        print(" | ".join(row))

    print("\nEvaluation complete!")
    return all_results


def main():
    parser = argparse.ArgumentParser(description="3-way RAG Evaluation")
    parser.add_argument(
        "--modes",
        nargs="+",
        default=["naive", "agentic", "multi_agent"],
        choices=["naive", "agentic", "multi_agent"],
    )
    parser.add_argument("--questions", default="./evaluation/test_questions.csv")
    parser.add_argument("--output-dir", default="./evaluation")
    parser.add_argument("--api-url", default="http://127.0.0.1:8001")
    parser.add_argument(
        "--mode",
        help="Shortcut for single mode (use --modes for multiple)",
    )

    args = parser.parse_args()

    # Handle --mode shortcut
    modes = [args.mode] if args.mode else args.modes
    if "all" in modes:
        modes = ["naive", "agentic", "multi_agent"]

    print(f"Running 3-way evaluation")
    print(f"  Modes: {modes}")
    print(f"  Questions file: {args.questions}")
    print(f"  API URL: {args.api_url}")

    # Check API is reachable
    try:
        import requests
        resp = requests.get(f"{args.api_url}/health", timeout=5)
        resp.raise_for_status()
        print(f"  API is reachable [OK]")
    except Exception as e:
        print(f"\n[ERROR] Cannot reach API at {args.api_url}")
        print(f"  Make sure server is running:")
        print(f"  uvicorn app.main:app --host 127.0.0.1 --port 8001")
        return

    run_evaluation(modes, args.questions, args.output_dir, args.api_url)


if __name__ == "__main__":
    main()
