"""Baseline: vanilla RAG (top-k chunks -> one LLM call). Used ONLY for comparison in evals."""
from __future__ import annotations

from . import llm
from .retriever import Retriever

PROMPT = ("Answer the employee's question using the context below.\n\nContext:\n{context}\n\nQuestion: {question}")


def vanilla_rag(question: str, retriever: Retriever, k: int = 3) -> str:
    hits = retriever.search(question, k=k)
    context = "\n\n".join(h.chunk.text for h in hits)
    reply = llm.chat([{"role": "user", "content": PROMPT.format(context=context, question=question)}],
                     component="baseline")
    return (reply.content or "").strip()
