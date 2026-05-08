"""Embedding generation and management."""

from typing import List, Optional
import os


class EmbeddingProvider:
    """Base class for embedding providers."""

    def embed(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of texts."""
        raise NotImplementedError("Implement embed method")

    def embed_single(self, text: str) -> List[float]:
        """Embed a single text."""
        embeddings = self.embed([text])
        return embeddings[0] if embeddings else []


class OpenAIEmbedder(EmbeddingProvider):
    """OpenAI text-embedding-ada-002 embeddings."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize with OpenAI API key."""
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set")

    def embed(self, texts: List[str]) -> List[List[float]]:
        """
        Embed texts using OpenAI API.

        TODO: Implement using openai.Embedding.create()
        """
        raise NotImplementedError("Implement OpenAI embedding")


class HuggingFaceEmbedder(EmbeddingProvider):
    """HuggingFace Sentence Transformers embeddings."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """Initialize with HuggingFace model."""
        self.model_name = model_name

    def embed(self, texts: List[str]) -> List[List[float]]:
        """
        Embed texts using HuggingFace Sentence Transformers.

        TODO: Implement using sentence_transformers.SentenceTransformer
        """
        raise NotImplementedError("Implement HuggingFace embedding")


def get_embedder(provider: str = "openai") -> EmbeddingProvider:
    """
    Get embedder based on provider name.

    Args:
        provider: "openai" or "huggingface"

    Returns:
        Initialized embedder instance
    """
    if provider == "openai":
        return OpenAIEmbedder()
    elif provider == "huggingface":
        return HuggingFaceEmbedder()
    else:
        raise ValueError(f"Unknown provider: {provider}")
