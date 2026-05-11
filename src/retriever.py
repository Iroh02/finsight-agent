"""Document retrieval with optional reranking and HyDE augmentation.

SOTA two-stage retrieval:
1. (Optional) HyDE: Generate hypothetical answer, use for embedding
2. Vector search: Find top-N candidates
3. Cross-encoder reranker: Re-score and return top-K

References:
- HyDE: Gao et al., 2023
- Cross-encoder reranking: Khattab & Zaharia, ColBERT 2020
"""

from typing import List, Dict, Optional
from src.vectorstore import VectorStore


class Retriever:
    """
    SOTA retriever with optional HyDE augmentation and cross-encoder reranking.

    Two-stage retrieval (when reranker enabled):
    1. Vector search: Fast, retrieves k_retrieve candidates (default 20)
    2. Reranker: Slow but accurate, picks top-k (default 5) from candidates

    Optional HyDE augmentation:
    - Embed a hypothetical answer instead of the question for better recall
    """

    def __init__(
        self,
        vectorstore: VectorStore,
        use_reranker: bool = False,
        reranker=None,
        retrieve_multiplier: int = 4,
        use_hyde: bool = False,
        hyde=None,
    ):
        """
        Initialize retriever with optional reranking and HyDE.

        Args:
            vectorstore: Vector store for initial retrieval
            use_reranker: If True, apply cross-encoder reranking
            reranker: CrossEncoderReranker instance (will create if None)
            retrieve_multiplier: How many chunks to retrieve before reranking
            use_hyde: If True, use HyDE to generate hypothetical answer for embedding
            hyde: HyDEAugmenter instance (will create if None)
        """
        self.vectorstore = vectorstore
        self.use_reranker = use_reranker
        self.retrieve_multiplier = retrieve_multiplier
        self.use_hyde = use_hyde

        if use_reranker and reranker is None:
            from src.reranker import CrossEncoderReranker
            reranker = CrossEncoderReranker()
        self.reranker = reranker

        if use_hyde and hyde is None:
            from src.hyde import HyDEAugmenter
            hyde = HyDEAugmenter()
        self.hyde = hyde

    def retrieve(self, query: str, k: int = 5) -> List[Dict]:
        """
        Retrieve top-k documents most relevant to query.

        Pipeline:
        1. (Optional) HyDE augment query
        2. Vector search (k * multiplier candidates if reranker on)
        3. (Optional) Cross-encoder rerank to top-k

        Args:
            query: Search query
            k: Number of documents to return

        Returns:
            List of retrieved documents with metadata and scores
        """
        # Step 1: HyDE augmentation (optional)
        search_query = query
        if self.use_hyde and self.hyde:
            try:
                search_query = self.hyde.augment_query(query, include_original=True)
            except Exception:
                # Fallback to original query if HyDE fails
                search_query = query

        # Step 2: Vector search
        if self.use_reranker:
            n_retrieve = k * self.retrieve_multiplier
            initial_results = self.vectorstore.similarity_search(search_query, k=n_retrieve)

            if not initial_results:
                return []

            # Step 3: Reranker (use ORIGINAL query for reranking, not HyDE-augmented)
            reranked = self.reranker.rerank(query, initial_results, top_k=k)
            return reranked
        else:
            return self.vectorstore.similarity_search(search_query, k=k)

    def retrieve_with_expansion(
        self, query: str, k_initial: int = 5, k_expanded: int = 10
    ) -> List[Dict]:
        """Retrieve with expansion capability (used by agentic RETRIEVE state)."""
        return self.retrieve(query, k=k_expanded)

    def batch_retrieve(self, queries: List[str], k: int = 5) -> List[List[Dict]]:
        """Retrieve for multiple queries."""
        return [self.retrieve(q, k) for q in queries]
