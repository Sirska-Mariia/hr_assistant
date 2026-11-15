from datetime import date

import pytest

from hr_assistant.leave import db
from hr_assistant.leave.tools import LeaveTools

TODAY = date(2026, 11, 16)


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "t.db")
    db.init_db(c)
    return c


def test_approved_request_deducts_balance(conn):
    t = LeaveTools(conn, 2, today=TODAY)
    res = t.submit_leave_request("annual", "2026-12-07", "2026-12-11")
    assert res["status"] == "approved"
    assert t.get_leave_balance()["annual"] == 7


def test_declined_request_is_recorded_without_deduction(conn):
    t = LeaveTools(conn, 10, today=TODAY)  # annual balance = 2
    res = t.submit_leave_request("annual", "2026-12-07", "2026-12-11")
    assert res["status"] == "declined" and res["reason_code"] == "insufficient_balance"
    assert t.get_leave_balance()["annual"] == 2
    assert len(t.list_my_requests()) == 1


def test_overlap_with_seeded_request(conn):
    t = LeaveTools(conn, 1, today=TODAY)
    assert t.submit_leave_request("annual", "2026-12-09", "2026-12-10")["reason_code"] == "overlap"


def test_bad_date_format_is_error_not_record(conn):
    t = LeaveTools(conn, 1, today=TODAY)
    assert t.submit_leave_request("annual", "next monday", "friday")["status"] == "error"
    assert t.list_my_requests() == [t.list_my_requests()[0]]  # only the seeded one


def test_unknown_tool_rejected(conn):
    assert LeaveTools(conn, 1, today=TODAY).call("drop_table", {})["status"] == "error"
