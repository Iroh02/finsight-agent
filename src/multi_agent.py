"""Multi-Agent RAG Orchestrator.

Coordinates 4 specialized agents (Planner, Decomposer, Synthesizer, Validator)
along with the existing single-agent Retriever to handle complex multi-hop questions.

Architecture inspired by:
- ReAct (Yao et al., 2023)
- AutoGen (Microsoft Wu et al., 2023)
- IRCoT (Trivedi et al., 2023)
- Plan-and-Solve (Wang et al., 2023)
- Self-RAG (Asai et al., 2024)
"""

import time
from typing import Dict, List, Optional

from src.agents import (
    PlannerAgent,
    DecomposerAgent,
    SynthesizerAgent,
    ValidatorAgent,
)
from src.retriever import Retriever
from src.agent import AgenticRouter
from src.llm_client import LLMClient, load_prompt, get_llm_client


class MultiAgentOrchestrator:
    """
    Orchestrates 4 specialized agents to handle complex multi-hop questions.

    Flow:
    1. Planner analyzes complexity
    2. If simple → fall back to AgenticRouter
    3. If complex → Decomposer → Retriever (per sub-Q) → Synthesizer → Validator
    """

    def __init__(
        self,
        retriever: Retriever,
        llm_client: Optional[LLMClient] = None,
        single_agent_fallback: Optional[AgenticRouter] = None,
    ):
        """
        Initialize the orchestrator.

        Args:
            retriever: Document retriever (with reranker)
            llm_client: LLM client for all agents
            single_agent_fallback: Existing AgenticRouter for simple questions
        """
        self.llm_client = llm_client or get_llm_client()
        self.retriever = retriever

        # Initialize all 4 agents
        self.planner = PlannerAgent(self.llm_client)
        self.decomposer = DecomposerAgent(self.llm_client)
        self.synthesizer = SynthesizerAgent(self.llm_client)
        self.validator = ValidatorAgent(self.llm_client)

        # Single-agent fallback for simple questions
        self.single_agent = single_agent_fallback or AgenticRouter(retriever, self.llm_client)

        # Load answer generator prompt (reuse existing)
        try:
            self.answer_prompt = load_prompt("answer_generator")
        except FileNotFoundError:
            self.answer_prompt = "Answer this question using only the context:\nQ: {question}\nContext: {context}\nA:"

    def query(self, question: str, k: int = 5) -> Dict:
        """
        Process query through multi-agent system.

        Args:
            question: User question
            k: Retrieval chunks per sub-query

        Returns:
            Dict with:
            - answer: Final synthesized answer
            - decision: ANSWER/REFUSE
            - reason: Routing reasoning
            - confidence: Final confidence
            - chunks: All retrieved chunks
            - citations: All citations
            - multi_agent_trace: Full execution trace
        """
        overall_start = time.time()
        timing = {}

        # ============== STEP 1: PLANNER ==============
        t = time.time()
        plan = self.planner.analyze(question)
        timing["planner"] = round(time.time() - t, 2)

        # ============== STEP 2: ROUTING DECISION ==============
        if plan["strategy"] == "SINGLE_AGENT":
            # Use existing single-agent (faster path)
            result = self.single_agent.route_and_answer(question, k=k)
            result["multi_agent_trace"] = {
                "planner_decision": "SINGLE_AGENT",
                "planner_reasoning": plan["reasoning"],
                "complexity_score": plan["complexity_score"],
                "sub_queries": [],
                "synthesis_reasoning": "Not applicable - single agent used",
                "validation_report": {},
                "execution_time_per_agent": timing,
            }
            return result

        # ============== STEP 3: DECOMPOSER ==============
        t = time.time()
        sub_questions = self.decomposer.decompose(question)
        timing["decomposer"] = round(time.time() - t, 2)

        # Safety: if decomposer returns empty or single, fall back to single agent
        if not sub_questions or len(sub_questions) <= 1:
            result = self.single_agent.route_and_answer(question, k=k)
            result["multi_agent_trace"] = {
                "planner_decision": "MULTI_AGENT_REQUESTED",
                "planner_reasoning": plan["reasoning"],
                "complexity_score": plan["complexity_score"],
                "fallback_reason": "Decomposer returned <=1 sub-queries",
                "sub_queries": [],
                "synthesis_reasoning": "Fell back to single agent",
                "validation_report": {},
                "execution_time_per_agent": timing,
            }
            return result

        # ============== STEP 4: PER-SUB-QUERY RETRIEVAL + ANSWER ==============
        t = time.time()
        sub_answers = []
        all_chunks = []

        for i, sub_q in enumerate(sub_questions, 1):
            try:
                # Retrieve for this sub-query
                chunks = self.retriever.retrieve(sub_q, k=k)
                all_chunks.extend(chunks)

                # Generate sub-answer
                sub_answer = self._generate_sub_answer(sub_q, chunks)

                sub_answers.append({
                    "question": sub_q,
                    "answer": sub_answer,
                    "chunks": chunks,
                    "order": i,
                })
            except Exception as e:
                sub_answers.append({
                    "question": sub_q,
                    "answer": f"[Error retrieving for this sub-question: {e}]",
                    "chunks": [],
                    "order": i,
                })
        timing["retrieval_and_subanswers"] = round(time.time() - t, 2)

        # ============== STEP 5: SYNTHESIZER ==============
        t = time.time()
        synthesis = self.synthesizer.synthesize(question, sub_answers)
        timing["synthesizer"] = round(time.time() - t, 2)
        final_answer = synthesis["answer"]

        # ============== STEP 6: VALIDATOR ==============
        t = time.time()
        validation = self.validator.validate(
            question=question,
            sub_answers=sub_answers,
            final_answer=final_answer,
            all_chunks=all_chunks,
        )
        timing["validator"] = round(time.time() - t, 2)

        # ============== STEP 7: ASSEMBLE FINAL RESPONSE ==============
        total_time = round(time.time() - overall_start, 2)

        # Use validator's suggested confidence
        final_confidence = validation.get("suggested_confidence", 0.5)

        # Decision based on validation
        if validation["supported"] == "NO":
            decision = "REFUSE"
            reason = f"Validator detected unsupported claims: {validation['summary']}"
        else:
            decision = "ANSWER"
            reason = f"Multi-agent synthesis ({len(sub_questions)} sub-queries). {validation['summary']}"

        return {
            "answer": final_answer,
            "decision": decision,
            "reason": reason,
            "confidence": final_confidence,
            "chunks": all_chunks,
            "citations": [],  # Will be filled by CitationExtractor downstream
            "multi_agent_trace": {
                "planner_decision": "MULTI_AGENT",
                "planner_reasoning": plan["reasoning"],
                "complexity_score": plan["complexity_score"],
                "sub_queries": sub_answers,
                "synthesis_reasoning": synthesis.get("reasoning", ""),
                "validation_report": validation,
                "execution_time_per_agent": timing,
                "total_time_seconds": total_time,
            },
        }

    def _generate_sub_answer(self, sub_question: str, chunks: List[Dict]) -> str:
        """Generate an answer for a single sub-query."""
        if not chunks:
            return "No relevant information found for this sub-question."

        # Format context
        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            src = chunk.get("source", "?")
            page = chunk.get("page", "?")
            text = chunk.get("text", "")
            context_parts.append(f"[Chunk {i}] ({src}, p.{page})\n{text}")
        context = "\n\n".join(context_parts)

        # Build prompt
        prompt = self.answer_prompt.replace("{question}", sub_question)
        prompt = prompt.replace("{context}", context)

        try:
            return self.llm_client.generate(
                prompt=prompt,
                system="Answer the question using ONLY the provided context. Be concise.",
                temperature=0.3,
                max_tokens=300,
            )
        except Exception as e:
            return f"[Error generating sub-answer: {e}]"
