"""Naive RAG baseline (no agentic layer)."""

from typing import Dict, List, Optional
from src.retriever import Retriever
from src.llm_client import LLMClient, load_prompt, get_llm_client


class NaiveRAG:
    """
    Simple RAG without agentic routing.

    Directly retrieves top-k chunks and passes to LLM for answer generation.
    No decision routing, no citations, no confidence scoring.
    Used as a baseline for comparison against agentic RAG.
    """

    def __init__(self, retriever: Retriever, llm_client: Optional[LLMClient] = None):
        """
        Initialize Naive RAG.

        Args:
            retriever: Document retriever
            llm_client: LLM client (uses default if None)
        """
        self.retriever = retriever
        self.llm_client = llm_client or get_llm_client()

        # Load prompt template
        try:
            self.answer_prompt = load_prompt("answer_generator")
        except FileNotFoundError:
            self.answer_prompt = self._default_prompt()

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
            - decision: Always "ANSWER" for naive RAG
            - reason: Brief explanation
            - confidence: Placeholder confidence (0.5 default)
            - citations: Empty list (naive RAG has no citations)
        """
        # Step 1: Retrieve top-k chunks
        chunks = self.retriever.retrieve(question, k=k)

        # Step 2: Format context
        context = self._format_context(chunks)

        # Step 3: Generate answer
        answer = self._generate_answer(question, context)

        return {
            "answer": answer,
            "chunks": chunks,
            "decision": "ANSWER",
            "reason": f"Retrieved {len(chunks)} chunks, generated answer (naive)",
            "confidence": 0.5,
            "citations": [],
        }

    def _format_context(self, chunks: List[Dict]) -> str:
        """Format retrieved chunks into context string."""
        if not chunks:
            return "No context available."

        context_parts = []
        for i, chunk in enumerate(chunks):
            source = chunk.get("source", "unknown")
            page = chunk.get("page", "?")
            text = chunk.get("text", "")
            context_parts.append(
                f"[Chunk {i + 1}] (Source: {source}, Page: {page})\n{text}"
            )
        return "\n\n".join(context_parts)

    def _generate_answer(self, question: str, context: str) -> str:
        """
        Generate answer using LLM.

        Args:
            question: User question
            context: Formatted context from retrieved chunks

        Returns:
            Generated answer text
        """
        # Format prompt with question and context
        prompt = self.answer_prompt.replace("{question}", question)
        prompt = prompt.replace("{context}", context)

        # Generate using LLM
        try:
            answer = self.llm_client.generate(
                prompt=prompt,
                system="You are an expert business analyst. Answer questions based ONLY on the provided context.",
                temperature=0.3,
                max_tokens=512,
            )
            return answer
        except Exception as e:
            return f"Error generating answer: {str(e)}"

    @staticmethod
    def _default_prompt() -> str:
        """Default prompt if prompts/answer_generator.txt is missing."""
        return """You are an expert business analyst answering questions about corporate documents.

Question: {question}

Context from documents:
{context}

Instructions:
1. Answer the question ONLY using information from the provided context.
2. If information is not in the context, state that clearly.
3. Be specific and factual. Include numbers and dates where available.
4. Keep the answer concise (2-4 sentences).

Answer:"""
