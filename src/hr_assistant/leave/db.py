"""SQLite schema and seed data for the leave module."""
from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[3] / "data" / "hr.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS employees (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    contract_type TEXT NOT NULL CHECK (contract_type IN ('full_time', 'contractor')),
    start_date TEXT NOT NULL,
    is_manager INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS leave_balances (
    employee_id INTEGER NOT NULL REFERENCES employees(id),
    leave_type TEXT NOT NULL,
    days_remaining INTEGER NOT NULL,
    PRIMARY KEY (employee_id, leave_type)
);
CREATE TABLE IF NOT EXISTS leave_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL REFERENCES employees(id),
    leave_type TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    working_days INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('approved', 'declined')),
    reason_code TEXT NOT NULL,
    decision_reason TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS blackout_periods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    reason TEXT NOT NULL
);
"""

# (id, name, role, contract_type, start_date, is_manager)
EMPLOYEES = [
    (1, "Olena Kovalenko", "Backend Engineer", "full_time", "2022-03-01", 0),
    (2, "Andrii Melnyk", "Data Engineer", "full_time", "2023-09-11", 0),
    (3, "Iryna Bondar", "Engineering Manager", "full_time", "2020-01-13", 1),
    (4, "Taras Shevchuk", "QA Engineer", "full_time", "2026-10-05", 0),  # on probation
    (5, "Sofiia Lysenko", "Designer", "contractor", "2024-02-01", 0),
    (6, "Dmytro Hrytsenko", "Platform Engineer", "full_time", "2021-06-14", 0),
    (7, "Kateryna Moroz", "HR Specialist", "full_time", "2019-11-04", 0),
    (8, "Maksym Pavlenko", "ML Engineer", "full_time", "2025-01-20", 0),
    (9, "Nadiia Tkachenko", "Product Manager", "full_time", "2026-09-14", 1),  # probation ends 2026-12-14
    (10, "Yurii Savchuk", "Frontend Engineer", "full_time", "2024-08-05", 0),  # low annual balance
]

DEFAULT_BALANCES = {"annual": 20, "sick": 10, "unpaid": 10}
BALANCE_OVERRIDES = {
    (2, "annual"): 12,
    (4, "annual"): 5,   # pro-rated for a mid-year joiner
    (9, "annual"): 6,
    (10, "annual"): 2,
    (3, "sick"): 4,
}

BLACKOUTS = [
    ("2026-12-21", "2026-12-31", "Year-end release freeze"),
    ("2027-03-25", "2027-03-31", "Quarter-end close"),
    ("2027-06-24", "2027-06-30", "Quarter-end close"),
]

# Pre-existing approved leave, used to test the overlap rule.
EXISTING_REQUESTS = [
    (1, "annual", "2026-12-07", "2026-12-11", 5, "approved", "ok", "Approved: all rules satisfied.", "2026-11-02T10:00:00"),
    (6, "annual", "2027-01-11", "2027-01-15", 5, "approved", "ok", "Approved: all rules satisfied.", "2026-11-03T09:30:00"),
]


def connect(path: Path | str = DB_PATH, check_same_thread: bool = True) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), check_same_thread=check_same_thread)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection, seed: bool = True) -> None:
    """Create the schema; optionally (re)load deterministic seed data."""
    conn.executescript(SCHEMA)
    if not seed:
        return
    for table in ("leave_requests", "leave_balances", "blackout_periods", "employees"):
        conn.execute(f"DELETE FROM {table}")
    conn.executemany("INSERT INTO employees VALUES (?,?,?,?,?,?)", EMPLOYEES)
    for emp in EMPLOYEES:
        for leave_type, days in DEFAULT_BALANCES.items():
            days = BALANCE_OVERRIDES.get((emp[0], leave_type), days)
            conn.execute("INSERT INTO leave_balances VALUES (?,?,?)", (emp[0], leave_type, days))
    conn.executemany("INSERT INTO blackout_periods (start_date, end_date, reason) VALUES (?,?,?)", BLACKOUTS)
    conn.executemany(
        "INSERT INTO leave_requests (employee_id, leave_type, start_date, end_date, working_days,"
        " status, reason_code, decision_reason, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        EXISTING_REQUESTS,
    )
    conn.commit()


if __name__ == "__main__":
    c = connect()
    init_db(c)
    print(f"Database created at {DB_PATH}")
