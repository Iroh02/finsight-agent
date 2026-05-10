"""Query handler endpoint for RAG system."""

import time
from fastapi import APIRouter, HTTPException
from app.schemas import QueryRequest, QueryResponse, Citation, RetrievedChunk

# Import RAG components
from src.vectorstore import get_vectorstore
from src.retriever import Retriever
from src.naive_rag import NaiveRAG
from src.agent import AgenticRouter
from src.citations import CitationExtractor
from src.confidence import ConfidenceScorer
from src.llm_client import get_llm_client


router = APIRouter()

# Global pipeline components (initialized on first request)
_pipeline = None


def get_pipeline():
    """Lazy-init pipeline components on first request."""
    global _pipeline
    if _pipeline is None:
        print("Initializing RAG pipeline...")
        vs = get_vectorstore()
        retriever = Retriever(vs)
        llm = get_llm_client()
        _pipeline = {
            "vectorstore": vs,
            "retriever": retriever,
            "llm": llm,
            "naive_rag": NaiveRAG(retriever, llm),
            "agent": AgenticRouter(retriever, llm),
            "citations": CitationExtractor(use_llm=False),
            "confidence": ConfidenceScorer(use_heuristic=True),
        }
        stats = vs.get_stats()
        print(f"Pipeline ready. Vector store: {stats}")
    return _pipeline


@router.post("/query", response_model=QueryResponse)
async def query_rag(request: QueryRequest):
    """
    Main RAG query endpoint.

    Routes question through naive or agentic RAG and returns:
    - answer text
    - confidence score (0.0-1.0)
    - decision state (ANSWER/RETRIEVE/CLARIFY/REFUSE)
    - citations (source documents and pages)
    - retrieved chunks
    """
    start_time = time.time()

    try:
        pipeline = get_pipeline()
        question = request.question.strip()

        if not question:
            raise HTTPException(status_code=400, detail="Question cannot be empty")

        # Route based on mode
        if request.mode == "naive":
            result = pipeline["naive_rag"].query(question, k=5)
        else:  # agentic (default)
            result = pipeline["agent"].route_and_answer(question, k=5)

        # Extract citations
        chunks = result.get("chunks", [])
        answer = result.get("answer", "")
        citations_raw = pipeline["citations"].extract_citations(answer, chunks)

        # Score confidence
        confidence = pipeline["confidence"].score(
            answer=answer,
            chunks=chunks,
            decision=result.get("decision", "ANSWER"),
        )

        # Format response
        formatted_citations = [
            Citation(
                source=c["source"],
                page=c.get("page"),
                excerpt=c.get("excerpt", "")[:200],
            )
            for c in citations_raw
        ]

        formatted_chunks = [
            RetrievedChunk(
                text=chunk["text"][:500] + ("..." if len(chunk["text"]) > 500 else ""),
                source=chunk["source"],
                page=chunk.get("page"),
                relevance_score=chunk.get("score"),
            )
            for chunk in chunks
        ]

        return QueryResponse(
            answer=answer,
            confidence=confidence,
            decision=result.get("decision", "ANSWER"),
            reason=result.get("reason", ""),
            citations=formatted_citations,
            chunks=formatted_chunks,
            execution_time_ms=round((time.time() - start_time) * 1000, 2),
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
