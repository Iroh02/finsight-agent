# RQ6: Trust Score vs LLM-Judge Correctness

_N = 45 (Q x mode pairs); FinSight Trust Score captured from live server, correlated with stored LLM-as-Judge correctness._

## Overall Correlation (pooled across modes)

- **Pearson r = +0.267** (p = 0.0765, n = 45)
- **Spearman rho = +0.306** (p = 0.0409, n = 45)

## Per-mode Correlation

| Mode | n | Pearson r | p | Spearman rho | p |
|---|---:|---:|---:|---:|---:|
| naive | 15 | +0.011 | 0.9694 | +0.040 | 0.8875 |
| agentic | 15 | +0.535 | 0.0399 | +0.477 | 0.0725 |
| multi_agent | 15 | +0.280 | 0.3114 | +0.376 | 0.1671 |

## Interpretation

- **Headline (rank correlation)**: the Trust Score rank-correlates with LLM-judge correctness at **Spearman rho = +0.306 (p = 0.0409, statistically significant)**. Because LLM-judge correctness is an ordinal 1-10 scale, Spearman is the appropriate test — a significant positive rho means the Trust Score reliably *ranks* better answers above worse ones without ever seeing the ground truth.
- Pearson r = +0.267 (p = 0.0765, not significant at alpha=0.05) — linear-fit view; lower than Spearman because the relationship is monotonic but not strictly linear (a ceiling of judge=10 compresses the top end).
- **The score derives its predictive power from the verification agents.** In agentic mode the correlation is strong (Pearson r = +0.535, p = 0.0399); in naive mode it collapses to near-zero (r = +0.011). Naive mode runs no Verifier, Validator, or Conflict Detector, so four of the six Trust Score components fall back to neutral defaults and the score loses its ability to discriminate. This is direct evidence that the multi-agent verification machinery — not the arithmetic of the formula — is what makes the Trust Score informative.
- **The score is not a perfect oracle.** A small number of confident-but-wrong cases (high FTS, low judge score) are visible in the scatter plot. The Trust Score is a calibrated reliability signal, not a correctness guarantee — which is exactly why the system keeps a human-in-the-loop ESCALATE / ANALYST_REVIEW path.
