"""Tests for VerifierAgent (Chain-of-Verification).

These tests use a fake LLM client and fake retriever — they run WITHOUT any
API key or network access. They verify the agent's parsing, orchestration,
and revision logic in isolation.

Run:
    python -m src.test_verifier
"""

from typing import Dict, List, Optional

from src.agents.verifier import VerifierAgent


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #

class FakeLLMClient:
    """Returns a canned response based on a content-substring -> response map.

    When multiple keys match, the LONGEST (most-specific) key wins. This is
    important because verifier prompts share substrings — e.g. the check prompt
    contains both "CLAIM:" and "EVIDENCE:", so we want the "EVIDENCE:" branch
    to take precedence.
    """

    def __init__(self, responses: Dict[str, str], default: str = ""):
        self.responses = responses
        self.default = default
        self.call_log: List[str] = []

    def generate(self, prompt: str, system: Optional[str] = None,
                 temperature: float = 0.0, max_tokens: int = 200) -> str:
        self.call_log.append(prompt[:80])
        # Longest-match wins so more specific keys override broader ones.
        matches = [(key, value) for key, value in self.responses.items() if key in prompt]
        if not matches:
            return self.default
        key, value = max(matches, key=lambda kv: len(kv[0]))
        return value


class FakeRetriever:
    """Returns canned chunks based on a substring match on the query."""

    def __init__(self, chunks_by_query: Dict[str, List[Dict]], default: Optional[List[Dict]] = None):
        self.chunks_by_query = chunks_by_query
        self.default = default or []

    def retrieve(self, query: str, k: int = 3) -> List[Dict]:
        for key, chunks in self.chunks_by_query.items():
            if key.lower() in query.lower():
                return chunks[:k]
        return self.default[:k]


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #

def _assert(condition: bool, message: str) -> None:
    status = "[PASS]" if condition else "[FAIL]"
    print(f"  {status} {message}")
    if not condition:
        raise AssertionError(message)


def test_extract_claims_basic():
    print("\n=== test_extract_claims_basic ===")
    fake = FakeLLMClient(responses={
        "Apple": (
            "- Apple's total revenue in fiscal 2025 was $416.161 billion.\n"
            "- Apple's services revenue was $109 billion.\n"
            "- Tim Cook is the CEO of Apple."
        ),
    })
    v = VerifierAgent(llm_client=fake)
    claims = v.extract_claims(
        question="What were Apple's results?",
        answer="In 2025 Apple reported $416B in revenue and $109B in services. Tim Cook is the CEO.",
    )
    _assert(len(claims) == 3, f"got 3 claims (got {len(claims)})")
    _assert("Apple" in claims[0], "first claim mentions Apple")
    _assert(all(not c.startswith("-") for c in claims), "bullet prefixes stripped")


def test_extract_claims_no_claims_marker():
    print("\n=== test_extract_claims_no_claims_marker ===")
    fake = FakeLLMClient(responses={"refused": "NO_CLAIMS"})
    v = VerifierAgent(llm_client=fake)
    claims = v.extract_claims(
        question="Stock price today?",
        answer="I refused — the docs don't cover real-time data.",
    )
    _assert(claims == [], "empty list when LLM returns NO_CLAIMS")


def test_extract_claims_dedupe_and_cap():
    print("\n=== test_extract_claims_dedupe_and_cap ===")
    # 10 lines including duplicates — should dedupe and cap at 8.
    bullets = "\n".join([f"- Claim number {i}" for i in [1, 2, 2, 3, 4, 5, 6, 7, 8, 9, 10]])
    fake = FakeLLMClient(responses={"x": bullets}, default=bullets)
    v = VerifierAgent(llm_client=fake)
    claims = v.extract_claims(question="x", answer="x")
    _assert(len(claims) == 8, f"capped at 8 (got {len(claims)})")
    _assert(len(set(claims)) == len(claims), "duplicates removed")


def test_generate_question_appends_qmark():
    print("\n=== test_generate_question_appends_qmark ===")
    fake = FakeLLMClient(responses={"revenue": "What was Apple's total revenue in fiscal 2025"})
    v = VerifierAgent(llm_client=fake)
    q = v.generate_question(claim="Apple's total revenue in fiscal 2025 was $416.161 billion")
    _assert(q.endswith("?"), f"question ends with '?' (got: {q!r})")
    _assert("Apple" in q and "revenue" in q, "preserves entities/keywords")


def test_check_parses_supported():
    print("\n=== test_check_parses_supported ===")
    fake = FakeLLMClient(responses={"Apple": "VERDICT: SUPPORTED\nREASON: Evidence 1 states the same figure."})
    v = VerifierAgent(llm_client=fake)
    result = v.check(
        claim="Apple revenue was $416.161B in fiscal 2025",
        evidence_chunks=[{"text": "Total net sales were $416.161B", "source": "Apple_10K.pdf", "page": 32}],
    )
    _assert(result["verdict"] == "SUPPORTED", "verdict parsed as SUPPORTED")
    _assert("Evidence 1" in result["reason"], "reason captured")


def test_check_parses_contradicted_and_insufficient():
    print("\n=== test_check_parses_contradicted_and_insufficient ===")
    # Keys must be unique to the claim text (the prompt template itself mentions
    # words like "future" / "evidence" so we route on phrases that only appear
    # in our specific claims).
    fake = FakeLLMClient(responses={
        "stock price is $234": "VERDICT: CONTRADICTED\nREASON: 10-K does not state any stock price; this is fabricated.",
        "smartwatch in 2027": "VERDICT: INSUFFICIENT\nREASON: Filing does not discuss 2027 product roadmap.",
    })
    v = VerifierAgent(llm_client=fake)
    r1 = v.check(claim="Apple stock price is $234", evidence_chunks=[])
    r2 = v.check(claim="Apple will launch a smartwatch in 2027", evidence_chunks=[])
    _assert(r1["verdict"] == "CONTRADICTED", "CONTRADICTED parsed")
    _assert(r2["verdict"] == "INSUFFICIENT", "INSUFFICIENT parsed")


def test_check_handles_empty_claim():
    print("\n=== test_check_handles_empty_claim ===")
    v = VerifierAgent(llm_client=FakeLLMClient({}))
    result = v.check(claim="", evidence_chunks=[])
    _assert(result["verdict"] == "INSUFFICIENT", "empty claim -> INSUFFICIENT")


def test_revise_drops_contradicted_sentences():
    print("\n=== test_revise_drops_contradicted_sentences ===")
    answer = (
        "Apple's revenue in 2025 was $416 billion. "
        "Apple stock price is $234. "
        "Tim Cook is the CEO."
    )
    verdicts = [
        {"claim": "Apple's revenue in 2025 was $416 billion", "verdict": "SUPPORTED", "reason": "ok"},
        {"claim": "Apple stock price is $234", "verdict": "CONTRADICTED", "reason": "fake"},
        {"claim": "Tim Cook is the CEO", "verdict": "SUPPORTED", "reason": "ok"},
    ]
    revised = VerifierAgent.revise(answer, verdicts)
    _assert("$234" not in revised, "contradicted sentence dropped")
    _assert("$416 billion" in revised, "supported sentence kept")
    _assert("Tim Cook" in revised, "other supported sentence kept")


def test_revise_appends_hedge_for_insufficient():
    print("\n=== test_revise_appends_hedge_for_insufficient ===")
    answer = "Apple revenue was $416B. Apple may launch new products in 2027."
    verdicts = [
        {"claim": "Apple revenue was $416B", "verdict": "SUPPORTED", "reason": "ok"},
        {"claim": "Apple may launch new products in 2027", "verdict": "INSUFFICIENT", "reason": "future"},
    ]
    revised = VerifierAgent.revise(answer, verdicts)
    _assert("could not be verified" in revised, "hedge note appended")
    _assert("$416B" in revised, "supported claim retained")


def test_revise_with_no_issues_is_no_op():
    print("\n=== test_revise_with_no_issues_is_no_op ===")
    answer = "Apple revenue was $416B."
    verdicts = [{"claim": "Apple revenue was $416B", "verdict": "SUPPORTED", "reason": "ok"}]
    revised = VerifierAgent.revise(answer, verdicts)
    _assert(revised == answer, "no changes when all SUPPORTED")


def test_end_to_end_verify_supported_path():
    print("\n=== test_end_to_end_verify_supported_path ===")
    # Route on each prompt's unique trailing label so the right canned response wins.
    fake_llm = FakeLLMClient(
        responses={
            # Stage 1: claim extraction (prompt ends with "CLAIMS:")
            "CLAIMS:": "- Apple revenue in 2025 was $416 billion.",
            # Stage 2: question generation (prompt ends with "VERIFICATION QUESTION:")
            "VERIFICATION QUESTION:": "What was Apple's revenue in fiscal 2025?",
            # Stage 3: check (prompt ends with "VERDICT AND REASON:")
            "VERDICT AND REASON:": "VERDICT: SUPPORTED\nREASON: The 10-K shows $416B total net sales.",
        },
    )
    fake_retr = FakeRetriever(
        chunks_by_query={"Apple": [{"text": "Total net sales: $416.161B", "source": "Apple_10K.pdf", "page": 32}]},
    )
    v = VerifierAgent(llm_client=fake_llm)
    out = v.verify(
        question="What was Apple's 2025 revenue?",
        answer="Apple revenue in 2025 was $416 billion.",
        retriever=fake_retr,
        k=3,
    )
    _assert(out["stats"]["n_claims"] == 1, "1 claim extracted")
    _assert(out["stats"]["supported"] == 1, "1 supported")
    _assert(out["stats"]["contradicted"] == 0, "0 contradicted")
    _assert(out["revised_answer"] == "Apple revenue in 2025 was $416 billion.", "answer unchanged when supported")


def test_end_to_end_verify_contradicted_path():
    print("\n=== test_end_to_end_verify_contradicted_path ===")
    # Naive's fake $234 stock price hallucination.
    fake_llm = FakeLLMClient(
        responses={
            "CLAIMS:": "- Apple stock price is $234.",
            "VERIFICATION QUESTION:": "What is Apple's stock price?",
            "VERDICT AND REASON:": "VERDICT: CONTRADICTED\nREASON: 10-K does not state any stock price.",
        },
    )
    fake_retr = FakeRetriever(chunks_by_query={}, default=[])  # no useful evidence
    v = VerifierAgent(llm_client=fake_llm)
    out = v.verify(
        question="What is Apple's current stock price?",
        answer="The current stock price is $234.",
        retriever=fake_retr,
    )
    _assert(out["stats"]["contradicted"] == 1, "1 contradicted")
    _assert("$234" not in out["revised_answer"] or "could not be verified" in out["revised_answer"],
            "contradicted content removed or flagged in revision")


def test_end_to_end_verify_no_claims_short_circuits():
    print("\n=== test_end_to_end_verify_no_claims_short_circuits ===")
    fake_llm = FakeLLMClient(responses={"ANSWER:": "NO_CLAIMS"})
    fake_retr = FakeRetriever(chunks_by_query={})
    v = VerifierAgent(llm_client=fake_llm)
    out = v.verify(question="anything", answer="I cannot answer.", retriever=fake_retr)
    _assert(out["stats"]["n_claims"] == 0, "0 claims when LLM says NO_CLAIMS")
    _assert(out["revised_answer"] == "I cannot answer.", "answer unchanged")
    _assert(len(fake_llm.call_log) == 1, "only one LLM call (no question gen / check)")


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #

def run_all() -> None:
    tests = [
        test_extract_claims_basic,
        test_extract_claims_no_claims_marker,
        test_extract_claims_dedupe_and_cap,
        test_generate_question_appends_qmark,
        test_check_parses_supported,
        test_check_parses_contradicted_and_insufficient,
        test_check_handles_empty_claim,
        test_revise_drops_contradicted_sentences,
        test_revise_appends_hedge_for_insufficient,
        test_revise_with_no_issues_is_no_op,
        test_end_to_end_verify_supported_path,
        test_end_to_end_verify_contradicted_path,
        test_end_to_end_verify_no_claims_short_circuits,
    ]
    print("=" * 70)
    print(f"Running {len(tests)} VerifierAgent tests (no API calls, no network)")
    print("=" * 70)
    failed = 0
    for fn in tests:
        try:
            fn()
        except AssertionError as e:
            failed += 1
            print(f"  [FAILED] {fn.__name__}: {e}")
        except Exception as e:
            failed += 1
            print(f"  [ERROR]  {fn.__name__}: {type(e).__name__}: {e}")
    print("\n" + "=" * 70)
    if failed == 0:
        print(f"All {len(tests)} tests passed.")
    else:
        print(f"{failed} of {len(tests)} tests FAILED.")
        raise SystemExit(1)


if __name__ == "__main__":
    run_all()
