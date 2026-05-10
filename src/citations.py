"""Citation extraction and management."""

import re
from typing import Dict, List, Optional
from src.llm_client import LLMClient, load_prompt, get_llm_client


class CitationExtractor:
    """
    Extract source citations from generated answers.

    Two modes:
    - Simple: Every retrieved chunk becomes a citation (dedup by source+page)
    - Smart: LLM-assisted mapping of claims to specific chunks
    """

    def __init__(self, llm_client: Optional[LLMClient] = None, use_llm: bool = False):
        """
        Initialize citation extractor.

        Args:
            llm_client: LLM client for smart citation mapping
            use_llm: If True, use LLM to map claims to chunks (more accurate, costs tokens)
        """
        self.llm_client = llm_client or (get_llm_client() if use_llm else None)
        self.use_llm = use_llm

        # Try to load the source explanation prompt
        try:
            self.source_prompt = load_prompt("source_explanation")
        except FileNotFoundError:
            self.source_prompt = self._default_source_prompt()

    def extract_citations(self, answer: str, chunks: List[Dict]) -> List[Dict]:
        """
        Extract citations from generated answer.

        Args:
            answer: Generated answer text
            chunks: Retrieved chunks with metadata (source, page, text)

        Returns:
            List of citation dicts:
            - source: Document filename
            - page: Page number
            - excerpt: Brief excerpt from chunk
            - chunk_index: Index of supporting chunk (if available)
        """
        if not chunks:
            return []

        if self.use_llm and self.llm_client:
            return self._smart_extract(answer, chunks)
        else:
            return self._simple_extract(answer, chunks)

    def _simple_extract(self, answer: str, chunks: List[Dict]) -> List[Dict]:
        """
        Simple citation extraction: every chunk → citation, deduplicated.

        Fast, no extra API calls.
        """
        seen = set()
        citations = []

        for i, chunk in enumerate(chunks):
            source = chunk.get("source", "unknown")
            page = chunk.get("page", None)

            # Deduplicate by source + page
            key = (source, page)
            if key in seen:
                continue
            seen.add(key)

            # Take first 150 chars as excerpt
            excerpt = chunk.get("text", "")[:150].strip()
            if excerpt and len(chunk.get("text", "")) > 150:
                excerpt += "..."

            citations.append({
                "source": source,
                "page": page,
                "excerpt": excerpt,
                "chunk_index": i,
            })

        return citations

    def _smart_extract(self, answer: str, chunks: List[Dict]) -> List[Dict]:
        """
        Smart citation extraction: ask LLM which chunks support which claims.

        More accurate but costs tokens.
        """
        # Format chunks for the prompt
        chunks_text = self._format_chunks_for_prompt(chunks)

        # Build prompt
        prompt = self.source_prompt.replace("{answer}", answer)
        prompt = prompt.replace("{chunks}", chunks_text)

        try:
            response = self.llm_client.generate(
                prompt=prompt,
                system="You are extracting citations. Be precise. Only cite chunks that directly support claims.",
                temperature=0.1,
                max_tokens=512,
            )
            return self._parse_llm_citations(response, chunks)
        except Exception:
            # Fallback to simple extraction
            return self._simple_extract(answer, chunks)

    def _parse_llm_citations(self, response: str, chunks: List[Dict]) -> List[Dict]:
        """
        Parse LLM citation response.

        Expected format:
            CHUNK [n]: source.pdf, Page X
            SUPPORTING_CLAIM: ...
            EXCERPT: ...
        """
        citations = []
        # Find all CHUNK [n] references
        chunk_refs = re.findall(
            r"CHUNK\s*\[?(\d+)\]?[:\s]+(.*?)(?=CHUNK\s*\[?\d+\]?|$)",
            response,
            re.DOTALL | re.IGNORECASE,
        )

        for chunk_num_str, content in chunk_refs:
            try:
                chunk_idx = int(chunk_num_str) - 1  # Convert to 0-indexed
                if 0 <= chunk_idx < len(chunks):
                    chunk = chunks[chunk_idx]
                    citations.append({
                        "source": chunk.get("source", "unknown"),
                        "page": chunk.get("page", None),
                        "excerpt": chunk.get("text", "")[:150].strip() + "...",
                        "chunk_index": chunk_idx,
                    })
            except (ValueError, IndexError):
                continue

        # If parsing failed completely, fall back to simple extraction
        if not citations:
            return self._simple_extract("", chunks)

        return citations

    def _format_chunks_for_prompt(self, chunks: List[Dict]) -> str:
        """Format chunks for source explanation prompt."""
        formatted = []
        for i, chunk in enumerate(chunks, 1):
            source = chunk.get("source", "unknown")
            page = chunk.get("page", "?")
            text = chunk.get("text", "")
            formatted.append(f"CHUNK [{i}]: {source}, Page {page}\n{text}")
        return "\n\n".join(formatted)

    def format_citations(self, citations: List[Dict]) -> str:
        """Format citations as readable text."""
        if not citations:
            return "No citations available."

        lines = []
        for i, citation in enumerate(citations, 1):
            source = citation.get("source", "unknown")
            page = citation.get("page")
            line = f"[{i}] {source}"
            if page is not None:
                line += f", Page {page}"
            lines.append(line)
        return "\n".join(lines)

    @staticmethod
    def _default_source_prompt() -> str:
        """Fallback source explanation prompt."""
        return """Match each claim in the answer to the supporting chunk.

Answer: {answer}

Chunks:
{chunks}

For each chunk that supports a claim in the answer, output:
CHUNK [n]: source, Page X
SUPPORTING_CLAIM: [the claim it supports]
EXCERPT: [key text from chunk]

Only include chunks that directly support claims."""
