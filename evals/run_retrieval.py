"""Eval: retrieval. Compares bm25 / dense / hybrid on data/eval/retrieval.jsonl.

Metrics: hit@1/3/5 (any gold chunk in top-k), MRR (first gold chunk), recall@5 (share of gold chunks found).
Also reports English vs Ukrainian queries separately (policies are in English).
Run: python evals/run_retrieval.py [bm25 dense hybrid]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from evals.common import load_jsonl, save_results  # noqa: E402
from hr_assistant.retriever import Retriever  # noqa: E402

CYR = re.compile(r"[а-яіїєґ]", re.I)


def evaluate(mode: str, cases: list[dict]) -> tuple[dict, list[dict]]:
    r = Retriever(mode=mode)
    rows, failures = [], []
    for c in cases:
        ids = [h.chunk.id for h in r.search(c["text"], k=5)]
        gold = set(c["gold"])
        rank = next((i + 1 for i, x in enumerate(ids) if x in gold), None)
        rows.append({"lang": "uk" if CYR.search(c["text"]) else "en", "rank": rank,
                     "recall5": len(gold & set(ids)) / len(gold)})
        if rank is None or rank > 3:
            failures.append({"id": c["id"], "text": c["text"], "gold": c["gold"], "top5": ids, "rank": rank})

    def agg(rs: list[dict]) -> dict:
        n = len(rs)
        hit = lambda k: sum(1 for x in rs if x["rank"] and x["rank"] <= k) / n
        return {"n": n, "hit@1": round(hit(1), 3), "hit@3": round(hit(3), 3), "hit@5": round(hit(5), 3),
                "mrr": round(sum(1 / x["rank"] for x in rs if x["rank"]) / n, 3),
                "recall@5": round(sum(x["recall5"] for x in rs) / n, 3)}

    return {"all": agg(rows), "en": agg([x for x in rows if x["lang"] == "en"]),
            "uk": agg([x for x in rows if x["lang"] == "uk"])}, failures


def main() -> None:
    modes = sys.argv[1:] or ["bm25", "dense", "hybrid"]
    cases = load_jsonl("retrieval.jsonl")
    all_metrics = {}
    for mode in modes:
        try:
            metrics, failures = evaluate(mode, cases)
        except ImportError as e:
            print(f"{mode}: skipped ({e})")
            continue
        all_metrics[mode] = metrics
        print(f"{mode:7s}", {k: v for k, v in metrics["all"].items()}, "| uk:", metrics["uk"])
        save_results(f"retrieval_{mode}", metrics, failures, "n/a (no LLM)")
        for f in failures[:3]:
            print("   miss:", f)


if __name__ == "__main__":
    main()
