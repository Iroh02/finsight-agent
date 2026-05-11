"""End-to-end RAG pipeline orchestration."""

import os
import sys
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional

# Ensure repo root is importable when this file is executed directly
# (e.g. `python src/pipeline.py`). Must run before any `from src.` imports.
_repo_root = str(Path(__file__).resolve().parent.parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

logger = logging.getLogger(__name__)

# ── Data-layer imports (Jillian) ──────────────────────────────────────────────
from src.loader import load_pdfs, load_directory
from src.cleaner import clean_text, detect_and_remove_headers_footers
from src.chunker import TextChunker, chunk_documents
from src.embedder import EmbeddingPipeline, get_embedder
from src.vectorstore import get_vectorstore, ChromaVectorStore

# ── RAG / Agent imports (Anushree) ────────────────────────────────────────────
from src.retriever import Retriever
from src.naive_rag import NaiveRAG
from src.agent import AgenticRouter
from src.citations import CitationExtractor
from src.confidence import ConfidenceScorer


# ─────────────────────────────────────────────────────────────────────────────
# DataPipeline — standalone ingestion & retrieval (no LLM required)
# ─────────────────────────────────────────────────────────────────────────────

class DataPipeline:
    """PDF → ChromaDB ingestion and vector retrieval pipeline.

    Operates entirely on local models (sentence-transformers) — no API key needed.
    """

    def __init__(
        self,
        data_dir: str = "data/raw",
        persist_dir: str = "data/vectorstore",
        collection_name: str = "financial_docs",
        embedding_model: str = "all-MiniLM-L6-v2",
    ):
        self.data_dir = data_dir
        self.embedder = EmbeddingPipeline(model_name=embedding_model)
        self.vectorstore: ChromaVectorStore = get_vectorstore(
            persist_directory=persist_dir,
            collection_name=collection_name,
        )

    # ── Ingestion ─────────────────────────────────────────────────────────────

    def ingest(self, data_dir: Optional[str] = None) -> Dict:
        """Load PDFs → clean → chunk → embed → store in ChromaDB.

        Returns:
            Dict with keys: pdfs, pages, chunks, embedding_seconds, total_seconds
        """
        directory = data_dir or self.data_dir
        t_start = time.perf_counter()

        # 1. Load
        print(f"\n[1/5] Loading PDFs from '{directory}' ...")
        pages = load_pdfs(directory)
        pdf_names = sorted({p["source"] for p in pages})
        print(f"      {len(pdf_names)} PDF(s) · {len(pages)} pages")

        if not pages:
            print("No pages loaded — aborting ingestion.")
            return {}

        # 2. Per-page cleaning
        print("[2/5] Cleaning text ...")
        for page in pages:
            page["text"] = clean_text(page["text"])

        # 3. Cross-page header/footer removal
        texts = [p["text"] for p in pages]
        cleaned = detect_and_remove_headers_footers(texts)
        for page, text in zip(pages, cleaned):
            page["text"] = text

        # 4. Chunk
        print("[3/5] Chunking documents ...")
        docs = chunk_documents(pages)
        print(f"      {len(docs)} chunks created")

        # 5. Embed
        print("[4/5] Generating embeddings (this may take a moment) ...")
        t_embed = time.perf_counter()
        embeddings = self.embedder.embed_documents(docs)
        embed_secs = round(time.perf_counter() - t_embed, 1)
        print(f"      {len(embeddings)} embeddings in {embed_secs}s")

        # 6. Store
        print("[5/5] Storing in ChromaDB ...")
        self.vectorstore.add_documents(docs, embeddings)

        total_secs = round(time.perf_counter() - t_start, 1)
        stats = {
            "pdfs": len(pdf_names),
            "pages": len(pages),
            "chunks": len(docs),
            "embedding_seconds": embed_secs,
            "total_seconds": total_secs,
        }
        print(f"\nIngestion complete in {total_secs}s")
        print(f"  PDFs:          {stats['pdfs']}")
        print(f"  Pages:         {stats['pages']}")
        print(f"  Chunks stored: {stats['chunks']}")
        print(f"  Embed time:    {embed_secs}s")
        return stats

    # ── Retrieval ─────────────────────────────────────────────────────────────

    def query(self, question: str, k: int = 5) -> List[Dict]:
        """Embed query and retrieve top-k matching chunks.

        Returns:
            List of dicts — each with: text, source, page, score
        """
        docs = self.vectorstore.similarity_search(question, k=k)
        return [
            {
                "text": doc.page_content,
                "source": doc.metadata.get("source", ""),
                "page": doc.metadata.get("page", 0),
                "score": doc.metadata.get("score", 0.0),
            }
            for doc in docs
        ]


# ─────────────────────────────────────────────────────────────────────────────
# RAGPipeline — full agentic pipeline (Anushree's layer)
# ─────────────────────────────────────────────────────────────────────────────

class RAGPipeline:
    """Complete RAG pipeline for ingestion and querying."""

    def __init__(
        self,
        vectorstore_type: str = "chroma",
        embedding_provider: str = "openai",
        llm_client=None,
        use_heuristic_confidence: bool = False,
    ):
        self.vectorstore_type = vectorstore_type
        self.embedding_provider = embedding_provider
        self.llm_client = llm_client

        self.embedder = get_embedder(embedding_provider)
        self.vectorstore = get_vectorstore()
        self.retriever = Retriever(self.vectorstore)

        self.naive_rag = NaiveRAG(self.retriever, llm_client)
        self.agentic_router = AgenticRouter(self.retriever, llm_client)
        self.citation_extractor = CitationExtractor()
        self.confidence_scorer = ConfidenceScorer(
            llm_client, use_heuristic=use_heuristic_confidence
        )
        self.chunker = TextChunker()

    def ingest(self, data_directory: str = "./data/raw") -> Dict:
        print(f"Starting ingestion from {data_directory}...")
        documents = load_directory(data_directory)
        print(f"Loaded {len(documents)} pages")

        for doc in documents:
            doc["text"] = clean_text(doc["text"])

        chunks = self.chunker.chunk(documents)
        print(f"Created {len(chunks)} chunks")

        for chunk in chunks:
            chunk["embedding"] = self.embedder.embed_single(chunk["text"])

        self.vectorstore.add_documents(chunks)
        print(f"Ingested {len(chunks)} chunks into {self.vectorstore_type}")

        return {
            "documents_ingested": len(documents),
            "chunks_created": len(chunks),
            "vectorstore": self.vectorstore_type,
        }

    def query(self, question: str, mode: str = "agentic", selected_docs: Optional[List[str]] = None) -> Dict:
        if mode == "agentic":
            return self._query_agentic(question)
        elif mode == "naive":
            return self._query_naive(question)
        else:
            raise ValueError(f"Unknown mode: {mode}")

    def _query_agentic(self, question: str) -> Dict:
        result = self.agentic_router.route_and_answer(question)
        citations = self.citation_extractor.extract_citations(
            result["answer"], result.get("chunks", [])
        )
        confidence = self.confidence_scorer.score(
            result["answer"],
            result.get("chunks", []),
            result.get("decision", "REFUSE"),
        )
        return {
            "answer": result.get("answer", ""),
            "decision": result.get("decision", "REFUSE"),
            "reason": result.get("reason", ""),
            "confidence": confidence,
            "citations": citations,
            "chunks": result.get("chunks", []),
            "execution_time_ms": 0,
        }

    def _query_naive(self, question: str) -> Dict:
        result = self.naive_rag.query(question)
        confidence = self.confidence_scorer.score(
            result["answer"], result.get("chunks", []), "ANSWER"
        )
        return {
            "answer": result.get("answer", ""),
            "decision": "ANSWER",
            "reason": "Naive RAG: no decision routing",
            "confidence": confidence * 0.8,
            "citations": [],
            "chunks": result.get("chunks", []),
            "execution_time_ms": 0,
        }


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    """CLI for the standalone data pipeline.

    Usage:
      python src/pipeline.py --ingest
      python src/pipeline.py --query "What was Apple's revenue?"
    """
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)s  %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="FinSight-Agent — data pipeline CLI")
    parser.add_argument("--ingest", action="store_true", help="Ingest PDFs into ChromaDB")
    parser.add_argument("--query", type=str, metavar="QUESTION", help="Retrieve top-k chunks")
    parser.add_argument("--data-dir", default="data/raw", help="PDF directory (default: data/raw)")
    parser.add_argument("--k", type=int, default=3, help="Number of results to return (default: 3)")
    parser.add_argument("--test", action="store_true", help="Run the 4 built-in test queries")
    args = parser.parse_args()

    pipeline = DataPipeline(data_dir=args.data_dir)

    if args.ingest:
        pipeline.ingest()

    elif args.query:
        _print_results(pipeline.query(args.query, k=args.k), args.query)

    elif args.test:
        test_queries = [
            "What was Apple's revenue growth?",
            "What did the company mention about cloud or AI?",
            "What are the delivery or shipment numbers?",
            "What risks did the company disclose?",
        ]
        for q in test_queries:
            print(f"\n{'='*60}")
            print(f"QUERY: {q}")
            print("=" * 60)
            _print_results(pipeline.query(q, k=3), q)

    else:
        parser.print_help()


def _print_results(results: List[Dict], query: str) -> None:
    if not results:
        print("No results found. Have you run --ingest yet?")
        return
    for i, r in enumerate(results, 1):
        print(f"\n  [{i}] score={r['score']:.4f}  {r['source']} p.{r['page']}")
        snippet = r["text"].replace("\n", " ")[:300]
        print(f"      {snippet}...")


if __name__ == "__main__":
    main()
