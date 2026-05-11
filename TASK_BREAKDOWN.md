# 📋 Final Task Breakdown — Who Does What

> **Project due TODAY by 8 PM.** Pick from the menus below.

---

## ⏱️ Time Budgets by Path

| Path | Anushree | Jillian | Nandita | Total Team Effort |
|------|----------|---------|---------|------------------|
| **Minimum** | ~1 hour | ~2 hours | ~1 hour | ~4 hours |
| **Good** | ~2.5 hours | ~3.5 hours | ~1.5 hours | ~7.5 hours |
| **Excellent** | ~4 hours | ~5 hours | ~2 hours | ~11 hours |

---

# 🔴 NANDITA (Project Lead)

## ⚡ Status
Already done: data pipeline, naive RAG, agentic router, multi-agent system, reranker, self-reflection, HyDE, parallel execution, streaming, PDF upload, citations, confidence, FastAPI, frontend, Jillian's merge, Gemini support.

## ✅ Remaining Tasks

### **CRITICAL (1.5 hours)**

| # | Task | Time | Notes |
|---|------|------|-------|
| **(no#)** | Run 3-way evaluation script | 30 min | Produces 3 CSVs for Anushree |
| **#25** | Write demo script + rehearsal | 60 min | docs/demo_script.md |

### **OPTIONAL (1 hour)**

| Task | Time | Why |
|------|------|-----|
| Final repo cleanup | 20 min | Close stray issues |
| Add 1 more SOTA myself | 30-45 min | E.g., CoVe (#36) if Anushree doesn't |
| Take screenshots for slides | 15 min | Give to Jillian |

---

# 🔵 ANUSHREE (Evaluation + SOTA)

## ⚡ What She's Doing
Evaluation, comparison analysis, and high-impact SOTA additions.

## 🎯 MINIMUM PATH (1 hour)

| # | Task | Time | Dependencies |
|---|------|------|-------------|
| **#28** | Compile 3-way evaluation results table | 30 min | Needs Nandita's CSVs |
| **#30 help** | Help review Jillian's docs | 15 min | None |

**Result**: Project submits with complete evaluation section. ✅

---

## ⭐ GOOD PATH (2.5 hours)

Add to minimum:

| # | Task | Time | Why |
|---|------|------|-----|
| **#31** | RAGAS evaluation library | 45 min | Research-standard metrics |
| **#32** | LLM-as-Judge evaluation | 30 min | Cite Zheng et al., 2023 |

**Result**: Publication-quality evaluation section.

---

## 🏆 EXCELLENT PATH (4 hours)

Add to good:

| # | Task | Time | Why |
|---|------|------|-----|
| **#36** | Chain-of-Verification (CoVe) | 45 min | Hallucination detection - new agent |
| **#38** | Error analysis dashboard | 45 min | Categorize failures by type |

**Result**: Research-paper grade analysis.

---

## ⚠️ AVOID (touches shared files)

- ~~#33 Hybrid Search~~ (changes retriever — coordinate with Jillian)
- ~~#37 Query Expansion~~ (changes retriever)

---

## 📂 Files Anushree Creates

```
evaluation/
├── ragas_eval.py         (#31)
├── llm_judge.py          (#32)
├── error_analysis.ipynb  (#38)
├── results_naive.csv     ← Nandita produces
├── results_agentic.csv   ← Nandita produces
├── results_multi_agent.csv ← Nandita produces
└── comparison_table.md   (#28 - her output)

src/agents/
└── verifier.py           (#36 - new 5th agent)

docs/
└── evaluation_results.md (#28 final writeup)
```

---

# 🟢 JILLIAN (Slides + Pipeline SOTA)

## ⚡ What She's Doing
Slides (critical), data pipeline documentation, pipeline SOTA improvements.

## 🎯 MINIMUM PATH (2 hours)

| # | Task | Time | Output |
|---|------|------|--------|
| **#29** | 10-slide presentation | 90 min | `slides/finsight_presentation.pdf` |
| **#30** | Data pipeline docs | 30 min | `docs/data_pipeline.md` |

**Result**: Project submits with slides + pipeline credit. ✅

---

## ⭐ GOOD PATH (3.5 hours)

Add to minimum:

| # | Task | Time | Why |
|---|------|------|-----|
| **#44** | Add 5+ more PDFs (Microsoft, Tesla, etc.) | 30 min | Demo variety |
| **#41** | Conversation history sidebar | 30 min | ChatGPT-style UX |

**Result**: Polished system with multi-doc demo.

---

## 🏆 EXCELLENT PATH (5 hours)

Add to good:

| # | Task | Time | Why |
|---|------|------|-----|
| **#45** | Parent-Child Chunking | 60 min | Real SOTA technique |
| **#47** | Stats dashboard doc | 30 min | Research polish |

**Result**: Publication-worthy pipeline contribution + polished demo.

---

## 🌟 ALTERNATIVE TRACKS for Jillian

### **Track A: Pipeline SOTA** (her domain)
- #44 More PDFs
- #45 Parent-Child Chunking
- #46 Semantic Chunking
- #47 Stats Dashboard
- #48 Metadata Enrichment

### **Track B: UI Polish** (visible in demo)
- #40 PDF export of reasoning
- #41 Conversation history
- #42 Citation hover
- #34 Multi-turn memory

### **Track C: Documentation**
- #30 Data pipeline docs
- #47 Stats dashboard
- Help write final report

---

## ⚠️ AVOID (conflicts)

- ~~#35 Contextual compression~~ if doing #45 (both change retriever)
- Multiple chunker changes (#45, #46) at the same time

---

## 📂 Files Jillian Creates

```
slides/
└── finsight_presentation.pdf  (#29)

docs/
├── data_pipeline.md            (#30)
└── dataset_stats.md            (#47)

data/raw/
├── Microsoft_10K.pdf            (#44)
├── Tesla_10K.pdf                (#44)
├── Google_10K.pdf               (#44)
└── ...etc

src/
├── parent_child_chunker.py     (#45)
├── semantic_chunker.py         (#46)
└── metadata_extractor.py       (#48)

app/
├── routes/export.py            (#40)
├── static/js/app.js (modify)   (#41, #42)
└── ...
```

---

# 📊 Parallel Execution Plan

## Phase 1: First Hour (everyone in parallel)

```
🔴 NANDITA:
   - Run 3-way evaluation script → produces CSVs
   - Push CSVs to master

🔵 ANUSHREE:
   - Set up local env, get Gemini key
   - Start #31 RAGAS (independent task)

🟢 JILLIAN:
   - Set up local env, get Gemini key
   - Start #30 Pipeline docs (independent)
   - OR start #29 slides
```

## Phase 2: Hour 2-3 (parallel)

```
🔴 NANDITA:
   - Write demo script (#25)
   - Help review PRs

🔵 ANUSHREE:
   - Finish #31 RAGAS
   - Start #28 compile (now has CSVs!)
   - Start #32 LLM-as-Judge

🟢 JILLIAN:
   - Continue slides (#29)
   - Add more PDFs (#44) - 30 min
   - Start #45 Parent-Child Chunking
```

## Phase 3: Final 2 hours

```
🔴 NANDITA:
   - Review all PRs
   - Merge to master
   - Final integration testing
   - Demo rehearsal

🔵 ANUSHREE:
   - #36 CoVe (if time)
   - #38 Error analysis
   - Submit PR

🟢 JILLIAN:
   - Finish slides
   - #41 Conversation history (if time)
   - Submit PRs
```

---

# 🚦 Coordination Rules

## File Ownership (avoid conflicts)

| File | Owner | Who else can touch |
|------|-------|------|
| `src/retriever.py` | Nandita (current owner) | ONE person at a time |
| `src/chunker.py` | Jillian | Anushree avoid |
| `src/multi_agent.py` | Nandita | Don't touch |
| `app/routes/query.py` | Nandita | Don't touch |
| `evaluation/*` | Anushree | Free to work |
| `slides/*` | Jillian | Free |
| `docs/*` | Anyone | Coordinate per file |

## Branch Naming

```bash
# Anushree
feature/anushree-eval
feature/anushree-ragas
feature/anushree-cove

# Jillian
feature/jillian-slides
feature/jillian-pdfs
feature/jillian-parentchild
feature/jillian-history
```

## Merge Order

1. Anushree's eval CSVs first
2. Jillian's docs/slides
3. Pipeline changes (one at a time)
4. UI changes
5. Nandita merges everything to master in batches

---

# ⏰ Suggested Schedule (if starting NOW)

```
00:00 - 00:30  ⏱️ Nandita runs eval, pushes CSVs
               ⏱️ Anushree sets up
               ⏱️ Jillian sets up

00:30 - 01:30  📝 Jillian writes slides (90 min)
               📊 Anushree: #28 compile + #31 RAGAS
               📋 Nandita: writes demo script

01:30 - 02:30  📝 Jillian: continues slides + #30 docs
               📊 Anushree: #32 LLM-Judge + #36 CoVe
               📋 Nandita: reviews PRs

02:30 - 03:30  📝 Jillian: #44 more PDFs + #45 parent-child
               📊 Anushree: #38 error analysis
               📋 Nandita: integration testing

03:30 - 04:30  ✨ All: final polish + PRs
               🎤 Nandita: demo rehearsal

04:30 - 05:00  🚀 SUBMIT
```

---

# 🎯 Submission Checklist

By submission time (8 PM):

- [ ] Master branch is clean
- [ ] Slides PDF in `slides/`
- [ ] Evaluation results CSVs in `evaluation/`
- [ ] `docs/data_pipeline.md` exists
- [ ] `docs/demo_script.md` exists
- [ ] README polished
- [ ] All critical issues closed
- [ ] Demo rehearsed at least 2x

---

**Questions?** Ask in the GitHub issue comments or group chat.

**GitHub**: https://github.com/Iroh02/finsight-agent
