"""Quick test script for naive RAG (use before vector store is ready)."""

from src.naive_rag import NaiveRAG
from src.llm_client import get_llm_client


class MockRetriever:
    """Mock retriever for testing without vector store."""

    def __init__(self, mock_chunks=None):
        self.mock_chunks = mock_chunks or self._default_chunks()

    def retrieve(self, query, k=5):
        """Return mock chunks for any query."""
        return self.mock_chunks[:k]

    @staticmethod
    def _default_chunks():
        """Sample chunks for testing."""
        return [
            {
                "text": "Apple Inc. reported total net sales of $394.3 billion for fiscal year 2023, "
                        "representing a 3% decrease from the prior year's $394.3 billion. "
                        "iPhone sales remained the largest revenue contributor at $200.6 billion.",
                "source": "Apple_2023_10K.pdf",
                "page": 34,
                "score": 0.92,
            },
            {
                "text": "The company's research and development expenses increased to $29.9 billion in fiscal 2023, "
                        "up from $26.3 billion in fiscal 2022. This represents an increase of approximately 14%.",
                "source": "Apple_2023_10K.pdf",
                "page": 47,
                "score": 0.88,
            },
            {
                "text": "Tim Cook serves as Chief Executive Officer of Apple Inc. He was appointed CEO in August 2011. "
                        "Under his leadership, Apple has continued to expand globally.",
                "source": "Apple_2023_10K.pdf",
                "page": 12,
                "score": 0.85,
            },
            {
                "text": "Apple Inc. is headquartered in Cupertino, California. The company designs, manufactures, "
                        "and markets smartphones, personal computers, tablets, wearables, and accessories.",
                "source": "Apple_2023_10K.pdf",
                "page": 5,
                "score": 0.82,
            },
            {
                "text": "Key risk factors include macroeconomic conditions, supply chain disruptions, "
                        "competition in highly competitive markets, dependence on key suppliers, "
                        "and regulatory and legal proceedings.",
                "source": "Apple_2023_10K.pdf",
                "page": 18,
                "score": 0.78,
            },
        ]


def test_naive_rag():
    """Test naive RAG with mock data."""
    print("=" * 60)
    print("Testing Naive RAG with Mock Data")
    print("=" * 60)

    # Initialize with mock retriever
    retriever = MockRetriever()
    llm = get_llm_client()
    rag = NaiveRAG(retriever, llm)

    # Test questions
    test_questions = [
        "What was Apple's total revenue in fiscal 2023?",
        "Who is the CEO of Apple?",
        "How did R&D spending change between 2022 and 2023?",
        "What are the key risk factors mentioned?",
    ]

    for question in test_questions:
        print(f"\n[QUESTION] {question}")
        print("-" * 60)

        try:
            result = rag.query(question, k=3)
            print(f"[ANSWER] {result['answer']}")
            print(f"[CHUNKS RETRIEVED] {len(result['chunks'])}")
            print(f"[DECISION] {result['decision']}")
        except Exception as e:
            print(f"[ERROR] {e}")
            print("Tip: Make sure your .env has OPENAI_API_KEY or ANTHROPIC_API_KEY set.")

    print("\n" + "=" * 60)
    print("Test complete!")
    print("=" * 60)


if __name__ == "__main__":
    test_naive_rag()
