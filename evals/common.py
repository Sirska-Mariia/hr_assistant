"""Shared helpers for eval scripts: load labelled data, save results with metadata."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_jsonl(name: str) -> list[dict]:
    with (ROOT / "data" / "eval" / name).open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def save_results(component: str, metrics: dict, failures: list[dict], model: str) -> Path:
    out = ROOT / "evals" / "results"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{component}_{datetime.now():%Y%m%d_%H%M}.json"
    payload = {"component": component, "model": model, "metrics": metrics, "failures": failures}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
