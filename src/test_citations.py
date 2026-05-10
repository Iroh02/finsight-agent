"""Test script for citation extraction."""

from src.citations import CitationExtractor
from src.test_naive_rag import MockRetriever


def test_citations():
    """Test citation extraction with mock data."""
    print("=" * 70)
    print("Testing Citation Extraction")
    print("=" * 70)

    # Get mock chunks
    retriever = MockRetriever()
    chunks = retriever.retrieve("any query", k=5)

    # Sample answer that uses info from multiple chunks
    sample_answer = (
        "Apple Inc. reported total net sales of $394.3 billion for fiscal year 2023, "
        "a 3% decrease from the prior year. The CEO is Tim Cook, who has held the "
        "position since August 2011. R&D expenses increased to $29.9 billion in 2023, "
        "up from $26.3 billion in 2022."
    )

    # Test 1: Simple extraction (no LLM)
    print("\n--- TEST 1: Simple Extraction (no LLM) ---")
    extractor_simple = CitationExtractor(use_llm=False)
    citations_simple = extractor_simple.extract_citations(sample_answer, chunks)

    print(f"\nFound {len(citations_simple)} citation(s):")
    for i, citation in enumerate(citations_simple, 1):
        print(f"\n  [{i}] Source: {citation['source']}")
        print(f"      Page: {citation['page']}")
        print(f"      Excerpt: {citation['excerpt'][:80]}...")
        print(f"      Chunk Index: {citation['chunk_index']}")

    print("\n--- Formatted Citations ---")
    print(extractor_simple.format_citations(citations_simple))

    # Test 2: Smart extraction (with LLM)
    print("\n\n--- TEST 2: Smart Extraction (with LLM) ---")
    try:
        extractor_smart = CitationExtractor(use_llm=True)
        citations_smart = extractor_smart.extract_citations(sample_answer, chunks)

        print(f"\nFound {len(citations_smart)} citation(s):")
        for i, citation in enumerate(citations_smart, 1):
            print(f"\n  [{i}] Source: {citation['source']}")
            print(f"      Page: {citation['page']}")
            print(f"      Excerpt: {citation['excerpt'][:80]}...")
    except Exception as e:
        print(f"[ERROR] Smart extraction failed: {e}")

    # Test 3: Empty chunks
    print("\n\n--- TEST 3: Empty Chunks (REFUSE case) ---")
    citations_empty = extractor_simple.extract_citations("No info available.", [])
    print(f"Citations for empty chunks: {len(citations_empty)} (expected: 0)")

    # Test 4: Deduplication (same source, same page)
    print("\n--- TEST 4: Deduplication ---")
    duplicate_chunks = [
        {"text": "First info", "source": "Apple_2023.pdf", "page": 34},
        {"text": "Same source, same page", "source": "Apple_2023.pdf", "page": 34},
        {"text": "Different page", "source": "Apple_2023.pdf", "page": 71},
        {"text": "Different doc", "source": "Microsoft_2023.pdf", "page": 5},
    ]
    citations_dedup = extractor_simple.extract_citations("test answer", duplicate_chunks)
    print(f"Input: 4 chunks (with 1 duplicate)")
    print(f"Output: {len(citations_dedup)} citations (expected: 3 after dedup)")
    for c in citations_dedup:
        print(f"  - {c['source']}, Page {c['page']}")

    print("\n" + "=" * 70)
    print("Citation tests complete!")
    print("=" * 70)


if __name__ == "__main__":
    test_citations()
