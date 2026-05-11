"""Text cleaning and preprocessing utilities.

Statistical header/footer detection and cleaning logic from Jillian's data pipeline work,
combined with original pipeline's clean_pages helper.
"""

import re
import logging
from collections import Counter
from typing import List, Dict

logger = logging.getLogger(__name__)


def remove_hyphen_breaks(text: str) -> str:
    """Rejoin words broken across lines: 'reve-\\nnue' -> 'revenue'."""
    return re.sub(r"(\w)-\n(\w)", r"\1\2", text)


def detect_and_remove_headers_footers(pages: List[str]) -> List[str]:
    """Remove lines that appear on >30% of pages (recurring headers/footers).

    Statistical approach: counts line frequency across pages.
    A line that appears on >=30% of pages is likely a header/footer.

    Args:
        pages: List of page text strings

    Returns:
        Pages with repeated lines stripped out
    """
    if len(pages) < 3:
        return pages

    line_counts: Counter = Counter()
    for page in pages:
        seen_on_page: set = set()
        for line in page.split("\n"):
            stripped = line.strip()
            # Only consider short-to-medium lines; very long ones are content
            if stripped and len(stripped) < 120 and stripped not in seen_on_page:
                line_counts[stripped] += 1
                seen_on_page.add(stripped)

    threshold = max(2, int(len(pages) * 0.3))
    repeated = {line for line, count in line_counts.items() if count >= threshold}

    if repeated:
        logger.debug(f"Removing {len(repeated)} repeated header/footer lines")

    cleaned = []
    for page in pages:
        lines = [ln for ln in page.split("\n") if ln.strip() not in repeated]
        cleaned.append("\n".join(lines))
    return cleaned


def clean_text(text: str) -> str:
    """Full single-page text cleaning pipeline.

    Steps:
      1. Rejoin hyphenated word breaks
      2. Strip non-printable chars (preserve $, %, EUR, GBP, JPY)
      3. Remove standalone page numbers
      4. Collapse runs of 3+ newlines to double newline
      5. Normalize horizontal whitespace
    """
    text = remove_hyphen_breaks(text)
    # Keep printable ASCII + common financial symbols + newline/tab
    text = re.sub(r"[^\x20-\x7E$%€£¥\n\t]", " ", text)
    # Standalone page numbers (a line containing only digits)
    text = re.sub(r"(?m)^\s*\d{1,4}\s*$", "", text)
    # Collapse 3+ consecutive newlines
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Normalize horizontal whitespace
    text = re.sub(r"[ \t]+", " ", text)
    # Clean up blank lines introduced by removals
    text = re.sub(r"\n +\n", "\n\n", text)
    return text.strip()


def batch_clean(texts: List[str]) -> List[str]:
    """Clean multiple text strings."""
    return [clean_text(t) for t in texts]


def remove_headers_footers(text: str) -> str:
    """Remove standalone page numbers and collapse excess blank lines."""
    text = re.sub(r"(?m)^\s*\d{1,4}\s*$", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize_whitespace(text: str) -> str:
    """Normalize excessive whitespace and hyphenation artifacts."""
    text = remove_hyphen_breaks(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def remove_special_characters(text: str) -> str:
    """Remove problematic Unicode characters but preserve smart quotes."""
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    text = text.replace("‘", "'").replace("’", "'")
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("–", "-").replace("—", "-")
    return text


def clean_pages(pages: List[Dict]) -> List[Dict]:
    """Clean a list of page dicts (from PDFLoader).

    Uses Jillian's statistical header/footer detection across pages.

    Args:
        pages: List of dicts with 'text' key (and other metadata)

    Returns:
        Same list with text cleaned (drops empty pages)
    """
    if not pages:
        return []

    # Step 1: per-page cleaning
    for page in pages:
        page["text"] = clean_text(page.get("text", ""))

    # Step 2: cross-page header/footer removal (statistical)
    texts = [p["text"] for p in pages]
    cleaned_texts = detect_and_remove_headers_footers(texts)

    # Step 3: rebuild list, drop empty pages
    cleaned = []
    for page, text in zip(pages, cleaned_texts):
        if text.strip():
            cleaned.append({**page, "text": text})
    return cleaned
