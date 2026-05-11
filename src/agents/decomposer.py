"""Decomposer Agent: Breaks complex questions into atomic sub-queries.

Inspired by Self-Ask (Press et al., 2022) and IRCoT (Trivedi et al., 2023).
"""

import re
from typing import List, Optional
from src.llm_client import LLMClient, load_prompt, get_llm_client


class DecomposerAgent:
    """
    Decomposes complex questions into atomic, self-contained sub-questions.

    Each sub-question is:
    - Self-contained (answerable independently)
    - Atomic (asks one thing)
    - Ordered (independent first, dependent later)
    """

    MAX_SUB_QUERIES = 5

    def __init__(self, llm_client: Optional[LLMClient] = None):
        """Initialize decomposer."""
        self.llm_client = llm_client or get_llm_client()
        try:
            self.prompt_template = load_prompt("decomposer")
        except FileNotFoundError:
            self.prompt_template = self._default_prompt()

    def decompose(self, question: str) -> List[str]:
        """
        Break question into sub-queries.

        Args:
            question: Original complex question

        Returns:
            List of sub-question strings (1-5 items)
        """
        if not question or not question.strip():
            return []

        prompt = self.prompt_template.replace("{question}", question)

        try:
            response = self.llm_client.generate(
                prompt=prompt,
                system="You are a precise question decomposition agent. Output only sub-queries in the requested format.",
                temperature=0.1,
                max_tokens=400,
            )
            sub_queries = self._parse_response(response)

            # Safety: if no sub-queries parsed, return original as single
            if not sub_queries:
                return [question]

            # Cap at MAX_SUB_QUERIES
            return sub_queries[: self.MAX_SUB_QUERIES]
        except Exception:
            # On failure, return original question as the only sub-query
            return [question]

    def _parse_response(self, response: str) -> List[str]:
        """Parse LLM response to extract sub-queries."""
        sub_queries = []

        # Find all SUB_QUERY_N: lines
        matches = re.findall(
            r"SUB_QUERY_\d+:\s*(.+?)(?=\nSUB_QUERY_\d+:|$)",
            response,
            re.DOTALL,
        )

        for match in matches:
            cleaned = match.strip()
            # Remove trailing punctuation issues
            cleaned = re.sub(r"\s+", " ", cleaned)
            if cleaned and len(cleaned) > 3:
                sub_queries.append(cleaned)

        # Alternative: parse numbered list format
        if not sub_queries:
            numbered = re.findall(r"^\s*\d+[.)]\s*(.+?)$", response, re.MULTILINE)
            for item in numbered:
                cleaned = item.strip()
                if cleaned and len(cleaned) > 3:
                    sub_queries.append(cleaned)

        return sub_queries

    @staticmethod
    def _default_prompt() -> str:
        return """Break this question into atomic sub-queries:
{question}

Output:
SUB_QUERY_1: ...
SUB_QUERY_2: ...
..."""
