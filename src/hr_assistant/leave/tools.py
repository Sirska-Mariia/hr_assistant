"""Tool layer between the LLM and the leave database.

Security design: the employee id is bound to the session (constructor), NOT a model argument,
so the LLM cannot act on behalf of someone else. Approve/decline comes from rules.decide().
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime

from . import rules

TOOL_SCHEMAS = [
    {"type": "function", "function": {
        "name": "get_leave_balance",
        "description": "Get the current employee's remaining days per leave type.",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "submit_leave_request",
        "description": "Submit a leave request for the current employee. The system applies policy rules and "
                       "returns approved or declined with a reason.",
        "parameters": {"type": "object", "properties": {
            "leave_type": {"type": "string", "enum": ["annual", "sick", "unpaid"]},
            "start_date": {"type": "string", "description": "YYYY-MM-DD"},
            "end_date": {"type": "string", "description": "YYYY-MM-DD"}},
            "required": ["leave_type", "start_date", "end_date"]}}},
    {"type": "function", "function": {
        "name": "list_my_requests",
        "description": "List the current employee's leave requests with their status.",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
]


class LeaveTools:
    def __init__(self, conn: sqlite3.Connection, employee_id: int, today: date | None = None):
        self.conn, self.employee_id, self.today = conn, employee_id, today or date.today()

    def get_leave_balance(self) -> dict:
        rows = self.conn.execute(
            "SELECT leave_type, days_remaining FROM leave_balances WHERE employee_id=?", (self.employee_id,)
        ).fetchall()
        return {r["leave_type"]: r["days_remaining"] for r in rows}

    def list_my_requests(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT id, leave_type, start_date, end_date, working_days, status, decision_reason "
            "FROM leave_requests WHERE employee_id=? ORDER BY id", (self.employee_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def submit_leave_request(self, leave_type: str, start_date: str, end_date: str) -> dict:
        try:
            start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
        except ValueError:
            return {"status": "error", "message": "Dates must be in YYYY-MM-DD format."}

        emp = self.conn.execute("SELECT * FROM employees WHERE id=?", (self.employee_id,)).fetchone()
        bal = self.conn.execute(
            "SELECT days_remaining FROM leave_balances WHERE employee_id=? AND leave_type=?",
            (self.employee_id, leave_type),
        ).fetchone()
        approved = [
            (date.fromisoformat(r["start_date"]), date.fromisoformat(r["end_date"]))
            for r in self.conn.execute(
                "SELECT start_date, end_date FROM leave_requests WHERE employee_id=? AND status='approved'",
                (self.employee_id,))
        ]
        blackouts = [
            (date.fromisoformat(r["start_date"]), date.fromisoformat(r["end_date"]))
            for r in self.conn.execute("SELECT start_date, end_date FROM blackout_periods")
        ]
        decision = rules.decide(
            contract_type=emp["contract_type"], employee_start=date.fromisoformat(emp["start_date"]),
            leave_type=leave_type, start=start, end=end, balance=bal["days_remaining"] if bal else 0,
            approved_ranges=approved, blackouts=blackouts, today=self.today,
        )
        if decision.reason_code in {"unknown_type", "invalid_dates"}:
            return {"status": "error", "reason_code": decision.reason_code, "message": decision.reason}

        status = "approved" if decision.approved else "declined"
        cur = self.conn.execute(
            "INSERT INTO leave_requests (employee_id, leave_type, start_date, end_date, working_days, status,"
            " reason_code, decision_reason, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (self.employee_id, leave_type, start_date, end_date, decision.working_days, status,
             decision.reason_code, decision.reason, datetime.now().isoformat(timespec="seconds")),
        )
        if decision.approved:
            self.conn.execute(
                "UPDATE leave_balances SET days_remaining = days_remaining - ? WHERE employee_id=? AND leave_type=?",
                (decision.working_days, self.employee_id, leave_type),
            )
        self.conn.commit()
        return {"request_id": cur.lastrowid, "status": status, "reason_code": decision.reason_code,
                "message": decision.reason, "working_days": decision.working_days}

    def call(self, name: str, arguments: dict) -> dict | list:
        """Dispatch a tool call by name; only whitelisted tools are reachable."""
        allowed = {"get_leave_balance", "submit_leave_request", "list_my_requests"}
        if name not in allowed:
            return {"status": "error", "message": f"Unknown tool {name}"}
        return getattr(self, name)(**arguments)
