"""Verifier Agent: Chain-of-Verification (CoVe) for hallucination reduction.

Implements the technique from:
    Dhuliawala et al., 2023 — "Chain-of-Verification Reduces Hallucination in LLMs"
    https://arxiv.org/abs/2309.11495

Flow:
    1. Extract atomic claims from a synthesized answer.
    2. Generate a focused verification question for each claim.
    3. Re-retrieve evidence for each verification question.
    4. Check each claim against its evidence -> SUPPORTED / CONTRADICTED / INSUFFICIENT.
    5. Revise the original answer by dropping or softening unsupported claims.

The Verifier sits between the Synthesizer and the Validator in the multi-agent
pipeline. The Validator's job (reasoning-chain soundness) is complementary: the
Verifier checks claim-level grounding against fresh retrieval, while the
Validator checks overall coherence.
"""

import re
from typing import Dict, List, Optional, Protocol

from src.llm_client import LLMClient, load_prompt, get_llm_client


class _RetrieverLike(Protocol):
    """Structural type for any retriever exposing `.retrieve(query, k=...)`."""

    def retrieve(self, query: str, k: int = 3) -> List[Dict]: ...


class VerifierAgent:
    """
    Chain-of-Verification (CoVe) agent.

    Public methods:
        extract_claims(question, answer)            -> List[str]
        generate_question(claim)                    -> str
        check(claim, evidence_chunks)               -> Dict (verdict, reason)
        verify(question, answer, retriever, k=3)    -> Dict (full CoVe trace)
        revise(answer, verdicts)                    -> str (claim-aware rewrite)
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or get_llm_client()
        self.claim_prompt = self._load("verifier_claim_extract", self._default_claim_prompt())
        self.question_prompt = self._load("verifier_question_gen", self._default_question_prompt())
        self.check_prompt = self._load("verifier_check", self._default_check_prompt())

    @staticmethod
    def _load(name: str, fallback: str) -> str:
        try:
            return load_prompt(name)
        except FileNotFoundError:
            return fallback

    # ------------------------------------------------------------------ #
    # Step 1 — claim extraction
    # ------------------------------------------------------------------ #
    def extract_claims(self, question: str, answer: str) -> List[str]:
        """Pull atomic factual claims from `answer`. Returns [] if no claims."""
        if not answer or not answer.strip():
            return []

        prompt = self.claim_prompt.replace("{question}", question).replace("{answer}", answer)
        try:
            response = self.llm_client.generate(
                prompt=prompt,
                system="Extract atomic factual claims. One per line.",
                temperature=0.0,
                max_tokens=400,
            )
        except Exception:
            return []

        return self._parse_claims(response)

    @staticmethod
    def _parse_claims(text: str) -> List[str]:
        """Parse the bullet-list response from the claim-extraction prompt."""
        if not text:
            return []
        cleaned = text.strip()
        if cleaned.upper().startswith("NO_CLAIMS"):
            return []

        claims: List[str] = []
        for line in cleaned.splitlines():
            line = line.strip()
            if not line:
                continue
            # Strip common bullet/number prefixes
            line = re.sub(r"^\s*([-*•·]|\d+[.)])\s+", "", line)
            if line and line.upper() != "NO_CLAIMS":
                claims.append(line)
        # Deduplicate while preserving order; cap at 8 to keep cost bounded.
        seen = set()
        unique: List[str] = []
        for c in claims:
            key = c.lower()
            if key not in seen:
                seen.add(key)
                unique.append(c)
        return unique[:8]

    # ------------------------------------------------------------------ #
    # Step 2 — verification-question generation
    # ------------------------------------------------------------------ #
    def generate_question(self, claim: str) -> str:
        """Generate a single neutral verification question for a claim."""
        if not claim:
            return ""
        prompt = self.question_prompt.replace("{claim}", claim)
        try:
            response = self.llm_client.generate(
                prompt=prompt,
                system="Write one short neutral verification question.",
                temperature=0.0,
                max_tokens=80,
            )
        except Exception:
            return ""
        # Take the first non-empty line as the question.
        for line in (response or "").splitlines():
            line = line.strip().strip('"').strip("'")
            if line:
                # Ensure it ends with '?'
                if not line.endswith("?"):
                    line = line + "?"
                return line
        return ""

    # ------------------------------------------------------------------ #
    # Step 3+4 — check a single claim against evidence
    # ------------------------------------------------------------------ #
    def check(self, claim: str, evidence_chunks: List[Dict]) -> Dict:
        """Return {verdict, reason} for a single claim against retrieved evidence."""
        if not claim:
            return {"verdict": "INSUFFICIENT", "reason": "Empty claim."}

        evidence_text = self._format_evidence(evidence_chunks)
        prompt = self.check_prompt.replace("{claim}", claim).replace("{evidence}", evidence_text)

        try:
            response = self.llm_client.generate(
                prompt=prompt,
                system="Fact-check the claim. Output VERDICT and REASON only.",
                temperature=0.0,
                max_tokens=150,
            )
        except Exception as e:
            return {"verdict": "INSUFFICIENT", "reason": f"LLM error: {e}"}

        return self._parse_verdict(response)

    @staticmethod
    def _format_evidence(chunks: List[Dict]) -> str:
        """Format retrieved chunks as a numbered evidence list."""
        if not chunks:
            return "(no evidence retrieved)"
        parts: List[str] = []
        for i, c in enumerate(chunks[:5], 1):
            text = (c.get("text") or "").strip()
            if len(text) > 350:
                text = text[:350] + "..."
            src = c.get("source", "?")
            page = c.get("page", "?")
            parts.append(f"[Evidence {i}] ({src}, p.{page}): {text}")
        return "\n\n".join(parts)

    @staticmethod
    def _parse_verdict(text: str) -> Dict:
        """Extract VERDICT + REASON from the check LLM response."""
        verdict = "INSUFFICIENT"
        reason = ""

        match = re.search(r"VERDICT:\s*(SUPPORTED|CONTRADICTED|INSUFFICIENT)", text, re.IGNORECASE)
        if match:
            verdict = match.group(1).upper()

        match = re.search(r"REASON:\s*(.+?)(?:\n\s*$|\Z)", text, re.IGNORECASE | re.DOTALL)
        if match:
            reason = match.group(1).strip().splitlines()[0].strip()

        if not reason:
            # Best-effort fallback: anything after the verdict line.
            tail = re.sub(r"(?i)^.*verdict[^\n]*\n?", "", text).strip()
            reason = tail.splitlines()[0].strip() if tail else "No reason given."

        return {"verdict": verdict, "reason": reason[:300]}

    # ------------------------------------------------------------------ #
    # Step 5 — answer revision based on verdicts
    # ------------------------------------------------------------------ #
    @staticmethod
    def revise(answer: str, verdicts: List[Dict]) -> str:
        """
        Conservatively rewrite the answer: drop sentences whose claims were
        CONTRADICTED, append a hedge for INSUFFICIENT claims. We deliberately
        do this without an LLM call so revision is deterministic and cheap.

        verdicts: list of dicts with keys {claim, verdict, reason}
        """
        if not answer or not verdicts:
            return answer

        contradicted = [v for v in verdicts if v.get("verdict") == "CONTRADICTED"]
        insufficient = [v for v in verdicts if v.get("verdict") == "INSUFFICIENT"]

        revised = answer

        # Drop sentences that contain a contradicted claim (best-effort substring match).
        if contradicted:
            sentences = re.split(r"(?<=[.!?])\s+", revised)
            kept: List[str] = []
            for sent in sentences:
                sent_lower = sent.lower()
                if any(VerifierAgent._claim_overlaps(v["claim"], sent_lower) for v in contradicted):
                    continue  # drop sentence
                kept.append(sent)
            revised = " ".join(kept).strip()
            if not revised:
                revised = "The verification step found contradictions in the original answer; no supported claims remain."

        # Append a hedge for insufficient claims.
        if insufficient:
            unverified = "; ".join(
                [v["claim"] for v in insufficient if v.get("claim")][:3]
            )
            if unverified:
                hedge = (
                    "\n\n*Note: the following parts of this answer could not be verified "
                    "against retrieved sources and should be treated cautiously: "
                    f"{unverified}.*"
                )
                revised = revised.rstrip() + hedge

        return revised

    @staticmethod
    def _claim_overlaps(claim: str, sentence_lower: str) -> bool:
        """Heuristic: claim overlaps sentence if the claim's distinctive token sequence appears."""
        claim_lower = claim.lower()
        # If the full claim text is in the sentence, trivially overlaps.
        if len(claim_lower) > 20 and claim_lower in sentence_lower:
            return True
        # Otherwise, require that >=3 multi-char tokens from the claim appear in the sentence.
        tokens = [t for t in re.findall(r"[a-z0-9]{3,}", claim_lower) if t not in _STOP]
        if not tokens:
            return False
        hits = sum(1 for t in tokens if t in sentence_lower)
        return hits >= max(3, int(0.6 * len(tokens)))

    # ------------------------------------------------------------------ #
    # End-to-end CoVe orchestration
    # ------------------------------------------------------------------ #
    def verify(
        self,
        question: str,
        answer: str,
        retriever: Optional[_RetrieverLike] = None,
        k: int = 3,
    ) -> Dict:
        """
        Full CoVe pass over a synthesized answer.

        Returns:
            {
                "claims":        [str, ...],
                "verifications": [{claim, question, verdict, reason}, ...],
                "stats":         {n_claims, supported, contradicted, insufficient},
                "revised_answer": str,   # answer with unsupported parts dropped/hedged
            }
        """
        claims = self.extract_claims(question, answer)
        if not claims:
            return {
                "claims": [],
                "verifications": [],
                "stats": {"n_claims": 0, "supported": 0, "contradicted": 0, "insufficient": 0},
                "revised_answer": answer,
            }

        verifications: List[Dict] = []
        for claim in claims:
            v_question = self.generate_question(claim)
            evidence: List[Dict] = []
            if retriever is not None and v_question:
                try:
                    evidence = retriever.retrieve(v_question, k=k) or []
                except Exception:
                    evidence = []
            verdict = self.check(claim, evidence)
            verifications.append({
                "claim": claim,
                "question": v_question,
                "verdict": verdict["verdict"],
                "reason": verdict["reason"],
                "evidence_count": len(evidence),
            })

        stats = {
            "n_claims": len(claims),
            "supported": sum(1 for v in verifications if v["verdict"] == "SUPPORTED"),
            "contradicted": sum(1 for v in verifications if v["verdict"] == "CONTRADICTED"),
            "insufficient": sum(1 for v in verifications if v["verdict"] == "INSUFFICIENT"),
        }
        revised_answer = self.revise(answer, verifications)

        return {
            "claims": claims,
            "verifications": verifications,
            "stats": stats,
            "revised_answer": revised_answer,
        }

    # ------------------------------------------------------------------ #
    # Default in-class prompts (fallback when prompts/*.txt is missing)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _default_claim_prompt() -> str:
        return (
            "List every atomic factual claim made in the answer, one per line, "
            'prefixed with "- ". If the answer makes no factual claims, output '
            "NO_CLAIMS.\n\nQUESTION:\n{question}\n\nANSWER:\n{answer}\n\nCLAIMS:\n"
        )

    @staticmethod
    def _default_question_prompt() -> str:
        return (
            "Write one short neutral verification question for this claim. "
            "Return only the question.\n\nCLAIM:\n{claim}\n\nQUESTION:"
        )

    @staticmethod
    def _default_check_prompt() -> str:
        return (
            "Decide if the evidence supports the claim. Output:\n"
            "VERDICT: SUPPORTED|CONTRADICTED|INSUFFICIENT\n"
            "REASON: one sentence\n\n"
            "CLAIM:\n{claim}\n\nEVIDENCE:\n{evidence}\n"
        )


_STOP = {
    "the", "and", "for", "from", "with", "that", "this", "into", "their", "they",
    "them", "have", "has", "had", "are", "was", "were", "but", "not", "any",
    "all", "its", "his", "her", "our", "out", "via", "per", "would", "should",
}
