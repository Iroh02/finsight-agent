"""Tests for the FinSight Trust Score calculator and extended decision states.

Pure-Python: no LLM, no network, no Chroma. Verifies that:
  * Each component clamps to [0, 1] and matches its weight
  * The composite respects the weighted formula
  * Trust bands are assigned correctly at boundaries
  * The extended-decision mapping respects its precedence order
  * Cross-encoder negative logits don't break the retrieval-quality score

Run:
    python -m src.test_trust_score
"""

from src.trust_score import (
    TrustScoreCalculator,
    derive_extended_decision,
    WEIGHTS,
    _sigmoid,
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _calc():
    return TrustScoreCalculator()


def _chunk(score=0.7, page=1):
    return {"text": "x", "source": "a.pdf", "page": page, "score": score}


# --------------------------------------------------------------------------- #
# Sigmoid sanity
# --------------------------------------------------------------------------- #

def test_sigmoid_handles_negative_logits():
    """Cross-encoder rerank scores can be negative — must not crash."""
    assert 0 < _sigmoid(-5) < 0.5
    assert 0.5 < _sigmoid(5) < 1
    assert abs(_sigmoid(0) - 0.5) < 1e-6
    assert _sigmoid("garbage") == 0.5
    assert _sigmoid(1000) == 1.0
    assert _sigmoid(-1000) == 0.0
    print("PASS test_sigmoid_handles_negative_logits")


# --------------------------------------------------------------------------- #
# Component-level
# --------------------------------------------------------------------------- #

def test_retrieval_quality_zero_when_no_chunks():
    ts = _calc().compute(chunks=[], mode="naive")
    rq = next(c for c in ts.components if c.name == "Retrieval Quality")
    assert rq.value == 0.0
    print("PASS test_retrieval_quality_zero_when_no_chunks")


def test_citation_coverage_full_when_all_pages_set():
    ts = _calc().compute(chunks=[_chunk(0.8, 1), _chunk(0.8, 2)], mode="agentic")
    cc = next(c for c in ts.components if c.name == "Citation Coverage")
    assert cc.value == 1.0
    print("PASS test_citation_coverage_full_when_all_pages_set")


def test_citation_coverage_partial():
    ts = _calc().compute(chunks=[_chunk(0.8, 1), _chunk(0.8, None), _chunk(0.8, 3)], mode="agentic")
    cc = next(c for c in ts.components if c.name == "Citation Coverage")
    assert abs(cc.value - (2 / 3)) < 1e-6, cc.value
    print("PASS test_citation_coverage_partial")


def test_faithfulness_penalizes_contradictions():
    verification = {"stats": {"n_claims": 4, "supported": 3, "contradicted": 1, "insufficient": 0}}
    ts = _calc().compute(chunks=[_chunk()], verification=verification, mode="multi_agent")
    f = next(c for c in ts.components if c.name == "Faithfulness")
    # 3/4 = 0.75, then -0.15 for the contradiction → 0.60
    assert abs(f.value - 0.60) < 1e-6, f.value
    print("PASS test_faithfulness_penalizes_contradictions")


def test_faithfulness_neutral_when_verifier_skipped():
    ts = _calc().compute(
        chunks=[_chunk()],
        verification={"skipped": True, "stats": {"n_claims": 0}},
        mode="agentic",
    )
    f = next(c for c in ts.components if c.name == "Faithfulness")
    assert f.value == 0.6
    print("PASS test_faithfulness_neutral_when_verifier_skipped")


def test_conflict_free_penalty_scales_with_severity():
    """High-severity conflicts hit harder than medium/low."""
    cr = {"pairs_checked": 2, "stats": {"by_severity": {"HIGH": 1, "MEDIUM": 0, "LOW": 0}}}
    ts = _calc().compute(chunks=[_chunk()], conflict_report=cr, mode="multi_agent")
    cf = next(c for c in ts.components if c.name == "Conflict-Free")
    # 1 high / 2 pairs = 0.25 penalty -> 0.75
    assert abs(cf.value - 0.75) < 1e-6
    print("PASS test_conflict_free_penalty_scales_with_severity")


def test_conflict_free_top_score_when_no_pairs():
    cr = {"pairs_checked": 0, "stats": {"by_severity": {}}}
    ts = _calc().compute(chunks=[_chunk()], conflict_report=cr, mode="agentic")
    cf = next(c for c in ts.components if c.name == "Conflict-Free")
    assert cf.value == 0.85
    print("PASS test_conflict_free_top_score_when_no_pairs")


def test_temporal_precision_high_when_filter_applied():
    tc = [{"sub_question": "x", "company": "Apple", "year": 2024}]
    ts = _calc().compute(chunks=[_chunk()], temporal_context=tc, mode="multi_agent")
    tp = next(c for c in ts.components if c.name == "Temporal Precision")
    assert tp.value == 1.0
    print("PASS test_temporal_precision_high_when_filter_applied")


def test_temporal_precision_neutral_when_no_dates():
    ts = _calc().compute(chunks=[_chunk()], temporal_context=[], mode="naive")
    tp = next(c for c in ts.components if c.name == "Temporal Precision")
    assert tp.value == 0.5
    print("PASS test_temporal_precision_neutral_when_no_dates")


# --------------------------------------------------------------------------- #
# Composite + band
# --------------------------------------------------------------------------- #

def test_weights_sum_to_one():
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9
    print("PASS test_weights_sum_to_one")


def test_composite_clamped_to_0_100():
    # Worst-case inputs
    ts = _calc().compute(chunks=[], mode="naive")
    assert 0 <= ts.composite <= 100
    print("PASS test_composite_clamped_to_0_100")


def test_band_assignment():
    calc = _calc()
    # Top-score scenario: high retrieval, full faithfulness, all pages, no conflicts, temporal hit
    ts = calc.compute(
        chunks=[_chunk(2.0, 1), _chunk(2.0, 2), _chunk(2.0, 3)],
        verification={"stats": {"n_claims": 3, "supported": 3, "contradicted": 0, "insufficient": 0}},
        validation={"suggested_confidence": 0.95, "summary": "ok"},
        conflict_report={"pairs_checked": 2, "stats": {"by_severity": {"HIGH": 0, "MEDIUM": 0, "LOW": 0}}},
        temporal_context=[{"company": "Apple", "year": 2024}],
        mode="multi_agent",
    )
    assert ts.composite >= 86, f"Expected HIGH_TRUST, got {ts.composite}"
    assert ts.band == "HIGH_TRUST"
    # Worst-case: empty chunks AND contradicted claims AND high-severity conflicts → REJECT band
    ts2 = calc.compute(
        chunks=[],
        verification={"stats": {"n_claims": 4, "supported": 0, "contradicted": 4, "insufficient": 0}},
        validation={"suggested_confidence": 0.05, "summary": "fail"},
        conflict_report={"pairs_checked": 1, "stats": {"by_severity": {"HIGH": 1, "MEDIUM": 0, "LOW": 0}}},
        mode="multi_agent",
    )
    assert ts2.band == "REJECT", f"Expected REJECT, got {ts2.band} ({ts2.composite})"
    # Empty-chunks + neutral defaults still legitimately lands LOW_TRUST
    ts3 = calc.compute(chunks=[], mode="naive")
    assert ts3.band == "LOW_TRUST", f"Expected LOW_TRUST, got {ts3.band} ({ts3.composite})"
    print("PASS test_band_assignment")


# --------------------------------------------------------------------------- #
# Extended decision precedence
# --------------------------------------------------------------------------- #

def _trust(band="HIGH_TRUST", composite=90):
    """Minimal TrustScore stub for decision tests."""
    class _T:
        pass
    t = _T()
    t.band = band
    t.composite = composite
    return t


def test_decision_refuse_passes_through():
    out = derive_extended_decision("REFUSE", _trust(), None, None, None, [_chunk()])
    assert out == "REFUSE"
    print("PASS test_decision_refuse_passes_through")


def test_decision_high_conflict_wins_over_trust():
    cr = {"stats": {"by_severity": {"HIGH": 1, "MEDIUM": 0, "LOW": 0}}}
    out = derive_extended_decision("ANSWER", _trust("HIGH_TRUST", 90), None, cr, [], [_chunk()])
    assert out == "CONFLICT_REVIEW"
    print("PASS test_decision_high_conflict_wins_over_trust")


def test_decision_request_more_docs_when_temporal_zero_chunks():
    out = derive_extended_decision(
        "ANSWER", _trust("HIGH_TRUST", 90),
        verification=None, conflict_report=None,
        temporal_context=[{"company": "Amazon", "year": 2024}],
        chunks=[],
    )
    assert out == "REQUEST_MORE_DOCS"
    print("PASS test_decision_request_more_docs_when_temporal_zero_chunks")


def test_decision_hedged_for_insufficient_claims():
    v = {"stats": {"n_claims": 3, "supported": 1, "insufficient": 2, "contradicted": 0}}
    out = derive_extended_decision(
        "ANSWER", _trust("HIGH_TRUST", 90),
        verification=v, conflict_report=None, temporal_context=None, chunks=[_chunk()],
    )
    assert out == "HEDGED_ANSWER"
    print("PASS test_decision_hedged_for_insufficient_claims")


def test_decision_escalate_in_analyst_review_band():
    out = derive_extended_decision(
        "ANSWER", _trust("ANALYST_REVIEW", 78),
        verification=None, conflict_report=None, temporal_context=None, chunks=[_chunk()],
    )
    assert out == "ESCALATE"
    print("PASS test_decision_escalate_in_analyst_review_band")


def test_decision_hedged_for_low_trust():
    out = derive_extended_decision(
        "ANSWER", _trust("LOW_TRUST", 35),
        verification=None, conflict_report=None, temporal_context=None, chunks=[_chunk()],
    )
    assert out == "HEDGED_ANSWER"
    print("PASS test_decision_hedged_for_low_trust")


def test_decision_plain_answer_when_high_trust_and_no_flags():
    out = derive_extended_decision(
        "ANSWER", _trust("HIGH_TRUST", 90),
        verification={"stats": {"n_claims": 2, "supported": 2, "contradicted": 0, "insufficient": 0}},
        conflict_report={"stats": {"by_severity": {"HIGH": 0, "MEDIUM": 0, "LOW": 0}}},
        temporal_context=None, chunks=[_chunk()],
    )
    assert out == "ANSWER"
    print("PASS test_decision_plain_answer_when_high_trust_and_no_flags")


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #

def main():
    tests = [
        test_sigmoid_handles_negative_logits,
        test_retrieval_quality_zero_when_no_chunks,
        test_citation_coverage_full_when_all_pages_set,
        test_citation_coverage_partial,
        test_faithfulness_penalizes_contradictions,
        test_faithfulness_neutral_when_verifier_skipped,
        test_conflict_free_penalty_scales_with_severity,
        test_conflict_free_top_score_when_no_pairs,
        test_temporal_precision_high_when_filter_applied,
        test_temporal_precision_neutral_when_no_dates,
        test_weights_sum_to_one,
        test_composite_clamped_to_0_100,
        test_band_assignment,
        test_decision_refuse_passes_through,
        test_decision_high_conflict_wins_over_trust,
        test_decision_request_more_docs_when_temporal_zero_chunks,
        test_decision_hedged_for_insufficient_claims,
        test_decision_escalate_in_analyst_review_band,
        test_decision_hedged_for_low_trust,
        test_decision_plain_answer_when_high_trust_and_no_flags,
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
