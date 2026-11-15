"""Question rewriter: turns a short follow-up ("but I am HR, you can check it") into a standalone question.

Only used for short policy follow-ups when there is a previous assistant message. One LLM call
(component="rewriter"). Falls back to the original message on any problem.
"""
from __future__ import annotations

from pathlib import Path

from . import llm
from .jsonparse import parse_json_object

PROMPT = (Path(__file__).parent / "prompts" / "rewriter.md").read_text(encoding="utf-8")
MAX_LEN = 300


def rewrite(message: str, last_user: str | None, last_assistant: str | None) -> str:
    prompt = PROMPT.format(last_user=last_user or "(none)", last_assistant=(last_assistant or "(none)")[:600], message=message)
    reply = llm.chat([{"role": "user", "content": prompt}], component="rewriter")
    data = parse_json_object(reply.content) or {}
    question = str(data.get("question", "")).strip()
    return question if question and len(question) <= MAX_LEN else message
