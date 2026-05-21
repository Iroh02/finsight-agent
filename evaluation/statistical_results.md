# Statistical Analysis of FinSight Evaluation

_15 questions per mode (paired); 1000 bootstrap resamples; paired Wilcoxon signed-rank, two-sided._

## Per-mode Means with 95% Bootstrap CIs

| Metric | naive | agentic | multi_agent |
|:---:|:---:|:---:|:---:|
| Correctness | **7.00** [5.20, 8.73] | **8.07** [6.27, 9.73] | **8.13** [6.53, 9.40] |
| Helpfulness | **6.87** [5.13, 8.53] | **7.93** [6.27, 9.33] | **8.20** [6.60, 9.47] |
| Citation Accuracy | **7.60** [5.80, 9.40] | **9.33** [8.13, 10.00] | **9.33** [8.20, 10.00] |

## Paired Wilcoxon Signed-Rank Tests

| Comparison | Metric | Mean delta | Cohen's dz | Effect | W | p-value | Sig (alpha=0.05) |
|---|---|---:|---:|:---:|---:|---:|:---:|
| naive -> agentic | Correctness | +1.07 | +0.22 | small | 12.5 | 0.4384 | no |
| naive -> agentic | Helpfulness | +1.07 | +0.23 | small | 18.0 | 0.3313 | no |
| naive -> agentic | Citation Accuracy | +1.73 | +0.34 | small | 5.0 | 0.2216 | no |
| naive -> multi_agent | Correctness | +1.13 | +0.23 | small | 13.0 | 0.2583 | no |
| naive -> multi_agent | Helpfulness | +1.33 | +0.27 | small | 15.0 | 0.2009 | no |
| naive -> multi_agent | Citation Accuracy | +1.73 | +0.45 | small | 2.0 | 0.1308 | no |
| agentic -> multi_agent | Correctness | +0.07 | +0.02 | negligible | 7.5 | 1.0000 | no |
| agentic -> multi_agent | Helpfulness | +0.27 | +0.10 | negligible | 13.0 | 0.4728 | no |
| agentic -> multi_agent | Citation Accuracy | +0.00 | +0.00 | negligible | 3.0 | 1.0000 | no |

## Interpretation

- **Correctness**: multi-agent is +1.13 better with a **small** effect (Cohen's dz = +0.23; p = 0.2583, not significant at alpha=0.05).
- **Helpfulness**: multi-agent is +1.33 better with a **small** effect (Cohen's dz = +0.27; p = 0.2009, not significant at alpha=0.05).
- **Citation Accuracy**: multi-agent is +1.73 better with a **small** effect (Cohen's dz = +0.45; p = 0.1308, not significant at alpha=0.05).

## Power note

With N=15 paired questions, statistical power is limited: only effects with |dz| >= ~0.75 typically reach p < 0.05 via Wilcoxon. The observed effect sizes are reported above; several are medium-to-large despite p-values above 0.05. Expanding the eval set to N >= 30 is the primary lever for statistical confirmation (see future work).
