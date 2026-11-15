"""Leave agent: the LLM talks to the leave database ONLY through whitelisted tools.

The model chooses which tool to call; approve/decline is decided inside the tool by rules.py.
Component name for tracing: "leave_agent". Max 4 model turns (booking needs 1-2).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from . import llm
from .leave.tools import TOOL_SCHEMAS, LeaveTools

PROMPT = (Path(__file__).parent / "prompts" / "leave_agent.md").read_text(encoding="utf-8")
MAX_TURNS = 4


@dataclass
class LeaveOutcome:
    text: str
    tool_calls: list[dict] = field(default_factory=list)  # {"name", "arguments", "result"}


def run(tools: LeaveTools, employee_name: str, today: date, message: str, hint: str = "") -> LeaveOutcome:
    system = PROMPT.format(name=employee_name, today=today.isoformat(), weekday=today.strftime("%A"))
    user = message if not hint else f"{message}\n\n(Extracted details: {hint})"
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    calls: list[dict] = []
    for _ in range(MAX_TURNS):
        reply = llm.chat(messages, component="leave_agent", tools=TOOL_SCHEMAS)
        if not reply.tool_calls:
            return LeaveOutcome((reply.content or "").strip(), calls)
        messages.append({"role": "assistant", "content": reply.content,
                         "tool_calls": [tc.model_dump() for tc in reply.tool_calls]})
        for tc in reply.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
                result = tools.call(tc.function.name, args)
            except (json.JSONDecodeError, TypeError) as err:
                result = {"status": "error", "message": f"bad tool arguments: {err}"}
            calls.append({"name": tc.function.name, "arguments": args if isinstance(args, dict) else {}, "result": result})
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result, default=str)})
    return LeaveOutcome("Sorry, I could not complete the request. Please contact HR.", calls)
