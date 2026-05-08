# FinSight Agent - System Architecture

## Overview

FinSight Agent is an Explainable Agentic RAG (Retrieval-Augmented Generation) system designed for business document intelligence.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        USER INTERFACE                        │
│                  (FastAPI + HTML/CSS/JS)                     │
└────────────────────┬────────────────────────────────────────┘
                     │ Question
                     ▼
        ┌────────────────────────────┐
        │  DATA INGESTION PIPELINE   │
        ├────────────────────────────┤
        │ 1. PDF Loader              │ ◄─── Jillian owns
        │ 2. Text Cleaner            │
        │ 3. Chunker                 │
        │ 4. Embedder                │
        │ 5. Vector Store            │
        └────────────────────────────┘
                     │
                     ▼
        ┌────────────────────────────┐
        │  RETRIEVAL & ROUTING       │
        ├────────────────────────────┤
        │ • Vector Store Retriever   │ ◄─── Anushree owns
        │ • Agentic Decision Router  │
        │   - ANSWER                 │
        │   - RETRIEVE               │
        │   - CLARIFY                │
        │   - REFUSE                 │
        └────────────────────────────┘
                     │
                     ▼
        ┌────────────────────────────┐
        │   ANSWER SYNTHESIS         │
        ├────────────────────────────┤
        │ • Answer Generator         │ ◄─── Anushree owns
        │ • Citation Extractor       │
        │ • Confidence Scorer        │
        └────────────────────────────┘
                     │
                     ▼
        ┌────────────────────────────┐
        │    RESPONSE FORMATTING     │
        ├────────────────────────────┤
        │ • JSON Response            │ ◄─── Nandita integrates
        │ • Frontend Display         │
        └────────────────────────────┘
```

## Pipeline Stages

### 1. Data Ingestion (Jillian)

**Goal**: Load PDFs and populate vector store with embedded chunks.

**Steps**:
- **PDF Loading** (`src/loader.py`): Extract text from PDFs page by page
- **Cleaning** (`src/cleaner.py`): Remove headers, footers, artifacts
- **Chunking** (`src/chunker.py`): Split into ~500-token overlapping chunks
- **Embedding** (`src/embedder.py`): Convert chunks to embeddings
- **Vector Storage** (`src/vectorstore.py`): Store in Chroma/FAISS

**Input**: PDF files in `data/raw/`  
**Output**: Populated vector store ready for retrieval

### 2. Retrieval & Agentic Routing (Anushree)

**Goal**: Retrieve relevant chunks and decide how to respond.

**Steps**:
- **Retrieval** (`src/retriever.py`): Similarity search for top-k chunks
- **Decision Router** (`src/agent.py`): 4-state routing decision:
  - **ANSWER**: Context is sufficient → proceed to generation
  - **RETRIEVE**: Insufficient context → expand retrieval to top-10
  - **CLARIFY**: Question is ambiguous → ask user
  - **REFUSE**: Evidence is insufficient → abstain

**Input**: User question  
**Output**: Decision state + retrieved chunks

### 3. Answer Generation (Anushree)

**Goal**: Generate grounded answer or appropriate response based on decision.

**Steps**:
- **Answer Generator**: LLM-based synthesis from chunks
- **Citation Mapper** (`src/citations.py`): Map claims to source chunks
- **Confidence Scorer** (`src/confidence.py`): Score answer confidence 0.0-1.0

**Input**: Question + decision + chunks  
**Output**: Answer + citations + confidence

### 4. Frontend Integration (Nandita)

**Goal**: Present results to user with full transparency.

**UI Components**:
- **Answer Panel**: Main generated answer
- **Confidence Badge**: Color-coded (green/yellow/red)
- **Decision Label**: Show routing decision and reason
- **Citations Expandable**: List of sources with pages
- **Chunks Expandable**: Show actual retrieved context

**Input**: JSON response from backend  
**Output**: Rendered web interface

## Technology Stack

### Backend
- **Framework**: FastAPI (Python)
- **Vector DB**: Chroma or FAISS
- **Embeddings**: OpenAI text-embedding-ada-002 or HuggingFace all-MiniLM-L6-v2
- **LLM**: GPT-4o mini or Claude 3 Haiku
- **PDF Processing**: pdfplumber, PyPDF2
- **Data**: pandas, numpy

### Frontend
- **Framework**: Vanilla HTML/CSS/JavaScript
- **API**: Fetch API (async/await)
- **Styling**: CSS3 with flexbox/grid

### Development
- **Version Control**: Git + GitHub
- **Testing**: pytest (for unit tests)
- **Notebooks**: Jupyter (for exploration)

## Module Dependencies

```
app/
  ├─ main.py (FastAPI app) → imports routes
  ├─ routes/
  │   ├─ query.py → imports from src/
  │   └─ health.py
  ├─ schemas.py (Pydantic models)
  ├─ static/ (CSS, JS)
  └─ templates/ (HTML)

src/
  ├─ pipeline.py (main orchestrator)
  │   ├─ loader.py
  │   ├─ cleaner.py
  │   ├─ chunker.py
  │   ├─ embedder.py
  │   ├─ vectorstore.py
  │   ├─ retriever.py
  │   ├─ naive_rag.py
  │   ├─ agent.py
  │   ├─ citations.py
  │   └─ confidence.py
  └─ pipeline.py imports all above

evaluation/
  ├─ eval_script.py → uses src/pipeline.py
  └─ test_questions.csv
```

## Decision Flow (Agentic Router)

```
Question
  │
  ├─► [Retrieval] ──► Top-5 chunks
  │
  ├─► [Decision Router]
  │   ├─ Is question clear? ──► NO  ──► CLARIFY
  │   │
  │   └─ Are chunks relevant?
  │       ├─ YES, sufficient ──► ANSWER
  │       │
  │       ├─ YES, marginal ──► RETRIEVE (expand to k=10)
  │       │                       │
  │       │                       └─► Re-evaluate
  │       │                           ├─ Now sufficient? ──► ANSWER
  │       │                           └─ Still marginal? ──► REFUSE
  │       │
  │       └─ NO, irrelevant ──► REFUSE
  │
  └─► [Action]
      ├─ ANSWER: Generate answer + citations
      ├─ RETRIEVE: Expand search + re-route
      ├─ CLARIFY: Ask user to rephrase
      └─ REFUSE: Polite abstention
```

## Confidence Scoring

### Heuristic Approach (Fast)

- **ANSWER state**: 0.7-1.0
  - Base: 0.7
  - Bonus for more chunks: +0.15 per 5 chunks (max 0.3)
  
- **RETRIEVE state**: 0.4-0.6 (marginal evidence)

- **CLARIFY state**: 0.1 (ambiguous question)

- **REFUSE state**: 0.0 (no evidence)

### LLM-Assisted Approach (More Accurate)

- Query LLM with answer + context
- Ask LLM to score 0.0-1.0 with justification
- Use `prompts/confidence_scorer.txt`

## Data Flow Example

```
Question: "What was Apple's total revenue in FY2023?"

1. RETRIEVE
   ├─ Query embedding generated
   ├─ Vector search in Chroma
   └─ Top-5 chunks: [financial statements, revenue tables, ...]

2. ROUTE
   ├─ Chunks contain "Total net sales 2023: $394.3B"
   ├─ Decision: ANSWER (relevant, direct match)
   └─ Reason: "Direct financial data found"

3. GENERATE
   ├─ Prompt: "Question + context → answer"
   ├─ LLM response: "Apple's total revenue in FY2023 was $394.3B"
   └─ Citations: [Apple_2023_10K.pdf, page 34]

4. SCORE
   ├─ Confidence: 0.95 (direct statement, multiple sources)
   └─ Confidence level: HIGH

5. RETURN
   {
     "answer": "Apple's total revenue in FY2023 was $394.3B",
     "decision": "ANSWER",
     "confidence": 0.95,
     "citations": [{"source": "Apple_2023_10K.pdf", "page": 34}],
     "chunks": [...]
   }
```

## Naive RAG Comparison

```
Naive RAG:
  Query
    │
    ├─► [Retrieve top-5]
    │
    ├─► [LLM: Generate answer from context]
    │
    └─► [Return answer only]

Problems:
  ✗ No routing → always attempts to answer
  ✗ Hallucination risk → fabricates when context weak
  ✗ No citations → user cannot verify
  ✗ No confidence → user doesn't know if answer is trustworthy
  ✗ No abstention → refuses to say "I don't know"

Agentic RAG:
  Query
    │
    ├─► [Retrieve top-5]
    │
    ├─► [Route: ANSWER/RETRIEVE/CLARIFY/REFUSE]
    │
    ├─► [If ANSWER: Generate + cite + score]
    │   [If RETRIEVE: Expand and re-route]
    │   [If CLARIFY: Ask user]
    │   [If REFUSE: Abstain gracefully]
    │
    └─► [Return answer + decision + confidence + citations]

Benefits:
  ✓ Smart routing → answers when appropriate, refuses when not
  ✓ Lower hallucination → decision layer prevents overconfidence
  ✓ Full transparency → citations + chunks + reasoning visible
  ✓ Confidence scores → users know answer trustworthiness
  ✓ Graceful abstention → system admits uncertainty
```

## Error Handling & Fallbacks

### Missing Data
- PDF extraction fails → Use pre-chunked text
- Embedding API down → Use local HuggingFace embeddings
- Vector store fails → Fall back to simple keyword search

### Low Confidence
- Confidence < 0.4 → Automatically route to REFUSE
- Multiple RETRIEVE attempts → Eventually REFUSE if no improvement

### Performance
- Slow embeddings → Cache embeddings locally
- Slow LLM calls → Use faster model (haiku, gpt-4o-mini)
- Many PDFs → Implement chunking by section/page for faster retrieval

---

**Next**: See `data_pipeline.md` for ingestion details, `demo_script.md` for presentation flow.
