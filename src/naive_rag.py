"""Naive RAG baseline (no agentic layer)."""

from typing import Dict, List
from src.retriever import Retriever


class NaiveRAG:
    """
    Simple RAG without agentic routing.

    Directly retrieves top-k chunks and passes to LLM for answer generation.
    """

    def __init__(self, retriever: Retriever, llm_client):
        """
        Initialize Naive RAG.

        Args:
            retriever: Document retriever
            llm_client: LLM client (OpenAI, Anthropic, etc.)
        """
        self.retriever = retriever
        self.llm_client = llm_client

    def query(self, question: str, k: int = 5) -> Dict:
        """
        Process query with naive RAG.

        Args:
            question: User question
            k: Number of chunks to retrieve

        Returns:
            Dict with keys:
            - answer: Generated answer text
            - chunks: Retrieved chunks
        """
        # Retrieve
        chunks = self.retriever.retrieve(question, k=k)

        # Format context
        context = self._format_context(chunks)

        # Generate answer
        answer = self._generate_answer(question, context)

        return {
            "answer": answer,
            "chunks": chunks,
            "decision": "ANSWER",  # Naive RAG always answers
            "reason": f"Retrieved {len(chunks)} chunks",
            "confidence": 0.5,  # Placeholder
            "citations": [],  # Naive RAG has no citations
        }

    def _format_context(self, chunks: List[Dict]) -> str:
        """Format retrieved chunks into context string."""
        context_parts = []
        for i, chunk in enumerate(chunks):
            context_parts.append(f"[Chunk {i + 1}]\n{chunk['text']}")
        return "\n\n".join(context_parts)

    def _generate_answer(self, question: str, context: str) -> str:
        """
        Generate answer using LLM.

        TODO: Implement LLM call with context and question
        """
        raise NotImplementedError("Implement _generate_answer")
