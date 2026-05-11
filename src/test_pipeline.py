"""End-to-end pipeline test: PDF -> chunks -> vectors -> retrieval -> agentic RAG."""

import sys
from pathlib import Path

from src.loader import load_directory
from src.cleaner import clean_pages
from src.chunker import TextChunker
from src.vectorstore import get_vectorstore
from src.retriever import Retriever
from src.agent import AgenticRouter
from src.naive_rag import NaiveRAG
from src.citations import CitationExtractor
from src.confidence import ConfidenceScorer
from src.llm_client import get_llm_client


def test_full_pipeline():
    """Run the complete pipeline: ingest -> retrieve -> answer."""
    print("=" * 70)
    print("END-TO-END PIPELINE TEST")
    print("=" * 70)

    # Step 1: Load PDFs
    print("\n[STEP 1] Loading PDFs from data/raw/...")
    pages = load_directory("data/raw")
    if not pages:
        print("[ERROR] No PDFs found in data/raw/. Add some PDFs first!")
        return
    print(f"  Loaded {len(pages)} pages")
    print(f"  Sample text: {pages[0]['text'][:150]}...")

    # Step 2: Clean text
    print("\n[STEP 2] Cleaning text...")
    cleaned_pages = clean_pages(pages)
    print(f"  Cleaned {len(cleaned_pages)} pages")

    # Step 3: Chunk
    print("\n[STEP 3] Chunking text...")
    chunker = TextChunker(chunk_size=1000, overlap=100)
    chunks = chunker.chunk(cleaned_pages)
    print(f"  Created {len(chunks)} chunks")
    print(f"  Sample chunk size: {len(chunks[0]['text'])} chars")

    # Step 4: Set up vector store
    print("\n[STEP 4] Setting up vector store...")
    vs = get_vectorstore()

    # Clear any existing data for clean test
    print("  Clearing previous data...")
    vs.delete_all()
    vs._collection = None  # Reset collection

    # Step 5: Add chunks to vector store
    print("\n[STEP 5] Embedding and storing chunks...")
    vs.add_documents(chunks)
    print(f"  Stats: {vs.get_stats()}")

    # Step 6: Test retrieval
    print("\n[STEP 6] Testing retrieval...")
    retriever = Retriever(vs)
    test_query = "What is the project about?"
    results = retriever.retrieve(test_query, k=3)
    print(f"  Query: '{test_query}'")
    print(f"  Retrieved {len(results)} chunks:")
    for i, r in enumerate(results, 1):
        print(f"    [{i}] Score: {r.get('score', 0):.3f} | Source: {r['source']}, Page {r.get('page', '?')}")
        print(f"        Text: {r['text'][:100]}...")

    # Step 7: Test naive RAG
    print("\n[STEP 7] Testing Naive RAG...")
    llm = get_llm_client()
    naive = NaiveRAG(retriever, llm)
    naive_result = naive.query(test_query, k=3)
    print(f"  Answer: {naive_result['answer'][:200]}...")

    # Step 8: Test agentic RAG
    print("\n[STEP 8] Testing Agentic RAG...")
    agent = AgenticRouter(retriever, llm)
    agent_result = agent.route_and_answer(test_query, k=3)
    print(f"  Decision: {agent_result['decision']}")
    print(f"  Reason: {agent_result['reason']}")
    print(f"  Answer: {agent_result.get('answer', '')[:200]}...")

    # Step 9: Test citations
    print("\n[STEP 9] Testing Citations...")
    citation_ext = CitationExtractor(use_llm=False)
    citations = citation_ext.extract_citations(
        agent_result.get("answer", ""),
        agent_result.get("chunks", []),
    )
    print(f"  Found {len(citations)} citation(s)")
    for c in citations[:3]:
        print(f"    -> {c['source']}, Page {c.get('page', '?')}")

    # Step 10: Test confidence
    print("\n[STEP 10] Testing Confidence Scoring...")
    scorer = ConfidenceScorer(use_heuristic=True)
    confidence = scorer.score(
        answer=agent_result.get("answer", ""),
        chunks=agent_result.get("chunks", []),
        decision=agent_result.get("decision", "ANSWER"),
    )
    level = scorer.get_confidence_level(confidence)
    print(f"  Confidence: {confidence} ({level})")

    # Final summary
    print("\n" + "=" * 70)
    print("PIPELINE TEST COMPLETE!")
    print("=" * 70)
    print(f"  PDFs loaded:    {len(set(p['filename'] for p in pages))}")
    print(f"  Pages:          {len(pages)}")
    print(f"  Chunks:         {len(chunks)}")
    print(f"  Vector count:   {vs.get_stats()['count']}")
    print(f"  Naive RAG:      Working")
    print(f"  Agentic RAG:    Working ({agent_result['decision']})")
    print(f"  Citations:      {len(citations)}")
    print(f"  Confidence:     {confidence} ({level})")
    print("=" * 70)


if __name__ == "__main__":
    test_full_pipeline()
