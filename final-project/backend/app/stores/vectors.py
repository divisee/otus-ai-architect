from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    text: str
    acl: str
    subject_id: str | None
    tokens: set[str] = field(default_factory=set)
    tf: Counter[str] = field(default_factory=Counter)
    via: str | None = None


def analyze(text: str) -> list[str]:
    normalized = text.lower().replace("ё", "е")
    return re.findall(r"[a-zа-я0-9.]{3,}", normalized)


def tokenize(text: str) -> set[str]:
    return set(analyze(text))


class VectorIndex:
    """BM25-индекс стенда с тем же payload, что у Qdrant: `acl`, `subject_id`, `doc_id`.

    Промышленный контур ищет гибридно: разрежённый BM25 плюс плотные векторы bge-m3,
    слияние результатов и переранжирование (ADR-0006). На стенде без GPU остаётся
    только разрежённая часть — ранжирование то же, эмбеддингов нет.
    """

    K1 = 1.2
    B = 0.75

    def __init__(self) -> None:
        self.chunks: list[Chunk] = []
        self.df: Counter[str] = Counter()

    def add(self, chunk: Chunk) -> None:
        terms = analyze(chunk.text)
        chunk.tf = Counter(terms)
        chunk.tokens = set(terms)
        self.df.update(chunk.tokens)
        self.chunks.append(chunk)

    @property
    def avgdl(self) -> float:
        if not self.chunks:
            return 0.0
        return sum(sum(chunk.tf.values()) for chunk in self.chunks) / len(self.chunks)

    def idf(self, term: str) -> float:
        n = len(self.chunks)
        df = self.df.get(term, 0)
        return math.log(1 + (n - df + 0.5) / (df + 0.5))

    def score(self, query_terms: list[str], chunk: Chunk, avgdl: float) -> float:
        if avgdl == 0:
            return 0.0
        length = sum(chunk.tf.values())
        total = 0.0
        for term in query_terms:
            freq = chunk.tf.get(term, 0)
            if not freq:
                continue
            norm = freq + self.K1 * (1 - self.B + self.B * length / avgdl)
            total += self.idf(term) * freq * (self.K1 + 1) / norm
        return total

    def search(self, query: str, limit: int = 8) -> list[Chunk]:
        query_terms = list(dict.fromkeys(analyze(query)))
        avgdl = self.avgdl
        scored: list[tuple[float, Chunk]] = []
        for chunk in self.chunks:
            value = self.score(query_terms, chunk, avgdl)
            if value > 0:
                scored.append((value, chunk))
        scored.sort(key=lambda item: (-item[0], item[1].chunk_id))
        return [chunk for _, chunk in scored[:limit]]
