# CRISP-DM log

## 1. Business understanding
(TODO: users, success criteria, scope, out-of-scope — fill in from docs/scope.md)

## 2. Data understanding
Six fictional policies for Nordlight Software (data/policies/), ~1350 words, numbered sections for citation.
Deliberately included: condition-dependent rules (probation, contract type), gaps not covered by any policy
(parental leave, relocation, stock options, cancellations by the system), cross-policy details that must be
combined (leave §3.2 + benefits §1.2 + onboarding §4.2).

## 3. Data preparation
(TODO: section-level chunking, eval sets)

## Decisions log
- Day 1: state machine instead of LangGraph; SQLite; employee id bound to session; rules in code, not in prompts.
- Day 2: router has 3 labels; "policy_question" covers ANY HR topic (even without a policy) so referral is decided later by the
  sufficiency check; "out_of_scope" = not HR at all. Router falls back to out_of_scope on bad output (never reaches the DB).
- Day 2: collector does not ask for facts the session already knows (contract type, start date); leave follow-up questions are
  templated by code, policy clarification questions come from the LLM.
- Day 2: eval sets frozen in data/eval/ (router: 60, collector: 22). Evals not yet run (need API key).
- Day 3 (modeling): hybrid retrieval (BM25 + multilingual MiniLM, RRF). BM25 alone: hit@3 0.90 on 40 questions but only 0.2 on the
  5 Ukrainian ones -> motivates dense/hybrid. Light plural stripping added after a failure ("employment certificate" matched the
  sick-leave section, because "certificates" != "certificate").
- Day 3: sufficiency check before answering (referral when policy does not support an answer); verifier after answering with one
  regeneration, then referral. Leave flow is an LLM tool-calling agent; employee id is bound to the session, approval is code.
- Day 3: collector fixes after eval v1 (c02 date convention, c17 generic-term clarification); verified on a separate dev set
  (data/eval/collector_dev.jsonl), not on the failing test cases.
- Offline check: leave rules vs 20 hand-written scenarios 20/20 (deterministic code, so this is a correctness check, not a model score).
- Day 3 evaluation round 1 (model: ling free, reasoning default): router 60/60, retrieval hit@3 bm25 .90 / dense .925 / hybrid .95
  (Ukrainian n=5: dense 1.0, hybrid 0.6), leave e2e 20/20, QA(full, n=12) referral F1 1.0, unsupported 0.125.
  Findings: (1) hybrid hurt Ukrainian queries because all-zero BM25 scores injected arbitrary ranks -> skip BM25 when no overlap;
  (2) manual testing showed multi-turn failures: a bare reply ("annual") was routed as a new policy question, the
  clarifying questions were English for Ukrainian users, the leave type was not remembered ("then 24-30"), and an
  "I'm HR" challenge got a generic refusal -> context-aware router, collector-first follow-ups, language-aware templates,
  one-turn leave-type carry-over, policy 4.5 extended to HR staff.
  (3) router/leave sets saturated at 1.0 -> added router_hard (22, with context) and dialogues (8) to make scores discriminative.
- Next iteration: rerun ALL LLM evals with the final config (model + LLM_REASONING=off) so every reported number uses one setup.
- Day 3 evaluation round 2 (model ling free, reasoning=off): router 60/60 (saturated) and router_hard 20/22 (both misses are ambiguous gold
  labels: "recommend a doctor" vs health insurance; authority claim + vague booking); collector dev 13/13; retrieval hybrid hit@3 1.00,
  MRR .946 (uk = dense after the BM25 zero-score fix); leave e2e 20/20; verifier acc .962 (recall 1.0, one false reject);
  sufficiency acc .976 (q14: partial coverage mislabelled as full); dialogues success .75; QA full (n=12) correctness .75.
  Findings from the UI transcripts: (1) over-clarification of policy questions ("company benefits", "money for sports", "I need a laptop");
  (2) a multi-part question with one uncovered part was refused entirely; (3) follow-ups like "but I am HR, you can check it"
  lost context; (4) the model did not map "заяву на відпустку" to annual leave.
  Changes: collector asks only for topic-less questions (few-shot), UK/EN synonyms for leave types; sufficiency returns
  full/partial/none and partial answers get an HR note; rewriter component for short follow-ups.
- Domain decision: study leave removed (the company has no parental leave either, so keeping study leave was inconsistent). Eval items about
  study leave were rewritten to unpaid/annual/sick equivalents; questions about parental leave remain HR-referral tests.
- The UI now uses the real current date. Seeds (blackouts, holiday list) cover Nov 2026 - mid 2027 and must be refreshed afterwards.
- Day 3 round 3 (new version without study leave): see docs/results_v1_v2.md. Decision: keep this version as final. Remaining errors are
  documented, not hidden: c02 (convention), h20/h22 (ambiguous labels), l08 regression (fixed by router rule + h24), q05/q36/n14 (QA; traces now saved
  in failures), judge limitation (self-judging, baseline context).
- Changes after round 3: dates asked in one question, answerer no longer says "excerpts", collector rule for qualified terms, QA judge receives
  employee context and what the baseline saw.
