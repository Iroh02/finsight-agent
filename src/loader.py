"""PDF text extraction and loading."""

import os
from pathlib import Path
from typing import List, Dict


class PDFLoader:
    """
    Load and extract text from PDF files.

    Uses pdfplumber for high-quality text extraction.
    Falls back to PyPDF2 if pdfplumber fails.
    """

    def __init__(self, pdf_path: str):
        """Initialize loader with PDF path."""
        self.pdf_path = pdf_path
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        self.filename = os.path.basename(pdf_path)

    def extract_text(self) -> List[Dict]:
        """
        Extract text from PDF page by page.

        Returns:
            List of dicts with keys: filename, page_number, text
        """
        try:
            return self._extract_with_pdfplumber()
        except Exception as e:
            print(f"pdfplumber failed for {self.filename}: {e}")
            print("Falling back to PyPDF2...")
            return self._extract_with_pypdf2()

    def _extract_with_pdfplumber(self) -> List[Dict]:
        """Extract using pdfplumber (better quality)."""
        import pdfplumber

        pages_data = []
        with pdfplumber.open(self.pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                if text.strip():
                    pages_data.append({
                        "filename": self.filename,
                        "page_number": page_num,
                        "text": text,
                    })
        return pages_data

    def _extract_with_pypdf2(self) -> List[Dict]:
        """Fallback extraction using PyPDF2."""
        from PyPDF2 import PdfReader

        pages_data = []
        reader = PdfReader(self.pdf_path)
        for page_num, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                pages_data.append({
                    "filename": self.filename,
                    "page_number": page_num,
                    "text": text,
                })
        return pages_data


def load_directory(directory_path: str, extensions: tuple = (".pdf",)) -> List[Dict]:
    """
    Load all PDFs from a directory.

    Args:
        directory_path: Path to directory containing PDFs
        extensions: Tuple of file extensions to include

    Returns:
        Combined list of extracted pages from all PDFs
    """
    directory = Path(directory_path)
    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory_path}")

    all_pages = []
    pdf_files = [f for f in directory.iterdir() if f.suffix.lower() in extensions]

    if not pdf_files:
        print(f"Warning: No PDF files found in {directory_path}")
        return all_pages

    print(f"Found {len(pdf_files)} PDF(s) in {directory_path}")
    for pdf_file in pdf_files:
        print(f"  Loading: {pdf_file.name}")
        try:
            loader = PDFLoader(str(pdf_file))
            pages = loader.extract_text()
            all_pages.extend(pages)
            print(f"    -> {len(pages)} pages extracted")
        except Exception as e:
            print(f"    -> ERROR: {e}")

    return all_pages
