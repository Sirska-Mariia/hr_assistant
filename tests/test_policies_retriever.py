from hr_assistant.policies import item_index, load_chunks, parse_citations
from hr_assistant.retriever import Retriever


def test_chunk_and_item_counts():
    chunks = load_chunks()
    assert len(chunks) == 31
    assert "leave.md §3.2" in item_index(chunks)
    assert all(c.items for c in chunks)


def test_parse_citations_normalises_and_drops_garbage():
    assert parse_citations(["leave.md §3.2", "see leave.md § 4.1 please", "nonsense"]) == ["leave.md §3.2", "leave.md §4.1"]


def test_bm25_finds_obvious_sections():
    r = Retriever(mode="bm25")
    assert r.search("learning budget per year", k=1)[0].chunk.id == "benefits.md#3"
    assert r.search("employment certificate", k=1)[0].chunk.id == "internal_requests.md#5"


def test_hybrid_skips_bm25_when_no_lexical_overlap(monkeypatch):
    import numpy as np
    r = Retriever(mode="hybrid")
    n = len(r.chunks)
    dense = np.zeros(n); dense[7] = 1.0  # dense says chunk 7 is best
    monkeypatch.setattr(r, "_dense_scores", lambda q: dense)
    monkeypatch.setattr(r, "_bm25_scores", lambda q: np.zeros(n))  # Cyrillic query: all-zero BM25
    assert r.search("Скільки днів?", k=1)[0].chunk is r.chunks[7]
