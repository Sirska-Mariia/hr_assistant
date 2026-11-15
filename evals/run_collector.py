"""Eval: information collector.

Leave cases: per-slot exact match, full-slot-set accuracy, missing-slot detection P/R
(a slot is 'missing' in gold when gold value is null). Policy cases: clarification accuracy,
precision and recall of needs_clarification (unnecessary questions hurt precision).
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from evals.common import load_jsonl, save_results  # noqa: E402
from evals.metrics import prf  # noqa: E402
from hr_assistant import llm  # noqa: E402
from hr_assistant.collector import LEAVE_SLOTS, collect  # noqa: E402


def main() -> None:
    fname = sys.argv[1] if len(sys.argv) > 1 else "collector.jsonl"
    cases = load_jsonl(fname)
    failures = []
    slot_hits = {s: 0 for s in LEAVE_SLOTS}
    n_leave = full_ok = 0
    m_tp = m_fp = m_fn = 0
    p_tp = p_fp = p_fn = p_tn = 0

    for c in cases:
        res = collect(c["text"], c["intent"], date.fromisoformat(c["today"]))
        if c["intent"] == "leave_request":
            n_leave += 1
            gold = c["gold"]
            ok_all = True
            if "action" in gold:  # optional field (dev set only)
                ok_all &= res.action == gold["action"]
            for s in LEAVE_SLOTS:
                hit = res.slots.get(s) == gold[s]
                slot_hits[s] += hit
                ok_all &= hit
            gold_missing = set() if gold.get("action", "book") != "book" else {s for s in LEAVE_SLOTS if gold[s] is None}
            pred_missing = set(res.missing)
            m_tp += len(gold_missing & pred_missing)
            m_fp += len(pred_missing - gold_missing)
            m_fn += len(gold_missing - pred_missing)
            full_ok += ok_all
            if not ok_all:
                failures.append({"id": c["id"], "text": c["text"], "expected": gold, "actual": {**res.slots, "action": res.action}})
        else:
            gold_flag, pred_flag = c["gold"]["needs_clarification"], res.needs_clarification
            p_tp += gold_flag and pred_flag
            p_fp += (not gold_flag) and pred_flag
            p_fn += gold_flag and (not pred_flag)
            p_tn += (not gold_flag) and (not pred_flag)
            if gold_flag != pred_flag:
                failures.append({"id": c["id"], "text": c["text"], "expected": gold_flag,
                                 "actual": pred_flag, "question": res.question})

    mp, mr, mf = prf(m_tp, m_fp, m_fn)
    pp, pr_, pf = prf(p_tp, p_fp, p_fn)
    n_policy = p_tp + p_fp + p_fn + p_tn
    metrics = {
        "leave": {"n": n_leave, "slot_accuracy": {s: round(slot_hits[s] / n_leave, 3) for s in LEAVE_SLOTS},
                  "all_slots_correct": round(full_ok / n_leave, 3),
                  "missing_detection": {"precision": round(mp, 3), "recall": round(mr, 3), "f1": round(mf, 3)}},
        "policy_clarification": {"n": n_policy, "accuracy": round((p_tp + p_tn) / n_policy, 3),
                                 "precision": round(pp, 3), "recall": round(pr_, 3), "f1": round(pf, 3)},
    }
    path = save_results(fname.split(".")[0], metrics, failures, llm.MODEL_DESC)
    print(metrics)
    print(f"{len(failures)} failures:")
    for f in failures:
        print("  ", f)
    print("saved to", path)


if __name__ == "__main__":
    main()
