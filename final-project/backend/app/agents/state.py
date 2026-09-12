from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from app.policy.acl import Actor
from app.stores.graph import GraphNode
from app.stores.sessions import Session
from app.stores.vectors import Chunk


Intent = Literal["knowledge", "crm", "both", "reject_diagnosis", "escalate"]


@dataclass
class GraphState:
    request_id: str
    actor: Actor
    text: str
    channel: str
    session: Session
    intent: Intent = "knowledge"
    subject_id: str | None = None
    chunks: list[Chunk] = field(default_factory=list)
    nodes: list[GraphNode] = field(default_factory=list)
    crm_facts: list[str] = field(default_factory=list)
    acl_via: str | None = None
    acl_denied: bool = False
    pending_confirm: bool = False
    escalate: bool = False
    answer: str = ""
    extra: dict[str, Any] = field(default_factory=dict)
