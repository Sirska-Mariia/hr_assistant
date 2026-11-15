"""Eval: multi-turn conversation handling (context, follow-ups, language, carry-over of leave type).

Per dialogue: reply kind at each turn must match, the final DB record must match (status + reason code),
and, where given, the policy answer must cite one of the expected sections.
Metrics: turn_kind_accuracy, dialogue_success (everything right). Needs the LLM.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from evals.common import load_jsonl, save_results  # noqa: E402
from hr_assistant import llm  # noqa: E402
from hr_assistant.leave import db  # noqa: E402
from hr_assistant.pipeline import Assistant  # noqa: E402
from hr_assistant.retriever import Retriever  # noqa: E402


def main() -> None:
    cases = load_jsonl("dialogues.jsonl")
    retriever = Retriever()
    turns_ok = turns_total = success = 0
    failures = []
    for c in cases:
        conn = db.connect(":memory:")
        db.init_db(conn)
        before = conn.execute("SELECT COALESCE(MAX(id),0) FROM leave_requests").fetchone()[0]
        a = Assistant(conn, c["employee_id"], date.fromisoformat(c["today"]), retriever)
        kinds, last = [], None
        for msg in c["turns"]:
            last = a.handle(msg)
            kinds.append(last.kind)
        kind_hits = sum(k == e for k, e in zip(kinds, c["expected_kinds"]))
        turns_ok += kind_hits; turns_total += len(c["expected_kinds"])
        ok = kinds == c["expected_kinds"]
        if c.get("final"):
            row = conn.execute("SELECT status, reason_code FROM leave_requests WHERE id > ? AND employee_id = ? ORDER BY id DESC LIMIT 1",
                               (before, c["employee_id"])).fetchone()
            ok &= bool(row) and row["status"] == c["final"]["status"] and row["reason_code"] == c["final"]["reason"]
        if c.get("citation_any"):
            ok &= any(x in last.citations for x in c["citation_any"])
        success += ok
        if not ok:
            failures.append({"id": c["id"], "turns": c["turns"], "expected": c["expected_kinds"], "actual": kinds,
                             "last_reply": last.text[:200]})
    n = len(cases)
    metrics = {"n_dialogues": n, "turn_kind_accuracy": round(turns_ok / turns_total, 3), "dialogue_success": round(success / n, 3)}
    path = save_results("dialogues", metrics, failures, llm.MODEL_DESC)
    print(metrics)
    for f in failures:
        print("  ", f)
    print("saved to", path)


if __name__ == "__main__":
    main()
