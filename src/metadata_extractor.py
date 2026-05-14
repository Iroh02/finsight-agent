"""Extract structured metadata (company, year, doc_type) from PDF filenames and content.

Used by the data pipeline to enrich every chunk with temporal/company context,
enabling temporal-aware retrieval and cross-document conflict detection.
"""

import re
from pathlib import Path
from typing import Dict, Optional

# Company name → list of strings to match in filename (lowercase)
_COMPANY_ALIASES: Dict[str, list] = {
    "Apple":     ["apple", "aapl"],
    "Amazon":    ["amazon", "amzn"],
    "Nvidia":    ["nvidia", "nvda"],
    "Microsoft": ["microsoft", "msft"],
    "Alphabet":  ["alphabet", "google", "googl", "goog"],
    "Meta":      ["meta", "facebook"],
    "Tesla":     ["tesla", "tsla"],
    "Netflix":   ["netflix", "nflx"],
}


def extract_metadata_from_filename(filename: str) -> Dict:
    """
    Heuristically extract company, year, quarter, and doc_type from a PDF filename.

    Examples
    --------
    Apple_10K_2025.pdf      -> company=Apple,   year=2025, quarter=,  doc_type=10-K
    Amazon_Q1_2026.pdf      -> company=Amazon,  year=2026, quarter=Q1, doc_type=earnings_report
    Nvidia_Report.pdf       -> company=Nvidia,  year=0,    quarter=,  doc_type=report
    GenAI_Project_Guide.pdf -> company=Unknown, year=0,    quarter=,  doc_type=reference

    Returns dict with keys: company, year, quarter, doc_type, fiscal_period
    """
    stem = Path(filename).stem.lower().replace("_", " ").replace("-", " ")

    # --- year ---
    year_match = re.search(r"\b(20\d{2})\b", stem)
    year = int(year_match.group(1)) if year_match else 0

    # --- quarter ---
    quarter_match = re.search(r"\b(q[1-4])\b", stem, re.IGNORECASE)
    quarter = quarter_match.group(1).upper() if quarter_match else ""

    # --- doc type (order matters: more specific first) ---
    if re.search(r"\b10[\s-]?k\b", stem):
        doc_type = "10-K"
    elif re.search(r"\b10[\s-]?q\b", stem):
        doc_type = "10-Q"
    elif quarter:
        doc_type = "earnings_report"
    elif "annual" in stem:
        doc_type = "annual_report"
    elif any(w in stem for w in ("guide", "project", "course", "syllabus")):
        doc_type = "reference"
    else:
        doc_type = "report"

    # --- company ---
    company = "Unknown"
    for name, aliases in _COMPANY_ALIASES.items():
        if any(alias in stem for alias in aliases):
            company = name
            break

    # --- fiscal_period ---
    if year and quarter:
        fiscal_period = f"{year} {quarter}"
    elif year:
        fiscal_period = str(year)
    else:
        fiscal_period = "unknown"

    return {
        "company": company,
        "year": year,
        "quarter": quarter,
        "doc_type": doc_type,
        "fiscal_period": fiscal_period,
    }


def extract_metadata_with_llm(
    filename: str,
    first_page_text: str,
    llm_client=None,
) -> Dict:
    """
    Refine metadata using LLM when heuristics yield Unknown company or year=0.

    Falls back to heuristic result if LLM is unavailable or fails.
    """
    base = extract_metadata_from_filename(filename)

    # Only call LLM when heuristics are uncertain
    if base["company"] != "Unknown" and base["year"] != 0:
        return base

    if llm_client is None:
        return base

    prompt = (
        "Extract the following from this document excerpt:\n"
        "1. Company name (e.g., Apple, Microsoft — or Unknown)\n"
        "2. Fiscal year as a 4-digit number (e.g., 2024 — or 0 if not found)\n"
        "3. Document type: one of 10-K, 10-Q, earnings_report, annual_report, reference, report\n"
        "4. Quarter if applicable: Q1, Q2, Q3, Q4, or empty string\n\n"
        f"Document excerpt (first page):\n{first_page_text[:800]}\n\n"
        "Respond in exactly this format (no extra text):\n"
        "company: <name>\nyear: <number>\ndoc_type: <type>\nquarter: <Q1-Q4 or blank>"
    )

    try:
        response = llm_client.complete(prompt, max_tokens=80)
        parsed: Dict = {}
        for line in response.strip().split("\n"):
            if ":" in line:
                k, _, v = line.partition(":")
                parsed[k.strip().lower()] = v.strip()

        enriched = dict(base)
        if parsed.get("company") and enriched["company"] == "Unknown":
            enriched["company"] = parsed["company"]
        raw_year = parsed.get("year", "")
        if raw_year.isdigit() and enriched["year"] == 0:
            enriched["year"] = int(raw_year)
        if parsed.get("doc_type"):
            enriched["doc_type"] = parsed["doc_type"]
        q = parsed.get("quarter", "")
        if q.upper().startswith("Q") and not enriched["quarter"]:
            enriched["quarter"] = q.upper()

        # Rebuild fiscal_period
        y, qt = enriched["year"], enriched["quarter"]
        enriched["fiscal_period"] = f"{y} {qt}" if y and qt else (str(y) if y else "unknown")
        return enriched

    except Exception:
        return base
