"""Eval: rewriter (short follow-up -> standalone question).

Measured downstream, where it matters: does retrieval find the gold section in the top 3?
  raw        = retrieve with the follow-up as written
  rewritten  = retrieve with the rewriter's standalone question
Two groups: "followup" (needs context; rewriting should help) and "standalone" (already self-contained after an
unrelated turn; rewriting must not break it). Also reports how often a standalone message was left unchanged.
Run: python evals/run_rewriter.py [--mode hybrid|bm25|dense]     (needs the LLM)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from evals.common import load_jsonl, save_results  # noqa: E402
from hr_assistant import llm, rewriter  # noqa: E402
from hr_assistant.retriever import Retriever  # noqa: E402


def rank_of(retriever: Retriever, query: str, gold: set[str]) -> int | None:
    ids = [h.chunk.id for h in retriever.search(query, k=3)]
    return next((i + 1 for i, x in enumerate(ids) if x in gold), None)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="hybrid")
    args = ap.parse_args()
    retriever = Retriever(mode=args.mode)
    rows, failures = [], []
    for c in load_jsonl("rewriter.jsonl"):
        new_q = rewriter.rewrite(c["message"], c["last_user"], c["last_assistant"])
        gold = set(c["gold"])
        raw, rew = rank_of(retriever, c["message"], gold), rank_of(retriever, new_q, gold)
        rows.append({"kind": c["kind"], "raw": raw, "rew": rew, "unchanged": new_q.strip() == c["message"].strip()})
        if rew is None:
            failures.append({"id": c["id"], "message": c["message"], "rewritten": new_q, "gold": c["gold"]})

    def agg(kind: str) -> dict:
        rs = [r for r in rows if r["kind"] == kind]
        n = len(rs)
        return {"n": n,
                "hit@3_raw": round(sum(r["raw"] is not None for r in rs) / n, 3),
                "hit@3_rewritten": round(sum(r["rew"] is not None for r in rs) / n, 3),
                "mrr_raw": round(sum(1 / r["raw"] for r in rs if r["raw"]) / n, 3),
                "mrr_rewritten": round(sum(1 / r["rew"] for r in rs if r["rew"]) / n, 3),
                "left_unchanged": round(sum(r["unchanged"] for r in rs) / n, 3)}

    metrics = {"followup": agg("followup"), "standalone": agg("standalone")}
    path = save_results("rewriter", metrics, failures, llm.MODEL_DESC)
    print(metrics)
    for f in failures:
        print("  ", f)
    print("saved to", path)


if __name__ == "__main__":
    main()
