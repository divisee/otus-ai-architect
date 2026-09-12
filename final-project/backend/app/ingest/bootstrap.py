from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

import yaml

from app.config import settings
from app.policy.acl import PolicyGate
from app.stores.audit import AuditLog
from app.stores.crm import CrmStub
from app.stores.graph import GraphStore
from app.stores.sessions import SessionStore
from app.stores.vectors import Chunk, VectorIndex


@dataclass
class Runtime:
    graph: GraphStore
    vectors: VectorIndex
    crm: CrmStub
    policy: PolicyGate
    sessions: SessionStore
    audit: AuditLog


def load_runtime(data_dir: Path | None = None) -> Runtime:
    root = data_dir or settings.data_dir
    graph = GraphStore()
    graph.load_cypher((root / "graph" / "seed.cypher").read_text(encoding="utf-8"))
    _load_icd(graph, root / "kb" / "reference" / "mkb10-parsed.csv")

    crm = CrmStub(json.loads((root / "crm" / "seed.json").read_text(encoding="utf-8")))
    vectors = VectorIndex()
    _load_corpus(vectors, root / "kb")

    return Runtime(
        graph=graph,
        vectors=vectors,
        crm=crm,
        policy=PolicyGate(crm),
        sessions=SessionStore(),
        audit=AuditLog(),
    )


def _load_icd(graph: GraphStore, path: Path) -> None:
    with path.open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    for row in rows:
        graph.add_icd(row["code"], row["name"], None, int(row["level"] or 0))
    for row in rows:
        parent = row.get("parent") or ""
        if parent and parent != "No":
            try:
                graph.add_edge(row["code"], "PARENT", parent)
            except KeyError:
                continue


def _load_corpus(index: VectorIndex, kb_dir: Path) -> None:
    manifest = yaml.safe_load((kb_dir / "manifest.yaml").read_text(encoding="utf-8"))
    for doc in manifest["documents"]:
        path = kb_dir / doc["path"]
        text = path.read_text(encoding="utf-8")
        for offset, chunk_text in enumerate(_split_markdown(text)):
            index.add(
                Chunk(
                    chunk_id=f"{doc['path']}#{offset}",
                    doc_id=doc["path"],
                    text=chunk_text,
                    acl=doc["acl"],
                    subject_id=doc.get("subject_id"),
                )
            )


def _split_markdown(text: str) -> list[str]:
    blocks = [part.strip() for part in text.split("\n\n") if part.strip()]
    if not blocks:
        return [text.strip()]
    return blocks
