"""Test self-reflection critic on various answer scenarios."""

from src.self_reflection import SelfReflectionCritic
from src.test_naive_rag import MockRetriever


def test_self_reflection():
    """Test self-reflection on supported and unsupported answers."""
    print("=" * 70)
    print("Testing Self-Reflection Critic (Self-RAG style)")
    print("=" * 70)

    critic = SelfReflectionCritic()
    retriever = MockRetriever()
    chunks = retriever.retrieve("any", k=5)

    test_cases = [
        {
            "name": "FULLY SUPPORTED ANSWER",
            "question": "What was Apple's revenue in 2023?",
            "answer": "Apple's total net sales were $394.3 billion in fiscal year 2023, a 3% decrease from the prior year.",
            "expected_supported": True,
        },
        {
            "name": "PARTIALLY SUPPORTED (extra claim)",
            "question": "What was Apple's revenue?",
            "answer": "Apple's total net sales were $394.3 billion in 2023. The company also acquired Twitter for $44 billion.",  # Twitter claim is hallucinated
            "expected_supported": False,
        },
        {
            "name": "UNSUPPORTED HALLUCINATION",
            "question": "Who is the CFO?",
            "answer": "Apple's CFO is Sarah Johnson, who joined in 2020.",  # Made up - not in chunks
            "expected_supported": False,
        },
        {
            "name": "WELL-CITED ANSWER",
            "question": "Who is the CEO?",
            "answer": "Tim Cook is the CEO of Apple Inc., having held the position since August 2011.",
            "expected_supported": True,
        },
    ]

    for tc in test_cases:
        print(f"\n{'=' * 70}")
        print(f"TEST: {tc['name']}")
        print('=' * 70)
        print(f"Question: {tc['question']}")
        print(f"Answer: {tc['answer']}")

        critique = critic.reflect(
            question=tc["question"],
            answer=tc["answer"],
            chunks=chunks,
        )

        print(f"\n[CRITIQUE]")
        print(f"  Supported: {critique['support_level']} (score: {critique['support_score']})")
        print(f"  Suggested confidence: {critique['suggested_confidence']}")
        if critique["issues"]:
            print(f"  Issues:")
            for issue in critique["issues"]:
                print(f"    - {issue}")

        # Test confidence adjustment
        original_confidence = 0.85
        adjusted = critic.adjust_confidence(original_confidence, critique)
        print(f"\n[CONFIDENCE ADJUSTMENT]")
        print(f"  Original: {original_confidence:.2f}")
        print(f"  Adjusted: {adjusted:.2f}")

        # Check expected
        match = critique["is_supported"] == tc["expected_supported"]
        print(f"\n[RESULT] {'[PASS]' if match else '[FAIL]'} Expected supported={tc['expected_supported']}")

    print("\n" + "=" * 70)
    print("Self-reflection tests complete!")
    print("=" * 70)


if __name__ == "__main__":
    test_self_reflection()
