---
name: update-report
description: Refresh docs/report.md after new eval results, keeping tables and error analysis consistent.
---
1. Read the newest files in evals/results/.
2. Update the metrics table (component, metric, value, n, date) in docs/report.md.
3. Update the error analysis: what failed, why scores are not higher, what to try next.
4. If a change was made after evaluation, add it to the CRISP-DM iteration section.
5. Do not change numbers by hand; copy from the results files.
