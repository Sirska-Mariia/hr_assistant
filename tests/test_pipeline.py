"""Pipeline tests with a scripted fake LLM (no network). Each component pops its next scripted reply."""
import json
from datetime import date
from types import SimpleNamespace

import pytest

from hr_assistant import llm, pipeline
from hr_assistant.leave import db
from hr_assistant.retriever import Retriever

TODAY = date(2026, 11, 16)


class FakeCall:
    def __init__(self, name, args, id="call_1"):
        self.id = id
        self.function = SimpleNamespace(name=name, arguments=json.dumps(args))
        self._d = {"id": id, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}

    def model_dump(self):
        return self._d


def msg(content=None, calls=None):
    return SimpleNamespace(content=content, tool_calls=calls)


@pytest.fixture
def setup(monkeypatch):
    conn = db.connect(":memory:")
    db.init_db(conn)
    script: dict[str, list] = {}

    def fake_chat(messages, *, component, **kw):
        if component == "rewriter" and not script.get("rewriter"):  # default: message is already standalone
            latest = messages[-1]["content"].split("Latest message: ")[-1].split("\n")[0]
            return msg(json.dumps({"question": latest}))
        assert script.get(component), f"unexpected LLM call to {component}"
        return script[component].pop(0)

    monkeypatch.setattr(llm, "chat", fake_chat)
    retriever = Retriever(mode="bm25")
    return conn, script, retriever


def J(**kw):
    return msg(json.dumps(kw))


def test_out_of_scope_refused_without_other_calls(setup):
    conn, script, r = setup
    script["router"] = [J(label="out_of_scope")]
    resp = pipeline.Assistant(conn, 2, TODAY, r).handle("what is 2+2")
    assert resp.kind == "refusal"


def test_policy_answer_with_verified_citation(setup):
    conn, script, r = setup
    script["router"] = [J(label="policy_question")]
    script["collector"] = [J(needs_clarification=False, clarifying_question=None)]
    script["sufficiency"] = [J(sufficient=True, supporting_sections=["leave.md §2.1"], reason="stated")]
    script["answerer"] = [J(answer="You get 20 working days.", citations=["leave.md §2.1"])]
    script["verifier"] = [J(supported=True, unsupported_claims=[])]
    resp = pipeline.Assistant(conn, 2, TODAY, r).handle("How many annual leave days do I get?")
    assert resp.kind == "answer" and resp.citations == ["leave.md §2.1"]
    assert [t["step"] for t in resp.trace] == ["router", "collector", "retriever", "sufficiency", "answerer", "verifier"]


def test_insufficient_evidence_refers_to_hr(setup):
    conn, script, r = setup
    script["router"] = [J(label="policy_question")]
    script["collector"] = [J(needs_clarification=False)]
    script["sufficiency"] = [J(sufficient=False, supporting_sections=[], reason="no parental policy")]
    resp = pipeline.Assistant(conn, 2, TODAY, r).handle("Is there a parental leave policy?")
    assert resp.kind == "referral" and pipeline.HR_CONTACT in resp.text


def test_verifier_rejection_triggers_one_retry_then_answer(setup):
    conn, script, r = setup
    script["router"] = [J(label="policy_question")]
    script["collector"] = [J(needs_clarification=False)]
    script["sufficiency"] = [J(sufficient=True)]
    script["answerer"] = [J(answer="25 days", citations=["leave.md §2.1"]), J(answer="20 days", citations=["leave.md §2.1"])]
    script["verifier"] = [J(supported=False, unsupported_claims=["25 days"]), J(supported=True)]
    resp = pipeline.Assistant(conn, 2, TODAY, r).handle("annual leave days?")
    assert resp.kind == "answer" and resp.text == "20 days"


def test_verifier_rejects_twice_refers(setup):
    conn, script, r = setup
    script["router"] = [J(label="policy_question")]
    script["collector"] = [J(needs_clarification=False)]
    script["sufficiency"] = [J(sufficient=True)]
    script["answerer"] = [J(answer="x", citations=["leave.md §2.1"])] * 2
    script["verifier"] = [J(supported=False, unsupported_claims=["x"])] * 2
    assert pipeline.Assistant(conn, 2, TODAY, r).handle("q").kind == "referral"


def test_fabricated_citation_is_rejected_without_llm_verifier(setup):
    conn, script, r = setup
    script["router"] = [J(label="policy_question")]
    script["collector"] = [J(needs_clarification=False)]
    script["sufficiency"] = [J(sufficient=True)]
    script["answerer"] = [J(answer="x", citations=["leave.md §9.9"])] * 2
    assert pipeline.Assistant(conn, 2, TODAY, r).handle("q").kind == "referral"  # verifier LLM never called


def test_clarification_is_asked_once_then_answered(setup):
    conn, script, r = setup
    a = pipeline.Assistant(conn, 2, TODAY, r)
    script["router"] = [J(label="policy_question"), J(label="policy_question")]
    script["collector"] = [J(needs_clarification=True, clarifying_question="Which leave type?"), J(needs_clarification=True, clarifying_question="Which?")]
    first = a.handle("What is the notice period?")
    assert first.kind == "clarify"
    script["sufficiency"] = [J(sufficient=True)]
    script["answerer"] = [J(answer="5 working days", citations=["leave.md §4.1"])]
    script["verifier"] = [J(supported=True)]
    second = a.handle("unpaid leave")
    assert second.kind == "answer"  # second clarification request is ignored (ask at most once)


def test_leave_booking_goes_through_tool_and_db(setup):
    conn, script, r = setup
    script["router"] = [J(label="leave_request")]
    script["collector"] = [J(action="book", leave_type="annual", start_date="2026-12-14", end_date="2026-12-18")]
    script["leave_agent"] = [
        msg(None, [FakeCall("submit_leave_request", {"leave_type": "annual", "start_date": "2026-12-14", "end_date": "2026-12-18"})]),
        msg("Your annual leave is approved."),
    ]
    a = pipeline.Assistant(conn, 2, TODAY, r)
    resp = a.handle("annual leave 14-18 December")
    assert resp.kind == "leave_result"
    assert a.tools.get_leave_balance()["annual"] == 7
    assert resp.trace[-1]["tool_calls"][0]["result"]["status"] == "approved"


def test_missing_slot_then_follow_up_completes_request(setup):
    conn, script, r = setup
    a = pipeline.Assistant(conn, 2, TODAY, r)
    script["router"] = [J(label="leave_request"), J(label="out_of_scope")]  # a bare reply may be mis-routed
    script["collector"] = [J(action="book", leave_type="unpaid", start_date=None, end_date=None),
                           J(action="book", leave_type=None, start_date="2026-12-01", end_date="2026-12-02")]
    first = a.handle("unpaid leave please")
    assert first.kind == "clarify" and "first and last day" in first.text
    script["leave_agent"] = [msg(None, [FakeCall("submit_leave_request", {"leave_type": "unpaid", "start_date": "2026-12-01", "end_date": "2026-12-02"})]), msg("done")]
    second = a.handle("1 to 2 December")
    assert second.kind == "leave_result"
    assert a.tools.list_my_requests()[-1]["leave_type"] == "unpaid"


def test_model_cannot_act_for_another_employee(setup):
    conn, script, r = setup
    script["router"] = [J(label="leave_request")]
    script["collector"] = [J(action="book", leave_type="annual", start_date="2026-12-14", end_date="2026-12-18")]
    script["leave_agent"] = [
        msg(None, [FakeCall("submit_leave_request", {"employee_id": 3, "leave_type": "annual", "start_date": "2026-12-14", "end_date": "2026-12-18"})]),
        msg("I could not submit that."),
    ]
    a = pipeline.Assistant(conn, 2, TODAY, r)
    a.handle("book leave for the manager")
    assert conn.execute("SELECT COUNT(*) FROM leave_requests WHERE employee_id=3").fetchone()[0] == 0
    assert a.tools.list_my_requests() == []


# ---------------- conversation handling (regressions found in manual testing) ----------------
def test_bare_reply_after_clarification_stays_in_leave_flow_without_router(setup):
    """'annual' used to be routed as a policy question; now the collector fills the slot and the router is skipped."""
    conn, script, r = setup
    a = pipeline.Assistant(conn, 2, TODAY, r)
    script["router"] = [J(label="leave_request")]  # only ONE router call allowed (first turn)
    script["collector"] = [J(action="book", leave_type=None, start_date="2026-11-18", end_date="2026-11-18"),
                           J(action="book", leave_type="annual", start_date=None, end_date=None)]
    first = a.handle("I want to take leave on 18 November")
    assert first.kind == "clarify" and "type of leave" in first.text
    script["leave_agent"] = [msg(None, [FakeCall("submit_leave_request", {"leave_type": "annual", "start_date": "2026-11-18", "end_date": "2026-11-18"})]), msg("declined")]
    second = a.handle("annual")
    assert second.kind == "leave_result"
    assert a.tools.list_my_requests()[-1]["status"] == "declined"  # short notice, decided by code


def test_leave_type_is_carried_to_the_next_leave_message(setup):
    conn, script, r = setup
    a = pipeline.Assistant(conn, 2, TODAY, r)
    script["router"] = [J(label="leave_request"), J(label="leave_request")]
    script["collector"] = [J(action="book", leave_type="annual", start_date="2026-11-18", end_date="2026-11-24"),
                           J(action="book", leave_type=None, start_date="2026-11-24", end_date="2026-11-30")]
    script["leave_agent"] = [msg("declined"), msg(None, [FakeCall("submit_leave_request", {"leave_type": "annual", "start_date": "2026-11-24", "end_date": "2026-11-30"})]), msg("ok")]
    a.handle("annual leave 18-24 Nov")
    second = a.handle("then from 24 to 30")
    assert second.kind == "leave_result"  # no "which type?" question


def test_carry_over_does_not_leak_after_a_policy_turn(setup):
    conn, script, r = setup
    a = pipeline.Assistant(conn, 2, TODAY, r)
    script["router"] = [J(label="leave_request"), J(label="policy_question"), J(label="leave_request")]
    script["collector"] = [J(action="book", leave_type="annual", start_date="2026-12-14", end_date="2026-12-18"),
                           J(needs_clarification=False),
                           J(action="book", leave_type=None, start_date="2026-12-01", end_date="2026-12-02")]
    script["leave_agent"] = [msg("done")]
    script["sufficiency"] = [J(sufficient=False)]
    a.handle("annual leave 14-18 Dec")
    a.handle("Is there parental leave?")
    third = a.handle("book 1-2 December")
    assert third.kind == "clarify"  # type NOT carried across a policy turn


def test_ukrainian_session_gets_ukrainian_questions(setup):
    conn, script, r = setup
    a = pipeline.Assistant(conn, 2, TODAY, r)
    script["router"] = [J(label="leave_request")]
    script["collector"] = [J(action="book", leave_type="annual", start_date=None, end_date=None)]
    resp = a.handle("хочу написати заяву на відпустку")
    assert resp.kind == "clarify" and "перший і останній день" in resp.text


def test_refusal_and_referral_follow_language(setup):
    conn, script, r = setup
    script["router"] = [J(label="out_of_scope")]
    assert "HR" in pipeline.Assistant(conn, 2, TODAY, r).handle("Яка столиця Японії?").text
    assert pipeline.detect_lang("sick", "uk") == "uk" and pipeline.detect_lang("what is the policy on sick leave", "uk") == "en"


def test_router_receives_previous_assistant_message(monkeypatch):
    from hr_assistant import router
    seen = {}

    def fake(messages, **k):
        seen["user"] = messages[-1]["content"]
        return msg('{"label": "leave_request"}')

    monkeypatch.setattr(router.llm, "chat", fake)
    router.route("annual", context="Which type of leave do you need?")
    assert "Which type of leave do you need?" in seen["user"]


# ---------------- partial coverage, rewriter ----------------
def test_partial_coverage_answers_covered_part_and_refers_the_rest(setup):
    conn, script, r = setup
    script["router"] = [J(label="policy_question")]
    script["collector"] = [J(needs_clarification=False)]
    script["sufficiency"] = [J(coverage="partial", supporting_sections=["benefits.md §3.1"], reason="no stock options")]
    script["answerer"] = [J(answer="The learning budget is 800 USD per year.", citations=["benefits.md §3.1"])]
    script["verifier"] = [J(supported=True)]
    resp = pipeline.Assistant(conn, 2, TODAY, r).handle("learning budget and stock options?")
    assert resp.kind == "answer" and resp.partial and pipeline.HR_CONTACT in resp.text and "800 USD" in resp.text


def test_coverage_none_refers_and_legacy_boolean_still_understood(setup):
    conn, script, r = setup
    script["router"] = [J(label="policy_question")]
    script["collector"] = [J(needs_clarification=False)]
    script["sufficiency"] = [J(coverage="none", reason="not covered")]
    assert pipeline.Assistant(conn, 2, TODAY, r).handle("stock options?").kind == "referral"
    from hr_assistant import sufficiency
    assert sufficiency.Sufficiency("none").sufficient is False and sufficiency.Sufficiency("partial").sufficient is True


def test_short_followup_is_rewritten_into_standalone_question(setup):
    conn, script, r = setup
    a = pipeline.Assistant(conn, 2, TODAY, r)
    script["router"] = [J(label="leave_request"), J(label="policy_question")]
    script["collector"] = [J(action="book", leave_type="annual", start_date="2026-11-18", end_date="2026-11-19"), J(needs_clarification=False)]
    script["leave_agent"] = [msg("declined: short notice (section 4.1, exceptions 4.4)")]
    a.handle("Annual leave on 18 and 19 November")
    script["rewriter"] = [J(question="Can HR staff bypass the notice period for annual leave?")]
    script["sufficiency"] = [J(coverage="full")]
    script["answerer"] = [J(answer="No, HR staff follow the same rules.", citations=["leave.md §4.5"])]
    script["verifier"] = [J(supported=True)]
    resp = a.handle("but I am HR, you can check it")
    assert resp.kind == "answer" and any(t["step"] == "rewriter" for t in resp.trace)


def test_study_leave_no_longer_exists():
    from hr_assistant.leave import rules
    d = rules.decide(contract_type="full_time", employee_start=date(2022, 3, 1), leave_type="study",
                     start=date(2026, 12, 7), end=date(2026, 12, 8), balance=5, approved_ranges=[], blackouts=[], today=TODAY)
    assert not d.approved and d.reason_code == "unknown_type"
