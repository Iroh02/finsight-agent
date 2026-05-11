# Team Update — Final Push (May 11, 2026)

## Big Picture

The technical heavy lifting is **DONE**. We have a working SOTA system:
- Multi-Agent RAG (4 specialized agents)
- Cross-encoder reranker
- Self-reflection critic
- Agentic 4-state router
- Citations + confidence scoring
- FastAPI + HTML/CSS/JS web app
- All 3 modes (naive, agentic, multi-agent) working end-to-end

Master branch is **submission-ready** with everyone's contributions merged.

## What's Left — Tasks for Final Polish

### 🔵 Anushree's Tasks
Pick these up to contribute meaningfully:

**Task A: Add Real Annual Report PDFs** — [Issue #27](https://github.com/Iroh02/finsight-agent/issues/27)
- Download 3-5 PDFs from SEC EDGAR (Apple, Microsoft, Tesla, etc.)
- Drop them in `data/raw/`
- Run `python -m src.test_pipeline` to ingest
- Push on `feature/anushree-pdfs`
- **Time**: 30 min

**Task B: Run 3-way Evaluation & Compile Results** — [Issue #28](https://github.com/Iroh02/finsight-agent/issues/28)
After Nandita updates the eval script:
1. Start server: `uvicorn app.main:app --host 127.0.0.1 --port 8001`
2. Run: `python evaluation/eval_script.py --modes naive agentic multi_agent`
3. Compile comparison table from the 3 CSV outputs
4. Generate bar chart
5. Write 1-paragraph summary
- **Time**: 30 min

### 🟢 Jillian's Tasks
You already contributed the data pipeline improvements (merged into master). To round out your contribution:

**Task C: Create 10-Slide Presentation** — [Issue #29](https://github.com/Iroh02/finsight-agent/issues/29)
- 10 slides total (see issue for structure)
- Save as PDF in `slides/finsight_presentation.pdf`
- Bonus: Include a section on your data pipeline contribution
- **Time**: 90 min

**Task D: Data Pipeline Documentation** — [Issue #30](https://github.com/Iroh02/finsight-agent/issues/30)
- Write `docs/data_pipeline.md`
- Explain your statistical header/footer detection
- This is YOUR contribution — show it off!
- **Time**: 30 min

### 🔴 Nandita's Tasks
- Run the 3-way evaluation script
- Polish README (DONE)
- Write demo script (`docs/demo_script.md`)
- Final repo cleanup

## How to Start

```bash
# 1. Pull the latest master
git checkout master
git pull

# 2. Create your feature branch
git checkout -b feature/anushree-pdfs    # for Anushree
# or
git checkout -b feature/jillian-slides   # for Jillian

# 3. Do your work, commit, push
git add .
git commit -m "your descriptive message"
git push -u origin feature/your-branch

# 4. Create a PR on GitHub
```

## Repo Status

- **Master**: Submission-ready with everyone's work merged
- **Open Issues**: #27, #28, #29, #30 (your tasks)
- **API**: Run `uvicorn app.main:app --port 8001` then visit http://127.0.0.1:8001

## Questions?

Open a GitHub issue or message the group chat.

**Timeline**: Project due TODAY. Aim to complete tasks by 8 PM.
