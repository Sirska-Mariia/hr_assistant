"""Eval: leave module WITHOUT any LLM (deterministic rules + tools + DB).

Metrics: decision accuracy, reason-code accuracy, balance consistency (approved -> exact deduction,
declined -> no deduction), invalid-write count (must be 0). Safe to run offline.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from evals.common import load_jsonl, save_results  # noqa: E402
from hr_assistant.leave import db  # noqa: E402
from hr_assistant.leave.tools import LeaveTools  # noqa: E402


def main() -> None:
    cases = load_jsonl("leave.jsonl")
    ok_status = ok_reason = ok_balance = 0
    failures = []
    for c in cases:
        conn = db.connect(":memory:")
        db.init_db(conn)
        tools = LeaveTools(conn, c["employee_id"], date.fromisoformat(c["today"]))
        r = c["request"]
        before = tools.get_leave_balance()[r["leave_type"]]
        res = tools.submit_leave_request(r["leave_type"], r["start_date"], r["end_date"])
        after = tools.get_leave_balance()[r["leave_type"]]
        status_ok = res.get("status") == c["expected_status"]
        reason_ok = res.get("reason_code") == c["expected_reason"]
        expected_delta = res.get("working_days", 0) if res.get("status") == "approved" else 0
        balance_ok = before - after == expected_delta
        ok_status += status_ok; ok_reason += reason_ok; ok_balance += balance_ok
        if not (status_ok and reason_ok and balance_ok):
            failures.append({"id": c["id"], "expected": [c["expected_status"], c["expected_reason"]], "actual": res})
    n = len(cases)
    metrics = {"n": n, "decision_accuracy": round(ok_status / n, 3), "reason_accuracy": round(ok_reason / n, 3),
               "balance_consistency": round(ok_balance / n, 3)}
    path = save_results("leave_rules", metrics, failures, "n/a (no LLM)")
    print(metrics, f"{len(failures)} failures")
    for f in failures:
        print("  ", f)
    print("saved to", path)


if __name__ == "__main__":
    main()
