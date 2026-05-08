"""Confidence scoring for answers."""

from typing import Dict, List, Literal


class ConfidenceScorer:
    """Score confidence of generated answers."""

    def __init__(self, llm_client=None, use_heuristic: bool = False):
        """
        Initialize confidence scorer.

        Args:
            llm_client: LLM for confidence assessment
            use_heuristic: If True, use heuristic-based scoring
        """
        self.llm_client = llm_client
        self.use_heuristic = use_heuristic

    def score(
        self,
        answer: str,
        chunks: List[Dict],
        decision: Literal["ANSWER", "RETRIEVE", "CLARIFY", "REFUSE"],
    ) -> float:
        """
        Score confidence of answer.

        Args:
            answer: Generated answer text
            chunks: Retrieved chunks supporting answer
            decision: Agentic decision state

        Returns:
            Confidence score 0.0-1.0
        """
        if self.use_heuristic:
            return self._heuristic_score(answer, chunks, decision)
        else:
            return self._llm_score(answer, chunks, decision)

    def _heuristic_score(
        self, answer: str, chunks: List[Dict], decision: str
    ) -> float:
        """
        Heuristic-based confidence scoring.

        Rules:
        - ANSWER state: 0.7-1.0 (higher with more chunks)
        - RETRIEVE state: 0.4-0.6
        - CLARIFY state: 0.0-0.2
        - REFUSE state: 0.0
        """
        if decision == "REFUSE":
            return 0.0
        elif decision == "CLARIFY":
            return 0.1
        elif decision == "RETRIEVE":
            return 0.5
        else:  # ANSWER
            # Higher confidence with more chunks and longer answer
            chunk_score = min(1.0, len(chunks) / 5)  # 5 chunks = max score
            length_score = min(1.0, len(answer) / 500)  # 500 chars = max score
            return 0.7 + 0.3 * (chunk_score + length_score) / 2

    def _llm_score(self, answer: str, chunks: List[Dict], decision: str) -> float:
        """
        LLM-assisted confidence scoring.

        TODO: Implement using prompts/confidence_scorer.txt
        """
        raise NotImplementedError("Implement _llm_score")

    def get_confidence_level(self, score: float) -> str:
        """Get confidence level label."""
        if score >= 0.7:
            return "HIGH"
        elif score >= 0.4:
            return "MEDIUM"
        else:
            return "LOW"
