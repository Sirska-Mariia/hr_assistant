# Evaluation iterations (numbers copied from evals/results; model: inclusionai/ling-3.2-flash:free, reasoning=off from v2)

| Component | Metric | v3 | v4 | What changed / why |
|---|---|---|---|---|
| Router (60, easy) | accuracy | 1.00 | 1.00 | set too easy (saturated) |
| Router hard (22-23, with context) | accuracy | 0.909 (n=22) | 0.913 (n=23) | 2 misses are ambiguous gold labels (h20, h22) |
| Collector test (22) | all slots correct (leave, n=14) | 0.929 | 0.929 | c02 "next Friday": model reads it as the Friday of next week; gold = nearest upcoming Friday (convention) |
| Collector test | policy clarification accuracy / recall | 0.875 / 0.75 | 1.00 / 1.00 | prompt: clarify only topic-less questions, with examples (c17 fixed) |
| Collector dev (13 -> 18) | all correct | 0.889 | 1.00 | dev cases from UI testing added (not used as test) |
| Retrieval hybrid (40) | hit@3 / MRR | 0.95 / 0.908 | 1.00 / 0.958 | skip BM25 when it has no lexical overlap |
| Retrieval hybrid, Ukrainian (5) | hit@3 | 0.60 | 1.00 | same fix (BM25 noise on Cyrillic) |
| Dialogues (8) | success | 0.75 | 1.00 | contextual router, collector-first follow-ups, rewriter, UK synonyms |
| Leave rules, no LLM (20) | decision accuracy | 1.00 | 1.00 | deterministic code vs hand-written expectations |
| Leave e2e (20) | decision accuracy | 1.00 | 0.95 | regression: "I'm sick today." routed as a policy question (fixed in prompt, h24 added) |
| Verifier (26) | accuracy | 0.962 | 1.00 | run-to-run variance of the free model (one false reject in v1) |
| Sufficiency (41 -> 45) | accuracy | 0.976 | 1.00 | partial coverage added (q14 was partial) |
| QA full (45) | referral F1 | - | 0.909 | failures: q05, q36 wrongly referred; n14 clarified instead of referred |
| QA full | correctness / citation hit / unsupported / fabrication | - | 0.931 / 0.897 / 0.037 / 0.0 | |
| QA baseline (vanilla RAG) | correctness / citation hit / unsupported / fabrication | - | 1.00 / 0.0 / 0.241* / 0.0 | *inflated: judge saw only gold chunks; fixed in the runner |

Notes for the report: the vanilla baseline did not hallucinate with this model (it abstained on 15/16 uncovered questions), so the honest
advantage of the full system is sources, explicit referral/partial handling, verification and the leave module, not raw correctness.
