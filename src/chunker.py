"""Text chunking and document splitting."""

import logging
from typing import List, Dict

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
logger = logging.getLogger(__name__)

_CHUNK_SIZE = 500
_CHUNK_OVERLAP = 50
_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]


def chunk_documents(pages: List[Dict]) -> List[Document]:
    """Chunk pages into overlapping LangChain Documents preserving metadata.

    Args:
        pages: List of dicts with keys: text, source, page

    Returns:
        List of Documents with .page_content and .metadata (source, page)
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=_CHUNK_SIZE,
        chunk_overlap=_CHUNK_OVERLAP,
        separators=_SEPARATORS,
    )
    docs: List[Document] = []
    for page in pages:
        text = page.get("text", "").strip()
        if not text:
            continue
        for chunk in splitter.split_text(text):
            docs.append(
                Document(
                    page_content=chunk,
                    metadata={"source": page["source"], "page": page["page"]},
                )
            )
    logger.info(f"Created {len(docs)} chunks from {len(pages)} pages")
    return docs


def chunk_text(text: str, chunk_size: int = _CHUNK_SIZE, overlap: int = _CHUNK_OVERLAP) -> List[str]:
    """Chunk a raw string into overlapping segments."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=_SEPARATORS,
    )
    return splitter.split_text(text)


def chunk_with_metadata(
    text: str,
    source: str,
    page: int,
    chunk_size: int = _CHUNK_SIZE,
) -> List[Dict]:
    """Chunk text while preserving source metadata as plain dicts."""
    return [
        {"text": chunk, "source": source, "page": page, "chunk_index": i}
        for i, chunk in enumerate(chunk_text(text, chunk_size=chunk_size))
    ]


class TextChunker:
    """Reusable chunker that returns plain dicts (used by RAGPipeline)."""

    def __init__(self, chunk_size: int = _CHUNK_SIZE, overlap: int = _CHUNK_OVERLAP):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=overlap,
            separators=_SEPARATORS,
        )

    def chunk(self, documents: List[Dict]) -> List[Dict]:
        """Chunk a list of page dicts into smaller dicts with metadata."""
        result: List[Dict] = []
        for doc in documents:
            text = doc.get("text", "").strip()
            if not text:
                continue
            for i, chunk in enumerate(self._splitter.split_text(text)):
                result.append(
                    {
                        "text": chunk,
                        "source": doc["source"],
                        "page": doc["page"],
                        "chunk_index": i,
                    }
                )
        return result
