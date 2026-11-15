---
name: write-eval
description: Create or update an evaluation script for one component with proper metrics and saved results.
---
1. Load the labelled set from data/eval/<component>.jsonl. Never modify it.
2. Metrics by component: router = accuracy, macro-F1, confusion matrix; collector = field-completeness %,
   unnecessary questions; retriever = recall@k, MRR (BM25 vs dense vs hybrid); sufficiency/referral = precision,
   recall on out-of-scope; answer = correctness (LLM judge, 1-5 rubric + 20 manual labels for agreement);
   source support = % claims backed by a cited section; leave = % correct decisions, 0 invalid DB writes.
3. Print a table and save JSON to evals/results/<component>_<date>.json (include model name, n, metrics).
4. List the 5 worst failures with input, expected, actual, and a hypothesis why.
5. Never report a single number without n.
