---
name: add-component
description: Add a new pipeline component (router, collector, retriever, ...) with typed I/O, tests, eval stub and CRISP-DM log entry.
---
1. Read AGENTS.md and docs/diagram.md for the component's purpose, input and output.
2. Create src/hr_assistant/<name>.py with a dataclass for input/output and a one-line purpose docstring.
3. If it calls a model, use llm.chat(..., component="<name>") and put the prompt in prompts/<name>.md.
4. Add tests/test_<name>.py: at least 3 normal cases and 2 edge cases, LLM mocked where possible.
5. Create evals/run_<name>.py (use the write-eval skill) and run it.
6. Append a decision entry to docs/crisp_dm.md (Modeling phase).
7. Report: files changed, test result, eval numbers.
