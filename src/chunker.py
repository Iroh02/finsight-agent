"""Text chunking and document splitting."""

from typing import List, Dict


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    """
    Chunk text into overlapping segments.

    TODO: Implement using LangChain RecursiveCharacterTextSplitter

    Args:
        text: Text to chunk
        chunk_size: Size of each chunk in tokens (~4 chars per token)
        overlap: Overlap between chunks in tokens

    Returns:
        List of text chunks
    """
    raise NotImplementedError("Implement chunk_text")


def chunk_with_metadata(text: str, source: str, page: int, chunk_size: int = 500) -> List[Dict]:
    """
    Chunk text while preserving source metadata.

    Returns:
        List of dicts with keys: text, source, page, chunk_index
    """
    raise NotImplementedError("Implement chunk_with_metadata")


class TextChunker:
    """Manage chunking strategy and settings."""

    def __init__(self, chunk_size: int = 500, overlap: int = 50):
        """Initialize chunker with settings."""
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, documents: List[Dict]) -> List[Dict]:
        """
        Chunk a list of documents.

        Args:
            documents: List of dicts with 'text', 'source', 'page'

        Returns:
            List of chunked documents with metadata
        """
        raise NotImplementedError("Implement chunk method")
