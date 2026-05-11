"""Vector store management (Chroma)."""

import os
from pathlib import Path
from typing import List, Dict, Optional
from dotenv import load_dotenv

load_dotenv()


class VectorStore:
    """Base class for vector stores."""

    def add_documents(self, documents: List[Dict]) -> None:
        """Add documents to the vector store."""
        raise NotImplementedError("Implement add_documents")

    def similarity_search(self, query: str, k: int = 5) -> List[Dict]:
        """Search for similar documents."""
        raise NotImplementedError("Implement similarity_search")

    def delete_all(self) -> None:
        """Delete all documents from store."""
        raise NotImplementedError("Implement delete_all")

    def get_stats(self) -> Dict:
        """Get vector store statistics."""
        raise NotImplementedError("Implement get_stats")


class ChromaVectorStore(VectorStore):
    """
    Chroma vector store - persistent local storage.

    Free, no API needed. Stores embeddings on disk.
    """

    def __init__(
        self,
        collection_name: str = "finsight_documents",
        persist_directory: str = None,
        embedder=None,
    ):
        """
        Initialize Chroma vector store.

        Args:
            collection_name: Name of the Chroma collection
            persist_directory: Path to persist data (defaults to .env value or ./data/chroma)
            embedder: EmbeddingProvider instance (will create one if None)
        """
        self.collection_name = collection_name
        self.persist_directory = persist_directory or os.getenv(
            "VECTOR_STORE_PATH", "./data/chroma"
        )
        Path(self.persist_directory).mkdir(parents=True, exist_ok=True)

        # Lazy-load embedder
        self._embedder = embedder
        self._client = None
        self._collection = None

    @property
    def embedder(self):
        """Get or create embedder."""
        if self._embedder is None:
            from src.embedder import get_embedder
            self._embedder = get_embedder()
        return self._embedder

    @property
    def client(self):
        """Get or create Chroma client."""
        if self._client is None:
            import chromadb
            from chromadb.config import Settings

            self._client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=Settings(anonymized_telemetry=False),
            )
        return self._client

    @property
    def collection(self):
        """Get or create collection."""
        if self._collection is None:
            self._collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    def add_documents(self, documents: List[Dict]) -> None:
        """
        Add documents to Chroma.

        Args:
            documents: List of dicts with 'text', 'source', 'page', 'chunk_index'
        """
        if not documents:
            return

        # Extract texts for embedding
        texts = [doc["text"] for doc in documents]

        # Generate embeddings
        print(f"Embedding {len(texts)} chunks...")
        embeddings = self.embedder.embed(texts)

        # Build IDs (must be unique)
        ids = [
            f"{doc.get('source', 'unk')}_p{doc.get('page', 0)}_c{doc.get('chunk_index', i)}"
            for i, doc in enumerate(documents)
        ]

        # Build metadata (Chroma requires non-None values)
        metadatas = []
        for doc in documents:
            metadata = {
                "source": str(doc.get("source", "unknown")),
                "page": int(doc.get("page", 0)) if doc.get("page") else 0,
                "chunk_index": int(doc.get("chunk_index", 0)),
            }
            metadatas.append(metadata)

        # Add to collection
        self.collection.add(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        print(f"Added {len(documents)} documents to vector store")

    def similarity_search(self, query: str, k: int = 5) -> List[Dict]:
        """
        Search for similar documents.

        Returns:
            List of dicts with 'text', 'source', 'page', 'score'
        """
        # Embed query
        query_embedding = self.embedder.embed_single(query)

        # Search
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
        )

        # Format results
        formatted = []
        if results["documents"] and results["documents"][0]:
            for i in range(len(results["documents"][0])):
                doc = {
                    "text": results["documents"][0][i],
                    "source": results["metadatas"][0][i].get("source", "unknown"),
                    "page": results["metadatas"][0][i].get("page", None),
                    "chunk_index": results["metadatas"][0][i].get("chunk_index", 0),
                    # Chroma returns distance, convert to similarity score (1 - distance)
                    "score": round(1 - results["distances"][0][i], 4)
                    if results["distances"]
                    else 0.0,
                }
                formatted.append(doc)
        return formatted

    def delete_all(self) -> None:
        """Delete all documents from store."""
        try:
            self.client.delete_collection(self.collection_name)
            self._collection = None
            print(f"Deleted collection: {self.collection_name}")
        except Exception as e:
            print(f"Could not delete collection: {e}")

    def get_stats(self) -> Dict:
        """Get vector store statistics."""
        return {
            "collection": self.collection_name,
            "count": self.collection.count(),
            "persist_directory": self.persist_directory,
            "embedder": type(self.embedder).__name__,
        }


def get_vectorstore(store_type: str = None, **kwargs) -> VectorStore:
    """
    Get vector store based on type.

    Args:
        store_type: "chroma" (only option for now)
        **kwargs: Additional arguments

    Returns:
        Initialized vector store
    """
    if store_type is None:
        store_type = os.getenv("VECTOR_STORE_TYPE", "chroma").lower()

    if store_type == "chroma":
        return ChromaVectorStore(**kwargs)
    else:
        # Default to Chroma
        return ChromaVectorStore(**kwargs)
