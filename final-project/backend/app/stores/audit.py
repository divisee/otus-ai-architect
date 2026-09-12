from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AuditEvent:
    request_id: str
    actor_id: str
    subject_id: str | None
    via: str | None
    acl_denied: bool
    intent: str
    chunk_ids: list[str] = field(default_factory=list)
    node_ids: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


class AuditLog:
    def __init__(self) -> None:
        self.events: dict[str, AuditEvent] = {}

    def write(self, event: AuditEvent) -> None:
        self.events[event.request_id] = event

    def get(self, request_id: str) -> AuditEvent | None:
        return self.events.get(request_id)
