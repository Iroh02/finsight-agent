"""Text chunking strategies: standard, parent-child, and semantic.

Three strategies are exposed:
- TextChunker        — character-based with sentence-boundary snapping (default)
- ParentChildChunker — LangChain-style; stores large parent context per small child chunk
- SemanticChunker    — embedding-based boundary detection (Kamradt / LangChain 2024)
"""

import re
from typing import List, Dict, Optional

# Keys that carry per-document metadata and should be forwarded to every chunk
_META_KEYS = ("company", "year", "quarter", "doc_type", "fiscal_period")


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 100) -> List[str]:
    """
    Chunk text into overlapping segments, snapping to sentence boundaries.

    Args:
        text: Text to chunk
        chunk_size: Target chunk size in characters (~250 tokens for 1000 chars)
        overlap: Character overlap between consecutive chunks

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

        # Snap to sentence boundary in the last 200 chars of the window
        if end < len(text):
            search_start = max(start + chunk_size // 2, end - 200)
            best_break = -1
            for delimiter in (". ", ".\n", "! ", "? ", "\n\n"):
                idx = text.rfind(delimiter, search_start, end)
                if idx > best_break:
                    best_break = idx + len(delimiter)
            if best_break > 0:
                end = best_break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap if end < len(text) else end

    return chunks


def chunk_with_metadata(
    text: str,
    source: str,
    page: Optional[int] = None,
    chunk_size: int = 1000,
    overlap: int = 100,
    extra_meta: Optional[Dict] = None,
) -> List[Dict]:
    """
    Chunk text while preserving source metadata and any extra fields.

    Returns:
        List of dicts with keys: text, source, page, chunk_index + extra_meta keys
    """
    text_chunks = chunk_text(text, chunk_size, overlap)
    base = extra_meta or {}
    return [
        {
            **base,
            "text": chunk,
            "source": source,
            "page": page,
            "chunk_index": i,
            "chunk_type": base.get("chunk_type", "standard"),
        }
        for i, chunk in enumerate(text_chunks)
    ]


def _extract_doc_meta(doc: Dict) -> Dict:
    """Pull enriched metadata fields out of a document dict."""
    return {k: doc[k] for k in _META_KEYS if k in doc}


class TextChunker:
    """Standard character-based chunker with sentence-boundary snapping."""

    def __init__(self, chunk_size: int = 1000, overlap: int = 100):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, documents: List[Dict]) -> List[Dict]:
        """
        Chunk a list of documents.

        Args:
            documents: List of dicts with 'text', 'filename' (or 'source'),
                       'page_number' (or 'page'), and optional enriched metadata.

        Returns:
            List of chunked documents with metadata forwarded.
        """
        all_chunks = []
        for doc in documents:
            source = doc.get("filename", doc.get("source", "unknown"))
            page = doc.get("page_number", doc.get("page", None))
            text = doc.get("text", "")
            extra_meta = _extract_doc_meta(doc)

            chunks = chunk_with_metadata(
                text=text,
                source=source,
                page=page,
                chunk_size=self.chunk_size,
                overlap=self.overlap,
                extra_meta=extra_meta,
            )
            all_chunks.extend(chunks)

        return all_chunks


class ParentChildChunker:
    """
    Parent-Child Chunking — LangChain ParentDocumentRetriever technique.

    Large parent chunks (default 2000 chars) give broad context.
    Small child chunks (default 500 chars) are what the vector store actually searches.
    Each child carries its parent's text in metadata so answer generation can use
    the full surrounding context even though retrieval matched the narrow child.

    Reference: LangChain ParentDocumentRetriever (2023-2024)
    """

    def __init__(
        self,
        parent_size: int = 2000,
        child_size: int = 500,
        parent_overlap: int = 200,
        child_overlap: int = 50,
    ):
        self.parent_size = parent_size
        self.child_size = child_size
        self.parent_overlap = parent_overlap
        self.child_overlap = child_overlap

    def chunk(self, documents: List[Dict]) -> List[Dict]:
        """
        Create child chunks, each with its parent context embedded in metadata.

        Returns only child chunks (the searchable units); parent text is stored
        in the 'parent_text' metadata field for context expansion at query time.
        """
        all_children = []

        for doc in documents:
            source = doc.get("filename", doc.get("source", "unknown"))
            page = doc.get("page_number", doc.get("page", None))
            text = doc.get("text", "")
            extra_meta = _extract_doc_meta(doc)

            if not text.strip():
                continue

            # Split into parents first
            parents = chunk_text(text, self.parent_size, self.parent_overlap)

            for p_idx, parent_text in enumerate(parents):
                parent_id = f"{source}_p{page or 0}_par{p_idx}"

                # Split each parent into children
                children = chunk_text(parent_text, self.child_size, self.child_overlap)

                for c_idx, child_text in enumerate(children):
                    all_children.append({
                        **extra_meta,
                        "text": child_text,
                        "source": source,
                        "page": page,
                        "chunk_index": p_idx * 100 + c_idx,
                        "chunk_type": "child",
                        "parent_id": parent_id,
                        # Store first 500 chars of parent — enough for answer context
                        "parent_text": parent_text[:500],
                    })

        return all_children


class SemanticChunker:
    """
    Semantic Chunking using sentence-embedding cosine distances to detect topic shifts.

    Algorithm (Kamradt 2023 / LangChain SemanticChunker 2024):
    1. Split text into sentences.
    2. Embed overlapping windows of `window_size` sentences.
    3. Compute cosine distance between adjacent windows.
    4. Breakpoints are placed where distance > 70th-percentile threshold.
    5. Merge sentences between breakpoints; fall back to character chunking if
       a segment exceeds `max_chunk_size`.

    The embedder is lazy-loaded on first use (avoids slow import at startup).
    """

    def __init__(
        self,
        max_chunk_size: int = 1500,
        min_chunk_size: int = 100,
        breakpoint_percentile: int = 70,
        window_size: int = 3,
        embedder=None,
    ):
        self.max_chunk_size = max_chunk_size
        self.min_chunk_size = min_chunk_size
        self.breakpoint_percentile = breakpoint_percentile
        self.window_size = window_size
        self._embedder = embedder

    @property
    def embedder(self):
        if self._embedder is None:
            from src.embedder import get_embedder
            self._embedder = get_embedder()
        return self._embedder

    @staticmethod
    def _split_sentences(text: str) -> List[str]:
        """Split text into individual sentences."""
        parts = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in parts if s.strip()]

    @staticmethod
    def _cosine_distance(a: List[float], b: List[float]) -> float:
        import numpy as np
        a_arr, b_arr = np.array(a), np.array(b)
        denom = np.linalg.norm(a_arr) * np.linalg.norm(b_arr)
        return 1.0 - float(np.dot(a_arr, b_arr) / denom) if denom > 0 else 1.0

    def _find_breakpoints(self, sentences: List[str]) -> List[int]:
        """Return sentence indices at which a new chunk should begin."""
        if len(sentences) < self.window_size * 2:
            return []

        windows = [
            " ".join(sentences[i: i + self.window_size])
            for i in range(len(sentences) - self.window_size + 1)
        ]
        embeddings = self.embedder.embed(windows)

        distances = [
            self._cosine_distance(embeddings[i], embeddings[i + 1])
            for i in range(len(embeddings) - 1)
        ]

        import numpy as np
        threshold = float(np.percentile(distances, self.breakpoint_percentile))
        # Ensure we're at least at the configured minimum
        return [i + 1 for i, d in enumerate(distances) if d >= threshold]

    def chunk(self, documents: List[Dict]) -> List[Dict]:
        """Create semantically coherent chunks from a list of documents."""
        all_chunks = []

        for doc in documents:
            source = doc.get("filename", doc.get("source", "unknown"))
            page = doc.get("page_number", doc.get("page", None))
            text = doc.get("text", "")
            extra_meta = _extract_doc_meta(doc)

            if not text.strip():
                continue

            sentences = self._split_sentences(text)
            chunk_idx = 0

            if len(sentences) <= 1:
                all_chunks.append({
                    **extra_meta,
                    "text": text,
                    "source": source,
                    "page": page,
                    "chunk_index": chunk_idx,
                    "chunk_type": "semantic",
                })
                continue

            try:
                breakpoints = self._find_breakpoints(sentences)
            except Exception:
                breakpoints = []

            # Build segments from breakpoints
            segments: List[List[str]] = []
            prev = 0
            for bp in breakpoints:
                segments.append(sentences[prev:bp])
                prev = bp
            segments.append(sentences[prev:])

            for segment in segments:
                segment_text = " ".join(segment)

                if len(segment_text) > self.max_chunk_size:
                    # Very long segment — fall back to character chunking
                    sub_chunks = chunk_text(segment_text, self.max_chunk_size, 100)
                    for sub in sub_chunks:
                        if len(sub) >= self.min_chunk_size:
                            all_chunks.append({
                                **extra_meta,
                                "text": sub,
                                "source": source,
                                "page": page,
                                "chunk_index": chunk_idx,
                                "chunk_type": "semantic",
                            })
                            chunk_idx += 1
                elif len(segment_text) >= self.min_chunk_size:
                    all_chunks.append({
                        **extra_meta,
                        "text": segment_text,
                        "source": source,
                        "page": page,
                        "chunk_index": chunk_idx,
                        "chunk_type": "semantic",
                    })
                    chunk_idx += 1

        return all_chunks
