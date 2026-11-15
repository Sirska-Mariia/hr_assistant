"""Eval: end-to-end policy QA, with baseline comparison and ablations.

Systems: baseline (vanilla RAG), full, no_verifier, no_sufficiency.
Metrics (positive class for referral = question NOT covered by policy):
  referral precision/recall/F1; on answerable questions: correctness (mean key-fact coverage, judge),
  citation_hit (a cited section is a gold section), unsupported_rate (judge), wrongly_referred;
  on unanswerable questions: fabrication_rate (judge).
Run: python evals/run_qa.py [baseline full no_verifier no_sufficiency] [--limit N] [--mode hybrid|bm25|dense]
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from evals.common import load_jsonl, save_results  # noqa: E402
from evals.judge import judge_answerable, judge_unanswerable  # noqa: E402
from evals.metrics import prf  # noqa: E402
from hr_assistant import llm  # noqa: E402
from hr_assistant.baseline import vanilla_rag  # noqa: E402
from hr_assistant.leave import db  # noqa: E402
from hr_assistant.pipeline import Assistant  # noqa: E402
from hr_assistant.policies import item_index  # noqa: E402
from hr_assistant.retriever import Retriever  # noqa: E402

TODAY = date(2026, 11, 16)
FLAGS = {"full": {}, "no_verifier": {"use_verifier": False}, "no_sufficiency": {"use_sufficiency": False}}


def brief(trace: list[dict]) -> list[str]:
    """Compact trace for failure reports."""
    out = []
    for t in trace:
        extra = {k: v for k, v in t.items() if k in ("label", "coverage", "supported", "needs_clarification", "hits", "reason", "unsupported")}
        out.append(f"{t['step']} {extra}")
    return out


def run_system(name: str, retriever: Retriever, conn, q: dict) -> tuple[str, str, list[str], bool, list[str]]:
    if name == "baseline":
        return "answer", vanilla_rag(q["text"], retriever), [], False, []
    resp = Assistant(conn, 2, TODAY, retriever, **FLAGS[name]).handle(q["text"])
    return resp.kind, resp.text, resp.citations, resp.partial, brief(resp.trace)


def evaluate(name: str, cases: list[dict], retriever: Retriever) -> tuple[dict, list[dict]]:
    conn = db.connect(":memory:")
    db.init_db(conn)
    chunks = {c.id: c for c in retriever.chunks}
    emp_ctx = Assistant(conn, 2, TODAY, retriever).employee_context()
    index = item_index(retriever.chunks)
    tp = fp = fn = tn = 0
    cover, cit_hit, unsupported, fabricated, wrongly_ref, clar = [], [], [], [], 0, 0
    p_total = p_flagged = 0
    failures = []
    for q in cases:
        kind, text, cites, partial, steps = run_system(name, retriever, conn, q)
        refer, clarified = kind == "referral", kind == "clarify"
        clar += clarified
        if q["answerable"] and q.get("partial"):  # policy covers only part of the question
            p_total += 1
            p_flagged += kind == "answer" and partial
        if not q["answerable"]:
            tp += refer; fn += not refer
            if not refer:
                j = judge_unanswerable(q["text"], text)
                fabricated.append(j["fabricated"])
                failures.append({"id": q["id"], "text": q["text"], "kind": kind, "answer": text[:200], "steps": steps, **j})
            continue
        fp += refer; tn += not refer
        wrongly_ref += refer
        if refer or clarified:
            cover.append(0.0); cit_hit.append(False)
            failures.append({"id": q["id"], "text": q["text"], "kind": kind, "answer": text[:200], "steps": steps})
            continue
        gold_text = "\n".join(chunks[g].cited_text() for g in q["gold"])
        cited_text = "\n".join(f"[{c}] {index[c]}" for c in cites if c in index)
        seen = "\n".join(h.chunk.cited_text() for h in retriever.search(q["text"], k=3)) if name == "baseline" else ""
        policy = f"{gold_text}\n{cited_text}\n{seen}\nEmployee context (the assistant may use it): {emp_ctx}"
        j = judge_answerable(q["text"], text, q["key_facts"], policy)
        cover.append(j["fact_coverage"]); unsupported.append(j["unsupported_claims"] > 0)
        cit_hit.append(any(f"{c.split(' §')[0]}#{c.split('§')[1].split('.')[0]}" in q["gold"] for c in cites))
        if j["fact_coverage"] < 1 or j["unsupported_claims"]:
            failures.append({"id": q["id"], "text": q["text"], "answer": text[:300], **j})
    p, r, f = prf(tp, fp, fn)
    n_a = sum(c["answerable"] for c in cases); n_u = len(cases) - n_a
    mean = lambda xs: round(sum(xs) / len(xs), 3) if xs else None
    metrics = {"n_answerable": n_a, "n_unanswerable": n_u,
               "referral": {"precision": round(p, 3), "recall": round(r, 3), "f1": round(f, 3)},
               "answerable": {"correctness": mean(cover), "citation_hit": mean(cit_hit),
                              "unsupported_rate": mean(unsupported), "wrongly_referred": round(wrongly_ref / max(1, n_a), 3)},
               "unanswerable": {"fabrication_rate": round(sum(fabricated) / max(1, n_u), 3)},
               "partial": {"n": p_total, "flagged_as_partial": round(p_flagged / p_total, 3) if p_total else None},
               "clarifications": clar}
    return metrics, failures


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("systems", nargs="*", default=["baseline", "full", "no_verifier", "no_sufficiency"])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--mode", default="hybrid")
    args = ap.parse_args()
    cases = load_jsonl("qa.jsonl")
    if args.limit:  # keep both classes represented
        ans = [c for c in cases if c["answerable"]][: args.limit]
        un = [c for c in cases if not c["answerable"]][: max(1, args.limit // 2)]
        cases = ans + un
    retriever = Retriever(mode=args.mode)
    for name in args.systems:
        metrics, failures = evaluate(name, cases, retriever)
        print(f"== {name} ==", metrics)
        save_results(f"qa_{name}", metrics, failures, llm.MODEL_DESC)


if __name__ == "__main__":
    main()
