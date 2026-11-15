"""Robust extraction of a JSON object from an LLM reply (handles ```json fences and extra prose)."""
from __future__ import annotations

import json
import re


def parse_json_object(text: str | None) -> dict | None:
    """Return the first JSON object found in text, or None if there is none / it is invalid."""
    if not text:
        return None
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    start = cleaned.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(cleaned)):
        depth += cleaned[i] == "{"
        depth -= cleaned[i] == "}"
        if depth == 0:
            try:
                obj = json.loads(cleaned[start:i + 1])
            except json.JSONDecodeError:
                return None
            return obj if isinstance(obj, dict) else None
    return None
