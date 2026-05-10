"""Document retrieval from vector store with optional reranking."""

from typing import List, Dict, Optional
from src.vectorstore import VectorStore


class Retriever:
    """
    Retrieve documents from vector store, with optional cross-encoder reranking.

    Two-stage retrieval (when reranker enabled):
    1. Vector search: Fast, retrieves k_retrieve candidates (default 20)
    2. Reranker: Slow but accurate, picks top-k (default 5) from candidates

    This is the standard SOTA approach used in production RAG systems.
    """

    def __init__(
        self,
        vectorstore: VectorStore,
        use_reranker: bool = False,
        reranker=None,
        retrieve_multiplier: int = 4,
    ):
        """
        Initialize retriever with optional reranking.

        Args:
            vectorstore: Vector store for initial retrieval
            use_reranker: If True, apply cross-encoder reranking
            reranker: CrossEncoderReranker instance (will create if None)
            retrieve_multiplier: How many chunks to retrieve before reranking
                                 (e.g., k=5 with multiplier=4 retrieves 20 then reranks to 5)
        """
        self.vectorstore = vectorstore
        self.use_reranker = use_reranker
        self.retrieve_multiplier = retrieve_multiplier

        if use_reranker and reranker is None:
            from src.reranker import CrossEncoderReranker
            reranker = CrossEncoderReranker()
        self.reranker = reranker

    def retrieve(self, query: str, k: int = 5) -> List[Dict]:
        """
        Retrieve top-k documents most relevant to query.

        Args:
            query: Search query
            k: Number of documents to return

        Returns:
            List of retrieved documents with metadata and scores
        """
        if self.use_reranker:
            # Two-stage: retrieve more, then rerank
            n_retrieve = k * self.retrieve_multiplier
            initial_results = self.vectorstore.similarity_search(query, k=n_retrieve)

            if not initial_results:
                return []

            # Rerank to get top-k most relevant
            reranked = self.reranker.rerank(query, initial_results, top_k=k)
            return reranked
        else:
            # Single-stage: vector search only
            return self.vectorstore.similarity_search(query, k=k)

    def retrieve_with_expansion(
        self, query: str, k_initial: int = 5, k_expanded: int = 10
    ) -> List[Dict]:
        """
        Retrieve with expansion capability (used by agentic RETRIEVE state).

        First retrieves k_expanded results (more than usual).
        """
        return self.retrieve(query, k=k_expanded)

    def batch_retrieve(self, queries: List[str], k: int = 5) -> List[List[Dict]]:
        """Retrieve for multiple queries."""
        return [self.retrieve(q, k) for q in queries]
