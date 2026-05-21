"""Tests for ConflictDetectorAgent.

Pure-Python: uses a fake LLM client that returns canned responses based on
substring matches. Validates pair eligibility, response parsing, and end-to-end
detect() reporting.

Run:
    python -m src.test_conflict_detector
"""

from typing import Dict, List, Optional

from src.agents.conflict_detector import ConflictDetectorAgent


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #

class FakeLLMClient:
    """Returns a canned response based on a substring -> response map."""

    def __init__(self, responses: Dict[str, str], default: str = "CONFLICT: NO\nREASON: nothing found"):
        self.responses = responses
        self.default = default
        self.calls: List[str] = []

    def generate(self, prompt: str, system: Optional[str] = None,
                 temperature: float = 0.0, max_tokens: int = 200) -> str:
        self.calls.append(prompt)
        matches = [(k, v) for k, v in self.responses.items() if k in prompt]
        if not matches:
            return self.default
        key, value = max(matches, key=lambda kv: len(kv[0]))
        return value


def _sub(answer: str, company: str = "Apple", year: int = 2024, source: str = "Apple_2024.pdf"):
    """Build a sub-answer dict with one chunk tagged for company/year."""
    return {
        "question": f"Q about {company} {year}",
        "answer": answer,
        "chunks": [{
            "text": "irrelevant", "source": source, "page": 5,
            "company": company, "year": year, "fiscal_period": str(year),
        }],
    }


# --------------------------------------------------------------------------- #
# Pair eligibility
# --------------------------------------------------------------------------- #

def test_pair_eligible_different_company():
    s1 = _sub("$100B revenue", company="Apple", year=2024)
    s2 = _sub("$200B revenue", company="Amazon", year=2024)
    assert ConflictDetectorAgent._pair_eligible(s1, s2)
    print("PASS test_pair_eligible_different_company")


def test_pair_eligible_different_period():
    s1 = _sub("$100B", company="Apple", year=2023, source="Apple_2023.pdf")
    s2 = _sub("$120B", company="Apple", year=2024, source="Apple_2024.pdf")
    assert ConflictDetectorAgent._pair_eligible(s1, s2)
    print("PASS test_pair_eligible_different_period")


def test_pair_ineligible_same_filing():
    s1 = _sub("$100B revenue", company="Apple", year=2024, source="Apple_2024.pdf")
    s2 = _sub("$100B net sales", company="Apple", year=2024, source="Apple_2024.pdf")
    assert not ConflictDetectorAgent._pair_eligible(s1, s2)
    print("PASS test_pair_ineligible_same_filing")


def test_pair_eligible_unknown_company_diff_source():
    s1 = _sub("xx", company="Unknown", year=0, source="doc_a.pdf")
    s2 = _sub("yy", company="Unknown", year=0, source="doc_b.pdf")
    assert ConflictDetectorAgent._pair_eligible(s1, s2)
    print("PASS test_pair_eligible_unknown_company_diff_source")


# --------------------------------------------------------------------------- #
# Response parsing
# --------------------------------------------------------------------------- #

def test_parse_conflict_yes_full():
    text = (
        "CONFLICT: YES\n"
        "TYPE: NUMERIC\n"
        "SEVERITY: HIGH\n"
        "SHARED_FACT: FY2024 total revenue\n"
        "CLAIM_1: Apple reported $383B\n"
        "CLAIM_2: Apple reported $400B\n"
        "EXPLANATION: figures disagree by $17B for the same period"
    )
    out = ConflictDetectorAgent._parse_response(text)
    assert out["conflict"] is True
    assert out["type"] == "NUMERIC"
    assert out["severity"] == "HIGH"
    assert "FY2024" in out["shared_fact"]
    assert "$383B" in out["claim_1"]
    assert "$400B" in out["claim_2"]
    print("PASS test_parse_conflict_yes_full")


def test_parse_conflict_no():
    text = "CONFLICT: NO\nREASON: different fiscal periods, no shared fact."
    out = ConflictDetectorAgent._parse_response(text)
    assert out["conflict"] is False
    assert "different fiscal" in out["reason"]
    print("PASS test_parse_conflict_no")


def test_parse_conflict_unparseable_defaults_to_no():
    """Empty/garbled output should be treated as NO CONFLICT — conservative."""
    out = ConflictDetectorAgent._parse_response("")
    assert out["conflict"] is False
    print("PASS test_parse_conflict_unparseable_defaults_to_no")


def test_parse_conflict_invalid_type_defaults_to_numeric():
    text = "CONFLICT: YES\nTYPE: WEIRD\nSEVERITY: LOL\nSHARED_FACT: x\nCLAIM_1: a\nCLAIM_2: b\nEXPLANATION: c"
    out = ConflictDetectorAgent._parse_response(text)
    assert out["type"] == "NUMERIC"      # fallback
    assert out["severity"] == "MEDIUM"   # fallback
    print("PASS test_parse_conflict_invalid_type_defaults_to_numeric")


# --------------------------------------------------------------------------- #
# End-to-end detect()
# --------------------------------------------------------------------------- #

def test_detect_returns_conflicts_for_cross_company_pair():
    llm = FakeLLMClient({
        "Apple": (
            "CONFLICT: YES\n"
            "TYPE: NUMERIC\n"
            "SEVERITY: HIGH\n"
            "SHARED_FACT: FY2024 revenue\n"
            "CLAIM_1: Apple reported $383B\n"
            "CLAIM_2: Amazon reported $574B\n"
            "EXPLANATION: numbers describe different companies"
        )
    })
    agent = ConflictDetectorAgent(llm)
    sub_answers = [
        _sub("Apple revenue was $383B in FY2024", company="Apple", year=2024),
        _sub("Amazon revenue was $574B in FY2024", company="Amazon", year=2024),
    ]
    report = agent.detect(sub_answers)
    assert report["pairs_checked"] == 1
    assert report["stats"]["n_conflicts"] == 1
    assert report["stats"]["by_severity"]["HIGH"] == 1
    conflict = report["conflicts"][0]
    assert conflict["sub_query_indices"] == [1, 2]
    assert conflict["source_1"]["company"] == "Apple"
    assert conflict["source_2"]["company"] == "Amazon"
    print("PASS test_detect_returns_conflicts_for_cross_company_pair")


def test_detect_skips_same_filing_pairs():
    """Two sub-answers from the same Apple FY2024 filing should be skipped."""
    llm = FakeLLMClient({"any": "CONFLICT: YES\nTYPE: NUMERIC\nSEVERITY: HIGH"})
    agent = ConflictDetectorAgent(llm)
    sub_answers = [
        _sub("Revenue was $383B", company="Apple", year=2024, source="Apple_2024.pdf"),
        _sub("Net sales were $383B", company="Apple", year=2024, source="Apple_2024.pdf"),
    ]
    report = agent.detect(sub_answers)
    assert report["pairs_checked"] == 0
    assert report["pairs_skipped"] == 1
    assert report["stats"]["n_conflicts"] == 0
    # No LLM call was made for the skipped pair.
    assert len(llm.calls) == 0
    print("PASS test_detect_skips_same_filing_pairs")


def test_detect_empty_sub_answers_returns_empty():
    agent = ConflictDetectorAgent(FakeLLMClient({}))
    report = agent.detect([])
    assert report["conflicts"] == []
    assert report["stats"]["n_conflicts"] == 0
    print("PASS test_detect_empty_sub_answers_returns_empty")


def test_detect_handles_llm_error_gracefully():
    class CrashingLLM:
        def generate(self, *_, **__):
            raise RuntimeError("API quota exhausted")

    agent = ConflictDetectorAgent(CrashingLLM())
    sub_answers = [
        _sub("a", company="Apple", year=2024),
        _sub("b", company="Amazon", year=2024),
    ]
    report = agent.detect(sub_answers)
    # Error path returns conflict=False — feature degrades gracefully.
    assert report["stats"]["n_conflicts"] == 0
    print("PASS test_detect_handles_llm_error_gracefully")


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #

def main():
    tests = [
        test_pair_eligible_different_company,
        test_pair_eligible_different_period,
        test_pair_ineligible_same_filing,
        test_pair_eligible_unknown_company_diff_source,
        test_parse_conflict_yes_full,
        test_parse_conflict_no,
        test_parse_conflict_unparseable_defaults_to_no,
        test_parse_conflict_invalid_type_defaults_to_numeric,
        test_detect_returns_conflicts_for_cross_company_pair,
        test_detect_skips_same_filing_pairs,
        test_detect_empty_sub_answers_returns_empty,
        test_detect_handles_llm_error_gracefully,
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
