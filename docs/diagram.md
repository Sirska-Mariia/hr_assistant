# System diagram and components

```mermaid
flowchart TD
    U[Employee message] --> P{Pending leave question?}
    P -- yes --> C0[Collector: fill slots]
    C0 -- slot found --> L
    C0 -- nothing new --> R
    P -- no --> R[Router LLM, sees previous assistant message]
    R -- out_of_scope --> X[Refusal, EN/UK]
    R -- leave_request --> L[Collector: slots + action, ask in user's language]
    L -- missing slot --> Q[Clarifying question]
    L -- complete --> A[Leave agent LLM]
    A -- tool call --> T[(Tools: balance / submit / list)]
    T --> RU[rules.py: deterministic approve or decline]
    RU --> DB[(SQLite)]
    R -- policy_question --> RW[Rewriter LLM: short follow-up to standalone question]
    RW --> C1[Collector: vague question?]
    C1 -- vague, ask once --> Q
    C1 -- ok --> RT[Hybrid retriever: BM25 + dense, RRF]
    RT --> S[Sufficiency LLM]
    S -- none --> H[HR referral]
    S -- full or partial --> AN[Answerer LLM, cited sections]
    AN --> V[Verifier: code + LLM]
    V -- unsupported, retry once --> AN
    V -- still unsupported --> H
    V -- supported --> OUT[Answer with sources, plus HR note if partial]
```

| Component | Purpose | Input -> Output | Model call / tool |
|---|---|---|---|
| Router | Intent: policy / leave / out of scope | message + previous assistant message -> label | LLM |
| Collector | Extract leave slots (type, dates, action), flag vague policy questions | message, known slots -> slots, missing, question | LLM + code validation |
| Retriever | Find relevant policy sections | question -> top-k section chunks | BM25 + sentence-transformers (no generation) |
| Rewriter | Make a short follow-up self-contained | message + previous turn -> standalone question | LLM |
| Sufficiency | How well do excerpts cover the question: full / partial / none | question, chunks -> coverage | LLM |
| Answerer | Short grounded answer with citations | question, chunks, employee context -> text + citations | LLM |
| Verifier | Every claim supported by cited text? | answer, cited items -> supported? | code (citation exists) + LLM |
| Leave agent | Book / check leave only through tools | message, slots -> reply + tool calls | LLM + tools |
| Rules engine | Approve / decline by policy | request, balance, calendar -> decision + reason | deterministic code |

Walkthrough ("Can I work from abroad?"): router -> policy_question; collector -> not vague; retriever -> remote_work.md#3 first;
sufficiency -> covered; answerer -> "up to 20 working days per year, 10 days notice" citing remote_work.md §3.1, §3.2;
verifier -> supported; the UI shows the answer and the cited items.
