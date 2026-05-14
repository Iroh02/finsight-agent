#!/usr/bin/env python3
"""
Download additional financial 10-K filings from SEC EDGAR for FinSight Agent demos.

Modern EDGAR 10-K filings are submitted as inline-XBRL HTML (not PDF).
This script downloads the primary .htm document for each company and saves it
to data/raw/ — the FinSight loader handles both PDF and HTM files.

Uses the public SEC EDGAR submissions API (no API key required).
SEC policy requires a descriptive User-Agent header; edit CONTACT_EMAIL below.

Usage:
    python scripts/download_pdfs.py
    python scripts/download_pdfs.py --companies Microsoft Meta Tesla
    python scripts/download_pdfs.py --list
"""

import argparse
import time
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CONTACT_EMAIL = "jillianpriscilla21@gmail.com"

# CIK numbers are permanent identifiers on SEC EDGAR
COMPANIES = {
    "Microsoft": "789019",
    "Alphabet":  "1652044",
    "Meta":      "1326801",
    "Tesla":     "1318605",
    "Netflix":   "1065280",
}

OUTPUT_DIR = Path(__file__).parent.parent / "data" / "raw"

_SLEEP = 0.4   # be polite to SEC servers (their limit is ~10 req/s)

# ---------------------------------------------------------------------------


def _headers(host: str) -> dict:
    return {
        "User-Agent": f"FinSight-Agent academic-research {CONTACT_EMAIL}",
        "Accept-Encoding": "gzip, deflate",
        "Host": host,
    }


def get_latest_10k_info(cik: str) -> dict | None:
    """
    Return filing metadata for the most recent 10-K.

    Keys: accessionNumber, filingDate, primaryDocument, primaryDocDescription
    """
    padded = cik.zfill(10)
    url = f"https://data.sec.gov/submissions/CIK{padded}.json"
    resp = requests.get(url, headers=_headers("data.sec.gov"), timeout=15)
    resp.raise_for_status()
    data = resp.json()

    recent = data.get("filings", {}).get("recent", {})
    forms      = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    dates      = recent.get("filingDate", [])
    primary    = recent.get("primaryDocument", [])
    desc       = recent.get("primaryDocDescription", [])

    for i, form in enumerate(forms):
        if form == "10-K":
            return {
                "accessionNumber": accessions[i],
                "filingDate":      dates[i],
                "primaryDocument": primary[i] if i < len(primary) else "",
                "description":     desc[i]    if i < len(desc) else "",
            }
    return None


def build_primary_doc_url(cik: str, accession: str, primary_doc: str) -> str:
    """Construct the direct URL for the primary document in a filing."""
    cik_int    = str(int(cik))
    acc_nodash = accession.replace("-", "")
    return (
        f"https://www.sec.gov/Archives/edgar/data/{cik_int}/"
        f"{acc_nodash}/{primary_doc}"
    )


def download_file(url: str, dest: Path) -> bool:
    """Stream-download a file from URL to dest; return True on success."""
    time.sleep(_SLEEP)
    try:
        resp = requests.get(
            url,
            headers=_headers("www.sec.gov"),
            stream=True,
            timeout=120,
        )
        if resp.status_code != 200:
            print(f"    [error] HTTP {resp.status_code} for {url}")
            return False
        with open(dest, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=65_536):
                fh.write(chunk)
        size_kb = dest.stat().st_size // 1024
        print(f"    Saved:  {dest.name}  ({size_kb:,} KB)")
        return True
    except Exception as exc:
        print(f"    [error] {exc}")
        if dest.exists():
            dest.unlink()
        return False


def process_company(name: str, cik: str) -> bool:
    """Download the latest 10-K filing for one company; return True on success."""
    print(f"\n[{name}]  CIK {cik}")

    info = get_latest_10k_info(cik)
    if not info:
        print("    No 10-K found in recent filings")
        return False

    acc       = info["accessionNumber"]
    date      = info["filingDate"]
    year      = date[:4]
    primary   = info["primaryDocument"]

    print(f"    Latest 10-K: {acc}  filed {date}")
    print(f"    Primary doc: {primary}")

    if not primary:
        print("    primaryDocument field is empty — skipping")
        return False

    # Determine output extension (.htm or .pdf)
    ext  = Path(primary).suffix.lower()           # ".htm" for almost all modern filings
    dest = OUTPUT_DIR / f"{name}_10K_{year}{ext}"

    if dest.exists():
        print(f"    Already downloaded: {dest.name}")
        return True

    url = build_primary_doc_url(cik, acc, primary)
    print(f"    URL: {url}")
    return download_file(url, dest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--companies",
        nargs="+",
        choices=list(COMPANIES.keys()),
        default=list(COMPANIES.keys()),
        help="Companies to download (default: all)",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="Print available companies and exit",
    )
    args = parser.parse_args()

    if args.list:
        print("Available companies:")
        for name, cik in COMPANIES.items():
            print(f"  {name:<12}  CIK {cik}")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {OUTPUT_DIR}")
    print("Note: modern EDGAR 10-Ks are HTML (.htm), not PDF — the loader handles both.\n")

    succeeded, failed = [], []
    for name in args.companies:
        if process_company(name, COMPANIES[name]):
            succeeded.append(name)
        else:
            failed.append(name)

    print("\n" + "=" * 50)
    print(f"Done: {len(succeeded)}/{len(args.companies)} downloaded")
    if succeeded:
        print(f"  OK:     {', '.join(succeeded)}")
    if failed:
        print(f"  Failed: {', '.join(failed)}")

    if succeeded:
        print(
            "\nNext step — re-ingest with new documents:\n"
            "  python -m src.test_pipeline\n"
            "  (the vector store will be rebuilt with metadata for all companies)"
        )


if __name__ == "__main__":
    main()
