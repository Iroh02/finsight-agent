"""Embedding generation using sentence-transformers (lazy-loaded, cached)."""

import logging
import os
from typing import List, Optional

import numpy as np
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "all-MiniLM-L6-v2"

# Module-level cache so the model is loaded at most once per process
_cached_model = None


def _load_cached_model(model_name: str = _DEFAULT_MODEL):
    global _cached_model
    if _cached_model is None:
        logger.info(f"Loading sentence-transformers model: {model_name}")
        from sentence_transformers import SentenceTransformer

        _cached_model = SentenceTransformer(model_name)
        logger.info("Model ready.")
    return _cached_model


def get_embeddings(texts: List[str]) -> np.ndarray:
    """Embed a list of texts using the cached sentence-transformers model.

    Args:
        texts: Strings to embed

    Returns:
        numpy array of shape (len(texts), embedding_dim)
    """
    model = _load_cached_model()
    return model.encode(texts, batch_size=32, show_progress_bar=False, convert_to_numpy=True)


class EmbeddingPipeline:
    """Instance-level lazy-loading embedding pipeline for LangChain Documents."""

    def __init__(self, model_name: str = _DEFAULT_MODEL):
        self.model_name = model_name
        self._model = None

    def _get_model(self):
        if self._model is None:
            logger.info(f"Loading embedding model: {self.model_name}")
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed_documents(self, docs: List[Document]) -> np.ndarray:
        """Embed a list of LangChain Documents.

        Returns:
            numpy array of shape (len(docs), embedding_dim)
        """
        texts = [doc.page_content for doc in docs]
        model = self._get_model()
        return model.encode(texts, batch_size=32, show_progress_bar=True, convert_to_numpy=True)

    def embed_query(self, query: str) -> np.ndarray:
        """Embed a single query string, returning a 1-D array."""
        model = self._get_model()
        return model.encode([query], convert_to_numpy=True)[0]


# ── Backward-compatible provider classes used by existing RAGPipeline ────────

class EmbeddingProvider:
    """Base class for embedding providers."""

    def embed(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError("Implement embed method")

    def embed_single(self, text: str) -> List[float]:
        result = self.embed([text])
        return result[0] if result else []


class OpenAIEmbedder(EmbeddingProvider):
    """OpenAI text-embedding-ada-002 embeddings."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set")

    def embed(self, texts: List[str]) -> List[List[float]]:
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key)
        response = client.embeddings.create(input=texts, model="text-embedding-ada-002")
        return [item.embedding for item in response.data]


class HuggingFaceEmbedder(EmbeddingProvider):
    """sentence-transformers embeddings, compatible with EmbeddingProvider API."""

    def __init__(self, model_name: str = _DEFAULT_MODEL):
        self.model_name = model_name

    def embed(self, texts: List[str]) -> List[List[float]]:
        return get_embeddings(texts).tolist()

    def embed_single(self, text: str) -> List[float]:
        return get_embeddings([text])[0].tolist()


def get_embedder(provider: str = "openai") -> EmbeddingProvider:
    """Factory for embedding providers.

    Args:
        provider: "openai" or "huggingface"
    """
    if provider == "openai":
        return OpenAIEmbedder()
    elif provider == "huggingface":
        return HuggingFaceEmbedder()
    else:
        raise ValueError(f"Unknown provider: {provider}")
