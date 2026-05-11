"""Text chunking and document splitting."""

from typing import List, Dict


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 100) -> List[str]:
    """
    Chunk text into overlapping segments by character count.

    Args:
        text: Text to chunk
        chunk_size: Size of each chunk in characters (~250 tokens for 1000 chars)
        overlap: Overlap between chunks in characters

    Returns:
        List of text chunks
    """
    if not text:
        return []

    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size

        # Try to break at sentence boundary if possible
        if end < len(text):
            # Look for sentence ending in last 200 chars
            search_start = max(start + chunk_size // 2, end - 200)
            best_break = -1
            for char in [". ", ".\n", "! ", "? ", "\n\n"]:
                idx = text.rfind(char, search_start, end)
                if idx > best_break:
                    best_break = idx + len(char)
            if best_break > 0:
                end = best_break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        # Move start forward, accounting for overlap
        start = end - overlap if end < len(text) else end

    return chunks


def chunk_with_metadata(
    text: str,
    source: str,
    page: int = None,
    chunk_size: int = 1000,
    overlap: int = 100,
) -> List[Dict]:
    """
    Chunk text while preserving source metadata.

    Returns:
        List of dicts with keys: text, source, page, chunk_index
    """
    text_chunks = chunk_text(text, chunk_size, overlap)
    return [
        {
            "text": chunk,
            "source": source,
            "page": page,
            "chunk_index": i,
        }
        for i, chunk in enumerate(text_chunks)
    ]


class TextChunker:
    """Manage chunking strategy and settings."""

    def __init__(self, chunk_size: int = 1000, overlap: int = 100):
        """Initialize chunker with settings."""
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, documents: List[Dict]) -> List[Dict]:
        """
        Chunk a list of documents.

        Args:
            documents: List of dicts with 'text', 'filename' (or 'source'), 'page_number' (or 'page')

        Returns:
            List of chunked documents with metadata
        """
        all_chunks = []
        for doc in documents:
            source = doc.get("filename", doc.get("source", "unknown"))
            page = doc.get("page_number", doc.get("page", None))
            text = doc.get("text", "")

            chunks = chunk_with_metadata(
                text=text,
                source=source,
                page=page,
                chunk_size=self.chunk_size,
                overlap=self.overlap,
            )
            all_chunks.extend(chunks)

        return all_chunks
