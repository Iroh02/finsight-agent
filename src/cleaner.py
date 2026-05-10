"""Text cleaning and preprocessing utilities."""

import re
from typing import List, Dict


def remove_headers_footers(text: str) -> str:
    """
    Remove common headers, footers, and page numbers from text.

    Targets:
    - Standalone page numbers (e.g., "Page 5 of 100")
    - Repeating header lines
    - Form feed / page break artifacts
    """
    # Remove "Page N of M" patterns
    text = re.sub(r"Page\s+\d+\s+of\s+\d+", "", text, flags=re.IGNORECASE)

    # Remove standalone page numbers (digit-only lines)
    text = re.sub(r"^\s*\d+\s*$", "", text, flags=re.MULTILINE)

    # Remove form feeds and tab artifacts
    text = text.replace("\f", "\n").replace("\t", " ")

    return text


def normalize_whitespace(text: str) -> str:
    """
    Normalize excessive whitespace and hyphenation artifacts.

    - Joins hyphenated line breaks (e.g., "compa-\nny" -> "company")
    - Collapses multiple spaces to single space
    - Normalizes line breaks
    """
    # Fix hyphenated line breaks: "word-\nword" -> "wordword"
    text = re.sub(r"-\s*\n\s*", "", text)

    # Replace multiple newlines with double newline (paragraph break)
    text = re.sub(r"\n\s*\n+", "\n\n", text)

    # Replace multiple spaces with single space
    text = re.sub(r" +", " ", text)

    # Strip leading/trailing whitespace from each line
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(line for line in lines if line)

    return text.strip()


def remove_special_characters(text: str) -> str:
    """Remove problematic Unicode characters."""
    # Remove null bytes and control characters (except newlines/tabs)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)

    # Replace fancy quotes with regular quotes
    text = text.replace("‘", "'").replace("’", "'")
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("–", "-").replace("—", "-")

    return text


def clean_text(text: str) -> str:
    """
    Full text cleaning pipeline.

    Args:
        text: Raw text from PDF

    Returns:
        Cleaned text
    """
    text = remove_special_characters(text)
    text = remove_headers_footers(text)
    text = normalize_whitespace(text)
    return text


def clean_pages(pages: List[Dict]) -> List[Dict]:
    """
    Clean a list of page dicts (from PDFLoader).

    Args:
        pages: List of dicts with 'text' key

    Returns:
        Same list with text cleaned
    """
    cleaned = []
    for page in pages:
        cleaned_text = clean_text(page.get("text", ""))
        if cleaned_text:  # Skip empty pages
            cleaned.append({
                **page,
                "text": cleaned_text,
            })
    return cleaned
