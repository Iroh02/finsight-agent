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
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

from src.agents import (
    PlannerAgent,
    DecomposerAgent,
    SynthesizerAgent,
    VerifierAgent,
    ValidatorAgent,
)
from src.retriever import Retriever
from src.agent import AgenticRouter
from src.llm_client import LLMClient, load_prompt, get_llm_client


class MultiAgentOrchestrator:
    """
    Orchestrates 5 specialized agents to handle complex multi-hop questions.

    Flow:
    1. Planner analyzes complexity
    2. If simple → fall back to AgenticRouter
    3. If complex → Decomposer → Retriever (per sub-Q) → Synthesizer
                  → Verifier (CoVe fact-check) → Validator
    """

    def __init__(
        self,
        retriever: Retriever,
        llm_client: Optional[LLMClient] = None,
        single_agent_fallback: Optional[AgenticRouter] = None,
        enable_verifier: bool = True,
    ):
        """
        Initialize the orchestrator.

        Args:
            retriever: Document retriever (with reranker)
            llm_client: LLM client for all agents
            single_agent_fallback: Existing AgenticRouter for simple questions
            enable_verifier: If True, run Chain-of-Verification after synthesis.
                Set False to bypass (e.g. for ablation studies or saving API quota).
        """
        self.llm_client = llm_client or get_llm_client()
        self.retriever = retriever
        self.enable_verifier = enable_verifier

        # Initialize all 5 agents
        self.planner = PlannerAgent(self.llm_client)
        self.decomposer = DecomposerAgent(self.llm_client)
        self.synthesizer = SynthesizerAgent(self.llm_client)
        self.verifier = VerifierAgent(self.llm_client)
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

        # ============== STEP 4: PER-SUB-QUERY RETRIEVAL + ANSWER (PARALLEL) ==============
        # SOTA optimization: process all sub-queries concurrently using thread pool
        # This reduces multi-agent latency significantly for multi-hop questions.
        t = time.time()

        # Preheat retrieval models before parallel execution to avoid race conditions
        # in lazy model loading (embedder + reranker)
        try:
            _ = self.retriever.retrieve(sub_questions[0], k=1)
        except Exception:
            pass  # Continue even if warmup fails
        sub_answers_dict = {}  # order -> result, to maintain ordering
        all_chunks = []

        def _process_sub_query(idx_q):
            """Process a single sub-query: retrieve + generate sub-answer."""
            i, sub_q = idx_q
            try:
                chunks = self.retriever.retrieve(sub_q, k=k)
                sub_answer = self._generate_sub_answer(sub_q, chunks)
                return (i, {
                    "question": sub_q,
                    "answer": sub_answer,
                    "chunks": chunks,
                    "order": i,
                })
            except Exception as e:
                return (i, {
                    "question": sub_q,
                    "answer": f"[Error: {e}]",
                    "chunks": [],
                    "order": i,
                })

        # Run all sub-queries concurrently
        indexed = list(enumerate(sub_questions, 1))
        with ThreadPoolExecutor(max_workers=min(5, len(sub_questions))) as executor:
            futures = [executor.submit(_process_sub_query, item) for item in indexed]
            for future in as_completed(futures):
                idx, result = future.result()
                sub_answers_dict[idx] = result
                all_chunks.extend(result.get("chunks", []))

        # Restore order
        sub_answers = [sub_answers_dict[i] for i in sorted(sub_answers_dict.keys())]
        timing["retrieval_and_subanswers"] = round(time.time() - t, 2)

        # ============== STEP 5: SYNTHESIZER ==============
        t = time.time()
        synthesis = self.synthesizer.synthesize(question, sub_answers)
        timing["synthesizer"] = round(time.time() - t, 2)
        synthesized_answer = synthesis["answer"]

        # ============== STEP 6: VERIFIER (Chain-of-Verification) ==============
        # Fact-check each claim in the synthesized answer via fresh retrieval.
        # Dhuliawala et al., 2023 — "Chain-of-Verification Reduces Hallucination".
        verification = {
            "claims": [],
            "verifications": [],
            "stats": {"n_claims": 0, "supported": 0, "contradicted": 0, "insufficient": 0},
            "revised_answer": synthesized_answer,
            "skipped": not self.enable_verifier,
        }
        if self.enable_verifier:
            t = time.time()
            try:
                verification.update(
                    self.verifier.verify(
                        question=question,
                        answer=synthesized_answer,
                        retriever=self.retriever,
                        k=3,
                    )
                )
            except Exception as e:
                # CoVe is an enhancement — never let it block the pipeline.
                verification["error"] = f"Verifier error: {e}"
            timing["verifier"] = round(time.time() - t, 2)

        # The answer used downstream is the verifier's revision (or the synthesis if disabled).
        final_answer = verification.get("revised_answer") or synthesized_answer

        # ============== STEP 7: VALIDATOR ==============
        t = time.time()
        validation = self.validator.validate(
            question=question,
            sub_answers=sub_answers,
            final_answer=final_answer,
            all_chunks=all_chunks,
        )
        timing["validator"] = round(time.time() - t, 2)

        # ============== STEP 8: ASSEMBLE FINAL RESPONSE ==============
        total_time = round(time.time() - overall_start, 2)

        # Confidence starts from the validator; the verifier can pull it down if
        # claims were contradicted or insufficient.
        final_confidence = validation.get("suggested_confidence", 0.5)
        v_stats = verification.get("stats", {})
        n_claims = v_stats.get("n_claims", 0)
        if n_claims:
            grounded_ratio = v_stats.get("supported", 0) / n_claims
            # Pull confidence toward the grounded ratio (50/50 blend).
            final_confidence = round((final_confidence + grounded_ratio) / 2, 3)

        # Decision based on validation AND verification.
        if validation["supported"] == "NO" or v_stats.get("contradicted", 0) > 0:
            decision = "REFUSE"
            why = (
                f"Verifier flagged {v_stats.get('contradicted', 0)} contradicted claim(s); "
                f"Validator: {validation['summary']}"
            )
            reason = why
        else:
            decision = "ANSWER"
            grounded_note = (
                f" Verifier: {v_stats.get('supported', 0)}/{n_claims} claims grounded."
                if n_claims else ""
            )
            reason = (
                f"Multi-agent synthesis ({len(sub_questions)} sub-queries). "
                f"{validation['summary']}{grounded_note}"
            )

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
                "synthesized_answer": synthesized_answer,
                "verification_report": verification,
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
