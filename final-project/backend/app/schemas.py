from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    text: str = Field(min_length=1)
    session_id: str | None = None
    channel: Literal["text", "voice"] = "text"


class VoiceRequest(BaseModel):
    transcript: str = Field(min_length=1)
    session_id: str | None = None
    speakers: list[str] = Field(default_factory=list)


class ChatResponse(BaseModel):
    request_id: str
    session_id: str
    text: str
    intent: str
    subject_id: str | None
    acl_via: str | None
    acl_denied: bool
    node_ids: list[str] = Field(default_factory=list)
    chunk_ids: list[str] = Field(default_factory=list)
    pending_confirm: bool = False
    escalate: bool = False
    channel: Literal["text", "voice"] = "text"
