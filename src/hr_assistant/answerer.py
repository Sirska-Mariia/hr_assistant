"""Answerer: write a short answer grounded in the retrieved excerpts, with item-level citations.

Input: question, hits, employee context, optional verifier feedback. Output: Answer.
One LLM call (component="answerer").
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import llm
from .jsonparse import parse_json_object
from .policies import parse_citations
from .retriever import Hit
from .sufficiency import format_excerpts

PROMPT = (Path(__file__).parent / "prompts" / "answer.md").read_text(encoding="utf-8")


@dataclass(frozen=True)
class Answer:
    text: str
    citations: list[str] = field(default_factory=list)
    parse_error: bool = False


def answer(question: str, hits: list[Hit], context: str = "none", feedback: list[str] | None = None,
           partial: bool = False) -> Answer:
    fb = ""
    if partial:
        fb += "- Only part of the question is covered by the excerpts: answer ONLY that part; do not mention or guess the rest.\n"
    if feedback:
        fb += "- A fact checker rejected your previous answer. Remove or fix these claims: " + "; ".join(feedback) + "\n"
    prompt = PROMPT.format(context=context, feedback=fb, question=question, excerpts=format_excerpts(hits))
    reply = llm.chat([{"role": "user", "content": prompt}], component="answerer")
    data = parse_json_object(reply.content)
    if not data or not str(data.get("answer", "")).strip():
        return Answer("", [], parse_error=True)
    return Answer(str(data["answer"]).strip(), parse_citations(list(data.get("citations") or [])))
