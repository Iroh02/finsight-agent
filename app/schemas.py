"""Pydantic models for request/response validation."""

from pydantic import BaseModel
from typing import List, Optional


class Citation(BaseModel):
    """A single citation source."""
    source: str
    page: Optional[int] = None
    excerpt: Optional[str] = None


class RetrievedChunk(BaseModel):
    """A single retrieved text chunk."""
    text: str
    source: str
    page: Optional[int] = None
    relevance_score: Optional[float] = None


class QueryRequest(BaseModel):
    """Request body for POST /query."""
    question: str
    mode: str = "agentic"  # "agentic" or "naive"
    selected_docs: Optional[List[str]] = None


class QueryResponse(BaseModel):
    """Response body for POST /query."""
    answer: str
    confidence: float  # 0.0 to 1.0
    decision: str  # ANSWER, RETRIEVE, CLARIFY, REFUSE
    reason: str
    citations: List[Citation]
    chunks: List[RetrievedChunk]
    execution_time_ms: Optional[float] = None


class HealthResponse(BaseModel):
    """Response body for GET /health."""
    status: str
    version: str
