"""Query handler endpoint for RAG system."""

import json
import time
import asyncio
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from app.schemas import (
    QueryRequest,
    QueryResponse,
    Citation,
    RetrievedChunk,
    SubQueryResult,
    MultiAgentTrace,
    ConflictReport,
    Conflict,
    ConflictSource,
    TemporalContext,
    TrustScore as TrustScoreSchema,
    TrustComponent as TrustComponentSchema,
)

# Import RAG components
from src.vectorstore import get_vectorstore
from src.retriever import Retriever
from src.temporal import TemporalAwareRetriever
from src.naive_rag import NaiveRAG
from src.agent import AgenticRouter
from src.citations import CitationExtractor
from src.confidence import ConfidenceScorer
from src.self_reflection import SelfReflectionCritic
from src.multi_agent import MultiAgentOrchestrator
from src.trust_score import (
    TrustScoreCalculator,
    derive_extended_decision,
    EXTENDED_DECISIONS,
)
from src.llm_client import get_llm_client


router = APIRouter()

# Global pipeline components (initialized on first request)
_pipeline = None


def get_pipeline():
    """Lazy-init pipeline components on first request."""
    global _pipeline
    if _pipeline is None:
        print("Initializing RAG pipeline (cross-encoder reranker + temporal-aware retrieval + multi-agent)...")
        vs = get_vectorstore()
        # SOTA: Two-stage retrieval with cross-encoder reranking
        # + temporal/company metadata filters when the query has dated refs.
        retriever = TemporalAwareRetriever(vs, use_reranker=True, retrieve_multiplier=4)
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
            "trust": TrustScoreCalculator(),
        }
        stats = vs.get_stats()
        print(f"Pipeline ready. Vector store: {stats}")
    return _pipeline


def _format_conflict_report(raw: Optional[dict]) -> Optional[ConflictReport]:
    """Convert raw conflict report dict into a Pydantic model (or None)."""
    if not raw:
        return None
    conflicts: List[Conflict] = []
    for c in raw.get("conflicts", []) or []:
        try:
            conflicts.append(Conflict(
                type=c.get("type", "NUMERIC"),
                severity=c.get("severity", "MEDIUM"),
                shared_fact=c.get("shared_fact", ""),
                claim_1=c.get("claim_1", ""),
                claim_2=c.get("claim_2", ""),
                explanation=c.get("explanation", ""),
                source_1=ConflictSource(**(c.get("source_1") or {"source": "?"})),
                source_2=ConflictSource(**(c.get("source_2") or {"source": "?"})),
                sub_query_indices=c.get("sub_query_indices", []),
            ))
        except Exception:
            continue
    return ConflictReport(
        conflicts=conflicts,
        pairs_checked=raw.get("pairs_checked", 0),
        pairs_skipped=raw.get("pairs_skipped", 0),
        stats=raw.get("stats", {}),
        skipped=raw.get("skipped", False),
        reason=raw.get("reason"),
    )


def _format_temporal_context(raw: Optional[list]) -> List[TemporalContext]:
    """Convert raw per-sub-query temporal context list into Pydantic models."""
    if not raw:
        return []
    out: List[TemporalContext] = []
    for t in raw:
        try:
            out.append(TemporalContext(**t))
        except Exception:
            continue
    return out


def _parse_temporal_for_question(question: str) -> list:
    """Parse the original user question into a temporal_context list.

    Used by agentic and naive modes (which don't go through the multi-agent
    orchestrator) so the UI still gets a freshness/scope badge.
    """
    try:
        from src.temporal import TemporalParser
    except Exception:
        return []
    parser = TemporalParser()
    tf = parser.parse(question)
    if not tf.has_filters and not tf.freshness:
        return []
    return [{
        "sub_query_index": 1,
        "sub_question": question,
        "company": tf.company,
        "year": tf.year,
        "quarter": tf.quarter,
        "doc_type": tf.doc_type,
        "freshness": tf.freshness,
        "badge": tf.badge_label(),
        "note": tf.note,
    }]


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
        conflict_report=_format_conflict_report(raw_trace.get("conflict_report")),
        temporal_context=_format_temporal_context(raw_trace.get("temporal_context")),
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
                company=chunk.get("company"),
                year=chunk.get("year"),
                fiscal_period=chunk.get("fiscal_period"),
                doc_type=chunk.get("doc_type"),
            )
            for chunk in unique_chunks[:10]  # Cap at 10 for UI
        ]

        # For non-multi-agent modes, parse the original question to surface
        # the same temporal badge in the UI.
        temporal_ctx = result.get("temporal_context")
        if not temporal_ctx:
            temporal_ctx = _parse_temporal_for_question(question)

        # Compute the composite FinSight Trust Score from whatever signals
        # this pipeline produced (some signals are mode-specific).
        raw_trace = (result.get("multi_agent_trace") or {})
        trust = pipeline["trust"].compute(
            chunks=chunks,
            verification=raw_trace.get("verification_report"),
            validation=raw_trace.get("validation_report"),
            conflict_report=result.get("conflict_report"),
            temporal_context=temporal_ctx,
            mode=request.mode,
        )

        # Derive extended decision (7-state) from base decision + signals
        extended = derive_extended_decision(
            base_decision=result.get("decision", "ANSWER"),
            trust=trust,
            verification=raw_trace.get("verification_report"),
            conflict_report=result.get("conflict_report"),
            temporal_context=temporal_ctx,
            chunks=chunks,
        )

        return QueryResponse(
            answer=answer,
            confidence=confidence,
            decision=result.get("decision", "ANSWER"),
            recommendation=extended,
            recommendation_description=EXTENDED_DECISIONS.get(extended),
            reason=result.get("reason", ""),
            citations=formatted_citations,
            chunks=formatted_chunks,
            execution_time_ms=round((time.time() - start_time) * 1000, 2),
            multi_agent_trace=multi_agent_trace,
            conflict_report=_format_conflict_report(result.get("conflict_report")),
            temporal_context=_format_temporal_context(temporal_ctx),
            trust_score=TrustScoreSchema(
                composite=trust.composite,
                band=trust.band,
                band_description=trust.band_description,
                components=[
                    TrustComponentSchema(
                        name=c.name,
                        value=round(c.value, 3),
                        weight=c.weight,
                        weighted=round(c.contribution, 3),
                        detail=c.detail,
                    )
                    for c in trust.components
                ],
            ),
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@router.post("/query/stream")
async def query_rag_stream(request: QueryRequest):
    """
    Streaming RAG query endpoint using Server-Sent Events.

    Streams progress updates as the agents work:
    - status events at each stage
    - final answer when complete

    Use this for richer UX where the user sees the agents progressing.
    """
    async def event_generator():
        try:
            pipeline = get_pipeline()
            question = request.question.strip()

            if not question:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Empty question'})}\n\n"
                return

            # Send initial status
            yield f"data: {json.dumps({'type': 'status', 'stage': 'starting', 'message': f'Processing in {request.mode} mode...'})}\n\n"
            await asyncio.sleep(0.1)

            if request.mode == "multi_agent":
                yield f"data: {json.dumps({'type': 'status', 'stage': 'planner', 'message': 'Planner agent analyzing complexity...'})}\n\n"
                await asyncio.sleep(0.1)

            # Run query (synchronous - in real production this would be async)
            start_time = time.time()
            if request.mode == "naive":
                result = pipeline["naive_rag"].query(question, k=5)
            elif request.mode == "multi_agent":
                yield f"data: {json.dumps({'type': 'status', 'stage': 'multi_agent', 'message': 'Coordinating 4 specialized agents...'})}\n\n"
                await asyncio.sleep(0.1)
                result = pipeline["multi_agent"].query(question, k=5)
            else:
                yield f"data: {json.dumps({'type': 'status', 'stage': 'agentic', 'message': 'Routing and retrieving...'})}\n\n"
                await asyncio.sleep(0.1)
                result = pipeline["agent"].route_and_answer(question, k=5)

            # Build the same response object as POST /query
            chunks = result.get("chunks", [])
            answer = result.get("answer", "")
            citations_raw = pipeline["citations"].extract_citations(answer, chunks)
            confidence = result.get("confidence", 0) or pipeline["confidence"].score(
                answer, chunks, result.get("decision", "ANSWER")
            )

            # Stream the answer word-by-word for visual effect
            yield f"data: {json.dumps({'type': 'status', 'stage': 'streaming', 'message': 'Streaming answer...'})}\n\n"

            words = answer.split()
            chunk_size = 3
            for i in range(0, len(words), chunk_size):
                word_chunk = " ".join(words[i:i + chunk_size])
                yield f"data: {json.dumps({'type': 'token', 'text': word_chunk + ' '})}\n\n"
                await asyncio.sleep(0.05)

            # Send final complete response
            final = {
                "type": "complete",
                "answer": answer,
                "decision": result.get("decision", "ANSWER"),
                "confidence": confidence,
                "reason": result.get("reason", ""),
                "citations": [
                    {"source": c["source"], "page": c.get("page"), "excerpt": c.get("excerpt", "")[:200]}
                    for c in citations_raw
                ],
                "chunks": [
                    {"text": ch["text"][:500], "source": ch.get("source", ""), "page": ch.get("page"), "relevance_score": ch.get("score")}
                    for ch in chunks[:10]
                ],
                "execution_time_ms": round((time.time() - start_time) * 1000, 2),
                "multi_agent_trace": result.get("multi_agent_trace"),
            }
            yield f"data: {json.dumps(final)}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload a PDF, save to data/raw/, and ingest into the vector store."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    # Save file
    upload_dir = Path("data/raw")
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / file.filename

    try:
        content = await file.read()
        file_path.write_bytes(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")

    # Ingest the new file
    try:
        from src.loader import PDFLoader
        from src.cleaner import clean_pages
        from src.chunker import TextChunker

        loader = PDFLoader(str(file_path))
        pages = loader.extract_text()
        cleaned = clean_pages(pages)

        chunker = TextChunker(chunk_size=1000, overlap=100)
        chunks = chunker.chunk(cleaned)

        pipeline = get_pipeline()
        pipeline["vectorstore"].add_documents(chunks)

        return {
            "status": "success",
            "filename": file.filename,
            "pages": len(pages),
            "chunks_ingested": len(chunks),
            "size_kb": round(len(content) / 1024, 1),
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to ingest: {e}")


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
