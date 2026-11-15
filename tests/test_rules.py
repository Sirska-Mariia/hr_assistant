from datetime import date

import pytest

from hr_assistant.leave import rules

TODAY = date(2026, 11, 16)  # Monday


def run(**over):
    base = dict(contract_type="full_time", employee_start=date(2022, 3, 1), leave_type="annual",
                start=date(2026, 12, 7), end=date(2026, 12, 11), balance=20,
                approved_ranges=[], blackouts=[(date(2026, 12, 21), date(2026, 12, 31))], today=TODAY)
    base.update(over)
    return rules.decide(**base)


def test_valid_request_is_approved():
    d = run()
    assert d.approved and d.working_days == 5


def test_contractor_declined():
    assert run(contract_type="contractor").reason_code == "not_eligible"


def test_probation_blocks_annual_but_not_unpaid():
    start = dict(employee_start=date(2026, 10, 5), start=date(2026, 12, 7), end=date(2026, 12, 8))
    assert run(**start).reason_code == "in_probation"
    assert run(leave_type="unpaid", **start).approved


def test_short_notice():
    assert run(start=date(2026, 11, 19), end=date(2026, 11, 20)).reason_code == "short_notice"


def test_notice_counts_submission_day():
    # Submitted Mon 16 Nov, leave starts Mon 23 Nov: Mon..Fri = 5 working days -> ok
    assert run(start=date(2026, 11, 23), end=date(2026, 11, 23)).approved


def test_too_long_annual():
    assert run(start=date(2026, 12, 1), end=date(2026, 12, 15)).reason_code == "too_long"


def test_blackout():
    assert run(start=date(2026, 12, 22), end=date(2026, 12, 23)).reason_code == "blackout"


def test_overlap():
    d = run(approved_ranges=[(date(2026, 12, 9), date(2026, 12, 10))])
    assert d.reason_code == "overlap"


def test_insufficient_balance():
    assert run(balance=2).reason_code == "insufficient_balance"


def test_sick_backdating_window():
    assert run(leave_type="sick", start=date(2026, 11, 13), end=date(2026, 11, 13)).approved
    assert run(leave_type="sick", start=date(2026, 11, 10), end=date(2026, 11, 10)).reason_code == "in_the_past"


def test_weekend_only_has_no_working_days():
    assert run(start=date(2026, 12, 12), end=date(2026, 12, 13)).reason_code == "no_working_days"


def test_manager_has_no_special_rights():
    # rules.decide has no manager parameter by design (policy 4.5)
    assert "is_manager" not in rules.decide.__code__.co_varnames[:rules.decide.__code__.co_kwonlyargcount]


@pytest.mark.parametrize("d,expected", [(date(2026, 11, 28), False), (date(2026, 12, 25), False), (date(2026, 12, 24), True)])
def test_is_working_day(d, expected):
    assert rules.is_working_day(d) is expected
