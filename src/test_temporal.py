"""Tests for temporal-aware retrieval.

Pure-Python tests — no API key, no network, no Chroma. Validates the
regex parser and the TemporalAwareRetriever wrapper against fakes.

Run:
    python -m src.test_temporal
"""

from typing import Dict, List, Optional

from src.temporal import TemporalParser, TemporalAwareRetriever


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #

class FakeVectorStore:
    """Records the last call and returns canned results.

    Supports both similarity_search and similarity_search_filtered so we can
    assert that the filtered path is taken when expected.
    """

    def __init__(self, results=None, filtered_results=None):
        self.results = results or []
        self.filtered_results = filtered_results
        self.last_call = None  # ("unfiltered", query, k) or ("filtered", kwargs)

    def similarity_search(self, query: str, k: int = 5):
        self.last_call = ("unfiltered", query, k)
        return list(self.results)

    def similarity_search_filtered(self, query: str, k: int = 5, **kwargs):
        self.last_call = ("filtered", query, k, kwargs)
        if self.filtered_results is None:
            return list(self.results)
        return list(self.filtered_results)


# --------------------------------------------------------------------------- #
# Parser tests
# --------------------------------------------------------------------------- #

def test_parser_extracts_company_and_year():
    p = TemporalParser(current_year=2026)
    tf = p.parse("What was Apple's revenue in 2024?")
    assert tf.company == "Apple", tf.company
    assert tf.year == 2024, tf.year
    assert tf.is_filterable
    assert tf.detected_companies == ["Apple"], tf.detected_companies
    assert not tf.is_multi_entity
    assert "Apple" in tf.badge_label()
    print("PASS test_parser_extracts_company_and_year")


def test_parser_detects_multi_company():
    p = TemporalParser(current_year=2026)
    tf = p.parse("Compare Apple and Nvidia revenue in 2024")
    assert set(tf.detected_companies) == {"Apple", "Nvidia"}, tf.detected_companies
    assert tf.company is None  # ambiguous → no single filter
    assert tf.is_multi_entity
    assert not tf.is_filterable
    assert "Multi-entity" in tf.note
    print("PASS test_parser_detects_multi_company")


def test_parser_detects_multi_year_is_multi_entity():
    p = TemporalParser(current_year=2026)
    tf = p.parse("Apple revenue in 2023 versus 2024")
    assert len(tf.detected_years) == 2
    assert tf.is_multi_entity
    print("PASS test_parser_detects_multi_year_is_multi_entity")


def test_parser_extracts_ticker_alias():
    p = TemporalParser(current_year=2026)
    tf = p.parse("AAPL FY2025 revenue")
    assert tf.company == "Apple", tf.company
    assert tf.year == 2025
    print("PASS test_parser_extracts_ticker_alias")


def test_parser_handles_relative_year():
    p = TemporalParser(current_year=2026)
    tf = p.parse("Amazon revenue last year")
    assert tf.company == "Amazon"
    assert tf.year == 2025, tf.year
    print("PASS test_parser_handles_relative_year")


def test_parser_extracts_quarter():
    p = TemporalParser(current_year=2026)
    tf = p.parse("Nvidia Q3 results")
    assert tf.company == "Nvidia"
    assert tf.quarter == "Q3"
    print("PASS test_parser_extracts_quarter")


def test_parser_detects_doc_type():
    p = TemporalParser(current_year=2026)
    tf = p.parse("Apple 10-K filing")
    assert tf.doc_type == "10-K", tf.doc_type
    print("PASS test_parser_detects_doc_type")


def test_parser_multiple_years_not_filterable():
    """Compare-across-periods queries should fail is_filterable so the
    decomposer can split them into single-year sub-queries."""
    p = TemporalParser(current_year=2026)
    tf = p.parse("Compare Apple revenue in 2023 vs 2024")
    assert len(tf.detected_years) == 2, tf.detected_years
    assert not tf.is_filterable
    print("PASS test_parser_multiple_years_not_filterable")


def test_parser_no_filters_for_generic_query():
    p = TemporalParser(current_year=2026)
    tf = p.parse("Tell me about machine learning")
    assert not tf.has_filters
    assert not tf.freshness
    print("PASS test_parser_no_filters_for_generic_query")


def test_parser_freshness_latest():
    p = TemporalParser(current_year=2026)
    tf = p.parse("Apple's latest 10-K")
    assert tf.company == "Apple"
    assert tf.doc_type == "10-K"
    assert tf.freshness == "latest"
    assert tf.year == 2026  # falls through to current_year when freshness=latest
    print("PASS test_parser_freshness_latest")


def test_parser_last_n_years_expansion():
    p = TemporalParser(current_year=2026)
    tf = p.parse("Apple revenue over the last 3 years")
    assert 2026 in tf.detected_years
    assert 2025 in tf.detected_years
    assert 2024 in tf.detected_years
    assert not tf.is_filterable  # multiple years -> needs decomposition
    print("PASS test_parser_last_n_years_expansion")


# --------------------------------------------------------------------------- #
# TemporalAwareRetriever tests
# --------------------------------------------------------------------------- #

def test_retriever_uses_filtered_when_refs_detected():
    vs = FakeVectorStore(
        filtered_results=[{"text": "filtered", "company": "Apple", "year": 2024, "source": "Apple_10K_2024.pdf"}],
    )
    r = TemporalAwareRetriever(vs)
    out = r.retrieve("What was Apple revenue in 2024?", k=3)
    assert len(out) == 1
    assert r.last_filter.company == "Apple"
    assert r.last_filter.year == 2024
    assert vs.last_call[0] == "filtered", vs.last_call
    assert vs.last_call[3] == {"company": "Apple", "year": 2024}
    print("PASS test_retriever_uses_filtered_when_refs_detected")


def test_retriever_falls_back_to_unfiltered_for_generic():
    vs = FakeVectorStore(results=[{"text": "anywhere"}])
    r = TemporalAwareRetriever(vs)
    out = r.retrieve("What is deep learning?", k=3)
    assert len(out) == 1
    assert vs.last_call[0] == "unfiltered"
    print("PASS test_retriever_falls_back_to_unfiltered_for_generic")


def test_retriever_soft_fallback_when_filter_empty():
    """If the filtered query returns nothing, the wrapper should fall back to
    unfiltered retrieval rather than starve the orchestrator."""
    vs = FakeVectorStore(
        results=[{"text": "any-period"}],
        filtered_results=[],  # filter zeroes out
    )
    r = TemporalAwareRetriever(vs)
    out = r.retrieve("Apple revenue in 2024", k=3)
    assert len(out) == 1
    # unfiltered call happened after filtered returned empty
    assert vs.last_call[0] == "unfiltered"
    print("PASS test_retriever_soft_fallback_when_filter_empty")


def test_retriever_multiple_years_skips_filter():
    vs = FakeVectorStore(results=[{"text": "all-time"}])
    r = TemporalAwareRetriever(vs)
    out = r.retrieve("Compare Apple revenue 2023 vs 2024", k=3)
    assert len(out) == 1
    # Multiple years detected -> not filterable -> falls through to parent.
    assert vs.last_call[0] == "unfiltered"
    print("PASS test_retriever_multiple_years_skips_filter")


def test_chroma_kwargs_excludes_quarter():
    """as_chroma_kwargs should only return keys the existing
    similarity_search_filtered API supports (company/year/doc_type)."""
    p = TemporalParser(current_year=2026)
    tf = p.parse("Apple Q1 2024 10-K")
    kwargs = tf.as_chroma_kwargs()
    assert "quarter" not in kwargs
    assert kwargs.get("company") == "Apple"
    assert kwargs.get("year") == 2024
    assert kwargs.get("doc_type") == "10-K"
    print("PASS test_chroma_kwargs_excludes_quarter")


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #

def main():
    tests = [
        test_parser_extracts_company_and_year,
        test_parser_detects_multi_company,
        test_parser_detects_multi_year_is_multi_entity,
        test_parser_extracts_ticker_alias,
        test_parser_handles_relative_year,
        test_parser_extracts_quarter,
        test_parser_detects_doc_type,
        test_parser_multiple_years_not_filterable,
        test_parser_no_filters_for_generic_query,
        test_parser_freshness_latest,
        test_parser_last_n_years_expansion,
        test_retriever_uses_filtered_when_refs_detected,
        test_retriever_falls_back_to_unfiltered_for_generic,
        test_retriever_soft_fallback_when_filter_empty,
        test_retriever_multiple_years_skips_filter,
        test_chroma_kwargs_excludes_quarter,
    ]
    failures = []
    for t in tests:
        try:
            t()
        except AssertionError as e:
            failures.append((t.__name__, str(e)))
            print(f"FAIL {t.__name__}: {e}")
        except Exception as e:
            failures.append((t.__name__, repr(e)))
            print(f"ERROR {t.__name__}: {e!r}")

    print()
    print(f"{len(tests) - len(failures)}/{len(tests)} tests passed.")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
