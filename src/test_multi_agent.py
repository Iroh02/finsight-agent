"""Test the Multi-Agent RAG system end-to-end."""

from src.multi_agent import MultiAgentOrchestrator
from src.vectorstore import get_vectorstore
from src.retriever import Retriever
from src.llm_client import get_llm_client


def test_multi_agent():
    """Test multi-agent orchestrator on various question types."""
    print("=" * 70)
    print("Testing Multi-Agent RAG System")
    print("=" * 70)

    # Initialize
    vs = get_vectorstore()
    stats = vs.get_stats()
    if stats.get("count", 0) == 0:
        print("\n[ERROR] Vector store empty. Run: python -m src.test_pipeline")
        return

    print(f"\nVector store: {stats['count']} chunks indexed")

    retriever = Retriever(vs, use_reranker=True)
    llm = get_llm_client()
    orchestrator = MultiAgentOrchestrator(retriever, llm)

    # Test cases - mix of simple and complex
    test_cases = [
        {
            "name": "SIMPLE Q (should fall back to single-agent)",
            "question": "What is the project about?",
            "expected_strategy": "SINGLE_AGENT",
        },
        {
            "name": "COMPARISON Q (multi-agent expected)",
            "question": "Compare Project 1 and Project 3 in terms of difficulty and deliverables",
            "expected_strategy": "MULTI_AGENT",
        },
        {
            "name": "MULTI-PART Q (multi-agent expected)",
            "question": "What deliverables does Project 1 require and how is the work distributed?",
            "expected_strategy": "MULTI_AGENT",
        },
    ]

    for i, tc in enumerate(test_cases, 1):
        print(f"\n{'=' * 70}")
        print(f"TEST {i}: {tc['name']}")
        print(f"{'=' * 70}")
        print(f"Question: {tc['question']}")

        try:
            result = orchestrator.query(tc["question"], k=3)
            trace = result.get("multi_agent_trace", {})

            # Display results
            print(f"\n[PLANNER DECISION] {trace.get('planner_decision')}")
            print(f"[COMPLEXITY] {trace.get('complexity_score', '?')}/5")
            print(f"[REASONING] {trace.get('planner_reasoning', '')[:150]}")

            sub_queries = trace.get("sub_queries", [])
            if sub_queries:
                print(f"\n[SUB-QUERIES] {len(sub_queries)}")
                for j, sub in enumerate(sub_queries, 1):
                    print(f"  Q{j}: {sub.get('question', '')[:80]}")
                    print(f"  A{j}: {sub.get('answer', '')[:120]}...")

            print(f"\n[FINAL ANSWER]")
            print(f"  {result.get('answer', '')[:300]}")

            print(f"\n[DECISION] {result.get('decision')}")
            print(f"[CONFIDENCE] {result.get('confidence', 0)}")

            validation = trace.get("validation_report", {})
            if validation:
                print(f"\n[VALIDATION]")
                print(f"  Score: {validation.get('validation_score', '?')}")
                print(f"  Supported: {validation.get('supported', '?')}")
                if validation.get("issues"):
                    print(f"  Issues:")
                    for issue in validation["issues"]:
                        print(f"    - {issue}")

            timing = trace.get("execution_time_per_agent", {})
            if timing:
                print(f"\n[TIMING]")
                for agent, t in timing.items():
                    print(f"  {agent}: {t}s")

            # Verify strategy matches expectation
            actual = trace.get("planner_decision", "")
            expected = tc["expected_strategy"]
            match = expected in actual
            print(f"\n[RESULT] {'[PASS]' if match else '[FAIL]'} Expected: {expected}, Got: {actual}")

        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"\n[ERROR] {e}")

    print("\n" + "=" * 70)
    print("Multi-Agent Tests Complete!")
    print("=" * 70)


if __name__ == "__main__":
    test_multi_agent()
