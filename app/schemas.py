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
    company: Optional[str] = None
    year: Optional[int] = None
    fiscal_period: Optional[str] = None
    doc_type: Optional[str] = None


class SubQueryResult(BaseModel):
    """Result for a single sub-query in multi-agent mode."""
    question: str
    answer: str
    order: int
    chunks_count: int = 0


class ConflictSource(BaseModel):
    """Document context for one side of a detected conflict."""
    source: str
    company: Optional[str] = None
    period: Optional[str] = None
    page: Optional[int] = None


class Conflict(BaseModel):
    """A detected cross-document factual conflict."""
    type: str  # NUMERIC | QUALITATIVE | TEMPORAL
    severity: str  # HIGH | MEDIUM | LOW
    shared_fact: str
    claim_1: str
    claim_2: str
    explanation: str
    source_1: ConflictSource
    source_2: ConflictSource
    sub_query_indices: List[int] = []


class ConflictReport(BaseModel):
    """Aggregated report from the ConflictDetectorAgent."""
    conflicts: List[Conflict] = []
    pairs_checked: int = 0
    pairs_skipped: int = 0
    stats: Dict[str, Any] = {}
    skipped: bool = False
    reason: Optional[str] = None


class TrustComponent(BaseModel):
    """One weighted input to the composite FinSight Trust Score."""
    name: str
    value: float        # 0.0 – 1.0
    weight: float       # 0.0 – 1.0
    weighted: float     # value × weight
    detail: Optional[str] = None


class TrustScore(BaseModel):
    """FinSight Trust Score — quantitative answer reliability (0–100)."""
    composite: int                       # 0 – 100
    band: str                            # REJECT / LOW_TRUST / NEEDS_REVIEW / ANALYST_REVIEW / HIGH_TRUST
    band_description: str
    components: List[TrustComponent] = []


class TemporalContext(BaseModel):
    """Detected temporal/company filter applied to one sub-query."""
    sub_query_index: Optional[int] = None
    sub_question: Optional[str] = None
    company: Optional[str] = None
    year: Optional[int] = None
    quarter: Optional[str] = None
    doc_type: Optional[str] = None
    freshness: Optional[str] = None
    badge: Optional[str] = None
    note: Optional[str] = None


class MultiAgentTrace(BaseModel):
    """Full trace of multi-agent execution."""
    planner_decision: str  # SINGLE_AGENT or MULTI_AGENT
    planner_reasoning: str
    complexity_score: int  # 1-5
    sub_queries: List[SubQueryResult] = []
    synthesis_reasoning: Optional[str] = None
    validation_report: Dict[str, Any] = {}
    conflict_report: Optional[ConflictReport] = None
    temporal_context: List[TemporalContext] = []
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
    decision: str  # legacy 4-state: ANSWER, RETRIEVE, CLARIFY, REFUSE
    recommendation: Optional[str] = None  # extended 7-state derived from trust
    recommendation_description: Optional[str] = None
    reason: str
    citations: List[Citation]
    chunks: List[RetrievedChunk]
    execution_time_ms: Optional[float] = None
    multi_agent_trace: Optional[MultiAgentTrace] = None
    conflict_report: Optional[ConflictReport] = None
    temporal_context: List[TemporalContext] = []
    trust_score: Optional[TrustScore] = None


class HealthResponse(BaseModel):
    """Response body for GET /health."""
    status: str
    version: str
