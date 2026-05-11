"""Self-reflection critic for RAG answers.

Implements answer self-critique inspired by Self-RAG (Asai et al., 2024).
After generating an answer, the system critiques itself:
- Is every claim supported by retrieved chunks?
- Are there unsupported assertions?
- Should confidence be reduced?
"""

import re
from typing import Dict, List, Optional
from src.llm_client import LLMClient, get_llm_client


class SelfReflectionCritic:
    """
    Self-reflection critic that evaluates answer quality.

    For each generated answer, asks:
    1. Is the answer fully supported by the retrieved chunks?
    2. Are there any unsupported claims?
    3. What's the appropriate confidence level?

    Reference: Self-RAG (Asai et al., 2024) - "Self-Reflective RAG"
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        """Initialize critic with LLM client."""
        self.llm_client = llm_client or get_llm_client()

    def reflect(
        self,
        question: str,
        answer: str,
        chunks: List[Dict],
    ) -> Dict:
        """
        Critique a generated answer.

        Args:
            question: Original question
            answer: Generated answer to critique
            chunks: Retrieved chunks that should support the answer

        Returns:
            Dict with:
            - is_supported: bool (is answer fully supported?)
            - support_score: float 0.0-1.0 (degree of support)
            - issues: List[str] (specific problems found)
            - suggested_confidence: float 0.0-1.0
            - critique: str (full critique text)
        """
        if not answer or not chunks:
            return self._unsupported_result("No answer or chunks to evaluate")

        # Format chunks for the prompt
        chunks_text = self._format_chunks(chunks)

        prompt = self._build_prompt(question, answer, chunks_text)

        try:
            response = self.llm_client.generate(
                prompt=prompt,
                system="You are a rigorous fact-checker. Analyze answers for unsupported claims. Be precise.",
                temperature=0.1,
                max_tokens=400,
            )
            return self._parse_critique(response)
        except Exception as e:
            return self._unsupported_result(f"Critique failed: {e}")

    def _build_prompt(self, question: str, answer: str, chunks_text: str) -> str:
        """Build self-reflection prompt."""
        return f"""You are critically evaluating whether a generated answer is supported by retrieved evidence.

QUESTION:
{question}

ANSWER TO EVALUATE:
{answer}

RETRIEVED EVIDENCE:
{chunks_text}

Your task:
1. Identify each major factual claim in the answer.
2. For each claim, determine if it's directly supported by the evidence.
3. Flag any unsupported, partially supported, or hallucinated claims.

Output exactly in this format:

SUPPORT_SCORE: [0.0-1.0, where 1.0 = all claims fully supported]
SUPPORTED: [YES/PARTIAL/NO]
ISSUES: [List specific issues, or "none". Be brief.]
SUGGESTED_CONFIDENCE: [0.0-1.0]
"""

    def _parse_critique(self, response: str) -> Dict:
        """Parse the critique response from LLM."""
        # Default values
        support_score = 0.5
        supported_str = "PARTIAL"
        issues_str = ""
        suggested_confidence = 0.5

        # Extract support score
        match = re.search(r"SUPPORT_SCORE:\s*([0-9]*\.?[0-9]+)", response, re.IGNORECASE)
        if match:
            try:
                support_score = float(match.group(1))
                support_score = max(0.0, min(1.0, support_score))
            except ValueError:
                pass

        # Extract supported flag
        match = re.search(r"SUPPORTED:\s*(YES|PARTIAL|NO)", response, re.IGNORECASE)
        if match:
            supported_str = match.group(1).upper()

        # Extract issues
        match = re.search(r"ISSUES:\s*(.+?)(?:\n[A-Z_]+:|$)", response, re.IGNORECASE | re.DOTALL)
        if match:
            issues_str = match.group(1).strip()

        # Extract suggested confidence
        match = re.search(r"SUGGESTED_CONFIDENCE:\s*([0-9]*\.?[0-9]+)", response, re.IGNORECASE)
        if match:
            try:
                suggested_confidence = float(match.group(1))
                suggested_confidence = max(0.0, min(1.0, suggested_confidence))
            except ValueError:
                pass

        # Parse issues into list
        if issues_str.lower() in ("none", "n/a", "no issues", ""):
            issues_list = []
        else:
            # Split by common delimiters
            issues_list = [i.strip("- ").strip() for i in re.split(r"[\n;]", issues_str) if i.strip()]
            issues_list = [i for i in issues_list if i and i.lower() not in ("none", "n/a")]

        return {
            "is_supported": supported_str == "YES",
            "support_level": supported_str,  # YES, PARTIAL, NO
            "support_score": round(support_score, 3),
            "issues": issues_list[:5],  # Limit to 5 issues
            "suggested_confidence": round(suggested_confidence, 3),
            "critique": response.strip(),
        }

    def _format_chunks(self, chunks: List[Dict]) -> str:
        """Format chunks for prompt."""
        formatted = []
        for i, chunk in enumerate(chunks, 1):
            text = chunk.get("text", "")[:400]
            source = chunk.get("source", "unknown")
            page = chunk.get("page", "?")
            formatted.append(f"[Chunk {i}] (Source: {source}, Page {page})\n{text}")
        return "\n\n".join(formatted)

    def _unsupported_result(self, reason: str) -> Dict:
        """Return a default unsupported result."""
        return {
            "is_supported": False,
            "support_level": "NO",
            "support_score": 0.0,
            "issues": [reason],
            "suggested_confidence": 0.0,
            "critique": reason,
        }

    def adjust_confidence(
        self,
        original_confidence: float,
        critique: Dict,
        weight: float = 0.5,
    ) -> float:
        """
        Adjust confidence based on self-reflection critique.

        Args:
            original_confidence: Original confidence score
            critique: Result from reflect()
            weight: How much to weight the critique (0-1)

        Returns:
            Adjusted confidence score
        """
        suggested = critique.get("suggested_confidence", original_confidence)

        # Weighted average
        adjusted = (1 - weight) * original_confidence + weight * suggested

        # Hard penalty for unsupported answers
        if not critique.get("is_supported", True):
            adjusted *= 0.7  # Reduce by 30%

        # Penalty for issues
        num_issues = len(critique.get("issues", []))
        if num_issues > 0:
            adjusted *= max(0.5, 1.0 - 0.1 * num_issues)

        return round(max(0.0, min(1.0, adjusted)), 3)
