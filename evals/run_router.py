"""Eval: router. Metrics: accuracy, macro-F1, per-class P/R/F1, confusion matrix, parse-error rate.

Run: python evals/run_router.py            (needs OPENROUTER_API_KEY)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from evals.common import load_jsonl, save_results  # noqa: E402
from evals.metrics import classification_report  # noqa: E402
from hr_assistant import llm  # noqa: E402
from hr_assistant.router import LABELS, route  # noqa: E402


def main() -> None:
    fname = sys.argv[1] if len(sys.argv) > 1 else "router.jsonl"
    cases = load_jsonl(fname)
    gold, pred, failures, parse_errors = [], [], [], 0
    for c in cases:
        res = route(c["text"], context=c.get("context"))
        gold.append(c["label"]); pred.append(res.label); parse_errors += res.parse_error
        if res.label != c["label"]:
            failures.append({"id": c["id"], "text": c["text"], "context": c.get("context"), "expected": c["label"],
                             "actual": res.label, "reason": res.reason})
    metrics = classification_report(gold, pred, list(LABELS))
    metrics["parse_error_rate"] = round(parse_errors / len(cases), 3)
    path = save_results(fname.split(".")[0], metrics, failures, llm.MODEL_DESC)
    print(f"n={metrics['n']} accuracy={metrics['accuracy']} macro_f1={metrics['macro_f1']} "
          f"parse_errors={metrics['parse_error_rate']}")
    for lab, v in metrics["per_class"].items():
        print(f"  {lab:16s} P={v['precision']} R={v['recall']} F1={v['f1']} (n={v['support']})")
    print("confusion matrix (rows=gold):", metrics["confusion_matrix"])
    print(f"{len(failures)} failures, first 5:")
    for f in failures[:5]:
        print("  ", f)
    print("saved to", path)


if __name__ == "__main__":
    main()
