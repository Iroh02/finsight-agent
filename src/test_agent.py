"""Test script for agentic RAG router."""

from src.agent import AgenticRouter
from src.test_naive_rag import MockRetriever
from src.llm_client import get_llm_client


def test_agentic_router():
    """Test the agentic router with various question types."""
    print("=" * 70)
    print("Testing Agentic RAG Router (4-State Decision Layer)")
    print("=" * 70)

    # Initialize
    retriever = MockRetriever()
    llm = get_llm_client()
    agent = AgenticRouter(retriever, llm)

    # Test questions designed to trigger different states
    test_cases = [
        {
            "question": "What was Apple's total revenue in fiscal 2023?",
            "expected_decision": "ANSWER",
            "why": "Direct fact in chunks",
        },
        {
            "question": "Who is the CEO of Apple?",
            "expected_decision": "ANSWER",
            "why": "Tim Cook info is in chunks",
        },
        {
            "question": "What is Apple's stock price right now?",
            "expected_decision": "REFUSE",
            "why": "Real-time data not in static documents",
        },
        {
            "question": "Tell me about that thing.",
            "expected_decision": "CLARIFY",
            "why": "Question is too vague",
        },
        {
            "question": "What did Tim Cook eat for breakfast?",
            "expected_decision": "REFUSE",
            "why": "Out of scope - not in business documents",
        },
    ]

    results = []
    for i, tc in enumerate(test_cases, 1):
        print(f"\n{'=' * 70}")
        print(f"TEST {i}: {tc['question']}")
        print(f"Expected: {tc['expected_decision']} ({tc['why']})")
        print(f"{'=' * 70}")

        try:
            response = agent.route_and_answer(tc["question"], k=3)

            decision = response.get("decision", "ERROR")
            reason = response.get("reason", "")
            answer = response.get("answer", "")
            chunks_count = len(response.get("chunks", []))

            # Display results
            print(f"\n[DECISION] {decision}")
            print(f"[REASON] {reason}")
            print(f"[CHUNKS] {chunks_count}")
            print(f"[ANSWER] {answer[:200]}{'...' if len(answer) > 200 else ''}")

            # Check if expected
            match = "[PASS] MATCHES" if decision == tc["expected_decision"] else "[FAIL] DIFFERENT"
            print(f"\n[RESULT] {match} expected ({tc['expected_decision']})")

            results.append({
                "question": tc["question"],
                "expected": tc["expected_decision"],
                "actual": decision,
                "match": decision == tc["expected_decision"],
            })

        except Exception as e:
            print(f"[ERROR] {e}")
            results.append({
                "question": tc["question"],
                "expected": tc["expected_decision"],
                "actual": "ERROR",
                "match": False,
            })

    # Summary
    print(f"\n{'=' * 70}")
    print("SUMMARY")
    print(f"{'=' * 70}")
    matches = sum(1 for r in results if r["match"])
    print(f"Correct decisions: {matches}/{len(results)}")
    for r in results:
        status = "PASS" if r["match"] else "FAIL"
        print(f"  [{status}] {r['question'][:50]:50} | Expected: {r['expected']:8} | Got: {r['actual']}")

    print(f"\n{'=' * 70}")
    print("Test complete!")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    test_agentic_router()
