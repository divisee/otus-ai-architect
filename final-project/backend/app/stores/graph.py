from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field


NODE_RE = re.compile(r"MERGE\s+\((\w+):(\w+)\s*\{([^}]*)\}\)", re.I)
REL_RE = re.compile(r"MERGE\s+\((\w+)\)-\[:(\w+)\]->\((\w+)\)", re.I)
PROP_RE = re.compile(r"(\w+)\s*:\s*(?:'([^']*)'|(\d+(?:\.\d+)?))")


@dataclass
class GraphNode:
    key: str
    label: str
    props: dict[str, str | int | float] = field(default_factory=dict)

    @property
    def id(self) -> str:
        raw = self.props.get("id") or self.props.get("code") or self.key
        return str(raw)

    def text(self) -> str:
        parts = [self.label, self.id]
        for key in ("name", "title", "address", "specialty"):
            value = self.props.get(key)
            if value:
                parts.append(str(value))
        return " ".join(parts)


@dataclass
class GraphEdge:
    src: str
    rel: str
    dst: str


class GraphStore:
    def __init__(self) -> None:
        self.nodes: dict[str, GraphNode] = {}
        self.alias: dict[str, str] = {}
        self.out: dict[str, list[GraphEdge]] = defaultdict(list)
        self.incoming: dict[str, list[GraphEdge]] = defaultdict(list)

    def add_node(self, node: GraphNode, alias: str | None = None) -> None:
        self.nodes[node.key] = node
        if alias:
            self.alias[alias] = node.key
        self.alias[node.id] = node.key
        self.alias[node.key] = node.key

    def add_edge(self, src_alias: str, rel: str, dst_alias: str) -> None:
        src = self.alias[src_alias]
        dst = self.alias[dst_alias]
        edge = GraphEdge(src, rel, dst)
        self.out[src].append(edge)
        self.incoming[dst].append(edge)

    def get(self, ident: str) -> GraphNode | None:
        key = self.alias.get(ident) or self.alias.get(ident.upper())
        if key:
            return self.nodes.get(key)
        return self.nodes.get(ident)

    def load_cypher(self, text: str) -> None:
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("//") or line.upper().startswith("CREATE CONSTRAINT"):
                continue
            node_match = NODE_RE.search(line)
            if node_match:
                alias, label, props_raw = node_match.groups()
                props: dict[str, str | int | float] = {}
                for key, string, number in PROP_RE.findall(props_raw):
                    props[key] = float(number) if number and "." in number else int(number) if number else string
                node = GraphNode(key=str(props.get("id") or props.get("code") or alias), label=label, props=props)
                self.add_node(node, alias=alias)
                continue
            rel_match = REL_RE.search(line)
            if rel_match:
                src, rel, dst = rel_match.groups()
                self.add_edge(src, rel, dst)

    def add_icd(self, code: str, name: str, parent: str | None, level: int) -> None:
        node = GraphNode(
            key=code,
            label="IcdCode",
            props={"code": code, "name": name, "acl": "public", "level": level},
        )
        self.add_node(node)
        if parent and parent != "No" and parent in self.nodes:
            self.add_edge(code, "PARENT", parent)

    def search(self, query: str, limit: int = 12) -> list[GraphNode]:
        tokens = tokenize(query)
        scored: list[tuple[int, GraphNode]] = []
        for node in self.nodes.values():
            blob = tokenize(node.text())
            overlap = len(tokens & blob)
            if node.label == "IcdCode" and node.id.upper() not in query.upper():
                continue
            if overlap:
                scored.append((overlap, node))
        scored.sort(key=lambda item: (-item[0], item[1].id))
        return [node for _, node in scored[:limit]]

    def walk(self, seeds: list[GraphNode], hops: int = 2) -> list[GraphNode]:
        seen = {seed.key for seed in seeds}
        frontier = list(seeds)
        collected = list(seeds)
        for _ in range(hops):
            nxt: list[GraphNode] = []
            for node in frontier:
                for edge in self.out.get(node.key, []) + self.incoming.get(node.key, []):
                    other_key = edge.dst if edge.src == node.key else edge.src
                    if other_key in seen:
                        continue
                    other = self.nodes.get(other_key)
                    if other is None or other.label == "IcdCode" and edge.rel != "PARENT":
                        if other is None:
                            continue
                        if other.label == "IcdCode" and edge.rel not in {"PARENT", "OFTEN_CODED_AS"}:
                            continue
                    seen.add(other_key)
                    nxt.append(other)
                    collected.append(other)
            frontier = nxt
        return collected

    def neighbors(self, node_id: str, rel: str) -> list[GraphNode]:
        key = self.alias.get(node_id, node_id)
        result = []
        for edge in self.out.get(key, []):
            if edge.rel == rel:
                result.append(self.nodes[edge.dst])
        return result


def tokenize(text: str) -> set[str]:
    normalized = text.lower().replace("ё", "е")
    return {token for token in re.findall(r"[a-zа-я0-9.]{2,}", normalized)}
