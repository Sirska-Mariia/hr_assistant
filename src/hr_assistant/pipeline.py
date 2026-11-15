"""Orchestrator (state machine). One Assistant instance = one employee session.

Flow per message:
  [pending leave slot-filling?] collector first: if it finds a slot in this message, the router is skipped
  router (sees the previous assistant message) ->
     out_of_scope: polite refusal
     leave_request: collector (ask for missing slots, in the user's language) -> leave_agent (LLM + DB tools)
     policy_question: collector (clarify at most once) -> retriever -> sufficiency
                      -> answerer -> verifier (<=1 regeneration) -> answer | HR referral
Every step is appended to Response.trace (shown in the UI and used for the demo).
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date

from . import answerer, collector, leave_agent, rewriter, router, sufficiency, verifier
from .leave.rules import PROBATION_MONTHS, add_months
from .leave.tools import LeaveTools
from .policies import item_index
from .retriever import Retriever

HR_CONTACT = "hr@nordlight.example"
REFERRAL = {
    "en": f"I couldn't find this in our HR policies, so I can't answer it reliably. Please contact HR at {HR_CONTACT}.",
    "uk": f"Цього немає в політиках HR, тому я не можу відповісти надійно. Будь ласка, зверніться до HR: {HR_CONTACT}.",
}
REFUSAL = {
    "en": f"I can only help with HR topics (policies, benefits, leave). For anything else, please use another tool, or contact HR at {HR_CONTACT}.",
    "uk": f"Я допомагаю лише з темами HR (політики, пільги, відпустки). З іншими питаннями зверніться деінде або до HR: {HR_CONTACT}.",
}
PARTIAL_NOTE = {
    "en": f"Note: part of your question isn't covered by our HR policies. Please contact HR at {HR_CONTACT} for that part.",
    "uk": f"Примітка: частина вашого питання не охоплена політиками HR. З цією частиною зверніться до HR: {HR_CONTACT}.",
}
CYRILLIC = re.compile(r"[а-яіїєґ]", re.I)


def detect_lang(message: str, previous: str = "en") -> str:
    """Ukrainian if the message has Cyrillic letters; short Latin replies ("sick") keep the session language."""
    if CYRILLIC.search(message):
        return "uk"
    return "uk" if previous == "uk" and len(message.split()) <= 3 else "en"


@dataclass
class Response:
    kind: str  # answer | clarify | leave_result | referral | refusal
    text: str
    citations: list[str] = field(default_factory=list)
    trace: list[dict] = field(default_factory=list)
    partial: bool = False  # answered only part of the question; the rest was referred to HR


class Assistant:
    def __init__(self, conn: sqlite3.Connection, employee_id: int, today: date, retriever: Retriever,
                 use_sufficiency: bool = True, use_verifier: bool = True, k: int = 4):
        self.conn, self.employee_id, self.today = conn, employee_id, today
        self.retriever, self.k = retriever, k
        self.use_sufficiency, self.use_verifier = use_sufficiency, use_verifier
        self.tools = LeaveTools(conn, employee_id, today)
        self.index = item_index(retriever.chunks)
        self.employee = dict(conn.execute("SELECT * FROM employees WHERE id=?", (employee_id,)).fetchone())
        # conversation state
        self.pending: dict | None = None      # set when we asked a clarifying question
        self.lang = "en"
        self.last_text: str | None = None     # previous assistant message (context for the router)
        self.last_user: str | None = None     # previous user message (context for the rewriter)
        self._prev_user: str | None = None
        self.last_leave_type: str | None = None
        self.in_leave = False                 # was the previous turn a leave turn?
        self._carry_ok = False

    # ------------------------------------------------------------------
    def employee_context(self) -> str:
        e = self.employee
        parts = [f"contract type: {e['contract_type']}", f"start date: {e['start_date']}"]
        probation_end = add_months(date.fromisoformat(e["start_date"]), PROBATION_MONTHS)
        parts.append(f"on probation until {probation_end}" if self.today < probation_end else "probation finished")
        return "; ".join(parts)

    def handle(self, message: str) -> Response:
        self.lang = detect_lang(message, self.lang)
        pending, self.pending = self.pending, None
        self._carry_ok, self.in_leave = self.in_leave, False
        self._prev_user, self.last_user = self.last_user, message
        resp = self._dispatch(message, pending)
        self.last_text = resp.text
        return resp

    def _dispatch(self, message: str, pending: dict | None) -> Response:
        trace: list[dict] = []
        # A reply to our "which type / which day?" question: let the collector try first.
        if pending and pending["intent"] == "leave_request":
            col = collector.collect(message, "leave_request", self.today, self._known(pending), self.lang)
            if any(col.extracted.values()):
                trace.append({"step": "router", "label": "leave_request", "reason": "follow-up, slots filled (router skipped)"})
                return self._leave(message, col, trace)
        if pending and pending["intent"] == "policy_question" and len(message.split()) <= 5:
            trace.append({"step": "router", "label": "policy_question", "reason": "short reply to a clarifying question (router skipped)"})
            return self._policy(message, pending, trace)
        route = router.route(message, context=self.last_text)
        trace.append({"step": "router", "label": route.label, "reason": route.reason})
        if route.label == "out_of_scope":
            return Response("refusal", REFUSAL[self.lang], trace=trace)
        if route.label == "leave_request":
            return self._leave(message, None, trace, pending)
        return self._policy(message, pending if pending and pending["intent"] == "policy_question" else None, trace)

    # ------------------------------------------------------------------
    def _known(self, pending: dict | None) -> dict:
        known: dict = {}
        if self._carry_ok and self.last_leave_type:  # "then from 24 to 30" keeps the previous leave type
            known["leave_type"] = self.last_leave_type
        if pending and pending["intent"] == "leave_request":
            known.update({k: v for k, v in pending["slots"].items() if v})
        return known

    def _leave(self, message: str, col, trace: list[dict], pending: dict | None = None) -> Response:
        self.in_leave = True
        if col is None:
            col = collector.collect(message, "leave_request", self.today, self._known(pending), self.lang)
        if col.slots.get("leave_type"):
            self.last_leave_type = col.slots["leave_type"]
        trace.append({"step": "collector", "action": col.action, "slots": col.slots, "missing": col.missing})
        if col.missing:
            self.pending = {"intent": "leave_request", "slots": col.slots}
            return Response("clarify", col.question or "", trace=trace)
        hint = ", ".join(f"{k}={v}" for k, v in col.slots.items() if v) if col.action == "book" else ""
        outcome = leave_agent.run(self.tools, self.employee["name"], self.today, message, hint)
        trace.append({"step": "leave_agent", "tool_calls": outcome.tool_calls})
        return Response("leave_result", outcome.text, trace=trace)

    def _policy(self, message: str, pending: dict | None, trace: list[dict]) -> Response:
        question = f"{pending['question']} {message}" if pending else message
        followup = bool(not pending and self.last_text and len(message.split()) <= 10)
        if followup:  # short follow-up -> standalone question
            question = rewriter.rewrite(message, self._prev_user, self.last_text)
            if question != message:
                trace.append({"step": "rewriter", "question": question})
        col = collector.collect(question, "policy_question", self.today, lang=self.lang)
        trace.append({"step": "collector", "needs_clarification": col.needs_clarification})
        if col.needs_clarification and not pending and not followup:  # ask at most once, never for follow-ups
            self.pending = {"intent": "policy_question", "question": message}
            return Response("clarify", col.question or "", trace=trace)

        hits = self.retriever.search(question, k=self.k)
        trace.append({"step": "retriever", "mode": self.retriever.mode, "hits": [h.chunk.id for h in hits]})
        referral = Response("referral", REFERRAL[self.lang], trace=trace)
        partial = False

        if self.use_sufficiency:
            suff = sufficiency.check(question, hits)
            trace.append({"step": "sufficiency", "coverage": suff.coverage, "reason": suff.reason})
            if not suff.sufficient:
                return referral
            partial = suff.partial

        ctx = self.employee_context()
        ans = answerer.answer(question, hits, ctx, partial=partial)
        trace.append({"step": "answerer", "citations": ans.citations, "parse_error": ans.parse_error})
        if ans.parse_error:
            return referral

        if self.use_verifier:
            ver = verifier.verify(ans, self.index, ctx)
            trace.append({"step": "verifier", "supported": ver.supported, "unsupported": ver.unsupported, "reason": ver.reason})
            if not ver.supported:
                ans = answerer.answer(question, hits, ctx, feedback=ver.unsupported or [ver.reason], partial=partial)
                ver = verifier.verify(ans, self.index, ctx) if not ans.parse_error else verifier.Verification(False)
                trace.append({"step": "verifier_retry", "supported": ver.supported, "unsupported": ver.unsupported})
                if not ver.supported:
                    return referral
        text = ans.text + (f"\n\n{PARTIAL_NOTE[self.lang]}" if partial else "")
        return Response("answer", text, ans.citations, trace, partial=partial)
