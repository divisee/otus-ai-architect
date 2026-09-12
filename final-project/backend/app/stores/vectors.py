from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    text: str
    acl: str
    subject_id: str | None
    tokens: set[str] = field(default_factory=set)
    via: str | None = None


def tokenize(text: str) -> set[str]:
    normalized = text.lower().replace("ё", "е")
    return {token for token in re.findall(r"[a-zа-я0-9.]{3,}", normalized)}


class VectorIndex:
    """Лексический индекс с тем же payload, что у Qdrant: acl, subject_id, doc_id."""

    def __init__(self) -> None:
        self.chunks: list[Chunk] = []

    def add(self, chunk: Chunk) -> None:
        chunk.tokens = tokenize(chunk.text)
        self.chunks.append(chunk)

    def search(self, query: str, limit: int = 8) -> list[Chunk]:
        tokens = tokenize(query)
        scored: list[tuple[int, Chunk]] = []
        for chunk in self.chunks:
            overlap = len(tokens & chunk.tokens)
            if overlap:
                scored.append((overlap, chunk))
        scored.sort(key=lambda item: (-item[0], item[1].chunk_id))
        return [chunk for _, chunk in scored[:limit]]
