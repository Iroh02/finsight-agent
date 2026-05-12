"""Multi-agent RAG system package.

Contains 5 specialized agents that collaborate to answer complex questions:
- PlannerAgent: Analyzes question complexity and decides routing strategy
- DecomposerAgent: Breaks complex questions into atomic sub-queries
- SynthesizerAgent: Combines sub-answers into a unified response
- VerifierAgent: Chain-of-Verification (CoVe) — fact-checks claims via re-retrieval
- ValidatorAgent: Validates the multi-hop reasoning chain

Inspired by ReAct, AutoGen, IRCoT, Plan-and-Solve, and Chain-of-Verification research.
"""

from src.agents.planner import PlannerAgent
from src.agents.decomposer import DecomposerAgent
from src.agents.synthesizer import SynthesizerAgent
from src.agents.verifier import VerifierAgent
from src.agents.validator import ValidatorAgent

__all__ = [
    "PlannerAgent",
    "DecomposerAgent",
    "SynthesizerAgent",
    "VerifierAgent",
    "ValidatorAgent",
]
