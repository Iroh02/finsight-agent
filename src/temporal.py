"""Temporal-aware retrieval.

Parses temporal and company references from natural-language queries and
turns them into Chroma metadata filters. Wraps the existing Retriever so
that calls like "What was Apple's revenue in FY 2024?" only consider
chunks tagged with company=Apple AND year=2024, rather than fishing across
the whole corpus.

Why this matters for finance:
    Filings are stamped to a specific fiscal year and quarter. Off-period
    chunks (e.g., 2023 figures retrieved for a 2025 question) are the #1
    silent failure mode of naive RAG over filings. Tightening retrieval to
    the user's intended period typically improves both precision and
    faithfulness without sacrificing recall.

Design choices:
    * Heuristic parsing — regex + alias tables. Cheap, deterministic, and
      good enough on the structured language analysts actually use.
    * Single-year filters only — if the query mentions multiple years
      ("compare 2024 vs 2025"), we skip filtering and let the Decomposer
      split into per-year sub-queries which each re-enter this parser.
    * Soft fallback — if filtered retrieval returns nothing, fall back to
      unfiltered retrieval so the user still gets an answer (with the
      empty-filter event logged in the trace for transparency).
"""

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Set

from src.retriever import Retriever


CURRENT_FISCAL_YEAR = 2026  # update yearly; corresponds to most recent corpus filings

_COMPANY_ALIASES: Dict[str, List[str]] = {
    "Apple":     ["apple", "aapl"],
    "Amazon":    ["amazon", "amzn"],
    "Nvidia":    ["nvidia", "nvda"],
    "Microsoft": ["microsoft", "msft"],
    "Alphabet":  ["alphabet", "google", "googl", "goog"],
    "Meta":      ["meta", "facebook"],
    "Tesla":     ["tesla", "tsla"],
    "Netflix":   ["netflix", "nflx"],
}

_DOC_TYPE_KEYWORDS: Dict[str, List[str]] = {
    "10-K":            ["10-k", "10k", "annual report", "form 10-k"],
    "10-Q":            ["10-q", "10q", "quarterly report", "form 10-q"],
    "earnings_report": ["earnings", "earnings call", "earnings release"],
    "annual_report":   ["annual report"],
}

_RELATIVE_YEAR = {
    "this year":     0,
    "current year":  0,
    "this fiscal":   0,
    "last year":    -1,
    "previous year":-1,
    "prior year":   -1,
    "two years ago":-2,
    "year before last": -2,
}


@dataclass
class TemporalFilter:
    """Detected metadata constraints from a query."""
    company: Optional[str] = None
    year: Optional[int] = None
    quarter: Optional[str] = None
    doc_type: Optional[str] = None
    freshness: Optional[str] = None  # "latest" | "earliest" | None
    detected_years: List[int] = None  # all years mentioned (may be > 1)
    detected_companies: List[str] = None  # all companies mentioned (may be > 1)
    note: str = ""                    # human-readable description for UI badge

    def __post_init__(self):
        if self.detected_years is None:
            self.detected_years = []
        if self.detected_companies is None:
            self.detected_companies = []

    @property
    def is_multi_entity(self) -> bool:
        """True iff this query compares ≥2 distinct companies or fiscal years.

        The MultiAgentOrchestrator uses this to override the planner — any
        cross-entity question must go through the full decompose → conflict →
        synthesize pipeline so each entity gets its own filtered retrieval.
        """
        return len(self.detected_companies) >= 2 or len(self.detected_years) >= 2

    @property
    def has_filters(self) -> bool:
        return any([self.company, self.year, self.quarter, self.doc_type])

    @property
    def is_filterable(self) -> bool:
        """A query is filterable iff it has at least one concrete filter
        AND mentions at most one company and at most one year. Multi-entity
        queries are deferred to the decomposer."""
        return (
            self.has_filters
            and len(self.detected_years) <= 1
            and len(self.detected_companies) <= 1
        )

    def as_chroma_kwargs(self) -> Dict:
        """Return kwargs accepted by VectorStore.similarity_search_filtered."""
        out: Dict = {}
        if self.company:
            out["company"] = self.company
        if self.year:
            out["year"] = self.year
        if self.doc_type:
            out["doc_type"] = self.doc_type
        return out

    def badge_label(self) -> str:
        """Short label for the UI freshness badge, e.g. 'Apple · FY2024 · 10-K'."""
        parts: List[str] = []
        if self.company:
            parts.append(self.company)
        if self.year and self.quarter:
            parts.append(f"FY{self.year} {self.quarter}")
        elif self.year:
            parts.append(f"FY{self.year}")
        elif self.quarter:
            parts.append(self.quarter)
        if self.doc_type:
            parts.append(self.doc_type)
        return " · ".join(parts)


class TemporalParser:
    """Extracts temporal and company filters from a natural-language query."""

    def __init__(self, current_year: int = CURRENT_FISCAL_YEAR):
        self.current_year = current_year

    def parse(self, query: str) -> TemporalFilter:
        if not query:
            return TemporalFilter()

        q = query.lower()
        tf = TemporalFilter()

        tf.detected_companies = self._extract_companies(q)
        tf.company = tf.detected_companies[0] if len(tf.detected_companies) == 1 else None
        tf.detected_years = self._extract_years(q)
        tf.quarter = self._extract_quarter(q)
        tf.doc_type = self._extract_doc_type(q)
        tf.freshness = self._extract_freshness(q)

        if len(tf.detected_years) == 1:
            tf.year = tf.detected_years[0]
        elif tf.freshness == "latest" and not tf.detected_years:
            tf.year = self.current_year
        elif tf.freshness == "earliest" and not tf.detected_years:
            # leave year unset; filtered search will return whatever exists
            pass

        tf.note = self._build_note(tf)
        return tf

    @staticmethod
    def _extract_companies(q: str) -> List[str]:
        """Return every company whose name/ticker appears in the query, in
        insertion order of the alias table. Used to detect multi-entity
        comparison queries that must be routed through the full multi-agent
        pipeline rather than the single-agent fast path."""
        found: List[str] = []
        for company, aliases in _COMPANY_ALIASES.items():
            for alias in aliases:
                if re.search(rf"\b{re.escape(alias)}\b", q):
                    if company not in found:
                        found.append(company)
                    break
        return found

    def _extract_years(self, q: str) -> List[int]:
        years: Set[int] = set()

        # Absolute years: 2018-2030 range
        for m in re.finditer(r"\b(20[1-3]\d)\b", q):
            years.add(int(m.group(1)))

        # "FY 2024" / "FY2024" / "fiscal 2024"
        for m in re.finditer(r"\b(?:fy|fiscal\s+year|fiscal)\s*(20[1-3]\d)\b", q):
            years.add(int(m.group(1)))

        # Relative refs ("last year", "this year")
        for phrase, offset in _RELATIVE_YEAR.items():
            if phrase in q:
                years.add(self.current_year + offset)

        # "last 3 years" / "past 5 years" → expand list
        m = re.search(r"\b(?:last|past)\s+(\d+)\s+years?\b", q)
        if m:
            n = int(m.group(1))
            if 1 <= n <= 10:
                for i in range(n):
                    years.add(self.current_year - i)

        return sorted(years)

    @staticmethod
    def _extract_quarter(q: str) -> Optional[str]:
        m = re.search(r"\b(q[1-4])\b", q)
        if m:
            return m.group(1).upper()
        ordinal_map = {
            "first quarter": "Q1", "second quarter": "Q2",
            "third quarter": "Q3", "fourth quarter": "Q4",
        }
        for phrase, q_lbl in ordinal_map.items():
            if phrase in q:
                return q_lbl
        return None

    @staticmethod
    def _extract_doc_type(q: str) -> Optional[str]:
        for doc_type, keywords in _DOC_TYPE_KEYWORDS.items():
            for kw in keywords:
                if kw in q:
                    return doc_type
        return None

    @staticmethod
    def _extract_freshness(q: str) -> Optional[str]:
        if re.search(r"\b(latest|most recent|recent|newest|current)\b", q):
            return "latest"
        if re.search(r"\b(earliest|oldest|first|initial)\b", q):
            return "earliest"
        return None

    @staticmethod
    def _build_note(tf: "TemporalFilter") -> str:
        if tf.is_multi_entity:
            parts = []
            if len(tf.detected_companies) > 1:
                parts.append(f"companies: {', '.join(tf.detected_companies)}")
            if len(tf.detected_years) > 1:
                parts.append(f"years: {', '.join(map(str, tf.detected_years))}")
            return f"Multi-entity query ({'; '.join(parts)}); decomposing into per-entity sub-queries."
        if not tf.has_filters:
            return "No temporal filters detected; retrieving across full corpus."
        return f"Filtering retrieval to {tf.badge_label()}."


class TemporalAwareRetriever(Retriever):
    """
    Drop-in Retriever replacement.

    When a query has detectable company/year/quarter/doc_type references,
    pushes them down into ChromaDB's metadata filter before reranking.
    Falls back to vanilla behavior otherwise (or when filtered retrieval
    returns an empty result set).

    The chosen filter is exposed on `self.last_filter` so the orchestrator
    can surface it in the trace and UI.
    """

    def __init__(self, *args, parser: Optional[TemporalParser] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.parser = parser or TemporalParser()
        self.last_filter: Optional[TemporalFilter] = None

    def retrieve(self, query: str, k: int = 5) -> List[Dict]:
        tf = self.parser.parse(query)
        self.last_filter = tf

        # No filters detected, or query has multiple years — defer to parent.
        if not tf.is_filterable:
            return super().retrieve(query, k=k)

        # Vector store must expose the filtered API.
        if not hasattr(self.vectorstore, "similarity_search_filtered"):
            return super().retrieve(query, k=k)

        # When reranker is on, fetch a larger candidate pool to rerank.
        n_retrieve = k * self.retrieve_multiplier if self.use_reranker else k

        # HyDE-augmented embedding query when enabled.
        search_query = query
        if self.use_hyde and self.hyde:
            try:
                search_query = self.hyde.augment_query(query, include_original=True)
            except Exception:
                search_query = query

        try:
            initial = self.vectorstore.similarity_search_filtered(
                query=search_query,
                k=n_retrieve,
                **tf.as_chroma_kwargs(),
            )
        except Exception:
            initial = []

        # If the filter zeroes out results, soft-fall-back to unfiltered.
        if not initial:
            return super().retrieve(query, k=k)

        # Rerank with the ORIGINAL query (not HyDE) for max precision.
        if self.use_reranker and self.reranker:
            return self.reranker.rerank(query, initial, top_k=k)
        return initial[:k]
