"""Cross-encoder reranker for retrieval refinement.

Improves retrieval quality by re-scoring chunks based on
fine-grained semantic relevance to the query (not just vector similarity).

Reference: This is a standard technique in production RAG systems
(used by Cohere Rerank, ColBERT, etc.).
"""

from typing import List, Dict, Optional


class CrossEncoderReranker:
    """
    Rerank retrieved chunks using a cross-encoder model.

    Cross-encoders look at the (query, chunk) pair together and produce
    a fine-grained relevance score. Slower than vector search but more accurate.

    Default model: cross-encoder/ms-marco-MiniLM-L-6-v2
    - Free, local, no API needed
    - Trained on MS MARCO (Microsoft's search benchmark)
    - 22M parameters, fast on CPU
    """

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        """
        Initialize cross-encoder reranker.

        Args:
            model_name: HuggingFace cross-encoder model name
        """
        self.model_name = model_name
        self._model = None

    @property
    def model(self):
        """Lazy-load model on first use."""
        if self._model is None:
            from sentence_transformers import CrossEncoder
            print(f"Loading reranker model: {self.model_name}...")
            self._model = CrossEncoder(self.model_name)
            print(f"  Reranker loaded.")
        return self._model

    def rerank(
        self,
        query: str,
        chunks: List[Dict],
        top_k: Optional[int] = None,
    ) -> List[Dict]:
        """
        Rerank chunks by relevance to the query.

        Args:
            query: Search query
            chunks: List of chunk dicts (must have 'text' key)
            top_k: Return only top-k chunks (None = return all reranked)

        Returns:
            Reranked list of chunks with updated 'rerank_score' field
        """
        if not chunks:
            return []

        # Build (query, chunk_text) pairs
        pairs = [(query, chunk["text"]) for chunk in chunks]

        # Score each pair using the cross-encoder
        scores = self.model.predict(pairs, show_progress_bar=False)

        # Attach scores to chunks
        scored_chunks = []
        for chunk, score in zip(chunks, scores):
            scored_chunk = dict(chunk)  # Don't mutate original
            scored_chunk["rerank_score"] = float(score)
            # Update primary score for downstream use
            scored_chunk["score"] = float(score)
            scored_chunks.append(scored_chunk)

        # Sort by rerank score (descending)
        scored_chunks.sort(key=lambda x: x["rerank_score"], reverse=True)

        # Return top-k
        if top_k is not None:
            scored_chunks = scored_chunks[:top_k]

        return scored_chunks

    def rerank_with_initial_scores(
        self,
        query: str,
        chunks: List[Dict],
        top_k: Optional[int] = None,
        alpha: float = 0.7,
    ) -> List[Dict]:
        """
        Rerank using a weighted combination of vector and rerank scores.

        Args:
            query: Search query
            chunks: List of chunks (must have 'text' and 'score' keys)
            top_k: Return top-k results
            alpha: Weight for rerank score (1-alpha for original score)

        Returns:
            Reranked chunks with combined scores
        """
        reranked = self.rerank(query, chunks, top_k=None)

        for chunk in reranked:
            original = chunk.get("score", 0.0) if "score" not in chunk else chunk.get("original_score", 0.0)
            rerank = chunk.get("rerank_score", 0.0)
            # Weighted combination
            combined = alpha * rerank + (1 - alpha) * original
            chunk["combined_score"] = float(combined)
            chunk["score"] = float(combined)

        # Re-sort by combined score
        reranked.sort(key=lambda x: x["combined_score"], reverse=True)

        if top_k is not None:
            reranked = reranked[:top_k]

        return reranked
