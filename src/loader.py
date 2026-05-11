"""PDF text extraction and loading."""

import logging
from pathlib import Path
from typing import List, Dict

logger = logging.getLogger(__name__)


class PDFLoader:
    """Load and extract text from PDF files using pdfplumber with PyPDF2 fallback."""

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.filename = Path(pdf_path).name

    def extract_text(self) -> List[Dict]:
        """Extract text from PDF page by page.

        Returns:
            List of dicts with keys: text, source, page
        """
        try:
            return self._extract_with_pdfplumber()
        except Exception as e:
            logger.warning(f"pdfplumber failed for {self.filename}: {e}. Falling back to PyPDF2.")
            try:
                return self._extract_with_pypdf2()
            except Exception as e2:
                logger.error(f"Both extractors failed for {self.filename}: {e2}")
                return []

    def _extract_with_pdfplumber(self) -> List[Dict]:
        import pdfplumber

        pages = []
        with pdfplumber.open(self.pdf_path) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                if text.strip():
                    pages.append({"text": text, "source": self.filename, "page": i})
        return pages

    def _extract_with_pypdf2(self) -> List[Dict]:
        import PyPDF2

        pages = []
        with open(self.pdf_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for i, page in enumerate(reader.pages, start=1):
                text = page.extract_text() or ""
                if text.strip():
                    pages.append({"text": text, "source": self.filename, "page": i})
        return pages

    def extract_with_metadata(self) -> List[Dict]:
        """Extract text with full PDF metadata preservation."""
        pages = self.extract_text()
        try:
            import pdfplumber

            with pdfplumber.open(self.pdf_path) as pdf:
                meta = pdf.metadata or {}
            for page in pages:
                page["metadata"] = {
                    "title": meta.get("Title", ""),
                    "author": meta.get("Author", ""),
                    "total_pages": len(pages),
                }
        except Exception:
            for page in pages:
                page["metadata"] = {}
        return pages


def load_pdfs(directory: str) -> List[Dict]:
    """Load all PDFs from a directory.

    Args:
        directory: Path to directory containing PDFs

    Returns:
        Combined list of page dicts — each with keys: text, source, page
    """
    pdf_dir = Path(directory)
    if not pdf_dir.exists():
        logger.error(f"Directory not found: {directory}")
        return []

    pdf_files = sorted(pdf_dir.glob("*.pdf"))
    if not pdf_files:
        logger.warning(f"No PDFs found in {directory}")
        return []

    all_pages: List[Dict] = []
    for pdf_path in pdf_files:
        logger.info(f"Loading {pdf_path.name}...")
        loader = PDFLoader(str(pdf_path))
        pages = loader.extract_text()
        all_pages.extend(pages)
        logger.info(f"  {pdf_path.name}: {len(pages)} pages extracted")

    logger.info(f"Total: {len(all_pages)} pages from {len(pdf_files)} PDFs")
    return all_pages


# Backward-compatible alias used by the existing RAGPipeline
def load_directory(directory_path: str) -> List[Dict]:
    return load_pdfs(directory_path)
