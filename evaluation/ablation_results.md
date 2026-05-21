# FinSight Ablation Study

_Each variant re-runs the multi-agent pipeline over 15 test questions with one component disabled. Metrics are LLM-judge-free (heuristic faithfulness, Trust Score, latency) for reproducibility._

## Per-variant Means

| Variant | Faithfulness | Trust Score | Latency (s) | Answer rate | Correct abstention |
|---|---:|---:|---:|---:|---:|
| full | 0.600 | 73.8 | 18.7 | 60% | 80% |
| no_reranker | 0.600 | 77.3 | 14.6 | 60% | 80% |
| no_temporal | 0.600 | 74.2 | 15.3 | 60% | 80% |
| no_verifier | 0.600 | 75.6 | 9.5 | 60% | 80% |
| no_conflict | 0.600 | 73.9 | 14.0 | 53% | 73% |

## Delta vs Full Pipeline (removing each component)

| Removed component | Faithfulness Δ | Trust Score Δ | Latency Δ |
|---|---:|---:|---:|
| reranker | +0.000 | +3.5 | -4.1s |
| temporal | +0.000 | +0.4 | -3.5s |
| verifier | +0.000 | +1.8 | -9.3s |
| conflict | +0.000 | +0.1 | -4.8s |

## Interpretation

A negative faithfulness / trust delta means **removing that component hurt quality** — i.e. the component was contributing. A negative latency delta means that component **costs time**; the trade-off is the value it adds against the seconds it spends.
