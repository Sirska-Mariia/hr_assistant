# AGENTS.md — HR Assistant (NLP Assignment 1)

## Project goal
Multi-component HR assistant for a fictional company (Nordlight Software). NOT a vanilla RAG:
router -> info collection -> hybrid retrieval -> sufficiency check -> cited answer -> source verifier,
plus a leave module where the LLM only calls DB tools and deterministic code decides.

## Process: CRISP-DM (mandatory)
Phases: 1 Business understanding, 2 Data understanding, 3 Data preparation, 4 Modeling, 5 Evaluation, 6 Deployment.
- Log each phase in docs/crisp_dm.md with a dated checkpoint (what was decided, why).
- Do not start a phase before the previous checkpoint is written.
- After Evaluation, write what changes in the next iteration (do not skip the loop).

## Hard rules
- A component is NOT done until it has: unit tests, an eval script in evals/, results in evals/results/.
- Never edit data/eval/*.jsonl without explicit permission (no tuning on the test set).
- All LLM calls go through src/hr_assistant/llm.py (one model config, retries, JSONL logging).
- The LLM never touches the database directly: only functions in leave/tools.py.
  Approve/decline comes from leave/rules.py. Employee id is bound to the session, never a model argument.
- Answers must cite policy file + section number (e.g. leave.md §3.2). No supporting citation -> route to HR.
- Never invent policy content. Policies live only in data/policies/.
- Prompts live in src/hr_assistant/prompts/ as files, not inline strings.

## Code style
- Python 3.11, type hints, small functions, English docstrings.
- Each component has a typed input/output and a one-line purpose in its docstring.
- No new dependencies without asking.

## Workflow
1. Before coding: restate the plan in 3-5 lines and wait for OK.
2. After coding: run `pytest` and the relevant eval; report the numbers.
3. Prefer the skills in skills/ (add-component, write-eval, update-report, crisp-dm-checkpoint).
4. Keep a short decisions log in docs/crisp_dm.md.

## Context management
- Read only AGENTS.md, the target component, and its tests before editing.
- Policies and eval data are loaded from files; never paste whole policies into prompts for code tasks.

## Evaluation hygiene
- Use ONE model config for every reported number (LLM_MODEL + LLM_REASONING); it is saved in each results file.
- Fix prompts on failures, but verify on a separate dev/hard set, never by editing the frozen test set.
- If a set scores 1.0 it is too easy: add harder cases before claiming success.
