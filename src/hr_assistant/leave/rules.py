"""Deterministic leave rules (Leave Policy v2.1). The LLM never decides; this code does."""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta

HOLIDAYS = {date(2026, 12, 25), date(2027, 1, 1), date(2027, 1, 7)}
LEAVE_TYPES = {"annual", "sick", "unpaid"}
PROBATION_MONTHS = 3
MIN_NOTICE_WD = {"annual": 5, "unpaid": 5, "sick": 0}
MAX_ANNUAL_REQUEST_WD = 10
SICK_BACKDATE_DAYS = 3


@dataclass(frozen=True)
class Decision:
    approved: bool
    reason_code: str
    reason: str
    working_days: int = 0


def add_months(d: date, months: int) -> date:
    month_index = d.month - 1 + months
    year, month = d.year + month_index // 12, month_index % 12 + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def is_working_day(d: date) -> bool:
    return d.weekday() < 5 and d not in HOLIDAYS


def count_working_days(start: date, end: date) -> int:
    """Working days in [start, end], inclusive. Returns 0 if end < start."""
    if end < start:
        return 0
    return sum(is_working_day(start + timedelta(days=i)) for i in range((end - start).days + 1))


def decline(code: str, reason: str, wd: int = 0) -> Decision:
    return Decision(False, code, f"Declined: {reason}", wd)


def decide(
    *,
    contract_type: str,
    employee_start: date,
    leave_type: str,
    start: date,
    end: date,
    balance: int,
    approved_ranges: list[tuple[date, date]],
    blackouts: list[tuple[date, date]],
    today: date,
) -> Decision:
    """Apply policy rules in a fixed order; the first violated rule produces the decline."""
    if leave_type not in LEAVE_TYPES:
        return decline("unknown_type", f"unknown leave type '{leave_type}' (annual, sick, unpaid).")
    if end < start:
        return decline("invalid_dates", "the end date is before the start date.")
    if contract_type != "full_time":
        return decline("not_eligible", "contractors are not covered by the Leave Policy (section 1.2).")

    wd = count_working_days(start, end)
    if wd == 0:
        return decline("no_working_days", "the selected period contains no working days.")

    # Date in the past (sick leave may be recorded up to 3 days after it started, section 4.1)
    earliest = today - timedelta(days=SICK_BACKDATE_DAYS) if leave_type == "sick" else today
    if start < earliest:
        return decline("in_the_past", "the start date is too far in the past (section 4.1).", wd)

    probation_end = add_months(employee_start, PROBATION_MONTHS)
    if leave_type == "annual" and start < probation_end:
        return decline(
            "in_probation",
            f"annual leave cannot be taken during probation (until {probation_end}, section 3.2).",
            wd,
        )

    notice = count_working_days(today, start - timedelta(days=1))
    needed = MIN_NOTICE_WD[leave_type]
    if notice < needed:
        return decline(
            "short_notice",
            f"{leave_type} leave needs {needed} working days of notice, you gave {notice} "
            "(section 4.1). Contact HR for an exception (section 4.4).",
            wd,
        )

    if leave_type == "annual" and wd > MAX_ANNUAL_REQUEST_WD:
        return decline(
            "too_long",
            f"a single annual leave request may not exceed {MAX_ANNUAL_REQUEST_WD} working days (section 5.1).",
            wd,
        )

    if leave_type == "annual":
        for b_start, b_end in blackouts:
            if start <= b_end and end >= b_start:
                return decline("blackout", f"the period overlaps a blackout period ({b_start} to {b_end}, section 5.2).", wd)

    for r_start, r_end in approved_ranges:
        if start <= r_end and end >= r_start:
            return decline("overlap", f"the period overlaps your approved leave ({r_start} to {r_end}, section 5.3).", wd)

    if wd > balance:
        return decline("insufficient_balance", f"you need {wd} working days but only {balance} remain (section 5.4).", wd)

    return Decision(True, "ok", "Approved: all rules satisfied.", wd)
