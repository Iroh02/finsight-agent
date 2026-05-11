"""Test reranker quality vs vanilla vector search.

Demonstrates that reranking improves retrieval quality.
"""

from src.vectorstore import get_vectorstore
from src.retriever import Retriever


def compare_retrieval():
    """Compare vector search alone vs vector search + reranker."""
    print("=" * 70)
    print("RETRIEVAL QUALITY: Vector Search vs Vector Search + Reranker")
    print("=" * 70)

    vs = get_vectorstore()
    stats = vs.get_stats()

    if stats.get("count", 0) == 0:
        print("\n[ERROR] Vector store is empty. Run: python -m src.test_pipeline first.")
        return

    print(f"\nVector store: {stats['count']} chunks indexed")

    # Two retrievers: with and without reranker
    retriever_vanilla = Retriever(vs, use_reranker=False)
    retriever_reranked = Retriever(vs, use_reranker=True, retrieve_multiplier=4)

    test_queries = [
        "What is the project deadline?",
        "How is work distributed between team members?",
        "What evaluation metrics are used?",
        "What deliverables are expected?",
    ]

    for query in test_queries:
        print(f"\n{'=' * 70}")
        print(f"QUERY: {query}")
        print('=' * 70)

        # Vanilla vector search
        print("\n[VANILLA VECTOR SEARCH] (no reranker)")
        vanilla_results = retriever_vanilla.retrieve(query, k=3)
        for i, r in enumerate(vanilla_results, 1):
            text_preview = r["text"][:120].replace("\n", " ")
            print(f"  [{i}] Score: {r.get('score', 0):.3f} | Page {r.get('page', '?')}")
            print(f"      {text_preview}...")

        # With reranker
        print("\n[WITH RERANKER] (retrieve 12 -> rerank to top 3)")
        reranked_results = retriever_reranked.retrieve(query, k=3)
        for i, r in enumerate(reranked_results, 1):
            text_preview = r["text"][:120].replace("\n", " ")
            rerank_score = r.get('rerank_score', r.get('score', 0))
            print(f"  [{i}] Rerank: {rerank_score:.3f} | Page {r.get('page', '?')}")
            print(f"      {text_preview}...")

    print("\n" + "=" * 70)
    print("Test complete!")
    print("=" * 70)


if __name__ == "__main__":
    compare_retrieval()
