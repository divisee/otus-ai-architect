"""Голосовой адаптер. Тот же оркестратор; актор не назначается по SPEAKER_*."""

from app.agents.orchestrator import Orchestrator
from app.agents.state import GraphState
from app.policy.acl import Actor
from app.schemas import VoiceRequest


def voice_to_state(orchestrator: Orchestrator, actor: Actor, request: VoiceRequest) -> GraphState:
    _ = request.speakers  # метаданные диаризации, не ACL
    return orchestrator.run(
        actor=actor,
        text=request.transcript,
        session_id=request.session_id,
        channel="voice",
    )
