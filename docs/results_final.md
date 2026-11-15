# Final evaluation results

Model: `inclusionai/ling-3.2-flash:free`, reasoning off, one config for every number. The LLM judge is the same model.
Source: latest files in `evals/results/` (15 Nov 2026). Small samples, so treat differences of one or two items as noise.

## Per component

| Component | Test set (n) | Metric | Result | Notes |
|---|---|---|---|---|
| Router | 60, easy | accuracy / macro-F1 | 1.00 / 1.00 | saturated, too easy |
| Router hard | 25, with context | accuracy / macro-F1 | 0.88 / 0.87 | h20, h22 ambiguous labels; h06 is a real miss |
| Collector, leave | 14 | all slots correct / missing-slot F1 | 0.93 / 1.00 | c02 "next Friday" convention |
| Collector, clarify | 8 | accuracy | 1.00 | |
| Collector, dev | 9 + 9 | all correct (leave / clarify) | 1.00 / 1.00 | used to check prompt fixes |
| Retrieval, hybrid | 40 | hit@3 / MRR | 1.00 / 0.96 | BM25 0.90, dense 0.93 at hit@3 |
| Retrieval, Ukrainian | 5 | hit@3 BM25 / dense / hybrid | 0.20 / 1.00 / 1.00 | BM25 fails on Cyrillic |
| Sufficiency | 45 | accuracy / uncovered F1 | 1.00 / 1.00 | small set |
| Answerer | 29 | correctness / citation hit | 1.00 / 0.97 | |
| Answerer | 29 | unsupported claims rate | 0.17 | judge flags facts from employee context |
| HR referral | 16 not covered | precision / recall / fabrication | 1.00 / 0.94 / 0.00 | n14 clarified instead of referred |
| Verifier | 26 | accuracy / false-reject rate | 1.00 / 0.00 | small set |
| Leave rules (code) | 20 | decision accuracy | 1.00 | checks the code, not a model |
| Leave e2e (LLM + DB) | 20 | decision accuracy / argument fidelity | 1.00 / 1.00 | saturated |
| Dialogues | 8 | dialogue success / turn accuracy | 0.88 / 0.94 | t05 "but I am HR" |

## Baseline vs full system, with ablations (45 questions: 29 covered, 16 not covered)

| System | Correctness | Citation hit | Unsupported | Referral recall | Fabrication | Partial flagged |
|---|---|---|---|---|---|---|
| Baseline (vanilla RAG) | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Full system | 1.00 | 0.97 | 0.17 | 0.94 | 0.00 | 1.00 |
| No verifier | 1.00 | 0.97 | 0.24 | 0.94 | 0.00 | 1.00 |
| No sufficiency | 1.00 | 0.97 | 0.24 | 0.19 | 0.125 | 0.00 |

- Correctness alone does not separate the systems. The baseline has no sources, no structured referral and no partial answers.
- The sufficiency check has the largest effect: referral recall falls from 0.94 to 0.19 and fabrication appears.
- The verifier effect (0.24 vs 0.17) is about 2 answers out of 29, within run-to-run noise.
- All 5 answers flagged unsupported in the full system contain "since your probation is finished", a fact from employee context.
- Full-system correctness over four runs ranged from 0.83 to 1.00 (free model, same judge).
