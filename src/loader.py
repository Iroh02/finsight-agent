"""PDF text extraction and loading."""

from typing import List, Dict, Optional


class PDFLoader:
    """
    Load and extract text from PDF files.

    TODO: Implement using pdfplumber or PyPDF2
    """

    def __init__(self, pdf_path: str):
        """Initialize loader with PDF path."""
        self.pdf_path = pdf_path

    def extract_text(self) -> List[Dict]:
        """
        Extract text from PDF page by page.

        Returns:
            List of dicts with keys: filename, page_number, text
        """
        raise NotImplementedError("Implement extract_text method")

    def extract_with_metadata(self) -> List[Dict]:
        """
        Extract text with full metadata preservation.

        Returns:
            List of dicts with keys: filename, page_number, text, metadata
        """
        raise NotImplementedError("Implement extract_with_metadata method")


def load_directory(directory_path: str) -> List[Dict]:
    """
    Load all PDFs from a directory.

    Args:
        directory_path: Path to directory containing PDFs

    Returns:
        Combined list of extracted pages from all PDFs
    """
    raise NotImplementedError("Implement load_directory function")
