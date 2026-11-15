"""Small dependency-free metric helpers."""
from __future__ import annotations

from collections import Counter


def prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


def classification_report(gold: list[str], pred: list[str], labels: list[str]) -> dict:
    """Accuracy, per-class precision/recall/F1, macro-F1 and confusion matrix (rows = gold)."""
    n = len(gold)
    acc = sum(g == p for g, p in zip(gold, pred)) / n if n else 0.0
    per_class = {}
    for lab in labels:
        tp = sum(g == lab and p == lab for g, p in zip(gold, pred))
        fp = sum(g != lab and p == lab for g, p in zip(gold, pred))
        fn = sum(g == lab and p != lab for g, p in zip(gold, pred))
        pr, rc, f1 = prf(tp, fp, fn)
        per_class[lab] = {"precision": round(pr, 3), "recall": round(rc, 3), "f1": round(f1, 3), "support": tp + fn}
    counts = Counter(zip(gold, pred))
    matrix = {g: {p: counts[(g, p)] for p in labels} for g in labels}
    macro = sum(v["f1"] for v in per_class.values()) / len(labels)
    return {"n": n, "accuracy": round(acc, 3), "macro_f1": round(macro, 3),
            "per_class": per_class, "confusion_matrix": matrix}
