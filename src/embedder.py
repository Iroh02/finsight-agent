"""Embedding generation and management."""

import os
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()


class EmbeddingProvider:
    """Base class for embedding providers."""

    def embed(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of texts."""
        raise NotImplementedError("Implement embed method")

    def embed_single(self, text: str) -> List[float]:
        """Embed a single text."""
        embeddings = self.embed([text])
        return embeddings[0] if embeddings else []

    @property
    def dimension(self) -> int:
        """Return embedding dimension."""
        raise NotImplementedError("Implement dimension property")


class HuggingFaceEmbedder(EmbeddingProvider):
    """
    HuggingFace Sentence Transformers embeddings.

    Free, local, no API needed.
    Default model: all-MiniLM-L6-v2 (384 dimensions, fast and good quality)
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """Initialize with HuggingFace model."""
        self.model_name = model_name
        self._model = None
        self._dimension = None

    @property
    def model(self):
        """Lazy-load model (only when needed)."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            print(f"Loading embedding model: {self.model_name}...")
            self._model = SentenceTransformer(self.model_name)
            self._dimension = self._model.get_sentence_embedding_dimension()
            print(f"  Loaded. Dimension: {self._dimension}")
        return self._model

    @property
    def dimension(self) -> int:
        """Return embedding dimension."""
        if self._dimension is None:
            _ = self.model  # Force load
        return self._dimension

    def embed(self, texts: List[str]) -> List[List[float]]:
        """Embed texts using HuggingFace Sentence Transformers."""
        if not texts:
            return []

        embeddings = self.model.encode(
            texts,
            convert_to_numpy=True,
            show_progress_bar=len(texts) > 50,
        )
        return embeddings.tolist()


class OpenAIEmbedder(EmbeddingProvider):
    """OpenAI text-embedding-ada-002 embeddings."""

    def __init__(self, api_key: Optional[str] = None, model: str = "text-embedding-3-small"):
        """Initialize with OpenAI API key."""
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self._dimension = 1536  # text-embedding-3-small dimension
        self._client = None

    @property
    def client(self):
        """Lazy-load client."""
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=self.api_key)
        return self._client

    @property
    def dimension(self) -> int:
        """Return embedding dimension."""
        return self._dimension

    def embed(self, texts: List[str]) -> List[List[float]]:
        """Embed texts using OpenAI API."""
        if not texts:
            return []

        response = self.client.embeddings.create(
            input=texts,
            model=self.model,
        )
        return [item.embedding for item in response.data]


def get_embedder(provider: str = None) -> EmbeddingProvider:
    """
    Get embedder based on provider name.

    Args:
        provider: "openai" or "huggingface" (auto-detected from .env if None)

    Returns:
        Initialized embedder instance
    """
    if provider is None:
        provider = os.getenv("EMBEDDING_MODEL", "huggingface").lower()

    # Allow specifying HF model name directly
    if provider == "openai":
        return OpenAIEmbedder()
    elif provider == "huggingface" or provider.startswith("all-") or "/" in provider:
        # Treat anything else as a HuggingFace model name
        model_name = provider if provider != "huggingface" else "all-MiniLM-L6-v2"
        return HuggingFaceEmbedder(model_name=model_name)
    else:
        # Default to HuggingFace
        return HuggingFaceEmbedder()
