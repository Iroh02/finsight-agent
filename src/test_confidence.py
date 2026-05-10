"""Test script for confidence scoring."""

from src.confidence import ConfidenceScorer
from src.test_naive_rag import MockRetriever


def test_confidence():
    """Test confidence scoring with various scenarios."""
    print("=" * 70)
    print("Testing Confidence Scoring")
    print("=" * 70)

    # Get mock chunks
    retriever = MockRetriever()
    chunks_5 = retriever.retrieve("any query", k=5)
    chunks_3 = retriever.retrieve("any query", k=3)

    # Initialize heuristic scorer
    scorer = ConfidenceScorer(use_heuristic=True)

    # Test cases: (description, answer, chunks, decision, expected_range)
    test_cases = [
        {
            "name": "Strong ANSWER (5 chunks, factual)",
            "answer": "Apple's revenue was $394.3B in 2023 (Source: Apple_2023_10K.pdf, Page 34).",
            "chunks": chunks_5,
            "decision": "ANSWER",
            "expected_min": 0.7,
        },
        {
            "name": "Weak ANSWER (3 chunks, hedging)",
            "answer": "Apple's revenue may be around $394B but I'm not sure.",
            "chunks": chunks_3,
            "decision": "ANSWER",
            "expected_max": 0.7,
        },
        {
            "name": "RETRIEVE (had to expand)",
            "answer": "Found something after expanding search.",
            "chunks": chunks_5,
            "decision": "RETRIEVE",
            "expected_min": 0.4,
            "expected_max": 0.7,
        },
        {
            "name": "CLARIFY (vague question)",
            "answer": "Please rephrase your question.",
            "chunks": [],
            "decision": "CLARIFY",
            "expected_max": 0.2,
        },
        {
            "name": "REFUSE (no info)",
            "answer": "I cannot answer this question.",
            "chunks": [],
            "decision": "REFUSE",
            "expected_max": 0.0,
        },
        {
            "name": "ANSWER with citations",
            "answer": "According to the report, Apple had $394.3B in revenue (Source: Apple_2023.pdf, Page 34).",
            "chunks": chunks_5,
            "decision": "ANSWER",
            "expected_min": 0.7,
        },
    ]

    results = []
    for tc in test_cases:
        score = scorer.score(
            answer=tc["answer"],
            chunks=tc["chunks"],
            decision=tc["decision"],
        )
        level = scorer.get_confidence_level(score)
        color = scorer.get_color(score)

        # Check expectations
        passed = True
        if "expected_min" in tc and score < tc["expected_min"]:
            passed = False
        if "expected_max" in tc and score > tc["expected_max"]:
            passed = False

        status = "[PASS]" if passed else "[FAIL]"
        results.append((tc["name"], score, level, status))

        print(f"\n{status} {tc['name']}")
        print(f"  Decision: {tc['decision']}")
        print(f"  Chunks: {len(tc['chunks'])}")
        print(f"  Answer: {tc['answer'][:70]}...")
        print(f"  Score: {score} ({level}, {color})")
        if "expected_min" in tc:
            print(f"  Expected: >= {tc['expected_min']}")
        if "expected_max" in tc:
            print(f"  Expected: <= {tc['expected_max']}")

    # LLM-assisted test
    print("\n\n--- LLM-Assisted Confidence Test ---")
    try:
        scorer_llm = ConfidenceScorer(use_heuristic=False)
        score_llm = scorer_llm.score(
            answer="Apple's revenue was $394.3B in 2023 according to the annual report.",
            chunks=chunks_5,
            decision="ANSWER",
            question="What was Apple's revenue?",
        )
        level_llm = scorer_llm.get_confidence_level(score_llm)
        print(f"LLM-assessed confidence: {score_llm} ({level_llm})")
    except Exception as e:
        print(f"LLM scoring failed (expected if no API key): {e}")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    passed = sum(1 for r in results if r[3] == "[PASS]")
    print(f"Passed: {passed}/{len(results)}")
    for name, score, level, status in results:
        print(f"  {status} {name:50} | Score: {score:.2f} | Level: {level}")

    print("\n" + "=" * 70)
    print("Confidence tests complete!")
    print("=" * 70)


if __name__ == "__main__":
    test_confidence()
