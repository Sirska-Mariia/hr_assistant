# Scope and business logic: Nordlight HR Assistant

## Goal
An assistant that answers employee questions about HR procedures from a small collection of company policies, always names its
sources, tracks leave requests in a database, and refers to HR whenever the policies do not support an answer.
Fictional company: Nordlight Software. Six policies (data/policies/): leave, sick leave, onboarding, benefits, remote work, internal requests.

## Users
Employees of the company (10 seeded employees: different contract types, start dates and balances). The employee is identified by the
session, never by what the message says.

## In scope
1. Policy questions (English or Ukrainian): retrieve the relevant sections, answer briefly, cite file + section number.
2. Leave requests: annual, sick and unpaid leave. The assistant collects type and dates, the LLM calls tools (balance, submit, list),
   the rules engine approves or declines, the decision is stored in SQLite.
3. Referral: if the policies do not cover the question (or only part of it), the assistant says so and points to HR. Partial answers
   get an HR note for the uncovered part.
4. Basic conversation handling: clarifying questions (asked once), short follow-ups, replies in the employee's language.

## Out of scope
Parental/maternity leave, study leave, salary and pay, legal or disciplinary matters, anything not about HR. Such questions must be
referred to HR (or refused if unrelated to HR). No approval workflow with managers: requests that follow the rules are approved
automatically, exceptions go to HR outside the system.

## Leave rules (implemented in code, src/hr_assistant/leave/rules.py)
| Rule | Value |
|---|---|
| Allowances per year | annual 20, sick 10, unpaid 10 working days |
| Notice | annual and unpaid: 5 working days (counted from the submission day); sick: none, can be recorded up to 3 days late |
| Probation | first 3 months: no annual leave (sick and unpaid allowed) |
| Limits | annual: max 10 working days per request; blackout periods (last 7 days of Mar/Jun/Sep, 21-31 Dec) for annual leave |
| Conflicts | no overlap with own approved leave; balance must cover the working days |
| Eligibility | full-time employees only; contractors are not covered |
| Roles | managers and HR staff follow the same rules; nobody can approve their own exception |
| Working days | Mon-Fri, excluding 1 Jan, 7 Jan, 25 Dec |

## Information collection
- Leave: the collector extracts action (book / balance / status), leave type and dates; if something is missing it asks, in the
  employee's language (type first, then dates). Facts already known from the employee record (contract type, start date, probation) are
  never asked.
- Policy questions: the assistant asks one clarifying question only when the question names no concrete topic ("What is the limit?").

## Data decision
Existing public datasets were checked first (Hugging Face: syncora/hr-policies-qa-dataset, ai-training-datasets/hr,
adarsh-08/hr-policy-dataset). They are small sets of generic question-answer pairs or conversations. None is a policy corpus with section
ids, none contains leave rules or employee records, so they cannot support the metrics this task asks for: retrieval of the right
section, source support of an answer, correct referral to HR and correct leave decisions. We therefore wrote our own six policies,
a seeded database, and labelled evaluation sets (data/eval/).

## Success criteria (metrics per component, see docs/results_final.md)
Router: accuracy, macro-F1. Collector: slot accuracy, missing-slot F1, clarification accuracy. Retrieval: hit@k, MRR.
Rewriter: retrieval hit@3 with and without rewriting. Sufficiency: precision/recall of "not covered". Answerer: correctness
(key facts), citation hit, unsupported-claim rate. Verifier: precision/recall of catching unsupported answers. HR referral: precision,
recall, fabrication rate. Leave: decision accuracy against the rules (no LLM), end-to-end decision accuracy and argument fidelity
(with LLM), no invalid writes. Conversation: multi-turn success. Baseline: vanilla RAG on the same questions, plus ablations.

## Known limits
One free model (self-judged evaluation), small evaluation sets, a policy corpus of 31 sections, seeds (blackouts, holidays) that cover
Nov 2026 to mid 2027.
