# FinSight Agent - GitHub Issues Template

Create the following 23 issues in your GitHub repository. Use this template for all issues:

**Labels**: Apply appropriate labels from the list:
- `priority: critical` - blocks demo or submission
- `priority: high` - core feature needed for eval  
- `priority: medium` - important but not blocking
- `type: feature` - new functionality
- `type: bug` - bug fix
- `type: docs` - documentation
- `type: eval` - evaluation work

---

## Milestone 1: Data + Retrieval Ready (Due: End of Day 1)

### Issue #1: Collect Annual Report PDFs
**Assignee**: Anushree  
**Labels**: `priority: critical`, `type: feature`  
**Description**:
- Collect 5–10 public annual report PDFs (S&P 500 companies recommended)
- Store in `data/raw/`
- Document sources and accessibility in README
- Suggested companies: Apple, Microsoft, Tesla, Amazon, Google, Meta, etc.
- Verify PDFs are readable and contain substantive financial/business information

**Acceptance Criteria**:
- [ ] 5–10 PDFs collected and stored in `data/raw/`
- [ ] Each PDF is readable and ~100+ pages
- [ ] Sources documented in README

---

### Issue #2: Implement PDF Extraction and Cleaning
**Assignee**: Anushree  
**Labels**: `priority: critical`, `type: feature`  
**Description**:
Implement PDF text extraction with cleaning:
- Use `pdfplumber` for structured extraction (fallback: `PyPDF2`)
- Extract page-by-page with metadata (filename, page number)
- Remove headers, footers, page numbers using regex
- Normalize whitespace and hyphenation artifacts
- Implement in `src/loader.py` and `src/cleaner.py`

**Acceptance Criteria**:
- [ ] `src/loader.py::PDFLoader.extract_text()` works
- [ ] `src/cleaner.py::clean_text()` removes artifacts
- [ ] Test on 2–3 PDFs from `data/raw/`

---

### Issue #3: Implement Chunking Pipeline
**Assignee**: Anushree  
**Labels**: `priority: critical`, `type: feature`  
**Description**:
Implement text chunking strategy:
- Use `LangChain RecursiveCharacterTextSplitter`
- Chunk size: ~500 tokens, overlap: ~50 tokens
- Preserve source metadata (document, page) per chunk
- Implement in `src/chunker.py`

**Acceptance Criteria**:
- [ ] `src/chunker.py::chunk_text()` produces chunks
- [ ] Chunks preserve source metadata
- [ ] Overlap is working correctly

---

### Issue #4: Set Up Vector Store and Embeddings
**Assignee**: Anushree  
**Labels**: `priority: critical`, `type: feature`  
**Description**:
- Implement embedding pipeline (`src/embedder.py`)
- Support OpenAI (`text-embedding-ada-002`) and HuggingFace (`all-MiniLM-L6-v2`)
- Set up vector store (`src/vectorstore.py`): Chroma or FAISS
- Persist vector store in `data/chroma/` or `data/faiss/`
- Ingest chunked documents from Issue #3

**Acceptance Criteria**:
- [ ] Embeddings generated for all chunks
- [ ] Vector store populated and searchable
- [ ] `vectorstore.similarity_search(query, k=5)` returns results

---

### Issue #5: Implement Naive RAG Baseline
**Assignee**: Nandita  
**Labels**: `priority: critical`, `type: feature`  
**Description**:
Implement baseline RAG without agentic layer:
- Retrieve top-5 chunks for query
- Concatenate into context
- Pass to LLM with basic Q&A prompt
- Return answer only (no citations, no confidence score)
- Implement in `src/naive_rag.py`

**Acceptance Criteria**:
- [ ] `NaiveRAG.query(question)` returns answer
- [ ] Works with vector store from Issue #4
- [ ] Answer is generated (even if placeholder LLM)

---

### Issue #6: Write 10–15 Test Questions
**Assignee**: Nandita  
**Labels**: `priority: critical`, `type: eval`  
**Description**:
Create evaluation test set:
- 4–5 factual questions (e.g., "What was revenue in FY2023?")
- 3–4 comparison questions (e.g., "How did revenue change 2022→2023?")
- 2–3 reasoning questions (e.g., "What are key risks?")
- 2–3 questions that should trigger REFUSE state (out of scope)
- Add ground truth answers based on documents
- Store in `evaluation/test_questions.csv`

**Acceptance Criteria**:
- [ ] 10–15 questions in CSV with categories
- [ ] Ground truth answers documented
- [ ] Mix of question types

---

### Issue #7: GitHub Repo Setup
**Assignee**: Nandita  
**Labels**: `priority: critical`, `type: docs`  
**Description**:
- Create GitHub repository
- Add branch protection on `main` (require PR review)
- Create labels: `priority: critical`, `priority: high`, `priority: medium`, `type: feature`, `type: bug`, `type: docs`, `type: eval`
- Create 3 milestones: Milestone 1/2/3
- Add `.gitignore`, `requirements.txt`, `.env.example`
- Create initial directory structure

**Acceptance Criteria**:
- [ ] Repo exists with all structure
- [ ] Labels created
- [ ] Milestones created
- [ ] Base files in place

---

### Issue #8: Draft Prompt Templates v1
**Assignee**: Jillian  
**Labels**: `priority: high`, `type: docs`  
**Description**:
Create initial prompt templates in `prompts/`:
- `query_rewriter.txt` - Rephrase ambiguous queries
- `retrieval_decision.txt` - 4-state routing logic
- `answer_generator.txt` - Generate grounded answers
- `source_explanation.txt` - Map claims to chunks
- `insufficient_evidence.txt` - Graceful refusal
- `confidence_scorer.txt` - Confidence assessment

**Acceptance Criteria**:
- [ ] All 6 prompt files created
- [ ] Prompts have clear instructions
- [ ] Placeholders for inputs marked with {variable}

---

## Milestone 2: Agentic RAG + UI Ready (Due: End of Day 2)

### Issue #9: Implement Agentic 4-State Decision Layer
**Assignee**: Nandita  
**Labels**: `priority: critical`, `type: feature`  
**Description**:
Implement agentic router with 4 states:
- **ANSWER**: Sufficient context → generate answer
- **RETRIEVE**: Marginal context → expand to k=10
- **CLARIFY**: Ambiguous query → ask user
- **REFUSE**: No relevant context → abstain

Implement in `src/agent.py`:
- Decision logic using prompt `retrieval_decision.txt`
- Integration with retriever from Issue #4
- Ability to expand retrieval if needed

**Acceptance Criteria**:
- [ ] `AgenticRouter.route_and_answer(question)` works
- [ ] Returns decision + reason + chunks
- [ ] ANSWER state generates answer
- [ ] REFUSE state returns graceful abstention

---

### Issue #10: Implement Source Citation Logic
**Assignee**: Nandita  
**Labels**: `priority: critical`, `type: feature`  
**Description**:
Map answer claims to source chunks:
- Use LLM-assisted extraction with `source_explanation.txt`
- Link each answer claim to specific chunk + document + page
- Handle multiple citations per claim
- Implement in `src/citations.py`

**Acceptance Criteria**:
- [ ] `CitationExtractor.extract_citations(answer, chunks)` returns list
- [ ] Citations include source, page, excerpt
- [ ] Works with test answers from eval script

---

### Issue #11: Implement Confidence Scoring
**Assignee**: Nandita  
**Labels**: `priority: high`, `type: feature`  
**Description**:
Score answer confidence 0.0–1.0:
- Heuristic approach: Based on decision state + chunk count
  - ANSWER: 0.7–1.0
  - RETRIEVE: 0.4–0.6
  - CLARIFY: 0.1
  - REFUSE: 0.0
- Optional LLM-assisted: Use `confidence_scorer.txt` for more nuanced scoring
- Implement in `src/confidence.py`

**Acceptance Criteria**:
- [ ] `ConfidenceScorer.score(answer, chunks, decision)` returns 0.0–1.0
- [ ] Heuristic version working
- [ ] Optional LLM version scaffolded

---

### Issue #12: Build FastAPI App Skeleton
**Assignee**: Jillian  
**Labels**: `priority: critical`, `type: feature`  
**Description**:
Set up FastAPI backend:
- `app/main.py`: FastAPI app initialization
- `app/routes/query.py`: POST `/query` endpoint
- `app/routes/health.py`: GET `/health` endpoint
- `app/schemas.py`: Pydantic request/response models
- Mount static files (CSS, JS)
- Serve `index.html` on root

**Acceptance Criteria**:
- [ ] `uvicorn app.main:app` runs without errors
- [ ] `/` serves HTML
- [ ] `/docs` shows Swagger UI
- [ ] `/health` responds with `{"status": "ok"}`

---

### Issue #13: Build Frontend UI (HTML/CSS/JS)
**Assignee**: Jillian  
**Labels**: `priority: critical`, `type: feature`  
**Description**:
Create frontend interface:
- `app/templates/index.html`: Single-page HTML
  - Question input box
  - Answer display area
  - Confidence badge (color-coded)
  - Citation list (expandable)
  - Chunk viewer (expandable)
  - Decision state label
  - Sidebar: document selector, mode toggle
  
- `app/static/css/style.css`: Clean, professional styling
  - Two-column layout (sidebar + main)
  - Card-based design for answer/citations/chunks
  - Color-coded confidence badges
  - Mobile responsive
  
- `app/static/js/app.js`: Frontend logic
  - Fetch to POST `/query`
  - Dynamic rendering of response
  - Mode toggle (agentic vs naive)
  - Error handling and loading states

**Acceptance Criteria**:
- [ ] HTML renders without errors
- [ ] CSS styling complete
- [ ] JS fetch calls work (even if no backend)
- [ ] UI responsive on desktop/mobile

---

### Issue #14: Finalize Prompt Templates
**Assignee**: Jillian  
**Labels**: `priority: high`, `type: feature`  
**Description**:
Refine and optimize all 6 prompts:
- Review based on initial testing
- Adjust instructions for clarity
- Add examples if needed
- Ensure all placeholders are clearly marked
- Test with sample questions/contexts

**Acceptance Criteria**:
- [ ] All prompts reviewed and refined
- [ ] Tested with sample inputs
- [ ] Ready for LLM integration

---

### Issue #15: Full End-to-End Integration Test
**Assignee**: Jillian  
**Labels**: `priority: critical`, `type: feature`  
**Description**:
Integrate all modules (pipeline → agent → UI):
- Connect `src/pipeline.py` to `app/routes/query.py`
- Test POST `/query` with sample question
- Verify full flow: retrieval → routing → generation → response
- Debug any integration issues

**Acceptance Criteria**:
- [ ] POST `/query` returns complete response
- [ ] Response includes: answer, decision, reason, confidence, citations, chunks
- [ ] UI renders response correctly
- [ ] At least 1 question works end-to-end

---

### Issue #16: Data Pipeline Documentation
**Assignee**: Anushree  
**Labels**: `priority: high`, `type: docs`  
**Description**:
Document data ingestion process:
- `docs/data_pipeline.md`: Architecture and decisions
  - PDF sources and accessibility
  - Cleaning strategy and artifacts removed
  - Chunking decisions (size, overlap)
  - Embedding choice rationale
  - Vector store choice (Chroma vs FAISS)
- `notebooks/01_data_pipeline.ipynb`: Walkthrough notebook
  - Load 1 PDF → extract → clean → chunk → embed → ingest
  - Show statistics (total pages, chunks, dimensions)

**Acceptance Criteria**:
- [ ] `docs/data_pipeline.md` written
- [ ] Notebook demonstrates full ingestion
- [ ] Clear explanations of design choices

---

## Milestone 3: Evaluation + Presentation Ready (Due: End of Day 3)

### Issue #17: Run Full Evaluation
**Assignee**: Nandita  
**Labels**: `priority: critical`, `type: eval`  
**Description**:
Run evaluation on all test questions:
- Execute `evaluation/eval_script.py`
- Query both naive and agentic RAG on all 10–15 questions
- Score each response on:
  - Answer relevance (1–5)
  - Faithfulness (1–5)
  - Citation accuracy (0/1)
  - Correct abstention (0/1)
  - Completeness (1–5)
  - Clarity (1–5)
- Generate `results_naive.csv` and `results_agentic.csv`

**Acceptance Criteria**:
- [ ] All test questions evaluated
- [ ] Naive RAG results in CSV
- [ ] Agentic RAG results in CSV
- [ ] Scores computed for all criteria

---

### Issue #18: Compile Evaluation Results Table
**Assignee**: Nandita  
**Labels**: `priority: critical`, `type: eval`  
**Description**:
Create comparison results:
- Aggregate scores from Issue #17
- Create comparison table:
  ```
  | Metric | Naive RAG | Agentic RAG | Improvement |
  |--------|-----------|-------------|-------------|
  | Avg Relevance | X.X | X.X | +X.X |
  | Avg Faithfulness | X.X | X.X | +X.X |
  | Citation Accuracy | X% | X% | +X% |
  | Correct Abstention | X% | X% | +X% |
  ```
- Create comparison bar chart (matplotlib/seaborn)
- Prepare for final report and slides

**Acceptance Criteria**:
- [ ] Comparison table created
- [ ] Bar chart generated
- [ ] Results summarized (1–2 key findings)

---

### Issue #19: Write Results Analysis
**Assignee**: Nandita  
**Labels**: `priority: high`, `type: docs`  
**Description**:
Write analysis section for final report:
- Interpret evaluation results (200–300 words)
- Explain where agentic RAG outperforms naive
- Discuss any surprising results
- Note limitations and caveats
- Suggest future improvements

**Acceptance Criteria**:
- [ ] Analysis written and spell-checked
- [ ] Clear conclusions from data
- [ ] Ready for final report

---

### Issue #20: Complete Slides Draft
**Assignee**: Jillian (KEPT - same as original)  
**Labels**: `priority: critical`, `type: docs`  
**Description**:
Create all 10 presentation slides:
1. Title Slide
2. Problem Statement
3. Project Objective
4. System Architecture
5. Implementation Details
6. Agentic Decision Layer
7. Live Demo (with screenshots)
8. Evaluation & Results
9. Takeaways & Limitations
10. Conclusion

- Use clean, consistent design
- Include diagrams/screenshots where helpful
- Keep text minimal (speaker notes)
- Ensure readable on projector

**Acceptance Criteria**:
- [ ] All 10 slides created
- [ ] Content complete and spell-checked
- [ ] Visuals included (diagrams, charts)
- [ ] Ready for review

---

### Issue #21: Final README Polish
**Assignee**: Jillian  
**Labels**: `priority: high`, `type: docs`  
**Description**:
Review and finalize README.md:
- Verify setup instructions work
- Update tech stack if any changes
- Add team contributions section
- Ensure all sections complete
- Add screenshots/GIFs if possible
- Spell-check and grammar review

**Acceptance Criteria**:
- [ ] README complete and accurate
- [ ] Setup instructions tested
- [ ] All sections present
- [ ] Visually polished

---

### Issue #22: Demo Script and Rehearsal
**Assignee**: Nandita (lead - technical coordination)  
**Labels**: `priority: critical`, `type: docs`  
**Description**:
Prepare demo script and practice:
- Write detailed demo script (`docs/demo_script.md`)
- Choose 2–3 demo questions (mix of decision types)
- Prepare talking points for each slide
- Assign speaking roles to team members
- Rehearse full presentation 2x
- Time the demo (target: 10 minutes)

**Acceptance Criteria**:
- [ ] Demo script written
- [ ] Demo questions chosen
- [ ] Full rehearsal completed 2x
- [ ] All team members comfortable with roles

---

### Issue #23: Repo Cleanup and Final Merge
**Assignee**: Nandita (final integration lead)  
**Labels**: `priority: critical`, `type: docs`  
**Description**:
Final repository preparation:
- Close all completed issues
- Merge all feature branches into `dev`
- Merge `dev` → `main` for final submission
- Remove any placeholder comments
- Verify no uncommitted changes
- Final code review of all modules
- Ensure all deliverables present:
  - ✓ Working FastAPI + HTML/CSS/JS app
  - ✓ Vector store populated
  - ✓ Naive + agentic RAG working
  - ✓ Evaluation results
  - ✓ Presentation slides
  - ✓ Final report
  - ✓ README complete

**Acceptance Criteria**:
- [ ] All issues closed
- [ ] All branches merged
- [ ] Final code review passed
- [ ] No uncommitted changes
- [ ] Ready for submission

---

## How to Create Issues in GitHub

1. Go to your GitHub repo
2. Click **Issues** → **New Issue**
3. Copy title from above
4. Copy description
5. Assign to team member
6. Add labels
7. Assign to milestone
8. Click **Submit new issue**

Or use GitHub CLI:
```bash
gh issue create --title "Issue Title" --body "Issue description" --assignee username --label "label" --milestone "Milestone 1"
```

---

## Issue Status During Development

- **Day 1 End**: Issues #1–8 should be completed
- **Day 2 End**: Issues #9–16 should be completed  
- **Day 3 End**: Issues #17–23 should be completed

Track progress using GitHub project board or milestones view.

---

**Next Steps**: Once repo is created and issues are in place, teams can start implementing independently. Use PR reviews and comments for coordination.
