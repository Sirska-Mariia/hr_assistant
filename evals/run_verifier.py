"""Eval: source verifier (LLM layer) on labelled (answer, cited text) pairs.

Positive class = UNSUPPORTED answer (what the verifier must catch). Reports precision/recall/F1 of catching
unsupported answers and the false-reject rate on supported ones. Subtly corrupted numbers/conditions and an
added extra claim are included, so a lazy verifier that approves everything scores recall 0.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from evals.common import load_jsonl, save_results  # noqa: E402
from evals.metrics import prf  # noqa: E402
from hr_assistant import llm  # noqa: E402
from hr_assistant.answerer import Answer  # noqa: E402
from hr_assistant.policies import item_index, load_chunks  # noqa: E402
from hr_assistant.verifier import verify  # noqa: E402


def main() -> None:
    index = item_index(load_chunks())
    cases = load_jsonl("verifier.jsonl")
    tp = fp = fn = tn = 0
    failures = []
    for c in cases:
        ver = verify(Answer(c["answer"], c["citations"]), index)
        pred_unsupported, gold_unsupported = not ver.supported, not c["supported"]
        tp += gold_unsupported and pred_unsupported
        fn += gold_unsupported and not pred_unsupported
        fp += (not gold_unsupported) and pred_unsupported
        tn += (not gold_unsupported) and not pred_unsupported
        if pred_unsupported != gold_unsupported:
            failures.append({"id": c["id"], "answer": c["answer"], "gold_supported": c["supported"],
                             "verifier": ver.supported, "claims": ver.unsupported, "reason": ver.reason})
    p, r, f = prf(tp, fp, fn)
    n = len(cases)
    metrics = {"n": n, "accuracy": round((tp + tn) / n, 3), "unsupported_precision": round(p, 3),
               "unsupported_recall": round(r, 3), "unsupported_f1": round(f, 3),
               "false_reject_rate": round(fp / max(1, fp + tn), 3)}
    path = save_results("verifier", metrics, failures, llm.MODEL_DESC)
    print(metrics)
    for f_ in failures:
        print("  ", f_)
    print("saved to", path)


if __name__ == "__main__":
    main()
