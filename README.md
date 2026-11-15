# HR Assistant (NLP Assignment 1)

Fictional company: Nordlight Software. Multi-component HR assistant (policy Q&A with citations + leave requests via DB tools).

## Setup
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # add OPENROUTER_API_KEY; LLM_MODEL; LLM_REASONING=off|low|default
pip install -e .
python -m hr_assistant.leave.db   # create and seed data/hr.db
pytest
```

## Evals
```bash
python evals/run_router.py
python evals/run_collector.py                      # test set
python evals/run_collector.py collector_dev.jsonl  # dev set (used to verify prompt fixes)
python evals/run_router.py router_hard.jsonl       # hard cases with conversation context
python evals/run_dialogues.py                      # multi-turn conversations
python evals/run_verifier.py                       # verifier on labelled supported/unsupported answers
python evals/run_sufficiency.py                    # sufficiency check in isolation
python evals/run_rewriter.py                       # follow-up rewriter: retrieval with vs without rewriting
python evals/run_retrieval.py                      # bm25 / dense / hybrid (no LLM)
python evals/run_leave_rules.py                    # deterministic leave rules (no LLM)
python evals/run_leave_e2e.py                      # leave flow through the LLM + DB tools
python evals/run_qa.py                             # baseline vs full vs ablations (many LLM calls)
```

## Run the app
```bash
streamlit run app/streamlit_app.py
```
Results are saved to `evals/results/`.
