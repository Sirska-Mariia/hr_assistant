"""Router: classify a message into policy_question / leave_request / out_of_scope.

Input: user message (str). Output: RouteResult. One LLM call (component="router").
Fallback on unparseable output is out_of_scope (safe: leads to HR referral, never to a DB write).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import llm
from .jsonparse import parse_json_object

LABELS = ("policy_question", "leave_request", "out_of_scope")
PROMPT = (Path(__file__).parent / "prompts" / "router.md").read_text(encoding="utf-8")


@dataclass(frozen=True)
class RouteResult:
    label: str
    reason: str = ""
    parse_error: bool = False


def route(message: str, context: str | None = None) -> RouteResult:
    """context = the previous assistant message (lets the router understand short follow-ups)."""
    user = f"Previous assistant message: {context or '(none)'}\n\nEmployee message: {message}"
    reply = llm.chat(
        [{"role": "system", "content": PROMPT}, {"role": "user", "content": user}],
        component="router",
    )
    data = parse_json_object(reply.content)
    if not data or data.get("label") not in LABELS:
        return RouteResult("out_of_scope", "unparseable router output", parse_error=True)
    return RouteResult(data["label"], str(data.get("reason", "")))
