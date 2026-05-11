"""Pydantic models for request/response validation."""

from pydantic import BaseModel
from typing import List, Optional, Dict, Any


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


class SubQueryResult(BaseModel):
    """Result for a single sub-query in multi-agent mode."""
    question: str
    answer: str
    order: int
    chunks_count: int = 0


class MultiAgentTrace(BaseModel):
    """Full trace of multi-agent execution."""
    planner_decision: str  # SINGLE_AGENT or MULTI_AGENT
    planner_reasoning: str
    complexity_score: int  # 1-5
    sub_queries: List[SubQueryResult] = []
    synthesis_reasoning: Optional[str] = None
    validation_report: Dict[str, Any] = {}
    execution_time_per_agent: Dict[str, float] = {}
    total_time_seconds: Optional[float] = None


class QueryRequest(BaseModel):
    """Request body for POST /query."""
    question: str
    mode: str = "agentic"  # "agentic", "naive", or "multi_agent"
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
    multi_agent_trace: Optional[MultiAgentTrace] = None


class HealthResponse(BaseModel):
    """Response body for GET /health."""
    status: str
    version: str
