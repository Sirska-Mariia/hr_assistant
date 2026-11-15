"""Information collector: decide whether we have what is needed, otherwise ask a follow-up.

Leave requests: slots leave_type, start_date, end_date (extracted by LLM, validated and
completed by code; the follow-up question is templated, not generated).
Policy questions: LLM judges whether the question is too vague; employee profile facts
(contract type, probation) are NOT asked because the session already knows them.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
import re
from datetime import date, timedelta
from pathlib import Path

from . import llm
from .jsonparse import parse_json_object

PROMPT = (Path(__file__).parent / "prompts" / "collector.md").read_text(encoding="utf-8")
LEAVE_SLOTS = ("leave_type", "start_date", "end_date")
LEAVE_TYPES = {"annual", "sick", "unpaid"}
ACTIONS = {"book", "balance", "status"}
QUESTIONS = {
    "en": {
        "leave_type": "Which type of leave do you need: annual, sick or unpaid?",
        "start_date": "Which dates do you need? Please give the first and last day (one date if it is a single day).",
        "end_date": "What is the last day of your leave?",
    },
    "uk": {
        "leave_type": "Який тип відпустки вам потрібен: щорічна, лікарняний чи без збереження зарплати?",
        "start_date": "Які дати вам потрібні? Вкажіть перший і останній день (одну дату, якщо це один день).",
        "end_date": "Який останній день вашої відпустки?",
    },
}


@dataclass
class CollectResult:
    intent: str
    slots: dict = field(default_factory=dict)
    action: str = "book"
    missing: list[str] = field(default_factory=list)
    needs_clarification: bool = False
    question: str | None = None
    extracted: dict = field(default_factory=dict)  # slot values found in THIS message only

    @property
    def complete(self) -> bool:
        return not self.missing and not self.needs_clarification


def _valid_iso(value) -> str | None:
    try:
        return date.fromisoformat(str(value)).isoformat()
    except (TypeError, ValueError):
        return None


YEAR_RE = re.compile(r"\b20\d{2}\b")


def fix_year(iso: str | None, message: str, today: date) -> str | None:
    """Models sometimes pick a past year for dates written without a year: roll such dates forward."""
    if not iso or YEAR_RE.search(message):
        return iso
    d = date.fromisoformat(iso)
    limit = today - timedelta(days=45)
    if d >= limit:
        return iso
    for year in (today.year, today.year + 1):
        try:
            cand = d.replace(year=year)
        except ValueError:  # 29 February
            continue
        if cand >= limit:
            return cand.isoformat()
    return iso


def clean_leave_slots(raw: dict) -> dict:
    """Keep only valid slot values; anything invalid becomes None."""
    ltype = raw.get("leave_type")
    return {
        "leave_type": ltype if ltype in LEAVE_TYPES else None,
        "start_date": _valid_iso(raw.get("start_date")),
        "end_date": _valid_iso(raw.get("end_date")),
    }


def collect(message: str, intent: str, today: date, known_slots: dict | None = None, lang: str = "en") -> CollectResult:
    known = {k: v for k, v in (known_slots or {}).items() if v}
    prompt = PROMPT.format(today=today.isoformat(), weekday=today.strftime("%A"), intent=intent,
                           known=json.dumps(known))
    reply = llm.chat([{"role": "system", "content": prompt}, {"role": "user", "content": message}],
                     component="collector")
    data = parse_json_object(reply.content) or {}

    if intent == "leave_request":
        action = data.get("action") if data.get("action") in ACTIONS else "book"
        new = clean_leave_slots(data)
        new = {k: (fix_year(v, message, today) if k in ("start_date", "end_date") else v) for k, v in new.items()}
        slots = {k: new[k] or known.get(k) for k in LEAVE_SLOTS}  # new values win, old ones persist
        # balance / status questions need no slots; only booking does
        missing = [k for k in LEAVE_SLOTS if not slots[k]] if action == "book" else []
        question = QUESTIONS.get(lang, QUESTIONS["en"])[missing[0]] if missing else None
        return CollectResult(intent, slots, action, missing, False, question, extracted=new)

    needs = bool(data.get("needs_clarification"))
    question = data.get("clarifying_question") if needs else None
    return CollectResult(intent, {}, "book", [], needs and bool(question), question if needs else None)
