"""Unit tests with a mocked LLM (no network)."""
from datetime import date
from types import SimpleNamespace

from hr_assistant import collector, router
from hr_assistant.jsonparse import parse_json_object


def fake_chat(content):
    return lambda *a, **k: SimpleNamespace(content=content, tool_calls=None)


def test_parse_json_handles_fences_and_prose():
    assert parse_json_object('Sure!\n```json\n{"label": "x"}\n```') == {"label": "x"}
    assert parse_json_object("no json here") is None
    assert parse_json_object('{"a": ') is None


def test_router_valid_label(monkeypatch):
    monkeypatch.setattr(router.llm, "chat", fake_chat('{"label": "leave_request", "reason": "books days"}'))
    assert router.route("book me a day").label == "leave_request"


def test_router_garbage_falls_back_to_out_of_scope(monkeypatch):
    monkeypatch.setattr(router.llm, "chat", fake_chat("I think it is about leave"))
    res = router.route("x")
    assert res.label == "out_of_scope" and res.parse_error


def test_router_unknown_label_falls_back(monkeypatch):
    monkeypatch.setattr(router.llm, "chat", fake_chat('{"label": "admin_override"}'))
    assert router.route("x").label == "out_of_scope"


def test_collector_leave_missing_slot_asks_question(monkeypatch):
    monkeypatch.setattr(collector.llm, "chat", fake_chat('{"leave_type": "unpaid", "start_date": null, "end_date": null}'))
    res = collector.collect("unpaid leave", "leave_request", date(2026, 11, 16))
    assert res.missing == ["start_date", "end_date"] and not res.complete
    assert "first and last day" in res.question


def test_collector_rejects_invalid_values(monkeypatch):
    monkeypatch.setattr(collector.llm, "chat", fake_chat('{"leave_type": "holiday", "start_date": "next friday", "end_date": "2026-13-40"}'))
    res = collector.collect("x", "leave_request", date(2026, 11, 16))
    assert set(res.missing) == {"leave_type", "start_date", "end_date"}


def test_collector_multi_turn_merges_known_slots(monkeypatch):
    monkeypatch.setattr(collector.llm, "chat", fake_chat('{"leave_type": null, "start_date": "2026-12-07", "end_date": "2026-12-11"}'))
    res = collector.collect("7 to 11 December", "leave_request", date(2026, 11, 16), known_slots={"leave_type": "annual"})
    assert res.complete and res.slots["leave_type"] == "annual"


def test_collector_policy_clarification(monkeypatch):
    monkeypatch.setattr(collector.llm, "chat", fake_chat('{"needs_clarification": true, "clarifying_question": "Which leave type?"}'))
    res = collector.collect("Can I take leave?", "policy_question", date(2026, 11, 16))
    assert res.needs_clarification and res.question == "Which leave type?" and not res.complete


def test_collector_policy_flag_without_question_is_ignored(monkeypatch):
    monkeypatch.setattr(collector.llm, "chat", fake_chat('{"needs_clarification": true, "clarifying_question": null}'))
    assert collector.collect("x", "policy_question", date(2026, 11, 16)).complete


def test_year_is_rolled_forward_for_dates_without_year():
    today = date(2026, 11, 16)
    assert collector.fix_year("2025-12-01", "from 1 December", today) == "2026-12-01"
    assert collector.fix_year("2025-12-01", "from 1 December 2025", today) == "2025-12-01"  # explicit year is kept
    assert collector.fix_year("2026-11-10", "sick on 10 November", today) == "2026-11-10"  # recent past is fine
