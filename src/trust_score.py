"""FinSight Trust Score (FTS) — composite quantitative score for answer reliability.

Six weighted components, each normalized to [0, 1]:

    FTS = 0.20 × Retrieval Quality       (avg sigmoid-normalized rerank score)
        + 0.20 × Faithfulness            (verifier supported / total claims)
        + 0.20 × Citation Coverage       (chunks with valid page references)
        + 0.15 × Validator Score         (multi-agent reasoning soundness)
        + 0.15 × Conflict-Free Score     (1 - weighted cross-doc conflicts)
        + 0.10 × Temporal Precision      (filtered retrieval applied to dated query)

Final score is rescaled to 0-100 and bucketed into trust bands. The same
score also informs the extended decision state (ANSWER / HEDGED_ANSWER /
CONFLICT_REVIEW / REQUEST_MORE_DOCS / ESCALATE / CLARIFY / REFUSE).

Design intent: turn the multiple verification signals already in the pipeline
(verifier, validator, conflict detector, temporal filter) into a single
quantitative number an analyst can act on, in the spirit of a clinical risk
score — every input is named, weighted, and reproducible.
"""

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional


# Component weights (must sum to 1.0)
WEIGHTS: Dict[str, float] = {
    "retrieval_quality":  0.20,
    "faithfulness":       0.20,
    "citation_coverage":  0.20,
    "validator_score":    0.15,
    "conflict_free":      0.15,
    "temporal_precision": 0.10,
}

# Trust bands keyed to composite score 0-100
TRUST_BANDS = [
    (0,  30, "REJECT",          "Score below reliability threshold — do not rely on this answer."),
    (31, 50, "LOW_TRUST",       "Weak evidence base — verify independently before acting."),
    (51, 70, "NEEDS_REVIEW",    "Plausible answer with notable gaps — analyst review recommended."),
    (71, 85, "ANALYST_REVIEW",  "Strong evidence — confirm key figures before financial decisions."),
    (86, 100, "HIGH_TRUST",     "Multi-verified answer with grounded citations and no conflicts."),
]


@dataclass
class TrustComponent:
    """One weighted input to the composite trust score."""
    name: str
    value: float       # 0.0–1.0
    weight: float      # 0.0–1.0
    detail: str = ""   # human-readable explanation

    @property
    def contribution(self) -> float:
        """Weighted contribution to the composite (0-1)."""
        return self.value * self.weight


@dataclass
class TrustScore:
    """Composite FinSight Trust Score with full component breakdown."""
    composite: int                                  # 0–100
    band: str                                       # REJECT / LOW_TRUST / ...
    band_description: str
    components: List[TrustComponent] = field(default_factory=list)

    def as_dict(self) -> Dict:
        return {
            "composite": self.composite,
            "band": self.band,
            "band_description": self.band_description,
            "components": [
                {
                    "name": c.name,
                    "value": round(c.value, 3),
                    "weight": c.weight,
                    "weighted": round(c.contribution, 3),
                    "detail": c.detail,
                }
                for c in self.components
            ],
        }


class TrustScoreCalculator:
    """Aggregates pipeline outputs into a FinSight Trust Score."""

    def compute(
        self,
        *,
        chunks: Optional[List[Dict]] = None,
        verification: Optional[Dict] = None,
        validation: Optional[Dict] = None,
        conflict_report: Optional[Dict] = None,
        temporal_context: Optional[List[Dict]] = None,
        mode: str = "agentic",
    ) -> TrustScore:
        """
        Compute the trust score from whatever signals are available.

        Args:
            chunks: retrieved chunks (must carry 'score' and optionally 'page')
            verification: VerifierAgent output (CoVe stats)
            validation: ValidatorAgent output (multi-agent only)
            conflict_report: ConflictDetectorAgent output
            temporal_context: list of detected temporal filters
            mode: "naive" | "agentic" | "multi_agent" — used to soften penalties
                  for pipelines that legitimately can't supply some signals.

        Returns:
            TrustScore with composite (0-100), band, and component breakdown.
        """
        comps: List[TrustComponent] = []

        # 1. Retrieval Quality — average sigmoid-normalized chunk scores
        rq, rq_detail = self._retrieval_quality(chunks or [])
        comps.append(TrustComponent("Retrieval Quality", rq, WEIGHTS["retrieval_quality"], rq_detail))

        # 2. Faithfulness — verifier supported/total claims
        f, f_detail = self._faithfulness(verification, mode)
        comps.append(TrustComponent("Faithfulness", f, WEIGHTS["faithfulness"], f_detail))

        # 3. Citation Coverage — fraction of chunks with a page reference
        cc, cc_detail = self._citation_coverage(chunks or [])
        comps.append(TrustComponent("Citation Coverage", cc, WEIGHTS["citation_coverage"], cc_detail))

        # 4. Validator Score — multi-agent reasoning soundness (neutral if absent)
        vs, vs_detail = self._validator_score(validation, mode)
        comps.append(TrustComponent("Validator Score", vs, WEIGHTS["validator_score"], vs_detail))

        # 5. Conflict-Free Score — penalty for cross-doc conflicts
        cf, cf_detail = self._conflict_free(conflict_report)
        comps.append(TrustComponent("Conflict-Free", cf, WEIGHTS["conflict_free"], cf_detail))

        # 6. Temporal Precision — was retrieval scoped to the right period?
        tp, tp_detail = self._temporal_precision(temporal_context)
        comps.append(TrustComponent("Temporal Precision", tp, WEIGHTS["temporal_precision"], tp_detail))

        # Composite
        raw = sum(c.contribution for c in comps)
        composite = int(round(raw * 100))
        composite = max(0, min(100, composite))
        band, desc = self._band(composite)

        return TrustScore(
            composite=composite,
            band=band,
            band_description=desc,
            components=comps,
        )

    # ------------------------------------------------------------------ #
    # Component calculators
    # ------------------------------------------------------------------ #

    @staticmethod
    def _retrieval_quality(chunks: List[Dict]) -> (float, str):
        if not chunks:
            return 0.0, "No chunks retrieved."
        scores = [c.get("score") for c in chunks if c.get("score") is not None]
        if not scores:
            return 0.5, "Chunks retrieved but no relevance scores available."
        normalized = [_sigmoid(s) for s in scores]
        avg = sum(normalized) / len(normalized)
        return avg, f"Avg normalized relevance over {len(scores)} chunks: {avg:.2f}."

    @staticmethod
    def _faithfulness(verification: Optional[Dict], mode: str) -> (float, str):
        if not verification or verification.get("skipped"):
            # Verifier didn't run — assume mid-band confidence rather than penalize
            # naive/agentic modes that legitimately don't include it.
            return 0.6, "Verifier did not run on this query path."
        stats = verification.get("stats", {})
        n = stats.get("n_claims", 0)
        if n == 0:
            return 0.7, "No factual claims extracted — answer was abstractive or refused."
        supported = stats.get("supported", 0)
        contradicted = stats.get("contradicted", 0)
        ratio = supported / n
        # Hard penalty for contradicted claims even if ratio is OK
        if contradicted:
            ratio = max(0.0, ratio - 0.15 * contradicted)
        return ratio, (
            f"{supported}/{n} claims supported"
            + (f", {contradicted} contradicted" if contradicted else "")
            + f"; ratio {ratio:.2f}."
        )

    @staticmethod
    def _citation_coverage(chunks: List[Dict]) -> (float, str):
        if not chunks:
            return 0.0, "No chunks to cite from."
        with_page = sum(1 for c in chunks if c.get("page") not in (None, "", 0))
        ratio = with_page / len(chunks)
        return ratio, f"{with_page}/{len(chunks)} chunks have page references."

    @staticmethod
    def _validator_score(validation: Optional[Dict], mode: str) -> (float, str):
        if not validation:
            return 0.6, "Validator did not run on this query path."
        # Prefer suggested_confidence; fall back to validation_score
        v = validation.get("suggested_confidence")
        if v is None:
            v = validation.get("validation_score")
        if v is None:
            return 0.6, "Validator ran but produced no numeric score."
        try:
            v = float(v)
        except (TypeError, ValueError):
            return 0.6, "Validator output not parseable."
        v = max(0.0, min(1.0, v))
        return v, f"Validator score: {v:.2f}; {validation.get('summary', '')[:120]}"

    @staticmethod
    def _conflict_free(conflict_report: Optional[Dict]) -> (float, str):
        if not conflict_report or conflict_report.get("skipped"):
            return 0.85, "Cross-document conflict check did not run."
        pairs = conflict_report.get("pairs_checked", 0)
        if pairs == 0:
            return 0.85, "No cross-document pairs eligible for comparison."
        sev = conflict_report.get("stats", {}).get("by_severity", {})
        h, m, l = sev.get("HIGH", 0), sev.get("MEDIUM", 0), sev.get("LOW", 0)
        penalty = (0.50 * h + 0.20 * m + 0.05 * l) / pairs
        score = max(0.0, 1.0 - penalty)
        if h or m or l:
            return score, f"{h} high / {m} medium / {l} low conflicts over {pairs} pairs."
        return score, f"No conflicts detected over {pairs} cross-document pairs."

    @staticmethod
    def _temporal_precision(temporal_context: Optional[List[Dict]]) -> (float, str):
        if not temporal_context:
            return 0.5, "No temporal references detected — broad retrieval."
        filtered = sum(
            1 for t in temporal_context
            if (t.get("year") or t.get("company") or t.get("doc_type"))
        )
        if filtered == 0:
            return 0.5, "Temporal references present but no concrete filters applied."
        ratio = filtered / len(temporal_context)
        # Cap below 1.0 unless every sub-query was filterable
        return ratio, f"{filtered}/{len(temporal_context)} sub-queries scoped to a specific filing."

    @staticmethod
    def _band(score: int) -> (str, str):
        for lo, hi, band, desc in TRUST_BANDS:
            if lo <= score <= hi:
                return band, desc
        return "REJECT", "Score below reliability threshold."


# ---------------------------------------------------------------------- #
# Extended decision states (7 states, derived from trust + signals)
# ---------------------------------------------------------------------- #

EXTENDED_DECISIONS = {
    "ANSWER":            "Strong evidence — answer accepted as-is.",
    "HEDGED_ANSWER":     "Answer with caveats — some claims could not be verified.",
    "CONFLICT_REVIEW":   "High-severity cross-document contradiction detected — needs analyst review.",
    "REQUEST_MORE_DOCS": "Required filings not in corpus — supply more documents.",
    "ESCALATE":          "Borderline trust — escalate to senior analyst.",
    "CLARIFY":           "Question is ambiguous — clarify before proceeding.",
    "REFUSE":            "Insufficient evidence or contradictions — refusing to answer.",
}


def derive_extended_decision(
    base_decision: str,
    trust: TrustScore,
    verification: Optional[Dict] = None,
    conflict_report: Optional[Dict] = None,
    temporal_context: Optional[List[Dict]] = None,
    chunks: Optional[List[Dict]] = None,
) -> str:
    """
    Map the legacy 4-state decision + trust signals onto a 7-state recommendation.

    Order of precedence:
        1. Legacy CLARIFY / REFUSE pass through unchanged.
        2. Empty retrieval after a temporal filter → REQUEST_MORE_DOCS.
        3. Any HIGH-severity conflict → CONFLICT_REVIEW.
        4. Verifier flagged INSUFFICIENT claims → HEDGED_ANSWER.
        5. Trust 71-85 → ESCALATE (strong but not bulletproof).
        6. Trust ≤ 50 → HEDGED_ANSWER (downgrade from ANSWER).
        7. Otherwise → ANSWER.
    """
    base = (base_decision or "ANSWER").upper()
    if base in ("CLARIFY", "REFUSE"):
        return base

    # Required filings missing
    if temporal_context and (not chunks or len(chunks) == 0):
        return "REQUEST_MORE_DOCS"

    # Cross-document conflict at HIGH severity
    sev = ((conflict_report or {}).get("stats", {}) or {}).get("by_severity", {})
    if sev.get("HIGH", 0) > 0:
        return "CONFLICT_REVIEW"

    # Verifier marked some claims insufficient (not contradicted — those refuse)
    v_stats = (verification or {}).get("stats", {}) or {}
    if v_stats.get("insufficient", 0) > 0:
        return "HEDGED_ANSWER"

    # Trust band gating
    band = trust.band
    if band in ("REJECT", "LOW_TRUST"):
        return "HEDGED_ANSWER"
    if band == "ANALYST_REVIEW":
        return "ESCALATE"

    return "ANSWER"


# ---------------------------------------------------------------------- #
# Utilities
# ---------------------------------------------------------------------- #

def _sigmoid(x) -> float:
    """Numerically safe sigmoid — handles negative cross-encoder logits."""
    try:
        x = float(x)
    except (TypeError, ValueError):
        return 0.5
    if x >= 50:
        return 1.0
    if x <= -50:
        return 0.0
    return 1.0 / (1.0 + math.exp(-x))
