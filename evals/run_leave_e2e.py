"""Eval: leave flow end-to-end WITH the LLM (router -> collector -> leave agent -> tools -> DB).

The check is on the database, not on the model's words: decision matches expectation, the submitted
leave type/dates match what the employee asked for (argument fidelity), exactly one request was written,
and the assistant did not ask an unnecessary question for a complete message.
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
    cases = load_jsonl("leave.jsonl")
    retriever = Retriever(mode="bm25")  # not used by the leave flow
    dec = fid = single = no_clarify = 0
    failures = []
    for c in cases:
        conn = db.connect(":memory:")
        db.init_db(conn)
        before = conn.execute("SELECT COALESCE(MAX(id),0) FROM leave_requests").fetchone()[0]
        resp = Assistant(conn, c["employee_id"], date.fromisoformat(c["today"]), retriever).handle(c["message"])
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM leave_requests WHERE id > ? AND employee_id = ?", (before, c["employee_id"]))]
        asked = resp.kind == "clarify"
        no_clarify += not asked
        single += len(rows) == 1
        ok_dec = len(rows) == 1 and rows[0]["status"] == c["expected_status"] and rows[0]["reason_code"] == c["expected_reason"]
        req = c["request"]
        ok_fid = len(rows) == 1 and (rows[0]["leave_type"], rows[0]["start_date"], rows[0]["end_date"]) == (
            req["leave_type"], req["start_date"], req["end_date"])
        dec += ok_dec; fid += ok_fid
        if not (ok_dec and ok_fid):
            failures.append({"id": c["id"], "message": c["message"], "kind": resp.kind, "rows": rows, "reply": resp.text,
                             "trace": [{k: v for k, v in t.items() if k in ("step", "label", "slots", "tool_calls")} for t in resp.trace]})
    n = len(cases)
    metrics = {"n": n, "decision_accuracy": round(dec / n, 3), "argument_fidelity": round(fid / n, 3),
               "exactly_one_write": round(single / n, 3), "no_unneeded_clarification": round(no_clarify / n, 3)}
    path = save_results("leave_e2e", metrics, failures, llm.MODEL_DESC)
    print(metrics, f"{len(failures)} failures")
    for f in failures[:6]:
        print("  ", f)
    print("saved to", path)


if __name__ == "__main__":
    main()
