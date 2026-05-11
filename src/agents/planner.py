"""Planner Agent: Analyzes question complexity and decides routing strategy.

Inspired by Plan-and-Solve (Wang et al., 2023) and ReAct (Yao et al., 2023).
"""

import re
from typing import Dict, Optional
from src.llm_client import LLMClient, load_prompt, get_llm_client


class PlannerAgent:
    """
    Analyzes question complexity and decides if multi-agent processing is needed.

    Returns a research plan with:
    - complexity_score (1-5)
    - strategy (SINGLE_AGENT or MULTI_AGENT)
    - expected_sub_queries (estimate)
    - reasoning
    """

    MULTI_AGENT_KEYWORDS = [
        "compare", "vs", "versus", "difference",
        "between", "and how", "also",
        "across", "over time", "trend",
    ]

    def __init__(self, llm_client: Optional[LLMClient] = None):
        """Initialize planner with LLM client."""
        self.llm_client = llm_client or get_llm_client()
        try:
            self.prompt_template = load_prompt("planner")
        except FileNotFoundError:
            self.prompt_template = self._default_prompt()

    def analyze(self, question: str) -> Dict:
        """
        Analyze question and return research plan.

        Args:
            question: User's question

        Returns:
            Dict with:
            - complexity_score: int 1-5
            - strategy: "SINGLE_AGENT" or "MULTI_AGENT"
            - expected_sub_queries: int
            - reasoning: str
        """
        # Quick heuristic check first (saves API call for obvious simple questions)
        heuristic_complex = self._heuristic_check(question)

        # Always run LLM analysis for confidence
        prompt = self.prompt_template.replace("{question}", question)

        try:
            response = self.llm_client.generate(
                prompt=prompt,
                system="You are a precise research planner. Output only in the requested format.",
                temperature=0.1,
                max_tokens=200,
            )
            plan = self._parse_response(response)

            # Combine heuristic and LLM signals
            # If heuristic detects multi-part question, ensure multi-agent routing
            if heuristic_complex:
                plan["complexity_score"] = max(plan["complexity_score"], 4)
                plan["reasoning"] = f"{plan['reasoning']} [Heuristic detected multi-part question.]"

            # Final decision
            if plan["complexity_score"] >= 4:
                plan["strategy"] = "MULTI_AGENT"
            else:
                plan["strategy"] = "SINGLE_AGENT"

            return plan
        except Exception as e:
            # Fallback to heuristic only
            return self._fallback_plan(question, heuristic_complex, str(e))

    def _heuristic_check(self, question: str) -> bool:
        """Quick heuristic to detect complex questions."""
        q_lower = question.lower()

        # Multi-part keywords
        keyword_hits = sum(1 for kw in self.MULTI_AGENT_KEYWORDS if kw in q_lower)

        # Multiple question marks or "and" connecting clauses
        multiple_qs = question.count("?") > 1
        compound_and = q_lower.count(" and ") >= 2

        return keyword_hits >= 1 or multiple_qs or compound_and

    def _parse_response(self, response: str) -> Dict:
        """Parse LLM response into structured plan."""
        # Default values
        complexity = 2
        strategy = "SINGLE_AGENT"
        expected_subs = 1
        reasoning = "Default analysis"

        # Extract complexity score
        match = re.search(r"COMPLEXITY_SCORE:\s*(\d+)", response, re.IGNORECASE)
        if match:
            try:
                complexity = max(1, min(5, int(match.group(1))))
            except ValueError:
                pass

        # Extract strategy
        match = re.search(r"STRATEGY:\s*(SINGLE_AGENT|MULTI_AGENT)", response, re.IGNORECASE)
        if match:
            strategy = match.group(1).upper()

        # Extract expected sub-queries
        match = re.search(r"EXPECTED_SUB_QUERIES:\s*(\d+)", response, re.IGNORECASE)
        if match:
            try:
                expected_subs = max(1, min(5, int(match.group(1))))
            except ValueError:
                pass

        # Extract reasoning
        match = re.search(r"REASONING:\s*(.+?)(?:\n[A-Z_]+:|$)", response, re.IGNORECASE | re.DOTALL)
        if match:
            reasoning = match.group(1).strip()

        return {
            "complexity_score": complexity,
            "strategy": strategy,
            "expected_sub_queries": expected_subs,
            "reasoning": reasoning,
        }

    def _fallback_plan(self, question: str, heuristic_complex: bool, error: str) -> Dict:
        """Return a fallback plan when LLM fails."""
        if heuristic_complex:
            return {
                "complexity_score": 3,
                "strategy": "MULTI_AGENT",
                "expected_sub_queries": 2,
                "reasoning": f"Heuristic fallback (LLM error: {error[:50]})",
            }
        return {
            "complexity_score": 1,
            "strategy": "SINGLE_AGENT",
            "expected_sub_queries": 1,
            "reasoning": f"Heuristic fallback (LLM error: {error[:50]})",
        }

    @staticmethod
    def _default_prompt() -> str:
        return """Analyze question complexity. Output:
COMPLEXITY_SCORE: 1-5
STRATEGY: SINGLE_AGENT or MULTI_AGENT
EXPECTED_SUB_QUERIES: 1-5
REASONING: brief explanation

Question: {question}"""
