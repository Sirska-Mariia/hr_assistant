"""LLM judges for QA evals. NOTE: the judge uses the same model as the system (self-evaluation bias);
validate against ~20 manual labels before trusting absolute numbers (see skills/write-eval)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hr_assistant import llm  # noqa: E402
from hr_assistant.jsonparse import parse_json_object  # noqa: E402

PROMPTS = Path(__file__).resolve().parents[1] / "src" / "hr_assistant" / "prompts"
ANSWERABLE = (PROMPTS / "judge_answerable.md").read_text(encoding="utf-8")
UNANSWERABLE = (PROMPTS / "judge_unanswerable.md").read_text(encoding="utf-8")


def judge_answerable(question: str, answer: str, key_facts: list[str], policy: str) -> dict:
    prompt = ANSWERABLE.format(question=question, key_facts=key_facts, answer=answer, policy=policy, n_facts=len(key_facts))
    data = parse_json_object(llm.chat([{"role": "user", "content": prompt}], component="judge").content) or {}
    covered = data.get("facts_covered")
    if not isinstance(covered, list) or len(covered) != len(key_facts):
        covered = [False] * len(key_facts)
    return {"fact_coverage": sum(bool(x) for x in covered) / max(1, len(key_facts)),
            "unsupported_claims": int(data.get("unsupported_claims", 0) or 0)}


def judge_unanswerable(question: str, answer: str) -> dict:
    prompt = UNANSWERABLE.format(question=question, answer=answer)
    data = parse_json_object(llm.chat([{"role": "user", "content": prompt}], component="judge").content) or {}
    return {"fabricated": bool(data.get("fabricated", False)), "refers_to_hr": bool(data.get("refers_to_hr", False))}
