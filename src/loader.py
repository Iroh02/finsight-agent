"""Document loading: PDF and HTML (SEC EDGAR inline-XBRL) extraction."""

import os
from pathlib import Path
from typing import List, Dict

from src.metadata_extractor import extract_metadata_from_filename

# Supported extensions (order matters for the loader dispatch)
_PDF_EXTS  = {".pdf"}
_HTML_EXTS = {".htm", ".html"}


class PDFLoader:
    """
    Load and extract text from PDF files.

    Uses pdfplumber for high-quality text extraction.
    Falls back to PyPDF2 if pdfplumber fails.
    """

    def __init__(self, pdf_path: str):
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


class HTMLLoader:
    """
    Load and extract text from HTML filings (e.g. SEC EDGAR inline-XBRL .htm).

    Strips all HTML markup and splits the resulting plaintext into
    ~4 000-character page-equivalent chunks so downstream chunkers receive
    page-sized units consistent with PDFLoader output.
    """

    # Characters per virtual "page"
    VIRTUAL_PAGE_SIZE = 4_000

    def __init__(self, html_path: str):
        self.html_path = html_path
        if not os.path.exists(html_path):
            raise FileNotFoundError(f"HTML file not found: {html_path}")
        self.filename = os.path.basename(html_path)

    def extract_text(self) -> List[Dict]:
        """
        Strip HTML markup and return page-equivalent chunks.

        Returns:
            List of dicts with keys: filename, page_number, text
        """
        from bs4 import BeautifulSoup

        with open(self.html_path, "r", encoding="utf-8", errors="ignore") as fh:
            raw = fh.read()

        soup = BeautifulSoup(raw, "lxml")

        # Remove boilerplate elements
        for tag in soup.find_all(["script", "style", "head", "nav", "footer",
                                   "header", "noscript"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)

        # Split into virtual pages
        pages_data = []
        page_size = self.VIRTUAL_PAGE_SIZE
        page_num = 1
        for start in range(0, len(text), page_size):
            chunk = text[start: start + page_size].strip()
            if chunk:
                pages_data.append({
                    "filename": self.filename,
                    "page_number": page_num,
                    "text": chunk,
                })
                page_num += 1

        return pages_data


def load_file(file_path: str) -> List[Dict]:
    """
    Load a single document file (PDF or HTML), returning page dicts.

    Attaches enriched metadata (company, year, doc_type, …) from filename.
    """
    path = Path(file_path)
    ext  = path.suffix.lower()
    file_meta = extract_metadata_from_filename(path.name)

    if ext in _PDF_EXTS:
        loader = PDFLoader(file_path)
    elif ext in _HTML_EXTS:
        loader = HTMLLoader(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")

    pages = loader.extract_text()
    for page in pages:
        page.update(file_meta)
    return pages


def load_directory(
    directory_path: str,
    extensions: tuple = (".pdf", ".htm", ".html"),
) -> List[Dict]:
    """
    Load all supported documents from a directory.

    Args:
        directory_path: Path to directory containing documents
        extensions: File extensions to include (PDFs and HTML by default)

    Returns:
        Combined list of extracted pages with enriched metadata attached.
    """
    directory = Path(directory_path)
    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory_path}")

    files = [f for f in directory.iterdir() if f.suffix.lower() in extensions]

    if not files:
        print(f"Warning: No supported documents found in {directory_path}")
        return []

    print(f"Found {len(files)} document(s) in {directory_path}")
    all_pages = []
    for doc_file in files:
        print(f"  Loading: {doc_file.name}")
        try:
            pages = load_file(str(doc_file))
            all_pages.extend(pages)
            meta = pages[0] if pages else {}
            print(
                f"    -> {len(pages)} pages  "
                f"({meta.get('company', '?')}, "
                f"{meta.get('doc_type', '?')}, "
                f"{meta.get('fiscal_period', '?')})"
            )
        except Exception as e:
            print(f"    -> ERROR: {e}")

    return all_pages
