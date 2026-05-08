"""Document retrieval from vector store."""

from typing import List, Dict, Optional
from src.vectorstore import VectorStore


class Retriever:
    """Retrieve documents from vector store."""

    def __init__(self, vectorstore: VectorStore):
        """Initialize retriever with vector store."""
        self.vectorstore = vectorstore

    def retrieve(self, query: str, k: int = 5) -> List[Dict]:
        """
        Retrieve top-k documents similar to query.

        Args:
            query: Search query
            k: Number of documents to retrieve

        Returns:
            List of retrieved documents with metadata
        """
        results = self.vectorstore.similarity_search(query, k=k)
        return results

    def retrieve_with_expansion(self, query: str, k_initial: int = 5, k_expanded: int = 10) -> List[Dict]:
        """
        Retrieve with expansion capability.

        First retrieves k_initial results, then can expand to k_expanded if needed.
        """
        results = self.vectorstore.similarity_search(query, k=k_expanded)
        return results[:k_expanded]

    def batch_retrieve(self, queries: List[str], k: int = 5) -> List[List[Dict]]:
        """Retrieve for multiple queries."""
        return [self.retrieve(q, k) for q in queries]
