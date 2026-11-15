"""Sufficiency check: do the retrieved excerpts cover the question? full / partial / none.

none -> HR referral; partial -> answer the covered part and refer the rest to HR.
Input: question + hits. Output: Sufficiency. One LLM call (component="sufficiency").
Parse failure counts as "none" (safe default). Legacy {"sufficient": bool} output is still understood.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import llm
from .jsonparse import parse_json_object
from .retriever import Hit

PROMPT = (Path(__file__).parent / "prompts" / "sufficiency.md").read_text(encoding="utf-8")
COVERAGE = ("full", "partial", "none")


@dataclass(frozen=True)
class Sufficiency:
    coverage: str
    sections: list[str] = field(default_factory=list)
    reason: str = ""

    @property
    def sufficient(self) -> bool:
        return self.coverage != "none"

    @property
    def partial(self) -> bool:
        return self.coverage == "partial"


def format_excerpts(hits: list[Hit]) -> str:
    return "\n".join(h.chunk.cited_text() for h in hits)


def check(question: str, hits: list[Hit]) -> Sufficiency:
    if not hits:
        return Sufficiency("none", [], "no retrieval hits")
    prompt = PROMPT.format(question=question, excerpts=format_excerpts(hits))
    reply = llm.chat([{"role": "user", "content": prompt}], component="sufficiency")
    data = parse_json_object(reply.content) or {}
    coverage = data.get("coverage")
    if coverage not in COVERAGE:
        legacy = data.get("sufficient")
        coverage = ("full" if legacy else "none") if isinstance(legacy, bool) else None
    if coverage is None:
        return Sufficiency("none", [], "unparseable output")
    return Sufficiency(coverage, list(data.get("supporting_sections") or []), str(data.get("reason", "")))
