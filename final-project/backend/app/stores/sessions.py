from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


@dataclass
class Session:
    session_id: str
    actor_id: str
    channel: str
    turns: list[dict[str, str]] = field(default_factory=list)
    pending: dict[str, Any] | None = None
    last_subject_id: str | None = None


class SessionStore:
    def __init__(self) -> None:
        self._items: dict[str, Session] = {}

    def get_or_create(self, session_id: str | None, actor_id: str, channel: str) -> Session:
        if session_id and session_id in self._items:
            session = self._items[session_id]
            session.channel = channel
            return session
        created = Session(session_id=session_id or uuid4().hex, actor_id=actor_id, channel=channel)
        self._items[created.session_id] = created
        return created

    def append(self, session: Session, role: str, text: str) -> None:
        session.turns.append({"role": role, "text": text})
        session.turns = session.turns[-8:]
