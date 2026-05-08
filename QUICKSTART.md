# FinSight Agent - Quick Start Guide

## First Steps (Before Day 1 Starts)

### 1. Create GitHub Repository
- Create public repo `finsight-agent`
- Add 3 collaborators (all three team members)
- Create 3 milestones: "Milestone 1", "Milestone 2", "Milestone 3"
- Create labels (see `GITHUB_ISSUES.md` for full list)

### 2. Clone & Set Up Local Environment
```bash
# Clone repo (adjust URL)
git clone https://github.com/your-username/finsight-agent.git
cd finsight-agent

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (macOS/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy env template
cp .env.example .env

# Edit .env with your API keys
# OPENAI_API_KEY=sk-...
```

### 3. Create GitHub Issues
Use `GITHUB_ISSUES.md` to create all 23 issues. Each issue has:
- Assignee (Nandita, Jillian, or Anushree)
- Labels
- Milestone
- Description with acceptance criteria

```bash
# Or use GitHub CLI for quick creation
gh issue create --title "Issue title" --body "Description" --assignee @username
```

---

## Day 1 Workflow

### Jillian's Tasks (Data Pipeline)
**Time**: Full day  
**Issues**: #1–4, #16 (docs)

```bash
# Create feature branch
git checkout -b feature/jillian-ingestion

# Work on:
# 1. src/loader.py - PDF extraction
# 2. src/cleaner.py - Text cleaning
# 3. src/chunker.py - Chunking strategy
# 4. src/vectorstore.py + src/embedder.py - Embeddings & vector store
# 5. data/raw/ - Collect and place PDFs

# When done, create PR and request review from Nandita
git add .
git commit -m "feat: implement PDF ingestion pipeline"
git push -u origin feature/jillian-ingestion
```

**Deliverables by end of Day 1**:
- 5–10 PDFs in `data/raw/`
- Working ingestion pipeline
- Vector store populated with ~1000+ chunks
- Vectors searchable with `similarity_search(query, k=5)`

---

### Anushree's Tasks (RAG & Evaluation)
**Time**: Full day  
**Issues**: #5–6, #8

```bash
# Create feature branch
git checkout -b feature/anushree-rag

# Work on:
# 1. src/naive_rag.py - Baseline RAG (doesn't need LLM yet, can placeholder)
# 2. evaluation/test_questions.csv - 10–15 test questions
# 3. Review Nandita's prompt templates and provide feedback

# When done, create PR
git add .
git commit -m "feat: implement naive RAG baseline and test questions"
git push -u origin feature/anushree-rag
```

**Deliverables by end of Day 1**:
- `src/naive_rag.py` working with vector store
- 10–15 test questions in CSV
- Prompt templates reviewed and ready

---

### Nandita's Tasks (Repo Setup & Integration)
**Time**: Morning + integration  
**Issues**: #7–8

```bash
# Create feature branch
git checkout -b feature/nandita-repo-setup

# Work on:
# 1. Set up GitHub repo (labels, milestones, branch protection)
# 2. Create initial prompt templates in prompts/
# 3. Review all team members' code as PRs come in
# 4. Keep README updated

# Coordinate with team for integration tests
git add .
git commit -m "docs: add prompt templates and repo setup"
git push -u origin feature/nandita-repo-setup
```

**Deliverables by end of Day 1**:
- GitHub repo fully configured
- All 6 prompt templates created
- README skeleton complete
- Integration checkpoint: naive RAG works with vector store

---

## Day 2 Workflow

### Anushree's Tasks (Agentic Layer)
**Time**: Full day  
**Issues**: #9–11, #17 partial

```bash
# Create feature branch
git checkout -b feature/anushree-agent

# Work on:
# 1. src/agent.py - 4-state agentic router
# 2. src/citations.py - Citation extraction
# 3. src/confidence.py - Confidence scoring
# 4. Integrate with Nandita's FastAPI routes

# Test against vector store and test questions
git add .
git commit -m "feat: implement agentic decision layer and citation logic"
git push -u origin feature/anushree-agent
```

**Deliverables by end of Day 2**:
- `AgenticRouter.route_and_answer(question)` working
- Citations extracted and formatted
- Confidence scores computed
- Integrated with FastAPI

---

### Nandita's Tasks (FastAPI + Frontend)
**Time**: Full day  
**Issues**: #12–15

```bash
# Create feature branch
git checkout -b feature/nandita-ui

# Work on:
# 1. app/main.py - FastAPI app
# 2. app/routes/query.py - POST /query endpoint
# 3. app/schemas.py - Pydantic models
# 4. app/templates/index.html - Frontend HTML
# 5. app/static/css/style.css - Styling
# 6. app/static/js/app.js - Frontend logic

# Test locally: uvicorn app.main:app --reload
git add .
git commit -m "feat: implement FastAPI backend and HTML/CSS/JS frontend"
git push -u origin feature/nandita-ui
```

**Deliverables by end of Day 2**:
- FastAPI app running at `localhost:8000`
- Web interface works with backend
- Demo-ready UI with all components

---

### Jillian's Tasks (Documentation)
**Time**: Morning + slide prep  
**Issues**: #16, #20 partial

```bash
# Create feature branch
git checkout -b feature/jillian-slides

# Work on:
# 1. docs/data_pipeline.md - Detailed explanation
# 2. notebooks/01_data_pipeline.ipynb - Walkthrough notebook
# 3. Begin slides draft (all 10 slides)

git add .
git commit -m "docs: add data pipeline documentation and slides draft"
git push -u origin feature/jillian-slides
```

**Deliverables by end of Day 2**:
- Documentation complete
- Slide draft with all 10 slides
- Notebook demonstrating ingestion

---

## Day 3 Workflow

### Anushree's Tasks (Evaluation)
**Time**: Morning + analysis  
**Issues**: #17–19

```bash
# Feature branch from Day 2 or new: feature/anushree-evaluation

# Work on:
# 1. evaluation/eval_script.py - Run evaluation
# 2. evaluation/results_naive.csv - Naive RAG results
# 3. evaluation/results_agentic.csv - Agentic RAG results
# 4. Generate comparison chart
# 5. Write results analysis

# Run evaluation
python evaluation/eval_script.py --mode both

git add .
git commit -m "eval: run full evaluation and analysis"
git push
```

**Deliverables by end of Day 3**:
- Evaluation results (CSV for both RAG types)
- Comparison table with 6 metrics
- Bar chart comparing naive vs agentic
- Written analysis of results

---

### Nandita's Tasks (Final Integration & Polish)
**Time**: Throughout Day 3  
**Issues**: #21–23

```bash
# Coordinate merges and final integration
# Issues: #21 (README), #22 (demo), #23 (cleanup)

# Work on:
# 1. Final README review and polish
# 2. Demo script writing (docs/demo_script.md)
# 3. Team rehearsal (2x full run-through)
# 4. Final code review of all PRs
# 5. Merge all branches: dev → main
# 6. Repo cleanup

# Final checklist:
# - All tests passing
# - No uncommitted changes
# - README complete
# - Slides polished
# - Demo script locked
# - All 23 issues closed

git add .
git commit -m "docs: final README and demo script"
git push

# Final merge
git checkout main
git merge --no-ff dev
git push
```

**Deliverables by end of Day 3**:
- Working end-to-end system
- Polished presentation slides
- Demo script with talking points
- Clean GitHub repo with all issues closed
- Final report ready

---

### Jillian's Tasks (Slides & Demo Support)
**Time**: Morning + demo  
**Issues**: #20, #22 support

```bash
# Finalize slides
# Work on all 10 slides with Nandita

# Responsibilities in demo:
# - Intro: Speak on slides 2–3 (problem + objective)
# - Demo: Support Nandita with technical Q&A
# - Help rehearse full presentation

git add .
git commit -m "docs: finalize presentation slides"
git push
```

**Deliverables**:
- Final slides (10 slides, polished)
- Prepared for Q&A
- Ready to present

---

## Git Workflow Best Practices

### Branching
```bash
# Always create feature branch
git checkout -b feature/owner-task

# Keep branches focused on single feature
# e.g., feature/jillian-ingestion, feature/anushree-agent

# Merge into dev when ready
git checkout dev
git merge --no-ff feature/owner-task
```

### Commits
```bash
# Clear, descriptive messages
git commit -m "feat: add PDF loader with pdfplumber"
git commit -m "fix: resolve chunk overlap issue"
git commit -m "docs: add architecture documentation"
```

### Pull Requests
```bash
# Create PR to dev (not main)
git push -u origin feature/owner-task

# On GitHub:
# 1. Open PR
# 2. Link to relevant issue: "Closes #N"
# 3. Request review from Nandita
# 4. Nandita merges after review
```

### Final Merge to Main
```bash
# Only Nandita does this on Day 3 evening
git checkout main
git merge --no-ff dev
git push
```

---

## Testing Locally

### Check FastAPI is working
```bash
uvicorn app.main:app --reload

# Visit http://localhost:8000
# Should see HTML interface
# Should see /docs with Swagger UI
```

### Check vector store is working
```bash
python -c "from src.vectorstore import get_vectorstore; vs = get_vectorstore(); results = vs.similarity_search('revenue', k=5); print(f'Found {len(results)} chunks')"
```

### Check RAG pipeline
```bash
python src/pipeline.py --query "What was the total revenue in 2023?" --mode agentic
```

### Run evaluation
```bash
python evaluation/eval_script.py --mode both
```

---

## Communication & Checkpoints

### Daily Standups (Suggested)
- **Morning** (9:00 AM): 5-min sync on blockers
- **Afternoon** (3:00 PM): Integration checkpoint
- **Evening** (5:00 PM): Day wrap-up and next-day plan

### Use GitHub for Async Communication
- Comments on PRs and issues for technical discussions
- GitHub Issues for blockers
- Update issue status: `In Progress` → `Ready for Review` → `Done`

### Nandita's Role
- Approve and merge PRs
- Coordinate integration
- Review final deliverables
- Ensure timeline stays on track

---

## Emergency Fallbacks

If you get blocked:

**Jillian's PDFs fail to load**
→ Use pre-chunked text from PDF-to-text online tool or provide Nandita with 3 PDFs to manually ingest

**Embedding API fails**
→ Switch to HuggingFace (`all-MiniLM-L6-v2`) in `src/embedder.py`

**LLM API fails**
→ Use HuggingFace `google/flan-t5-base` or Claude 3 Haiku via Anthropic SDK

**Agentic layer too complex**
→ Simplify to 3-state router: ANSWER / RETRIEVE / REFUSE

**Not enough time for full evaluation**
→ Reduce test questions from 15 to 10 and focus on key metrics

---

## Success Criteria for Submission

✓ GitHub repo is public and clean  
✓ FastAPI app runs locally without errors  
✓ HTML/CSS/JS frontend loads and works  
✓ Vector store populated with chunks  
✓ Naive RAG baseline answers questions  
✓ Agentic RAG with 4-state router  
✓ Citations displayed for each answer  
✓ Confidence scores shown  
✓ Evaluation on 10+ questions complete  
✓ Comparison table (naive vs agentic)  
✓ 10-minute presentation slides ready  
✓ Demo script finalized and rehearsed 2x  
✓ README complete with setup instructions  
✓ All 23 GitHub issues closed  

---

**Ready? Start with creating the GitHub repo and issues. Good luck! 🚀**
