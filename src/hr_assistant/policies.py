"""Load policy files and split them into section chunks with numbered items (for citations)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

POLICY_DIR = Path(__file__).resolve().parents[2] / "data" / "policies"
SECTION_RE = re.compile(r"^##\s+(\d+)\.\s+(.*)$")
ITEM_RE = re.compile(r"^(\d+\.\d+)\s+(.*)$")
CITATION_RE = re.compile(r"([a-z_]+\.md)\s*§\s*(\d+\.\d+)")


@dataclass(frozen=True)
class Chunk:
    id: str                      # e.g. "leave.md#3"
    doc: str                     # file name
    doc_title: str
    section_no: str
    section_title: str
    items: dict = field(default_factory=dict, hash=False, compare=False)  # "3.2" -> text

    @property
    def text(self) -> str:
        body = "\n".join(f"{no} {txt}" for no, txt in self.items.items())
        return f"{self.doc_title} | {self.section_no}. {self.section_title}\n{body}"

    def cited_text(self) -> str:
        """Text with item ids in citation form, used inside prompts."""
        return "\n".join(f"[{self.doc} §{no}] {txt}" for no, txt in self.items.items())


def load_chunks(policy_dir: Path = POLICY_DIR) -> list[Chunk]:
    chunks: list[Chunk] = []
    for path in sorted(policy_dir.glob("*.md")):
        title, current = "", None
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("# "):
                title = line[2:].strip()
            elif (m := SECTION_RE.match(line)):
                current = Chunk(f"{path.name}#{m.group(1)}", path.name, title, m.group(1), m.group(2), {})
                chunks.append(current)
            elif current and (m := ITEM_RE.match(line)):
                current.items[m.group(1)] = m.group(2)
    return chunks


def item_index(chunks: list[Chunk]) -> dict[str, str]:
    """Map 'leave.md §3.2' -> item text; used to validate and look up citations."""
    return {f"{c.doc} §{no}": txt for c in chunks for no, txt in c.items.items()}


def parse_citations(citations: list[str]) -> list[str]:
    """Normalise citation strings to 'doc.md §n.m'; unparseable ones are dropped."""
    out = []
    for c in citations:
        m = CITATION_RE.search(str(c))
        if m:
            out.append(f"{m.group(1)} §{m.group(2)}")
    return out
