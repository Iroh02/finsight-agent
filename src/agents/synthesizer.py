"""Synthesizer Agent: Combines multiple sub-answers into a unified response.

Inspired by IRCoT (Trivedi et al., 2023) and ReAct (Yao et al., 2023).
"""

import re
from typing import Dict, List, Optional
from src.llm_client import LLMClient, load_prompt, get_llm_client


class SynthesizerAgent:
    """
    Synthesizes multiple sub-answers into a coherent final answer.

    Takes a list of (sub_question, sub_answer) pairs and combines them,
    cross-referencing information and resolving any contradictions.
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        """Initialize synthesizer."""
        self.llm_client = llm_client or get_llm_client()
        try:
            self.prompt_template = load_prompt("synthesizer")
        except FileNotFoundError:
            self.prompt_template = self._default_prompt()

    def synthesize(
        self,
        question: str,
        sub_answers: List[Dict],
    ) -> Dict:
        """
        Combine sub-answers into a unified response.

        Args:
            question: Original question
            sub_answers: List of dicts with keys: question, answer, chunks

        Returns:
            Dict with:
            - answer: Synthesized final answer
            - reasoning: How sub-answers were combined
        """
        if not sub_answers:
            return {
                "answer": "No sub-answers available for synthesis.",
                "reasoning": "Empty sub-answers list",
            }

        # If only one sub-answer, return it directly
        if len(sub_answers) == 1:
            single = sub_answers[0]
            return {
                "answer": single.get("answer", ""),
                "reasoning": "Single sub-query, no synthesis needed",
            }

        # Format sub-answers for the prompt
        formatted_subs = self._format_sub_answers(sub_answers)

        # Build prompt
        prompt = self.prompt_template.replace("{question}", question)
        prompt = prompt.replace("{sub_answers}", formatted_subs)

        try:
            response = self.llm_client.generate(
                prompt=prompt,
                system="You are an expert synthesis agent. Combine sub-answers into one coherent response. Preserve citations.",
                temperature=0.3,
                max_tokens=600,
            )
            return self._parse_response(response, sub_answers)
        except Exception as e:
            # Fallback: concatenate sub-answers
            return self._fallback_synthesis(sub_answers, str(e))

    def _format_sub_answers(self, sub_answers: List[Dict]) -> str:
        """Format sub-answers for the prompt."""
        formatted = []
        for i, sub in enumerate(sub_answers, 1):
            q = sub.get("question", "")
            a = sub.get("answer", "")
            sources = self._extract_source_summary(sub.get("chunks", []))
            formatted.append(
                f"Sub-Question {i}: {q}\n"
                f"Sub-Answer {i}: {a}\n"
                f"Sources: {sources}"
            )
        return "\n\n".join(formatted)

    def _extract_source_summary(self, chunks: List[Dict]) -> str:
        """Extract a brief source summary from chunks."""
        if not chunks:
            return "No sources"
        sources = set()
        for chunk in chunks[:3]:
            src = chunk.get("source", "unknown")
            page = chunk.get("page", "?")
            sources.add(f"{src} p.{page}")
        return ", ".join(sources)

    def _parse_response(self, response: str, sub_answers: List[Dict]) -> Dict:
        """Parse LLM synthesis response."""
        answer = ""
        reasoning = ""

        # Extract FINAL_ANSWER
        match = re.search(
            r"FINAL_ANSWER:\s*(.+?)(?=SYNTHESIS_REASONING:|$)",
            response,
            re.DOTALL | re.IGNORECASE,
        )
        if match:
            answer = match.group(1).strip()

        # Extract SYNTHESIS_REASONING
        match = re.search(
            r"SYNTHESIS_REASONING:\s*(.+?)$",
            response,
            re.DOTALL | re.IGNORECASE,
        )
        if match:
            reasoning = match.group(1).strip()

        # If parsing failed, use entire response as answer
        if not answer:
            answer = response.strip()
            reasoning = "Unstructured synthesis output"

        return {
            "answer": answer,
            "reasoning": reasoning,
        }

    def _fallback_synthesis(self, sub_answers: List[Dict], error: str) -> Dict:
        """Concatenate sub-answers when LLM synthesis fails."""
        parts = []
        for i, sub in enumerate(sub_answers, 1):
            q = sub.get("question", f"Sub-question {i}")
            a = sub.get("answer", "[no answer]")
            parts.append(f"Regarding '{q}': {a}")

        return {
            "answer": " ".join(parts),
            "reasoning": f"Fallback concatenation due to error: {error[:50]}",
        }

    @staticmethod
    def _default_prompt() -> str:
        return """Combine these sub-answers into one unified response to the question.

Question: {question}

Sub-Answers:
{sub_answers}

Output:
FINAL_ANSWER: [unified answer]
SYNTHESIS_REASONING: [how you combined them]"""
