# CLAUDE.md — FinSight Agent Project Context

> This file gives any Claude session immediate context about the project.

## What This Is

**FinSight Agent** — A SOTA Multi-Agent RAG system for business document intelligence. Built as a 3-day final project for *Advanced Topics in Generative AI* course at SP Jain. Now extended to 5+ days for research-grade quality.

**Repo**: https://github.com/Iroh02/finsight-agent
**Team**: Nandita (lead), Anushree (evaluation), Jillian (data pipeline)
**Deadline**: Originally May 11 2026, extended ~May 17 2026
**Working dir**: `c:\Users\nandi\Desktop\agentic scraping\atgai_final`

## Quick Architecture

```
PDF → Loader → Cleaner → Chunker → Embedder → ChromaDB
                                                    ↓
User Query → Reranker ← Retriever ←──────────────────
                ↓
        ┌───────────────────────────────────┐
        │  3 MODES:                          │
        │  - Naive RAG (baseline)            │
        │  - Agentic RAG (4-state router)    │
        │  - Multi-Agent RAG (5 agents):     │
        │    Planner → Decomposer →          │
        │    Retriever → Synthesizer →       │
        │    Verifier → Validator            │
        └───────────────────────────────────┘
                ↓
        Citations + Confidence + Self-Reflection
                ↓
        FastAPI + HTML/CSS/JS frontend
```

## Tech Stack

- **Backend**: FastAPI (Python 3.10+)
- **LLM**: OpenAI gpt-4o-mini (also supports Anthropic + Gemini auto-detected from `.env`)
- **Embeddings**: HuggingFace `all-MiniLM-L6-v2` (free, local)
- **Vector DB**: ChromaDB (local persistent)
- **Reranker**: `cross-encoder/ms-marco-MiniLM-L-6-v2`
- **Frontend**: Vanilla HTML/CSS/JS + marked.js for markdown
- **Eval**: RAGAS, LLM-as-Judge (gpt-4o-mini)

## Critical Files & Their Purpose

```
src/
├── llm_client.py         # Unified LLM wrapper (OpenAI/Anthropic/Gemini)
├── loader.py             # PDF extraction (pdfplumber + PyPDF2 fallback)
├── cleaner.py            # Text cleaning + Jillian's statistical header/footer detection
├── chunker.py            # 1000-char chunks with 100 overlap, sentence-boundary aware
├── embedder.py           # HuggingFace + OpenAI embeddings
├── vectorstore.py        # ChromaDB wrapper
├── reranker.py           # Cross-encoder reranking (SOTA)
├── retriever.py          # Two-stage: vector search + rerank (+ optional HyDE)
├── hyde.py               # Hypothetical Document Embeddings
├── naive_rag.py          # Baseline RAG (no routing)
├── agent.py              # Agentic 4-state router (ANSWER/RETRIEVE/CLARIFY/REFUSE)
├── citations.py          # Citation extraction (simple + LLM modes)
├── confidence.py         # Confidence scoring (heuristic + LLM)
├── self_reflection.py    # Self-RAG style critic
├── multi_agent.py        # 5-agent orchestrator (PARALLEL sub-query execution)
├── agents/
│   ├── planner.py        # Decides MULTI_AGENT vs SINGLE_AGENT
│   ├── decomposer.py     # Breaks Q into sub-queries
│   ├── synthesizer.py    # Combines sub-answers
│   ├── verifier.py       # ⭐ CoVe Chain-of-Verification (Anushree's work)
│   └── validator.py      # Validates reasoning chain
└── pipeline.py           # End-to-end orchestrator (legacy, see test_pipeline.py)

app/
├── main.py               # FastAPI entry
├── routes/query.py       # POST /query (all 3 modes) + /upload + /query/stream
├── schemas.py            # Pydantic models
├── static/css/style.css  # All styling
├── static/js/app.js      # Frontend logic + agent trace renderer
└── templates/index.html  # SPA UI with mode toggle

evaluation/
├── eval_script.py        # 3-way evaluation runner
├── llm_judge.py          # LLM-as-Judge (Anushree)
├── ragas_eval.py         # RAGAS evaluation (Anushree)
├── results_naive.csv     # 15 questions × naive RAG
├── results_agentic.csv   # 15 questions × agentic RAG
├── results_multi_agent.csv # 15 questions × multi-agent
├── llm_judge_scores.csv  # 45 rows of GPT-4 judge scores
├── ragas_scores.csv      # RAGAS faithfulness scores
├── analysis.ipynb        # 3-way comparison analysis (Anushree)
└── error_analysis.ipynb  # Failure mode analysis (Anushree)

prompts/                  # All LLM prompts
data/raw/                 # PDFs (Apple, Amazon, Nvidia, Project Guide)
docs/                     # Architecture, evaluation, business case
```

## How to Run

```bash
# Setup (once)
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env: add OPENAI_API_KEY (or GOOGLE_API_KEY for free)

# Run server
uvicorn app.main:app --host 127.0.0.1 --port 8001
# Visit: http://127.0.0.1:8001

# Run tests
python -m src.test_pipeline       # End-to-end ingestion test
python -m src.test_multi_agent    # 5-agent flow test
python -m src.test_verifier       # Anushree's verifier tests (13 pass)

# Run evaluation
python evaluation/eval_script.py --modes naive agentic multi_agent
python evaluation/llm_judge.py --resume
python evaluation/ragas_eval.py --run
```

## Key Commands & Conventions

- **Branch naming**: `feature/<name>-<task>` (e.g., `feature/jillian-pipeline`)
- **Master is protected for stable submission**
- **All teammates have `write` permission**
- **Auto-detect LLM provider from `.env`** (in order: OpenAI > Anthropic > Gemini)
- **Vector store persists in `data/chroma/`**

## Three Operating Modes (key feature)

| Mode | Pipeline | Latency | Use Case |
|------|----------|---------|----------|
| **naive** | retrieve → answer | ~3s | Simple facts, baseline |
| **agentic** | retrieve → route → answer → self-reflect | ~7s | Most questions |
| **multi_agent** | plan → decompose → retrieve (parallel) → synth → verify → validate | ~16-60s | Multi-hop, comparisons |

## SOTA Features Implemented (Research Refs)

| Feature | Paper | File |
|---------|-------|------|
| Agentic routing | Self-RAG (Asai et al., 2024) | `src/agent.py` |
| Cross-encoder reranking | ColBERT (Khattab 2020) | `src/reranker.py` |
| Self-reflection | Self-RAG (Asai 2024) | `src/self_reflection.py` |
| Multi-agent | ReAct, AutoGen, IRCoT | `src/multi_agent.py` + `src/agents/` |
| Chain-of-Verification | Dhuliawala et al., 2023 | `src/agents/verifier.py` |
| HyDE | Gao et al., 2023 | `src/hyde.py` |
| Query decomposition | Self-Ask (Press 2022) | `src/agents/decomposer.py` |
| Plan-and-Solve | Wang et al., 2023 | `src/agents/planner.py` |
| Refusal/abstention | CRAG (Yan 2024) | `src/agent.py` |
| LLM-as-Judge eval | Zheng et al., 2023 | `evaluation/llm_judge.py` |
| RAGAS metrics | Es et al., 2024 | `evaluation/ragas_eval.py` |

## Coding Conventions Used

- **Type hints**: Use `Optional`, `List`, `Dict` from typing
- **Docstrings**: Triple-quoted for all classes and public methods
- **Lazy imports**: Heavy deps (chromadb, sentence-transformers, torch) imported inside methods
- **Lazy initialization**: Models loaded on first use, not at import
- **Singleton pattern**: `get_llm_client()`, `get_vectorstore()`, `get_embedder()`
- **Dict-based interfaces**: Most components return `Dict[str, Any]` not Pydantic models (faster iteration)
- **Error handling**: Try/except with graceful fallback in pipelines

## Evaluation State

Current results (15 questions, 3 modes):

```
LLM-as-Judge (1-10 scale):
| Metric            | Naive | Agentic | Multi-Agent |
| Correctness       | 7.00  | 8.07    | 8.13        |
| Helpfulness       | 6.87  | 7.93    | 8.20        |
| Citation Accuracy | 7.60  | 9.33    | 9.33        |

Heuristic Eval (0-1 scale):
| Metric           | Naive | Agentic | Multi-Agent |
| Relevance        | 0.835 | 0.920   | 0.917       |
| Faithfulness     | 0.947 | 0.753   | 0.893       |
| Correct refuse % | 80%   | 53%     | 73%         |
| Latency (s)      | 2.96  | 6.88    | 16.38       |

RAGAS Faithfulness:
| Mode | Score |
| Naive | 0.378 |
| Agentic | 0.494 |
| Multi-Agent | 0.294 |
```

## Open Issues (Snapshot)

22 open GitHub issues across:
- Critical: #25 (demo script), #28 (eval table), #29 (slides), #30 (pipeline docs)
- SOTA additions: #31-#48 (RAGAS, hybrid search, CoVe, parent-child chunking, etc.)
- Some already in progress (Jillian working on pipeline tasks)

## What's Next (Planned)

User wants to extend the project with novel additions:
- **Cross-Document Conflict Detection** (NEW novel feature, not GraphRAG which was done last sem)
- **Temporal-Aware Retrieval** (filter by document fiscal year)
- These together = publication-worthy framework

Implementation pending — waiting for Jillian's current PR to merge first.

## Reading Order for New Sessions

If starting fresh, read in this order:
1. `CLAUDE.md` (this file)
2. `HANDOVER.md` (latest session summary)
3. `README.md` (public-facing project doc)
4. `TASK_BREAKDOWN.md` (what each team member does)
5. `5_DAY_PLAN.md` (extended project plan)
6. `BUSINESS_CASE.md` (commercial positioning)
7. `src/multi_agent.py` (core technical work)
8. `evaluation/analysis.ipynb` (Anushree's analysis)

## Notes & Gotchas

- **PDFs in `data/raw/` are tracked in git** (5.7 MB total). If you re-ingest, vector store rebuilds.
- **Vector store is in `data/chroma/`** — gitignored, must re-ingest on fresh clone.
- **`.env` is gitignored** — every dev needs their own API key.
- **Cross-encoder rerank scores are negative logits** — that's normal. Higher = more relevant.
- **`gpt-4o-mini` is the default LLM** — fast and cheap for the project.
- **Avoid Anthropic + Gemini SDK deprecation warnings** — they still work but show warnings.
