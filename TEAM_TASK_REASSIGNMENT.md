# Task Reassignment Summary

## NEW Distribution (Updated)

### Nandita — Core Technical Lead
**Priority**: HIGHEST (Agentic Logic + Evaluation + Demo Control)

**Day 1 Tasks**:
- #5: Implement naive RAG baseline
- #6: Write 10–15 test questions  
- #7: GitHub repo setup

**Day 2 Tasks**:
- #9: Implement agentic 4-state decision layer (CORE)
- #10: Implement source citation logic
- #11: Implement confidence scoring
- #22: Demo script and rehearsal (lead)

**Day 3 Tasks**:
- #17: Run full evaluation
- #18: Compile evaluation results table
- #19: Write results analysis
- #22: Demo rehearsal x2 (lead)
- #23: Final repo cleanup and merge

**Key Files Owned**:
- `src/naive_rag.py`
- `src/agent.py` ← Agentic router (intellectual core)
- `src/citations.py`
- `src/confidence.py`
- `evaluation/` (all evaluation scripts)
- `docs/demo_script.md`

**Why**: Agentic decision logic is the technical heart of the project. Nandita owns this means she understands the system best and naturally leads the demo. She also controls project success via evaluation.

---

### Anushree — Data Infrastructure Lead
**Priority**: HIGH (Complete Data Pipeline)

**Day 1 Tasks**:
- #1: Collect annual report PDFs
- #2: Implement PDF extraction and cleaning
- #3: Implement chunking pipeline
- #4: Set up vector store and embeddings

**Day 2 Tasks**:
- #16: Data pipeline documentation
- (Support: integrate with pipeline)

**Day 3 Tasks**:
- (Support: demo if questions about data)

**Key Files Owned**:
- `src/loader.py`
- `src/cleaner.py`
- `src/chunker.py`
- `src/embedder.py`
- `src/vectorstore.py`
- `src/retriever.py`
- `data/raw/` (PDFs)
- `data/processed/` (processed text)
- `docs/data_pipeline.md`

**Why**: Complete ownership of modular, isolated pipeline. Data infrastructure is foundational. If issues arise, Anushree is solely responsible, not bottlenecking others.

---

### Jillian — Frontend + Integration Lead
**Priority**: HIGH (FastAPI + UI + Final Polish)

**Day 1 Tasks**:
- #8: Draft prompt templates v1

**Day 2 Tasks**:
- #12: Build FastAPI app skeleton
- #13: Build frontend UI (HTML/CSS/JS)
- #14: Finalize prompt templates
- #15: Full end-to-end integration test

**Day 3 Tasks**:
- #20: Complete slides draft (KEPT from original)
- #21: Final README polish
- #22: Demo rehearsal (support)
- #23: Help with repo cleanup

**Key Files Owned**:
- `app/main.py`
- `app/routes/` (FastAPI routes)
- `app/schemas.py` (Pydantic models)
- `app/static/` (CSS, JS)
- `app/templates/` (HTML)
- `prompts/` (all 6 prompts)
- `README.md`
- `slides/` (presentation)

**Why**: Frontend and integration are visible in the demo. Jillian's UI work is polished and professional-looking. FastAPI routing shows solid engineering. Prompt engineering shows domain understanding.

---

## Work Distribution by GitHub Issue

### Milestone 1: Data + Retrieval Ready
| Issue | Task | Assignee |
|-------|------|----------|
| #1 | Collect PDFs | Anushree |
| #2 | PDF extraction + cleaning | Anushree |
| #3 | Chunking pipeline | Anushree |
| #4 | Vector store + embeddings | Anushree |
| #5 | Naive RAG baseline | Nandita |
| #6 | Test questions | Nandita |
| #7 | GitHub repo setup | Nandita |
| #8 | Prompt templates v1 | Jillian |

### Milestone 2: Agentic RAG + UI Ready
| Issue | Task | Assignee |
|-------|------|----------|
| #9 | Agentic 4-state router | Nandita |
| #10 | Citation logic | Nandita |
| #11 | Confidence scoring | Nandita |
| #12 | FastAPI app | Jillian |
| #13 | Frontend UI | Jillian |
| #14 | Finalize prompts | Jillian |
| #15 | Integration test | Jillian |
| #16 | Data pipeline docs | Anushree |

### Milestone 3: Evaluation + Presentation Ready
| Issue | Task | Assignee |
|-------|------|----------|
| #17 | Run evaluation | Nandita |
| #18 | Results table | Nandita |
| #19 | Results analysis | Nandita |
| #20 | Slides draft | Jillian |
| #21 | README polish | Jillian |
| #22 | Demo script + rehearsal | Nandita (lead) + all |
| #23 | Repo cleanup | Nandita + all |

---

## Why This Distribution Works

### For Nandita
- **Most technical**: Agentic routing is the intellectual core
- **Demo control**: She owns the system deeply, naturally leads presentation
- **Project success**: Controls evaluation metrics and final integration
- **Looks fair**: Not obviously "highest" on GitHub, just "the person who knows the agentic system best"

### For Anushree
- **Modular responsibility**: Data pipeline is isolated, easy to verify/debug
- **Not bottlenecking**: If issues arise, they don't block others
- **Infrastructure credibility**: Building solid foundation shows engineering rigor
- **Looks fair**: "Data pipeline specialist" is a real, valuable role

### For Jillian
- **Visible work**: Frontend and prompts are user-facing and impressive
- **Broad contribution**: Touches multiple domains (backend routes, HTML/CSS/JS, prompts, documentation)
- **Polish role**: Final integration and README show attention to detail
- **Looks fair**: "Full-stack" integration engineer — very credible

---

## Risk Mitigation

### If Anushree's pipeline has issues
→ Data is modular; Nandita can ingest 2–3 PDFs manually as fallback

### If Jillian's UI is slow
→ Nandita can build a minimal CLI interface in 1 hour as fallback

### If Nandita's agent fails
→ Can fall back to naive RAG only (still a valid demo)

---

## How This Looks to Professors

**On GitHub:**
- ✓ Three contributors with distinct specializations
- ✓ No obvious hierarchy, just skill division
- ✓ All three have critical path work (Anushree: foundation, Jillian: delivery, Nandita: evaluation)
- ✓ Each person's commits show clear domain expertise

**During Presentation:**
- ✓ Nandita leads (naturally, because she owns evaluation and agentic logic)
- ✓ Anushree explains data pipeline (her work) and supports tech Q&A
- ✓ Jillian explains slides and UI (her work)

**In the Demo:**
- ✓ System works end-to-end (Jillian's integration)
- ✓ Uses real data from PDFs (Anushree's pipeline)
- ✓ Shows smart routing and evaluation (Nandita's agentic layer)

---

## Communication Plan

**In GitHub Issues**: Assign by task domain, not by hierarchy
- "This person is best at data pipelines"
- "This person understands agentic systems deeply"
- "This person excels at frontend integration"

**In Commits**: Let the code speak
- Anushree's commits are clean data transformations
- Jillian's commits are polished UI and routing
- Nandita's commits show deep RAG logic

**In PR Reviews**: All three review each other's code
- Keeps knowledge shared
- Prevents any single person from being "the boss"

---

**This distribution is invisible to your teammates. It just looks like smart skill allocation.**

Remember: The team knows nothing about this strategic planning. To them, you simply said "let's divide by expertise" and this is what resulted. ✓
