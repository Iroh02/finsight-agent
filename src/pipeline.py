"""End-to-end RAG pipeline orchestration."""

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Literal

# Data pipeline imports (Jillian's responsibility)
from src.loader import PDFLoader, load_directory
from src.cleaner import clean_text
from src.chunker import TextChunker, ParentChildChunker, SemanticChunker
from src.embedder import get_embedder
from src.vectorstore import get_vectorstore

# RAG pipeline imports (Anushree's responsibility)
from src.retriever import Retriever
from src.naive_rag import NaiveRAG
from src.agent import AgenticRouter
from src.citations import CitationExtractor
from src.confidence import ConfidenceScorer


class RAGPipeline:
    """Complete RAG pipeline for ingestion and querying."""

    def __init__(
        self,
        vectorstore_type: str = "chroma",
        embedding_provider: str = "openai",
        llm_client=None,
        use_heuristic_confidence: bool = False,
        chunking_strategy: str = "standard",
    ):
        """
        Initialize RAG pipeline.

        Args:
            vectorstore_type: "chroma" or "faiss"
            embedding_provider: "openai" or "huggingface"
            llm_client: LLM client instance
            use_heuristic_confidence: Use heuristic vs LLM confidence scoring
            chunking_strategy: "standard" | "parent_child" | "semantic"
        """
        self.vectorstore_type = vectorstore_type
        self.embedding_provider = embedding_provider
        self.llm_client = llm_client

        # Initialize components
        self.embedder = get_embedder(embedding_provider)
        self.vectorstore = get_vectorstore(vectorstore_type)
        self.retriever = Retriever(self.vectorstore)

        # RAG components
        self.naive_rag = NaiveRAG(self.retriever, llm_client)
        self.agentic_router = AgenticRouter(self.retriever, llm_client)
        self.citation_extractor = CitationExtractor()
        self.confidence_scorer = ConfidenceScorer(
            llm_client, use_heuristic=use_heuristic_confidence
        )

        if chunking_strategy == "parent_child":
            self.chunker = ParentChildChunker()
        elif chunking_strategy == "semantic":
            self.chunker = SemanticChunker()
        else:
            self.chunker = TextChunker()

    def ingest(self, data_directory: str = "./data/raw") -> Dict:
        """
        Ingest PDFs from directory into vector store.

        Args:
            data_directory: Path to directory containing PDFs

        Returns:
            Dict with ingestion statistics
        """
        print(f"Starting ingestion from {data_directory}...")

        # Load PDFs
        documents = load_directory(data_directory)
        print(f"Loaded {len(documents)} pages")

        # Clean text
        for doc in documents:
            doc["text"] = clean_text(doc["text"])

        # Chunk
        chunks = self.chunker.chunk(documents)
        print(f"Created {len(chunks)} chunks")

        # Embed and ingest
        for chunk in chunks:
            embedding = self.embedder.embed_single(chunk["text"])
            chunk["embedding"] = embedding

        self.vectorstore.add_documents(chunks)
        print(f"Ingested {len(chunks)} chunks into {self.vectorstore_type}")

        return {
            "documents_ingested": len(documents),
            "chunks_created": len(chunks),
            "vectorstore": self.vectorstore_type,
        }

    def query(self, question: str, mode: str = "agentic", selected_docs: Optional[List[str]] = None) -> Dict:
        """
        Query the RAG system.

        Args:
            question: User question
            mode: "agentic" or "naive"
            selected_docs: Filter to specific documents (if supported)

        Returns:
            Response dict with answer, citations, chunks, confidence, etc.
        """
        if mode == "agentic":
            return self._query_agentic(question)
        elif mode == "naive":
            return self._query_naive(question)
        else:
            raise ValueError(f"Unknown mode: {mode}")

    def _query_agentic(self, question: str) -> Dict:
        """Query using agentic RAG."""
        result = self.agentic_router.route_and_answer(question)

        # Extract citations
        citations = self.citation_extractor.extract_citations(result["answer"], result.get("chunks", []))

        # Score confidence
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
            "execution_time_ms": 0,  # TODO: Add timing
        }

    def _query_naive(self, question: str) -> Dict:
        """Query using naive RAG."""
        result = self.naive_rag.query(question)

        # Score confidence (lower for naive)
        confidence = self.confidence_scorer.score(
            result["answer"],
            result.get("chunks", []),
            "ANSWER",  # Naive always answers
        )

        return {
            "answer": result.get("answer", ""),
            "decision": "ANSWER",  # Naive always answers
            "reason": "Naive RAG: no decision routing",
            "confidence": confidence * 0.8,  # Penalize naive RAG
            "citations": [],  # Naive RAG has no citations
            "chunks": result.get("chunks", []),
            "execution_time_ms": 0,  # TODO: Add timing
        }


def main():
    """CLI for pipeline operations."""
    import argparse

    parser = argparse.ArgumentParser(description="FinSight Agent RAG Pipeline")
    parser.add_argument("--ingest", action="store_true", help="Run ingestion")
    parser.add_argument("--query", type=str, help="Query the system")
    parser.add_argument("--mode", choices=["agentic", "naive"], default="agentic")
    parser.add_argument("--data-dir", default="./data/raw")

    args = parser.parse_args()

    # TODO: Initialize LLM client based on .env
    pipeline = RAGPipeline()

    if args.ingest:
        stats = pipeline.ingest(args.data_dir)
        print(f"Ingestion complete: {stats}")
    elif args.query:
        response = pipeline.query(args.query, mode=args.mode)
        print(f"Answer: {response['answer']}")
        print(f"Confidence: {response['confidence']:.2f}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
