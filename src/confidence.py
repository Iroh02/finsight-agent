"""Confidence scoring for answers."""

import re
from typing import Dict, List, Optional, Literal
from src.llm_client import LLMClient, load_prompt, get_llm_client


class ConfidenceScorer:
    """
    Score the confidence of generated answers (0.0 to 1.0).

    Two modes:
    - Heuristic: Fast, free, based on decision state + chunk count
    - LLM-assisted: More accurate, asks LLM to assess
    """

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        use_heuristic: bool = True,
    ):
        """
        Initialize confidence scorer.

        Args:
            llm_client: LLM client (only needed if use_heuristic=False)
            use_heuristic: If True, use rule-based scoring (recommended for speed)
        """
        self.use_heuristic = use_heuristic
        self.llm_client = llm_client

        if not use_heuristic:
            self.llm_client = self.llm_client or get_llm_client()
            try:
                self.confidence_prompt = load_prompt("confidence_scorer")
            except FileNotFoundError:
                self.confidence_prompt = self._default_confidence_prompt()

    def score(
        self,
        answer: str,
        chunks: List[Dict],
        decision: Literal["ANSWER", "RETRIEVE", "CLARIFY", "REFUSE"] = "ANSWER",
        question: str = "",
    ) -> float:
        """
        Score confidence of answer.

        Args:
            answer: Generated answer text
            chunks: Retrieved chunks supporting answer
            decision: Agentic decision state
            question: Original question (for LLM mode)

        Returns:
            Confidence score 0.0 to 1.0
        """
        if self.use_heuristic:
            return self._heuristic_score(answer, chunks, decision)
        else:
            return self._llm_score(answer, chunks, decision, question)

    def _heuristic_score(
        self,
        answer: str,
        chunks: List[Dict],
        decision: str,
    ) -> float:
        """
        Rule-based confidence scoring.

        Logic:
        - REFUSE → 0.0 (no info)
        - CLARIFY → 0.1 (uncertain question)
        - RETRIEVE → 0.4-0.6 (marginal evidence, had to expand)
        - ANSWER → 0.7-1.0 (scaled by chunks and answer quality)
        """
        # Refuse case: zero confidence
        if decision == "REFUSE":
            return 0.0

        # Clarify case: very low confidence
        if decision == "CLARIFY":
            return 0.1

        # Retrieve case: medium confidence (had to expand search)
        if decision == "RETRIEVE":
            base = 0.4
            chunk_bonus = min(0.2, len(chunks) * 0.03)
            return round(base + chunk_bonus, 2)

        # Answer case: scale 0.7 to 1.0 based on quality signals
        base = 0.7

        # Bonus for more chunks (more evidence)
        chunk_bonus = min(0.15, len(chunks) * 0.03)

        # Bonus for longer, more detailed answers
        length_bonus = min(0.1, len(answer) / 5000)

        # Penalty if answer contains hedging phrases (lower confidence)
        hedging_phrases = [
            "i'm not sure", "i cannot", "unable to", "not certain",
            "may be", "might be", "possibly", "unclear",
            "do not have", "doesn't contain", "cannot find",
        ]
        answer_lower = answer.lower()
        hedging_penalty = sum(0.05 for phrase in hedging_phrases if phrase in answer_lower)
        hedging_penalty = min(0.3, hedging_penalty)

        # Bonus for citations in answer (e.g., "Source:", "Page")
        citation_indicators = ["source:", "page", "according to", "report states"]
        citation_bonus = 0.05 if any(c in answer_lower for c in citation_indicators) else 0

        score = base + chunk_bonus + length_bonus + citation_bonus - hedging_penalty
        return round(max(0.0, min(1.0, score)), 2)

    def _llm_score(
        self,
        answer: str,
        chunks: List[Dict],
        decision: str,
        question: str = "",
    ) -> float:
        """
        LLM-assisted confidence scoring.

        Asks the LLM to assess confidence on a 0.0-1.0 scale.
        """
        # Quick early returns for non-ANSWER states
        if decision == "REFUSE":
            return 0.0
        if decision == "CLARIFY":
            return 0.1

        # Format chunks for prompt
        chunks_text = self._format_chunks(chunks)

        # Build prompt
        prompt = self.confidence_prompt.replace("{question}", question or "[not provided]")
        prompt = prompt.replace("{answer}", answer)
        prompt = prompt.replace("{chunks}", chunks_text)

        try:
            response = self.llm_client.generate(
                prompt=prompt,
                system="You are a precise confidence scorer. Output ONLY the score in the requested format.",
                temperature=0.1,
                max_tokens=150,
            )
            return self._parse_confidence(response)
        except Exception:
            # Fallback to heuristic if LLM fails
            return self._heuristic_score(answer, chunks, decision)

    def _parse_confidence(self, response: str) -> float:
        """
        Parse LLM response to extract confidence score.

        Expected format:
            CONFIDENCE_SCORE: 0.85
            JUSTIFICATION: ...
        """
        # Try to find a confidence score in the response
        match = re.search(
            r"CONFIDENCE_SCORE:\s*([0-9]*\.?[0-9]+)",
            response,
            re.IGNORECASE,
        )
        if match:
            try:
                score = float(match.group(1))
                return round(max(0.0, min(1.0, score)), 2)
            except ValueError:
                pass

        # Fallback: try to find any decimal number
        match = re.search(r"\b(0?\.\d+|1\.0+)\b", response)
        if match:
            try:
                score = float(match.group(1))
                return round(max(0.0, min(1.0, score)), 2)
            except ValueError:
                pass

        # Default to medium confidence if parsing fails
        return 0.5

    def get_confidence_level(self, score: float) -> str:
        """Return human-readable confidence level."""
        if score >= 0.7:
            return "HIGH"
        elif score >= 0.4:
            return "MEDIUM"
        elif score >= 0.1:
            return "LOW"
        else:
            return "NONE"

    def get_color(self, score: float) -> str:
        """Return color code for confidence (for UI badges)."""
        if score >= 0.7:
            return "green"
        elif score >= 0.4:
            return "yellow"
        else:
            return "red"

    def _format_chunks(self, chunks: List[Dict]) -> str:
        """Format chunks for prompt."""
        if not chunks:
            return "No chunks."

        formatted = []
        for i, chunk in enumerate(chunks, 1):
            text = chunk.get("text", "")[:200]
            source = chunk.get("source", "unknown")
            formatted.append(f"[Chunk {i}] (Source: {source})\n{text}...")
        return "\n\n".join(formatted)

    @staticmethod
    def _default_confidence_prompt() -> str:
        """Fallback confidence prompt."""
        return """Assess the confidence in the following answer based on the supporting evidence.

Question: {question}
Answer: {answer}
Supporting chunks: {chunks}

Score from 0.0 (no support) to 1.0 (fully supported by clear evidence).

Output:
CONFIDENCE_SCORE: [0.0-1.0]
JUSTIFICATION: [brief reason]"""
