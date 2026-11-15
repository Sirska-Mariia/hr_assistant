"""Source verifier: is every claim in the answer supported by the cited policy text?

Two layers: (1) deterministic: answer must cite at least one existing policy item;
(2) LLM fact check of the answer against the cited text (component="verifier").
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import llm
from .answerer import Answer
from .jsonparse import parse_json_object

PROMPT = (Path(__file__).parent / "prompts" / "verify.md").read_text(encoding="utf-8")


@dataclass(frozen=True)
class Verification:
    supported: bool
    unsupported: list[str] = field(default_factory=list)
    reason: str = ""


def verify(ans: Answer, index: dict[str, str], context: str = "none") -> Verification:
    if not ans.citations:
        return Verification(False, [], "no citations")
    unknown = [c for c in ans.citations if c not in index]
    if unknown:
        return Verification(False, [], f"citation does not exist: {unknown}")
    cited = "\n".join(f"[{c}] {index[c]}" for c in ans.citations)
    prompt = PROMPT.format(answer=ans.text, cited=cited, context=context)
    reply = llm.chat([{"role": "user", "content": prompt}], component="verifier")
    data = parse_json_object(reply.content)
    if not data or not isinstance(data.get("supported"), bool):
        return Verification(False, [], "unparseable verifier output")
    return Verification(data["supported"], list(data.get("unsupported_claims") or []))
