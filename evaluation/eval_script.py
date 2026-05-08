"""Evaluation script for RAG system comparison."""

import csv
import json
import time
from pathlib import Path
from typing import Dict, List

import pandas as pd


class RAGEvaluator:
    """Evaluate RAG system performance."""

    def __init__(self, pipeline, output_dir: str = "./evaluation"):
        """
        Initialize evaluator.

        Args:
            pipeline: RAGPipeline instance
            output_dir: Output directory for results
        """
        self.pipeline = pipeline
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    def load_test_questions(self, csv_path: str = "./evaluation/test_questions.csv") -> List[Dict]:
        """Load test questions from CSV."""
        questions = []
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            questions = list(reader)
        return questions

    def evaluate(self, mode: str = "both") -> Dict:
        """
        Run evaluation on all test questions.

        Args:
            mode: "agentic", "naive", or "both"

        Returns:
            Evaluation results dictionary
        """
        questions = self.load_test_questions()

        results = {
            "agentic": [],
            "naive": [],
        }

        print(f"Starting evaluation with {len(questions)} questions...")

        for i, q in enumerate(questions, 1):
            print(f"\n[{i}/{len(questions)}] {q['question'][:60]}...")

            # Evaluate agentic RAG
            if mode in ["agentic", "both"]:
                agentic_result = self._evaluate_single(q, "agentic")
                results["agentic"].append(agentic_result)

            # Evaluate naive RAG
            if mode in ["naive", "both"]:
                naive_result = self._evaluate_single(q, "naive")
                results["naive"].append(naive_result)

        # Save results
        self._save_results(results)

        # Print summary
        self._print_summary(results)

        return results

    def _evaluate_single(self, question: Dict, mode: str) -> Dict:
        """Evaluate a single question."""
        q_id = question["question_id"]
        q_text = question["question"]
        should_refuse = question["should_refuse"].lower() == "true"

        try:
            # Query the system
            start = time.time()
            response = self.pipeline.query(q_text, mode=mode)
            elapsed = time.time() - start

            # Score the response
            scores = self._score_response(response, should_refuse)

            return {
                "question_id": q_id,
                "question": q_text,
                "mode": mode,
                "answer": response.get("answer", ""),
                "decision": response.get("decision", ""),
                "confidence": response.get("confidence", 0.0),
                "execution_time_s": elapsed,
                **scores,
            }
        except Exception as e:
            print(f"Error evaluating {q_id}: {e}")
            return {
                "question_id": q_id,
                "question": q_text,
                "mode": mode,
                "answer": f"ERROR: {str(e)}",
                "decision": "ERROR",
                "confidence": 0.0,
                "execution_time_s": 0,
                "relevance_score": 0,
                "faithfulness_score": 0,
                "citation_accuracy": 0,
                "correct_abstention": 0,
            }

    def _score_response(self, response: Dict, should_refuse: bool) -> Dict:
        """
        Score a response.

        TODO: Implement manual scoring logic or use RAGAS-style metrics
        """
        return {
            "relevance_score": 0,  # 1-5 scale
            "faithfulness_score": 0,  # 1-5 scale
            "citation_accuracy": 0,  # 0-1
            "correct_abstention": 1 if should_refuse and response.get("decision") == "REFUSE" else 0,
        }

    def _save_results(self, results: Dict) -> None:
        """Save evaluation results to CSV."""
        for mode, data in results.items():
            if data:
                df = pd.DataFrame(data)
                output_path = self.output_dir / f"results_{mode}.csv"
                df.to_csv(output_path, index=False)
                print(f"Saved {mode} results to {output_path}")

    def _print_summary(self, results: Dict) -> None:
        """Print evaluation summary."""
        print("\n" + "="*60)
        print("EVALUATION SUMMARY")
        print("="*60)

        for mode, data in results.items():
            if not data:
                continue

            df = pd.DataFrame(data)
            print(f"\n{mode.upper()} RAG:")
            print(f"  Total questions: {len(df)}")
            print(f"  Avg answer relevance: {df.get('relevance_score', [0]).mean():.2f}")
            print(f"  Avg faithfulness: {df.get('faithfulness_score', [0]).mean():.2f}")
            print(f"  Avg confidence: {df.get('confidence', [0]).mean():.2f}")
            print(f"  Avg execution time: {df.get('execution_time_s', [0]).mean():.3f}s")

        print("\n" + "="*60)


def main():
    """CLI for evaluation."""
    import argparse

    parser = argparse.ArgumentParser(description="Evaluate RAG System")
    parser.add_argument("--mode", choices=["agentic", "naive", "both"], default="both")
    parser.add_argument("--questions", default="./evaluation/test_questions.csv")

    args = parser.parse_args()

    # TODO: Initialize pipeline
    # from src.pipeline import RAGPipeline
    # pipeline = RAGPipeline()

    # evaluator = RAGEvaluator(pipeline)
    # evaluator.evaluate(mode=args.mode)


if __name__ == "__main__":
    main()
