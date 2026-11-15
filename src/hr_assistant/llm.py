"""Single entry point for all LLM calls: one model config, retries, JSONL logging (tracing).

Env: OPENROUTER_API_KEY, LLM_MODEL, LLM_REASONING = off | minimal | low | medium | high | default
  off     -> sends reasoning.effort="none" (fast, cheap, stable for JSON/classification tasks)
  default -> sends nothing (model decides). If a model has mandatory reasoning and rejects the
             setting, the call is retried once without it.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path

try:  # optional at import time so unit tests work without the packages
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # pragma: no cover
    pass

MODEL = os.getenv("LLM_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
REASONING = os.getenv("LLM_REASONING", "off")
MODEL_DESC = f"{MODEL} | reasoning={REASONING}"  # stored with every eval result
LOG_PATH = Path(__file__).resolve().parents[2] / "logs" / "llm_calls.jsonl"

_client = None


def client():
    global _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.environ["OPENROUTER_API_KEY"])
    return _client


def _reasoning_body() -> dict | None:
    if REASONING == "default":
        return None
    return {"reasoning": {"effort": "none" if REASONING == "off" else REASONING}}


def chat(messages: list[dict], *, component: str, tools: list | None = None,
         temperature: float = 0.0, retries: int = 3, **kwargs):
    """Call the model; log component name, latency and I/O. Returns the raw response message."""
    last_err: Exception | None = None
    extra = _reasoning_body()
    for attempt in range(retries):
        started = time.time()
        try:
            kw = dict(kwargs)
            if tools:
                kw["tools"] = tools
            if extra:
                kw["extra_body"] = extra
            resp = client().chat.completions.create(
                model=MODEL, messages=messages, temperature=temperature, **kw)
            msg = resp.choices[0].message
            _log(component, messages, msg, time.time() - started)
            return msg
        except Exception as err:  # network / rate limit / unsupported setting
            last_err = err
            if extra and "reasoning" in str(err).lower():
                extra = None  # model rejects the reasoning setting: retry without it
                continue
            time.sleep(2 ** attempt)
    raise RuntimeError(f"LLM call failed after {retries} attempts: {last_err}")


def _log(component: str, messages: list[dict], msg, latency: float) -> None:
    LOG_PATH.parent.mkdir(exist_ok=True)
    record = {
        "ts": datetime.now().isoformat(timespec="seconds"), "component": component, "model": MODEL_DESC,
        "latency_s": round(latency, 2), "messages": messages,
        "output": msg.content, "reasoning_chars": len(getattr(msg, "reasoning", None) or ""),
        "tool_calls": [tc.model_dump() for tc in (msg.tool_calls or [])],
    }
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
