"""HyDE: Hypothetical Document Embeddings for improved retrieval.

Reference: Gao et al., 2023 - "Precise Zero-Shot Dense Retrieval without Relevance Labels"

Standard retrieval: embed the QUESTION, find similar chunks.
HyDE: generate a HYPOTHETICAL answer, embed THAT, find chunks similar to it.

Why it works:
- Questions and documents often have very different vocabulary
- A hypothetical answer is closer to actual document language
- Bridges the question-document semantic gap
"""

from typing import Optional
from src.llm_client import LLMClient, load_prompt, get_llm_client


class HyDEAugmenter:
    """
    Generates hypothetical answer for HyDE-style retrieval.

    Workflow:
    1. Take user question
    2. LLM generates a "fake" answer in document-like language
    3. Caller embeds the fake answer (not the question)
    4. Search vector store with that embedding
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        """Initialize HyDE augmenter."""
        self.llm_client = llm_client or get_llm_client()
        try:
            self.prompt_template = load_prompt("hyde")
        except FileNotFoundError:
            self.prompt_template = self._default_prompt()

    def generate_hypothetical(self, question: str) -> str:
        """
        Generate a hypothetical document-like answer to the question.

        Args:
            question: Original user question

        Returns:
            Hypothetical answer text (used for retrieval embedding)
        """
        if not question or not question.strip():
            return ""

        prompt = self.prompt_template.replace("{question}", question)

        try:
            response = self.llm_client.generate(
                prompt=prompt,
                system="You generate confident, document-style hypothetical answers. No hedging.",
                temperature=0.4,
                max_tokens=200,
            )
            return response.strip()
        except Exception:
            # Fallback: return question itself if generation fails
            return question

    def augment_query(self, question: str, include_original: bool = True) -> str:
        """
        Build augmented query: original + hypothetical.

        Args:
            question: Original question
            include_original: If True, concatenate original with hypothetical

        Returns:
            Augmented query string for embedding
        """
        hypothetical = self.generate_hypothetical(question)
        if not hypothetical:
            return question

        if include_original:
            return f"{question}\n\n{hypothetical}"
        return hypothetical

    @staticmethod
    def _default_prompt() -> str:
        return """Write a brief, plausible answer to this question as if quoting an annual report:

Question: {question}

Hypothetical Answer:"""
