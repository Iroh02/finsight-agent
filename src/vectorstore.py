"""Vector store management using ChromaDB (persistent)."""

import logging
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Union

from langchain_core.documents import Document

logger = logging.getLogger(__name__)

_PERSIST_DIR = "data/vectorstore"
_COLLECTION_NAME = "financial_docs"


# ── Public factory ────────────────────────────────────────────────────────────

def get_vectorstore(
    persist_directory: str = _PERSIST_DIR,
    collection_name: str = _COLLECTION_NAME,
) -> "ChromaVectorStore":
    """Return (or lazily create) the ChromaDB vector store for financial docs."""
    return ChromaVectorStore(
        collection_name=collection_name,
        persist_directory=persist_directory,
    )


# ── Base class ────────────────────────────────────────────────────────────────

class VectorStore:
    """Base interface for vector stores."""

    def add_documents(self, documents, embeddings=None) -> None:
        raise NotImplementedError

    def similarity_search(self, query: str, k: int = 5) -> List[Document]:
        raise NotImplementedError

    def delete_all(self) -> None:
        raise NotImplementedError

    def get_stats(self) -> Dict:
        raise NotImplementedError


# ── ChromaDB implementation ───────────────────────────────────────────────────

class ChromaVectorStore(VectorStore):
    """ChromaDB persistent vector store.

    Supports two call styles for add_documents:
      • add_documents(docs: List[Document], embeddings: np.ndarray | list)
      • add_documents(dicts: List[Dict])  — each dict may carry an 'embedding' key
    """

    def __init__(
        self,
        collection_name: str = _COLLECTION_NAME,
        persist_directory: str = _PERSIST_DIR,
    ):
        self.collection_name = collection_name
        self.persist_directory = str(persist_directory)
        self._client = None
        self._collection = None

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _get_collection(self):
        if self._collection is None:
            import chromadb

            Path(self.persist_directory).mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=self.persist_directory)
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info(
                f"Collection '{self.collection_name}' ready "
                f"({self._collection.count()} existing docs)"
            )
        return self._collection

    # ── Public API ────────────────────────────────────────────────────────────

    def add_documents(
        self,
        documents: Union[List[Document], List[Dict]],
        embeddings=None,
    ) -> None:
        """Add documents with their pre-computed embeddings to ChromaDB.

        Args:
            documents: LangChain Documents *or* plain dicts (text/source/page)
            embeddings: Parallel list/array of embeddings (optional if dicts carry
                        an 'embedding' key)
        """
        collection = self._get_collection()

        ids, texts, metadatas, embeds = [], [], [], []

        for i, doc in enumerate(documents):
            if isinstance(doc, Document):
                text = doc.page_content
                meta = doc.metadata
            else:
                text = doc.get("text") or doc.get("page_content", "")
                meta = {"source": doc.get("source", ""), "page": doc.get("page", 0)}

            if not text.strip():
                continue

            # Resolve embedding from argument list or embedded in dict
            emb: Optional[list] = None
            if embeddings is not None:
                raw = embeddings[i]
                emb = raw.tolist() if hasattr(raw, "tolist") else list(raw)
            elif isinstance(doc, dict) and "embedding" in doc:
                raw = doc["embedding"]
                emb = raw.tolist() if hasattr(raw, "tolist") else list(raw)

            ids.append(str(uuid.uuid4()))
            texts.append(text)
            metadatas.append(
                {"source": meta.get("source", ""), "page": int(meta.get("page", 0))}
            )
            if emb is not None:
                embeds.append(emb)

        if not ids:
            logger.warning("add_documents called with no non-empty documents.")
            return

        kwargs: Dict = dict(ids=ids, documents=texts, metadatas=metadatas)
        if embeds:
            kwargs["embeddings"] = embeds

        # Chroma recommends batches ≤ 5 000 for memory safety
        batch_size = 5_000
        for start in range(0, len(ids), batch_size):
            batch = {k: v[start : start + batch_size] for k, v in kwargs.items()}
            collection.add(**batch)

        logger.info(f"Stored {len(ids)} chunks in '{self.collection_name}'")

    def similarity_search(self, query: str, k: int = 5) -> List[Document]:
        """Return the top-k Documents most similar to the query.

        Metadata on returned Documents includes 'source', 'page', and 'score'
        (cosine similarity, higher = more similar).
        """
        from src.embedder import get_embeddings

        collection = self._get_collection()
        n = min(k, collection.count())
        if n == 0:
            logger.warning("Vector store is empty — run ingestion first.")
            return []

        query_emb = get_embeddings([query])[0].tolist()
        results = collection.query(
            query_embeddings=[query_emb],
            n_results=n,
            include=["documents", "metadatas", "distances"],
        )

        docs: List[Document] = []
        for text, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            score = round(1.0 - dist, 4)  # cosine distance → similarity
            docs.append(Document(page_content=text, metadata={**meta, "score": score}))
        return docs

    def delete_all(self) -> None:
        """Remove all documents from the collection."""
        collection = self._get_collection()
        all_ids = collection.get()["ids"]
        if all_ids:
            collection.delete(ids=all_ids)
        logger.info(f"Deleted {len(all_ids)} docs from '{self.collection_name}'")

    def get_stats(self) -> Dict:
        collection = self._get_collection()
        return {
            "collection": self.collection_name,
            "document_count": collection.count(),
            "persist_directory": self.persist_directory,
        }


# ── FAISS stub (kept for interface completeness) ──────────────────────────────

class FAISSVectorStore(VectorStore):
    """FAISS vector store stub — not used by the primary pipeline."""

    def __init__(self, dimension: int = 384, index_path: str = "./data/faiss.index"):
        self.dimension = dimension
        self.index_path = index_path

    def add_documents(self, documents, embeddings=None) -> None:
        raise NotImplementedError("FAISSVectorStore is not implemented in this pipeline")

    def similarity_search(self, query: str, k: int = 5) -> List[Document]:
        raise NotImplementedError("FAISSVectorStore is not implemented in this pipeline")


# ── Legacy factory kept for backward compatibility ────────────────────────────

def get_vectorstore_legacy(store_type: str = "chroma", **kwargs) -> VectorStore:
    if store_type == "chroma":
        return ChromaVectorStore(**kwargs)
    elif store_type == "faiss":
        return FAISSVectorStore(**kwargs)
    else:
        raise ValueError(f"Unknown store type: {store_type}")
