"""Agentic decision layer and routing."""

from typing import Dict, List, Literal
from src.retriever import Retriever


class AgenticRouter:
    """
    Route queries through 4-state decision logic:
    - ANSWER: Context is sufficient, generate answer
    - RETRIEVE: Insufficient context, retrieve more
    - CLARIFY: Query is ambiguous, ask user
    - REFUSE: Evidence clearly insufficient, abstain
    """

    def __init__(self, retriever: Retriever, llm_client, max_retrieval_attempts: int = 2):
        """
        Initialize agentic router.

        Args:
            retriever: Document retriever
            llm_client: LLM client for routing and generation
            max_retrieval_attempts: Max times to expand retrieval
        """
        self.retriever = retriever
        self.llm_client = llm_client
        self.max_retrieval_attempts = max_retrieval_attempts

    def route_and_answer(self, question: str, k: int = 5) -> Dict:
        """
        Route question through agentic layer and generate answer.

        Args:
            question: User question
            k: Initial number of chunks to retrieve

        Returns:
            Dict with:
            - decision: ANSWER, RETRIEVE, CLARIFY, or REFUSE
            - reason: Explanation of decision
            - answer: Generated answer (if ANSWER)
            - chunks: Retrieved chunks
            - citations: Source citations
            - confidence: Confidence score 0.0-1.0
        """
        # Step 1: Retrieve initial chunks
        chunks = self.retriever.retrieve(question, k=k)

        # Step 2: Make routing decision
        decision, reason = self._decide(question, chunks)

        # Step 3: Act on decision
        if decision == "ANSWER":
            return self._answer(question, chunks, reason)
        elif decision == "RETRIEVE":
            # Expand retrieval
            chunks = self.retriever.retrieve(question, k=k * 2)
            decision, reason = self._decide(question, chunks)
            if decision == "ANSWER":
                return self._answer(question, chunks, reason)
            else:
                return self._refuse(question, chunks, reason)
        elif decision == "CLARIFY":
            return self._clarify(question)
        else:  # REFUSE
            return self._refuse(question, chunks, reason)

    def _decide(self, question: str, chunks: List[Dict]) -> tuple[Literal["ANSWER", "RETRIEVE", "CLARIFY", "REFUSE"], str]:
        """
        Make routing decision based on question and retrieved chunks.

        TODO: Implement LLM-assisted decision logic
        Should use prompts/retrieval_decision.txt
        """
        raise NotImplementedError("Implement _decide method")

    def _answer(self, question: str, chunks: List[Dict], reason: str) -> Dict:
        """Generate grounded answer from chunks."""
        raise NotImplementedError("Implement _answer method")

    def _refuse(self, question: str, chunks: List[Dict], reason: str) -> Dict:
        """Return abstention response."""
        raise NotImplementedError("Implement _refuse method")

    def _clarify(self, question: str) -> Dict:
        """Return clarification request."""
        return {
            "decision": "CLARIFY",
            "reason": "Question is ambiguous or requires clarification",
            "answer": "I need more context to answer your question. Could you please rephrase or provide more details?",
            "chunks": [],
            "citations": [],
            "confidence": 0.0,
        }
