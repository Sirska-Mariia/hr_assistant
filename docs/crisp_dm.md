# CRISP-DM log

## 1. Business understanding
Employees ask repetitive HR questions and request leave. Goal: answer from policies with sources, track leave in a database, refer to HR
when the policies do not support an answer. Success = correct, source-supported answers, correct referrals, correct leave decisions,
no invented rules. Details and out-of-scope items: docs/scope.md.

## 2. Data understanding
Six fictional policies (~1350 words, 31 numbered sections, citations as "file §n.m"). Built in on purpose: condition-dependent rules
(probation, contract type), gaps that no policy covers (parental leave, relocation, stock options, salary), and multi-section answers.
Public HR Q&A datasets were checked and not used (see docs/scope.md). Seeded database: 10 employees, balances, blackout periods and
two approved requests used for overlap tests.

## 3. Data preparation
Policies split into section chunks with item ids. Evaluation sets built by hand (frozen; changes only for domain reasons):
router 60 + hard 25, collector 22 + dev 18, retrieval 40, QA 45 (29 covered, 5 of them partial, 16 not covered), leave 20, dialogues 8,
verifier 26, rewriter 12. Test sets are not edited to fit results; prompt fixes are checked on dev/hard sets.

## 4. Modeling
Router -> (rewriter) -> collector -> hybrid retriever (BM25 + multilingual MiniLM, RRF) -> sufficiency (full/partial/none) -> answerer
-> verifier (code + LLM, one retry) for policy questions; collector -> leave agent -> tools -> rules.py -> SQLite for leave.
Baseline: vanilla RAG (top-3 chunks, one call). One model for every number: ling-3.2-flash (free, OpenRouter), reasoning off.

## 5. Evaluation (three rounds; numbers in docs/results_v1_v2.md and docs/results_final.md)
Round 1: first numbers. Findings: hybrid hurt Ukrainian queries (BM25 noise on Cyrillic); multi-turn failures seen in manual UI
testing (bare replies re-routed, English questions for Ukrainian users, lost leave type, generic refusal to "I am HR").
Round 2: contextual router, collector-first follow-ups, language-aware questions, BM25 skipped without overlap, partial coverage,
rewriter, study leave removed (the company has no parental leave either). Findings: over-clarification, verifier flagging "the policies
do not say X", wrong year in dates, employee context replacing the asked rule.
Round 3 (final): verifier ignores absence statements and context-based claims, answerer rules, year normalisation, follow-ups never get
a clarifying question. Everything with an LLM was rerun with one configuration. Remaining errors are documented, not hidden:
c02 ("next Friday" convention), h20/h22 (ambiguous gold labels), h06 (short reply to our question, covered in the pipeline), n14
(clarification instead of referral), judge limits (same model, employee-context facts counted as unsupported).

## 6. Deployment
Streamlit app (app/streamlit_app.py) with employee switch, sources, step trace and a database view; setup and run commands in README.md;
every model call is logged to logs/llm_calls.jsonl (tracing). Deliverables: code, docs/diagram.png, docs/scope.md, evaluation results,
demo video.

## Decisions log
- State machine instead of an agent framework; SQLite; the LLM reaches the database only through tools; the employee id comes from the
  session; approve/decline is deterministic code.
- Router label "policy_question" covers any HR topic, so the referral decision belongs to the sufficiency check.
- Study leave removed to keep the domain consistent. Eval items that mentioned it were rewritten, not tuned.
- LLM_REASONING=off for all numbers (JSON tasks, fewer rate-limit problems).
- The UI shows the real current date; evals use a fixed date (2026-11-16) for reproducibility.
