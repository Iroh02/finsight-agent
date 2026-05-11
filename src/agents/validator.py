"""Validator Agent: Validates multi-hop reasoning chains.

Extends self-reflection (Self-RAG, Asai et al. 2024) to multi-agent reasoning.
Verifies that sub-answers are supported, synthesis is logical, and no
contradictions exist.
"""

import re
from typing import Dict, List, Optional
from src.llm_client import LLMClient, load_prompt, get_llm_client


class ValidatorAgent:
    """
    Validates the multi-hop reasoning chain in a multi-agent response.

    Checks:
    1. Each sub-answer is supported by evidence
    2. Synthesis logically follows from sub-answers
    3. No internal contradictions
    4. Completeness vs original question
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        """Initialize validator."""
        self.llm_client = llm_client or get_llm_client()
        try:
            self.prompt_template = load_prompt("validator")
        except FileNotFoundError:
            self.prompt_template = self._default_prompt()

    def validate(
        self,
        question: str,
        sub_answers: List[Dict],
        final_answer: str,
        all_chunks: Optional[List[Dict]] = None,
    ) -> Dict:
        """
        Validate the multi-hop reasoning chain.

        Args:
            question: Original question
            sub_answers: List of (sub_question, sub_answer, chunks) dicts
            final_answer: Synthesized final answer
            all_chunks: All retrieved chunks (optional)

        Returns:
            Dict with:
            - validation_score: 0.0-1.0
            - supported: YES/PARTIAL/NO
            - issues: List of issues found
            - suggested_confidence: 0.0-1.0
            - summary: One-line assessment
        """
        if not sub_answers or not final_answer:
            return self._invalid_result("Missing sub-answers or final answer")

        # Format inputs for prompt
        sub_answers_text = self._format_sub_answers(sub_answers)
        evidence_text = self._format_evidence(all_chunks or self._collect_chunks(sub_answers))

        prompt = self.prompt_template.replace("{question}", question)
        prompt = prompt.replace("{sub_answers}", sub_answers_text)
        prompt = prompt.replace("{final_answer}", final_answer)
        prompt = prompt.replace("{evidence}", evidence_text)

        try:
            response = self.llm_client.generate(
                prompt=prompt,
                system="You are a rigorous validator. Check reasoning chains for soundness. Be precise.",
                temperature=0.1,
                max_tokens=400,
            )
            return self._parse_response(response)
        except Exception as e:
            return self._invalid_result(f"Validation failed: {e}")

    def _format_sub_answers(self, sub_answers: List[Dict]) -> str:
        """Format sub-answers for the prompt."""
        formatted = []
        for i, sub in enumerate(sub_answers, 1):
            q = sub.get("question", "")
            a = sub.get("answer", "")
            formatted.append(f"Q{i}: {q}\nA{i}: {a}")
        return "\n\n".join(formatted)

    def _format_evidence(self, chunks: List[Dict]) -> str:
        """Format evidence chunks."""
        if not chunks:
            return "No evidence chunks available."

        # Limit to first 10 chunks to avoid token explosion
        formatted = []
        for i, chunk in enumerate(chunks[:10], 1):
            text = chunk.get("text", "")[:300]
            src = chunk.get("source", "?")
            page = chunk.get("page", "?")
            formatted.append(f"[Evidence {i}] ({src}, p.{page}): {text}")
        return "\n\n".join(formatted)

    def _collect_chunks(self, sub_answers: List[Dict]) -> List[Dict]:
        """Collect all chunks from sub-answers."""
        all_chunks = []
        for sub in sub_answers:
            all_chunks.extend(sub.get("chunks", []))
        return all_chunks

    def _parse_response(self, response: str) -> Dict:
        """Parse validator LLM response."""
        # Default values
        score = 0.5
        supported = "PARTIAL"
        issues = []
        suggested_conf = 0.5
        summary = "Default validation"

        # Extract VALIDATION_SCORE
        match = re.search(r"VALIDATION_SCORE:\s*([0-9]*\.?[0-9]+)", response, re.IGNORECASE)
        if match:
            try:
                score = max(0.0, min(1.0, float(match.group(1))))
            except ValueError:
                pass

        # Extract SUPPORTED
        match = re.search(r"SUPPORTED:\s*(YES|PARTIAL|NO)", response, re.IGNORECASE)
        if match:
            supported = match.group(1).upper()

        # Extract ISSUES
        match = re.search(r"ISSUES:\s*(.+?)(?=\n[A-Z_]+:|$)", response, re.IGNORECASE | re.DOTALL)
        if match:
            issues_str = match.group(1).strip()
            if issues_str.lower() not in ("none", "n/a", ""):
                # Split by semicolon or newline
                issues = [
                    i.strip("-* ").strip()
                    for i in re.split(r"[;\n]", issues_str)
                    if i.strip()
                ]
                issues = [i for i in issues if i and i.lower() not in ("none", "n/a")][:5]

        # Extract SUGGESTED_CONFIDENCE
        match = re.search(r"SUGGESTED_CONFIDENCE:\s*([0-9]*\.?[0-9]+)", response, re.IGNORECASE)
        if match:
            try:
                suggested_conf = max(0.0, min(1.0, float(match.group(1))))
            except ValueError:
                pass

        # Extract SUMMARY
        match = re.search(r"SUMMARY:\s*(.+?)$", response, re.IGNORECASE | re.DOTALL)
        if match:
            summary = match.group(1).strip()

        return {
            "validation_score": round(score, 3),
            "supported": supported,
            "issues": issues,
            "suggested_confidence": round(suggested_conf, 3),
            "summary": summary,
        }

    def _invalid_result(self, reason: str) -> Dict:
        """Return a default invalid result."""
        return {
            "validation_score": 0.0,
            "supported": "NO",
            "issues": [reason],
            "suggested_confidence": 0.0,
            "summary": reason,
        }

    @staticmethod
    def _default_prompt() -> str:
        return """Validate the reasoning chain.

Question: {question}
Sub-answers: {sub_answers}
Final answer: {final_answer}
Evidence: {evidence}

Output:
VALIDATION_SCORE: 0.0-1.0
SUPPORTED: YES/PARTIAL/NO
ISSUES: ...
SUGGESTED_CONFIDENCE: 0.0-1.0
SUMMARY: ..."""
