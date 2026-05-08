"""Citation extraction and management."""

from typing import Dict, List


class CitationExtractor:
    """Extract and format citations from answer and retrieved chunks."""

    def extract_citations(self, answer: str, chunks: List[Dict]) -> List[Dict]:
        """
        Extract citations from generated answer by mapping claims to chunks.

        Args:
            answer: Generated answer text
            chunks: Retrieved chunks with metadata

        Returns:
            List of citation dicts with keys:
            - source: Document filename
            - page: Page number
            - excerpt: Short text excerpt from chunk
            - chunk_index: Index of supporting chunk
        """
        raise NotImplementedError("Implement extract_citations")

    def format_citations(self, citations: List[Dict]) -> str:
        """Format citations for display."""
        if not citations:
            return ""

        lines = []
        for citation in citations:
            line = f"[Source: {citation['source']}"
            if citation.get('page'):
                line += f", Page {citation['page']}"
            line += "]"
            lines.append(line)

        return "\n".join(lines)

    def get_inline_citations(self, answer: str, chunks: List[Dict]) -> str:
        """
        Add inline citations to answer text.

        TODO: Implement LLM-assisted citation mapping
        """
        raise NotImplementedError("Implement get_inline_citations")
