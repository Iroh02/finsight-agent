"""Text cleaning and preprocessing utilities."""

from typing import List


def remove_headers_footers(text: str) -> str:
    """
    Remove headers, footers, and page numbers from text.

    TODO: Implement regex-based removal
    """
    raise NotImplementedError("Implement remove_headers_footers")


def normalize_whitespace(text: str) -> str:
    """
    Normalize excessive whitespace and hyphenation artifacts.

    TODO: Implement whitespace normalization
    """
    raise NotImplementedError("Implement normalize_whitespace")


def clean_text(text: str) -> str:
    """
    Full text cleaning pipeline.

    Args:
        text: Raw text from PDF

    Returns:
        Cleaned text
    """
    raise NotImplementedError("Implement clean_text")


def batch_clean(texts: List[str]) -> List[str]:
    """Clean multiple text strings."""
    return [clean_text(t) for t in texts]
