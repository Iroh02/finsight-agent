"""Query handler endpoint for RAG system."""

import time
from fastapi import APIRouter, HTTPException
from app.schemas import (
    QueryRequest,
    QueryResponse,
    Citation,
    RetrievedChunk,
    SubQueryResult,
    MultiAgentTrace,
)

# Import RAG components
from src.vectorstore import get_vectorstore
from src.retriever import Retriever
from src.naive_rag import NaiveRAG
from src.agent import AgenticRouter
from src.citations import CitationExtractor
from src.confidence import ConfidenceScorer
from src.self_reflection import SelfReflectionCritic
from src.multi_agent import MultiAgentOrchestrator
from src.llm_client import get_llm_client


router = APIRouter()

# Global pipeline components (initialized on first request)
_pipeline = None


def get_pipeline():
    """Lazy-init pipeline components on first request."""
    global _pipeline
    if _pipeline is None:
        print("Initializing RAG pipeline (with cross-encoder reranker + multi-agent)...")
        vs = get_vectorstore()
        # SOTA: Two-stage retrieval with cross-encoder reranking
        retriever = Retriever(vs, use_reranker=True, retrieve_multiplier=4)
        llm = get_llm_client()
        agentic = AgenticRouter(retriever, llm)
        _pipeline = {
            "vectorstore": vs,
            "retriever": retriever,
            "llm": llm,
            "naive_rag": NaiveRAG(retriever, llm),
            "agent": agentic,
            "multi_agent": MultiAgentOrchestrator(retriever, llm, single_agent_fallback=agentic),
            "citations": CitationExtractor(use_llm=False),
            "confidence": ConfidenceScorer(use_heuristic=True),
            "critic": SelfReflectionCritic(llm),
        }
        stats = vs.get_stats()
        print(f"Pipeline ready. Vector store: {stats}")
    return _pipeline


def _format_trace_for_response(raw_trace: dict) -> MultiAgentTrace:
    """Convert raw orchestrator trace into Pydantic model."""
    sub_query_results = []
    for sq in raw_trace.get("sub_queries", []):
        sub_query_results.append(SubQueryResult(
            question=sq.get("question", ""),
            answer=sq.get("answer", ""),
            order=sq.get("order", 0),
            chunks_count=len(sq.get("chunks", [])),
        ))

    return MultiAgentTrace(
        planner_decision=raw_trace.get("planner_decision", ""),
        planner_reasoning=raw_trace.get("planner_reasoning", ""),
        complexity_score=int(raw_trace.get("complexity_score", 1)),
        sub_queries=sub_query_results,
        synthesis_reasoning=raw_trace.get("synthesis_reasoning"),
        validation_report=raw_trace.get("validation_report", {}),
        execution_time_per_agent=raw_trace.get("execution_time_per_agent", {}),
        total_time_seconds=raw_trace.get("total_time_seconds"),
    )


@router.post("/query", response_model=QueryResponse)
async def query_rag(request: QueryRequest):
    """
    Main RAG query endpoint.

    Modes:
    - "naive": Baseline RAG (retrieve + generate)
    - "agentic": 4-state agentic router with self-reflection
    - "multi_agent": Full multi-agent system (Planner → Decomposer → Retriever → Synthesizer → Validator)
    """
    start_time = time.time()

    try:
        pipeline = get_pipeline()
        question = request.question.strip()

        if not question:
            raise HTTPException(status_code=400, detail="Question cannot be empty")

        # Route based on mode
        multi_agent_trace = None
        if request.mode == "naive":
            result = pipeline["naive_rag"].query(question, k=5)
        elif request.mode == "multi_agent":
            result = pipeline["multi_agent"].query(question, k=5)
            raw_trace = result.get("multi_agent_trace")
            if raw_trace:
                multi_agent_trace = _format_trace_for_response(raw_trace)
        else:  # agentic (default)
            result = pipeline["agent"].route_and_answer(question, k=5)

        # Extract citations
        chunks = result.get("chunks", [])
        answer = result.get("answer", "")
        citations_raw = pipeline["citations"].extract_citations(answer, chunks)

        # Determine confidence (multi-agent already has validator-based confidence)
        if request.mode == "multi_agent" and result.get("confidence", 0) > 0:
            confidence = result["confidence"]
        else:
            confidence = pipeline["confidence"].score(
                answer=answer,
                chunks=chunks,
                decision=result.get("decision", "ANSWER"),
            )

            # SOTA: Self-reflection (only for agentic mode and ANSWER decisions)
            if (
                request.mode == "agentic"
                and result.get("decision") == "ANSWER"
                and answer
                and chunks
            ):
                try:
                    critique = pipeline["critic"].reflect(
                        question=question,
                        answer=answer,
                        chunks=chunks,
                    )
                    confidence = pipeline["critic"].adjust_confidence(
                        original_confidence=confidence,
                        critique=critique,
                        weight=0.5,
                    )
                except Exception as e:
                    print(f"Self-reflection failed: {e}")

        # Format response
        formatted_citations = [
            Citation(
                source=c["source"],
                page=c.get("page"),
                excerpt=c.get("excerpt", "")[:200],
            )
            for c in citations_raw
        ]

        # Deduplicate chunks (multi-agent retrieves same chunks across sub-queries)
        seen_chunk_ids = set()
        unique_chunks = []
        for chunk in chunks:
            chunk_id = (chunk.get("source", ""), chunk.get("page", 0), chunk.get("text", "")[:50])
            if chunk_id not in seen_chunk_ids:
                seen_chunk_ids.add(chunk_id)
                unique_chunks.append(chunk)

        formatted_chunks = [
            RetrievedChunk(
                text=chunk["text"][:500] + ("..." if len(chunk["text"]) > 500 else ""),
                source=chunk["source"],
                page=chunk.get("page"),
                relevance_score=chunk.get("score"),
            )
            for chunk in unique_chunks[:10]  # Cap at 10 for UI
        ]

        return QueryResponse(
            answer=answer,
            confidence=confidence,
            decision=result.get("decision", "ANSWER"),
            reason=result.get("reason", ""),
            citations=formatted_citations,
            chunks=formatted_chunks,
            execution_time_ms=round((time.time() - start_time) * 1000, 2),
            multi_agent_trace=multi_agent_trace,
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@router.get("/documents")
async def list_documents():
    """List available documents in the vector store."""
    try:
        pipeline = get_pipeline()
        stats = pipeline["vectorstore"].get_stats()

        # Get unique sources from a sample
        try:
            collection = pipeline["vectorstore"].collection
            results = collection.get(limit=1000, include=["metadatas"])
            sources = set()
            for meta in results.get("metadatas", []):
                if meta and meta.get("source"):
                    sources.add(meta["source"])
            sources_list = sorted(list(sources))
        except Exception:
            sources_list = []

        return {
            "total_chunks": stats.get("count", 0),
            "documents": sources_list,
            "embedder": stats.get("embedder", "unknown"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list documents: {str(e)}")
