"""Eval: sufficiency check in isolation (retrieval fixed to hybrid top-4), on qa.jsonl.

Positive class = "policy does NOT cover it" (should lead to HR referral).
Metrics: accuracy, precision/recall/F1 of detecting uncovered questions, wrongly-insufficient rate on covered ones.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from evals.common import load_jsonl, save_results  # noqa: E402
from evals.metrics import prf  # noqa: E402
from hr_assistant import llm  # noqa: E402
from hr_assistant.retriever import Retriever  # noqa: E402
from hr_assistant.sufficiency import check  # noqa: E402


def main() -> None:
    cases = load_jsonl("qa.jsonl")
    retriever = Retriever()
    tp = fp = fn = tn = 0
    failures = []
    for c in cases:
        res = check(c["text"], retriever.search(c["text"], k=4))
        pred_insuff, gold_insuff = not res.sufficient, not c["answerable"]
        tp += gold_insuff and pred_insuff
        fn += gold_insuff and not pred_insuff
        fp += (not gold_insuff) and pred_insuff
        tn += (not gold_insuff) and not pred_insuff
        if pred_insuff != gold_insuff:
            failures.append({"id": c["id"], "text": c["text"], "gold_answerable": c["answerable"], "reason": res.reason})
    p, r, f = prf(tp, fp, fn)
    n = len(cases)
    metrics = {"n": n, "accuracy": round((tp + tn) / n, 3), "uncovered_precision": round(p, 3),
               "uncovered_recall": round(r, 3), "uncovered_f1": round(f, 3),
               "wrongly_insufficient_rate": round(fp / max(1, fp + tn), 3)}
    path = save_results("sufficiency", metrics, failures, llm.MODEL_DESC)
    print(metrics)
    for f_ in failures:
        print("  ", f_)
    print("saved to", path)


if __name__ == "__main__":
    main()
