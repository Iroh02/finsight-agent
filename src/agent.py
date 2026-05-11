"""Agentic decision layer and routing."""

import re
from typing import Dict, List, Literal, Optional, Tuple
from src.retriever import Retriever
from src.llm_client import LLMClient, load_prompt, get_llm_client


class AgenticRouter:
    """
    Route queries through 4-state decision logic:
    - ANSWER: Context is sufficient, generate answer
    - RETRIEVE: Insufficient context, retrieve more
    - CLARIFY: Query is ambiguous, ask user
    - REFUSE: Evidence clearly insufficient, abstain
    """

    VALID_DECISIONS = {"ANSWER", "RETRIEVE", "CLARIFY", "REFUSE"}

    def __init__(
        self,
        retriever: Retriever,
        llm_client: Optional[LLMClient] = None,
        max_retrieval_attempts: int = 2,
    ):
        """
        Initialize agentic router.

        Args:
            retriever: Document retriever
            llm_client: LLM client for routing and generation
            max_retrieval_attempts: Max times to expand retrieval
        """
        self.retriever = retriever
        self.llm_client = llm_client or get_llm_client()
        self.max_retrieval_attempts = max_retrieval_attempts

        # Load all prompts we'll need
        try:
            self.decision_prompt = load_prompt("retrieval_decision")
            self.answer_prompt = load_prompt("answer_generator")
            self.refuse_prompt = load_prompt("insufficient_evidence")
        except FileNotFoundError as e:
            print(f"Warning: Prompt file missing: {e}")
            self.decision_prompt = self._default_decision_prompt()
            self.answer_prompt = self._default_answer_prompt()
            self.refuse_prompt = self._default_refuse_prompt()

    def route_and_answer(self, question: str, k: int = 5) -> Dict:
        """
        Main entry point: Route question through agentic layer and generate answer.

        Flow:
        1. Retrieve top-k chunks
        2. Ask LLM what to do (ANSWER/RETRIEVE/CLARIFY/REFUSE)
        3. Act on the decision
        """
        # Step 1: Retrieve initial chunks
        chunks = self.retriever.retrieve(question, k=k)

        # Step 2: Make routing decision
        decision, reason = self._decide(question, chunks)

        # Step 3: Act on decision
        if decision == "ANSWER":
            return self._answer(question, chunks, reason)

        elif decision == "RETRIEVE":
            # Try expanding retrieval to get more context
            expanded_chunks = self.retriever.retrieve(question, k=k * 2)
            new_decision, new_reason = self._decide(question, expanded_chunks)

            # If still not enough info, refuse
            if new_decision == "ANSWER":
                return self._answer(question, expanded_chunks, new_reason)
            else:
                return self._refuse(question, expanded_chunks, new_reason)

        elif decision == "CLARIFY":
            return self._clarify(question, reason)

        else:  # REFUSE
            return self._refuse(question, chunks, reason)

    def _decide(
        self, question: str, chunks: List[Dict]
    ) -> Tuple[Literal["ANSWER", "RETRIEVE", "CLARIFY", "REFUSE"], str]:
        """
        Ask the LLM what to do with this question and these chunks.

        Returns: (decision, reason) tuple.
        """
        # Format chunks into readable text
        chunks_text = self._format_chunks_for_decision(chunks)

        # Fill in the prompt template
        prompt = self.decision_prompt.replace("{question}", question)
        prompt = prompt.replace("{chunks}", chunks_text)

        # Ask the LLM
        try:
            response = self.llm_client.generate(
                prompt=prompt,
                system="You are a precise routing decision-maker. Output ONLY the decision and reason in the requested format.",
                temperature=0.1,  # Low temperature for consistent decisions
                max_tokens=200,
            )
            return self._parse_decision(response)
        except Exception as e:
            # Fallback: if LLM fails, refuse safely
            return ("REFUSE", f"Decision LLM error: {str(e)}")

    def _parse_decision(self, response: str) -> Tuple[str, str]:
        """
        Parse LLM response to extract decision and reason.

        Expected format:
            DECISION: ANSWER
            REASON: 3 relevant chunks found
        """
        decision = "REFUSE"  # Safe default
        reason = "Could not parse decision"

        # Extract decision
        decision_match = re.search(
            r"DECISION:\s*(ANSWER|RETRIEVE|CLARIFY|REFUSE)",
            response,
            re.IGNORECASE,
        )
        if decision_match:
            decision = decision_match.group(1).upper()

        # Extract reason
        reason_match = re.search(r"REASON:\s*(.+?)(?:\n|$)", response, re.IGNORECASE)
        if reason_match:
            reason = reason_match.group(1).strip()

        # Validate decision
        if decision not in self.VALID_DECISIONS:
            decision = "REFUSE"

        return (decision, reason)

    def _answer(self, question: str, chunks: List[Dict], reason: str) -> Dict:
        """
        Generate a grounded answer using the retrieved chunks.
        """
        # Format chunks as context
        context = self._format_context(chunks)

        # Build prompt
        prompt = self.answer_prompt.replace("{question}", question)
        prompt = prompt.replace("{context}", context)

        # Generate answer
        try:
            answer = self.llm_client.generate(
                prompt=prompt,
                system="You are an expert business analyst. Answer ONLY using provided context. Cite sources.",
                temperature=0.3,
                max_tokens=512,
            )
        except Exception as e:
            answer = f"Error generating answer: {str(e)}"

        return {
            "decision": "ANSWER",
            "reason": reason,
            "answer": answer,
            "chunks": chunks,
            "citations": [],  # Will be filled by CitationExtractor
            "confidence": 0.0,  # Will be filled by ConfidenceScorer
        }

    def _refuse(self, question: str, chunks: List[Dict], reason: str) -> Dict:
        """
        Politely tell the user we can't answer.
        """
        # Format any context we did find (might be irrelevant but shows transparency)
        context = self._format_context(chunks) if chunks else "No relevant information found."

        # Build prompt
        prompt = self.refuse_prompt.replace("{question}", question)
        prompt = prompt.replace("{context}", context)

        # Generate refusal message
        try:
            answer = self.llm_client.generate(
                prompt=prompt,
                system="You are a transparent assistant. Explain why you cannot answer.",
                temperature=0.3,
                max_tokens=256,
            )
        except Exception as e:
            answer = (
                "I cannot answer this question based on the available documents. "
                f"({reason})"
            )

        return {
            "decision": "REFUSE",
            "reason": reason,
            "answer": answer,
            "chunks": chunks,
            "citations": [],
            "confidence": 0.0,
        }

    def _clarify(self, question: str, reason: str = "") -> Dict:
        """
        Ask the user to rephrase the question.
        """
        return {
            "decision": "CLARIFY",
            "reason": reason or "Question is ambiguous or requires clarification",
            "answer": (
                "I need more context to answer your question accurately. "
                "Could you please rephrase or provide more specific details? "
                f"({reason})" if reason else ""
            ),
            "chunks": [],
            "citations": [],
            "confidence": 0.1,
        }

    def _format_chunks_for_decision(self, chunks: List[Dict]) -> str:
        """Format chunks for the decision prompt (compact)."""
        if not chunks:
            return "No chunks retrieved."

        formatted = []
        for i, chunk in enumerate(chunks, 1):
            source = chunk.get("source", "unknown")
            text = chunk.get("text", "")[:300]  # Truncate for decision
            formatted.append(f"[Chunk {i}] (Source: {source})\n{text}...")
        return "\n\n".join(formatted)

    def _format_context(self, chunks: List[Dict]) -> str:
        """Format chunks as full context for answer generation."""
        if not chunks:
            return "No context available."

        formatted = []
        for i, chunk in enumerate(chunks, 1):
            source = chunk.get("source", "unknown")
            page = chunk.get("page", "?")
            text = chunk.get("text", "")
            formatted.append(
                f"[Chunk {i}] (Source: {source}, Page: {page})\n{text}"
            )
        return "\n\n".join(formatted)

    @staticmethod
    def _default_decision_prompt() -> str:
        """Fallback decision prompt."""
        return """You are evaluating whether retrieved documents can answer a question.

Question: {question}

Retrieved Chunks:
{chunks}

Decide:
- ANSWER: Chunks contain clear info to answer
- RETRIEVE: Some relevant info but incomplete
- CLARIFY: Question is too ambiguous
- REFUSE: No relevant info to answer

Output:
DECISION: [ANSWER | RETRIEVE | CLARIFY | REFUSE]
REASON: [Brief explanation]"""

    @staticmethod
    def _default_answer_prompt() -> str:
        """Fallback answer prompt."""
        return """Answer the question using ONLY the context provided.

Question: {question}
Context: {context}

Cite sources. Be factual.
Answer:"""

    @staticmethod
    def _default_refuse_prompt() -> str:
        """Fallback refuse prompt."""
        return """The available documents do not contain information to answer this question.

Question: {question}
Available context: {context}

Explain politely that you cannot answer and what info would be needed.
Response:"""
