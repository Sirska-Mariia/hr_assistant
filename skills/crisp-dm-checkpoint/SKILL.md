---
name: crisp-dm-checkpoint
description: Check that a CRISP-DM phase is complete before moving on, and write the checkpoint entry.
---
Checklists (all items must be true):
- Business: users, scope, out-of-scope and success metrics are written in docs/scope.md.
- Data understanding: policies, gaps, conflicts and test-set plan are described.
- Data preparation: policies chunked by section id, eval sets built and frozen, DB seeded.
- Modeling: each component runs, has tests and its own eval stub.
- Evaluation: every component has results; baseline vs system compared; error analysis written.
- Deployment: app runs from README, demo scenarios are listed, report and diagram are up to date.
Then append "## Checkpoint <phase> — <date>" with decisions and open issues to docs/crisp_dm.md.
