# FinSight Agent - Team Setup Guide

Welcome to the FinSight Agent project! 🚀

This guide will walk you through cloning the repo, setting up your local environment, and getting started with your assigned work.

---

## Step 1: Clone the Repository

```bash
git clone https://github.com/Iroh02/finsight-agent.git
cd finsight-agent
```

**Repo**: https://github.com/Iroh02/finsight-agent

---

## Step 2: Set Up Your Local Environment

### Create Virtual Environment

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- FastAPI & Uvicorn (backend)
- LangChain (RAG framework)
- Chroma & FAISS (vector stores)
- OpenAI SDK
- PDF processing tools
- Data science libraries

---

## Step 3: Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and add your API keys:

```
OPENAI_API_KEY=sk-your-key-here
# OR use Anthropic
ANTHROPIC_API_KEY=sk-ant-your-key-here

EMBEDDING_MODEL=openai
LLM_MODEL=gpt-4o-mini
VECTOR_STORE_TYPE=chroma
```

---

## Step 4: Understand the Project Structure

```
finsight-agent/
├── src/                 ← Core RAG pipeline
│   ├── loader.py        ← PDF extraction
│   ├── cleaner.py       ← Text cleaning
│   ├── chunker.py       ← Chunking strategy
│   ├── embedder.py      ← Embeddings
│   ├── vectorstore.py   ← Vector DB setup
│   ├── retriever.py     ← Retrieval logic
│   ├── naive_rag.py     ← Baseline RAG
│   ├── agent.py         ← Agentic routing (4-state)
│   ├── citations.py     ← Citation extraction
│   ├── confidence.py    ← Confidence scoring
│   └── pipeline.py      ← End-to-end orchestrator
│
├── app/                 ← FastAPI backend + UI
│   ├── main.py          ← FastAPI app
│   ├── routes/          ← API endpoints
│   ├── schemas.py       ← Data models
│   ├── static/          ← CSS & JavaScript
│   └── templates/       ← HTML interface
│
├── prompts/             ← LLM prompt templates
│   ├── query_rewriter.txt
│   ├── retrieval_decision.txt
│   ├── answer_generator.txt
│   ├── source_explanation.txt
│   ├── insufficient_evidence.txt
│   └── confidence_scorer.txt
│
├── evaluation/          ← Evaluation framework
│   ├── test_questions.csv
│   ├── eval_script.py
│   └── analysis.ipynb
│
├── data/                ← Data directory
│   ├── raw/             ← Original PDFs
│   └── processed/       ← Extracted text
│
└── docs/                ← Documentation
    ├── architecture.md
    ├── data_pipeline.md
    └── demo_script.md
```

---

## Step 5: Read the Key Documentation

**Start here** (in order):
1. `README.md` — Project overview (5 min)
2. `QUICKSTART.md` — Day-by-day workflow (10 min)
3. `docs/architecture.md` — System design (15 min)
4. `GITHUB_ISSUES.md` — All tasks and acceptance criteria (20 min)

---

## Step 6: Find Your Assigned Issues

Go to: **[GitHub Issues](https://github.com/Iroh02/finsight-agent/issues)**

Look for issues with your name in the description. Use the **Labels** filter to find your work:

**Anushree**: Filter by `owner: anushree`
- Data pipeline (PDFs → embeddings → vector store)
- Milestone 1: Complete by end of Day 1

**Nandita**: Filter by `owner: nandita`
- Agentic decision layer + evaluation
- Test questions + repo setup
- Milestone 1–3: Throughout project

**Jillian**: Filter by `owner: jillian`
- FastAPI backend + HTML/CSS/JS frontend
- Prompt templates
- Slides
- Milestone 2–3: Day 2 onward

---

## Step 7: Get Your First Task

### For Anushree (Data Pipeline)

**Day 1 Focus**: Complete Milestone 1
- Issue #1: Collect annual report PDFs
- Issue #2: PDF extraction + cleaning
- Issue #3: Chunking pipeline
- Issue #4: Vector store + embeddings

Start with: `src/loader.py` and `data/raw/`

**Test your work**:
```bash
python src/pipeline.py --ingest
```

### For Nandita (Agentic Logic + Evaluation)

**Day 1 Focus**: Complete Milestone 1
- Issue #5: Naive RAG baseline
- Issue #6: Test questions (10–15)
- Issue #7: GitHub repo setup (mostly done)
- Issue #8: Prompt templates draft

Start with: `src/naive_rag.py` and `evaluation/test_questions.csv`

**Test your work**:
```bash
python src/pipeline.py --query "What was the revenue?" --mode naive
```

### For Jillian (Frontend + Integration)

**Day 1 Focus**: Draft Milestone 2
- Issue #8: Finalize prompt templates

**Day 2 Focus**: Complete Milestone 2
- Issue #12: FastAPI app (`app/main.py`)
- Issue #13: Frontend UI (`app/static/`, `app/templates/`)
- Issue #14: Finalize prompts
- Issue #15: End-to-end integration test

Start with: `app/main.py` and `app/static/`

**Test your work**:
```bash
uvicorn app.main:app --reload
# Visit http://localhost:8000
```

---

## Step 8: Git Workflow

### Create a Feature Branch

```bash
git checkout -b feature/your-name-task-name
```

Examples:
```bash
git checkout -b feature/anushree-ingestion
git checkout -b feature/nandita-agent
git checkout -b feature/jillian-ui
```

### Commit Your Work

```bash
git add .
git commit -m "feat: brief description of what you added"
```

Examples:
```bash
git commit -m "feat: implement PDF loader with pdfplumber"
git commit -m "feat: implement agentic 4-state router"
git commit -m "feat: add FastAPI backend and HTML UI"
```

### Push to GitHub

```bash
git push -u origin feature/your-branch-name
```

### Create a Pull Request

Go to GitHub → Pull Requests → New PR
- Compare: `master` ← `feature/your-branch`
- Link to issue: "Closes #N"
- Request review from Nandita
- Add labels

---

## Step 9: Daily Workflow

### Morning
1. Check GitHub issues assigned to you
2. Create/checkout your feature branch
3. Read acceptance criteria for your task
4. Start coding

### Afternoon
1. Test your work locally
2. Commit progress
3. Push to GitHub

### Evening
1. Create PR and request review
2. Check PR feedback (if any)
3. Prepare for next day

### Nightly Sync (Suggested)
- Quick standup: 5 min
- Share blockers: 2 min
- Plan next day: 3 min

---

## Testing Locally

### Test Vector Store
```bash
python -c "
from src.vectorstore import get_vectorstore
vs = get_vectorstore()
results = vs.similarity_search('revenue', k=5)
print(f'Found {len(results)} chunks')
"
```

### Test Naive RAG
```bash
python src/pipeline.py --query "What was the revenue?" --mode naive
```

### Test FastAPI
```bash
uvicorn app.main:app --reload
# Visit http://localhost:8000
```

### Test Evaluation
```bash
python evaluation/eval_script.py --mode both
```

---

## Common Issues & Solutions

| Problem | Solution |
|---------|----------|
| "Module not found" | Make sure you're in repo root and venv is activated |
| OpenAI API error | Check `.env` has valid `OPENAI_API_KEY` |
| Port 8000 already in use | Change port: `uvicorn app.main:app --port 8001` |
| PDF extraction fails | Check PDF is readable; try PyPDF2 instead of pdfplumber |
| Vector store not found | Run ingestion first: `python src/pipeline.py --ingest` |

---

## Questions?

- Check `README.md` for project overview
- Check `docs/architecture.md` for system design
- Check `QUICKSTART.md` for workflow details
- Open a GitHub issue if blocked
- Ask in daily sync

---

## Timeline Reminder

- **Day 1 (Today - May 9)**: Foundation & data pipeline
- **Day 2 (May 10)**: Agentic RAG + UI
- **Day 3 (May 11)**: Evaluation + presentation

---

## You're Ready! 🚀

1. ✅ Clone repo
2. ✅ Set up venv + install dependencies
3. ✅ Configure `.env`
4. ✅ Read `QUICKSTART.md`
5. ✅ Find your issues on GitHub
6. ✅ Create feature branch
7. ✅ Start building!

**Good luck, team! Let's build something great.** 💪
