"""Hybrid retriever over policy section chunks: BM25 + multilingual dense embeddings, fused with RRF.

modes: "bm25", "dense", "hybrid". The dense model is loaded lazily (first use).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

from .policies import Chunk, load_chunks

DENSE_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
RRF_K = 60


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float


def _stem(token: str) -> str:
    """Very light English plural stripping ("certificates" -> "certificate"); no external stemmer."""
    return token[:-1] if len(token) > 3 and token.endswith("s") and not token.endswith("ss") else token


def tokenize(text: str) -> list[str]:
    return [_stem(t) for t in re.findall(r"\w+", text.lower())]


class Retriever:
    def __init__(self, chunks: list[Chunk] | None = None, mode: str = "hybrid", dense_model: str = DENSE_MODEL):
        assert mode in {"bm25", "dense", "hybrid"}
        self.chunks = chunks or load_chunks()
        self.mode, self.dense_model_name = mode, dense_model
        self._bm25 = None
        self._model = None
        self._emb = None

    # --- BM25 -----------------------------------------------------------
    def _bm25_scores(self, query: str) -> np.ndarray:
        if self._bm25 is None:
            from rank_bm25 import BM25Okapi
            self._bm25 = BM25Okapi([tokenize(c.text) for c in self.chunks])
        return np.asarray(self._bm25.get_scores(tokenize(query)), dtype=float)

    # --- dense ----------------------------------------------------------
    def _dense_scores(self, query: str) -> np.ndarray:
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.dense_model_name)
            self._emb = self._model.encode([c.text for c in self.chunks], normalize_embeddings=True)
        q = self._model.encode([query], normalize_embeddings=True)[0]
        return np.asarray(self._emb @ q, dtype=float)

    # --- public ---------------------------------------------------------
    def search(self, query: str, k: int = 4) -> list[Hit]:
        if self.mode == "bm25":
            scores = self._bm25_scores(query)
        elif self.mode == "dense":
            scores = self._dense_scores(query)
        else:
            scores = np.zeros(len(self.chunks))
            for s in (self._bm25_scores(query), self._dense_scores(query)):
                if s.max() <= 0:  # no lexical overlap (e.g. Ukrainian query): BM25 carries no information, skip it
                    continue
                ranks = np.empty(len(s), dtype=int)
                ranks[np.argsort(-s, kind="stable")] = np.arange(len(s))
                scores += 1.0 / (RRF_K + ranks + 1)
        order = np.argsort(-scores, kind="stable")[:k]
        return [Hit(self.chunks[i], float(scores[i])) for i in order]
