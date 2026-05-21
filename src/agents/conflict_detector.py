"""Conflict Detection Agent — cross-document fact contradiction surfacing.

A novel addition to the multi-agent pipeline. Sits AFTER per-sub-query
retrieval and BEFORE synthesis. For every pair of sub-answers that come from
different companies or different fiscal periods, asks the LLM whether they
contain a direct factual contradiction on a shared fact (revenue, margin,
headcount, guidance, etc.).

Why this matters for finance:
    Analysts routinely compare statements across filings (10-K vs 10-Q vs
    earnings call) and across competitors. Silent disagreements between
    documents are the highest-value signal in equity research — they imply
    either an error in one filing or a material change worth flagging.

Design choices:
    * LLM-based — heuristic numeric matching is too brittle on free-form
      financial language ("net sales" vs "revenue" vs "top line").
    * Pairwise — N sub-answers => N*(N-1)/2 pairs, capped at MAX_PAIRS.
    * Filtered pairs only — same-company-same-period pairs are skipped
      because differences there are usually rounding or scope, not conflict.
    * Conservative — the prompt instructs the model to favor CONFLICT: NO
      when uncertain, since false positives destroy user trust.
"""

import re
from itertools import combinations
from typing import Dict, List, Optional

from src.llm_client import LLMClient, load_prompt, get_llm_client


MAX_PAIRS = 10  # bound the LLM calls per query (covers 5 sub-answers fully)


class ConflictDetectorAgent:
    """
    Pairwise cross-document conflict detector.

    Public methods:
        detect(sub_answers)           -> Dict (full conflict report)
        detect_pair(sa_1, sa_2)       -> Dict (single pair verdict)
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or get_llm_client()
        try:
            self.prompt_template = load_prompt("conflict_detect")
        except FileNotFoundError:
            self.prompt_template = self._default_prompt()

    def detect(self, sub_answers: List[Dict]) -> Dict:
        """
        Detect conflicts across all eligible sub-answer pairs.

        Args:
            sub_answers: list of dicts as produced by multi_agent.py, each with
                keys: question, answer, chunks.

        Returns:
            {
                "conflicts":  [conflict_dict, ...],
                "pairs_checked": int,
                "pairs_skipped": int,
                "stats": {n_conflicts, by_severity: {HIGH, MEDIUM, LOW}},
            }
        """
        if not sub_answers or len(sub_answers) < 2:
            return self._empty_report()

        pairs = list(combinations(range(len(sub_answers)), 2))
        eligible: List[tuple] = []
        skipped = 0
        for i, j in pairs:
            if self._pair_eligible(sub_answers[i], sub_answers[j]):
                eligible.append((i, j))
            else:
                skipped += 1

        eligible = eligible[:MAX_PAIRS]

        conflicts: List[Dict] = []
        for i, j in eligible:
            verdict = self.detect_pair(sub_answers[i], sub_answers[j])
            if verdict.get("conflict"):
                conflicts.append({
                    **verdict,
                    "sub_query_indices": [i + 1, j + 1],
                })

        severity_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for c in conflicts:
            sev = c.get("severity", "MEDIUM")
            if sev in severity_counts:
                severity_counts[sev] += 1

        return {
            "conflicts": conflicts,
            "pairs_checked": len(eligible),
            "pairs_skipped": skipped,
            "stats": {
                "n_conflicts": len(conflicts),
                "by_severity": severity_counts,
            },
        }

    def detect_pair(self, sa_1: Dict, sa_2: Dict) -> Dict:
        """Run the LLM conflict check on a single pair."""
        ctx_1 = self._extract_context(sa_1)
        ctx_2 = self._extract_context(sa_2)

        prompt = self.prompt_template
        replacements = {
            "{source_1}": ctx_1["source"],
            "{company_1}": ctx_1["company"],
            "{period_1}": ctx_1["period"],
            "{question_1}": sa_1.get("question", ""),
            "{answer_1}": sa_1.get("answer", ""),
            "{source_2}": ctx_2["source"],
            "{company_2}": ctx_2["company"],
            "{period_2}": ctx_2["period"],
            "{question_2}": sa_2.get("question", ""),
            "{answer_2}": sa_2.get("answer", ""),
        }
        for k, v in replacements.items():
            prompt = prompt.replace(k, v)

        try:
            response = self.llm_client.generate(
                prompt=prompt,
                system=(
                    "Compare two grounded sub-answers and decide whether they "
                    "contain a direct factual conflict on a shared fact. Be strict."
                ),
                temperature=0.0,
                max_tokens=350,
            )
        except Exception as e:
            return {
                "conflict": False,
                "error": f"LLM error: {e}",
                "source_1": ctx_1,
                "source_2": ctx_2,
            }

        parsed = self._parse_response(response)
        parsed["source_1"] = ctx_1
        parsed["source_2"] = ctx_2
        return parsed

    @staticmethod
    def _pair_eligible(sa_1: Dict, sa_2: Dict) -> bool:
        """
        A pair is worth checking when the underlying documents differ in
        company OR fiscal period. Two chunks from the same filing won't
        contradict each other in the conflict sense — we leave that to the
        Verifier's intra-doc claim check.
        """
        c1 = ConflictDetectorAgent._extract_context(sa_1)
        c2 = ConflictDetectorAgent._extract_context(sa_2)
        if c1["company"] == "Unknown" or c2["company"] == "Unknown":
            # Without metadata we can't tell — fall back to checking
            # whenever the source filenames differ.
            return c1["source"] != c2["source"]
        if c1["company"] != c2["company"]:
            return True
        if c1["period"] != c2["period"] and c1["period"] != "unknown" and c2["period"] != "unknown":
            return True
        return False

    @staticmethod
    def _extract_context(sub_answer: Dict) -> Dict:
        """Pull company / period / source from the top-ranked chunk of a sub-answer."""
        chunks = sub_answer.get("chunks") or []
        top = chunks[0] if chunks else {}
        return {
            "source": str(top.get("source", "unknown")),
            "company": str(top.get("company", "Unknown")),
            "period": str(top.get("fiscal_period", "unknown")),
            "page": top.get("page", None),
        }

    @staticmethod
    def _parse_response(text: str) -> Dict:
        """Parse the structured LLM response into a dict."""
        if not text:
            return {"conflict": False, "reason": "Empty model response."}

        # Decision line
        conflict_match = re.search(r"CONFLICT:\s*(YES|NO)", text, re.IGNORECASE)
        if not conflict_match or conflict_match.group(1).upper() == "NO":
            reason_match = re.search(r"REASON:\s*(.+?)(?:\n|$)", text, re.IGNORECASE)
            return {
                "conflict": False,
                "reason": (reason_match.group(1).strip() if reason_match else "No conflict identified."),
            }

        def grab(field: str) -> str:
            m = re.search(rf"{field}:\s*(.+?)(?:\n[A-Z_]+:|\Z)", text, re.IGNORECASE | re.DOTALL)
            return m.group(1).strip() if m else ""

        type_raw = grab("TYPE").upper() or "NUMERIC"
        if type_raw not in {"NUMERIC", "QUALITATIVE", "TEMPORAL"}:
            type_raw = "NUMERIC"

        sev_raw = grab("SEVERITY").upper() or "MEDIUM"
        if sev_raw not in {"HIGH", "MEDIUM", "LOW"}:
            sev_raw = "MEDIUM"

        return {
            "conflict": True,
            "type": type_raw,
            "severity": sev_raw,
            "shared_fact": grab("SHARED_FACT"),
            "claim_1": grab("CLAIM_1"),
            "claim_2": grab("CLAIM_2"),
            "explanation": grab("EXPLANATION"),
        }

    @staticmethod
    def _empty_report() -> Dict:
        return {
            "conflicts": [],
            "pairs_checked": 0,
            "pairs_skipped": 0,
            "stats": {"n_conflicts": 0, "by_severity": {"HIGH": 0, "MEDIUM": 0, "LOW": 0}},
        }

    @staticmethod
    def _default_prompt() -> str:
        return (
            "Decide whether these two sub-answers conflict on a shared fact.\n\n"
            "SUB-ANSWER 1 ({company_1} {period_1}, {source_1}):\n"
            "Q: {question_1}\nA: {answer_1}\n\n"
            "SUB-ANSWER 2 ({company_2} {period_2}, {source_2}):\n"
            "Q: {question_2}\nA: {answer_2}\n\n"
            "Output CONFLICT: YES|NO and follow the schema."
        )
