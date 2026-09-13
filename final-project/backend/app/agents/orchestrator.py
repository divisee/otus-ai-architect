"""Машина состояний Control Plane.

Узлы совпадают с ADR-0008: Memory → Router → Knowledge | CRM | Policy → Guardrails.
Промышленный checkpointer — PostgreSQL / LangGraph; на стенде состояние в SessionStore.
"""

from __future__ import annotations

from uuid import uuid4

from app.agents.crm_node import run_crm
from app.agents.generator import GroundedGenerator
from app.agents.knowledge import retrieve_knowledge
from app.agents.router import route
from app.agents.state import GraphState
from app.guardrails.output import REFUSAL
from app.ingest.bootstrap import Runtime
from app.policy.acl import Actor
from app.stores.audit import AuditEvent


class Orchestrator:
    def __init__(self, runtime: Runtime) -> None:
        self.runtime = runtime
        self.generator = GroundedGenerator()

    def run(
        self,
        actor: Actor,
        text: str,
        session_id: str | None,
        channel: str,
    ) -> GraphState:
        session = self.runtime.sessions.get_or_create(session_id, actor.id, channel)
        state = GraphState(
            request_id=uuid4().hex,
            actor=actor,
            text=text,
            channel=channel,
            session=session,
        )
        self.runtime.sessions.append(session, "user", text)

        state = route(state, self.runtime.crm.known_names())
        if state.intent == "reject_diagnosis":
            state.answer = REFUSAL
        elif state.intent == "knowledge":
            state = retrieve_knowledge(state, self.runtime)
            _scope_patient_chunks(state)
            state.answer = self.generator.generate(state, self.runtime)
        elif state.intent == "crm":
            state = run_crm(state, self.runtime)
            state.answer = self.generator.generate(state, self.runtime)
        elif state.intent == "both":
            state = retrieve_knowledge(state, self.runtime)
            _scope_patient_chunks(state)
            state = run_crm(state, self.runtime)
            state.answer = self.generator.generate(state, self.runtime)
        else:
            state.escalate = True
            state.answer = "Передаю запрос оператору регистратуры."

        session.last_subject_id = state.subject_id
        self.runtime.sessions.append(session, "assistant", state.answer)
        self.runtime.audit.write(
            AuditEvent(
                request_id=state.request_id,
                actor_id=actor.login,
                subject_id=state.subject_id,
                via=state.acl_via,
                acl_denied=state.acl_denied,
                intent=state.intent,
                chunk_ids=[chunk.chunk_id for chunk in state.chunks],
                node_ids=[node.id for node in state.nodes],
            )
        )
        return state


def _scope_patient_chunks(state: GraphState) -> None:
    if not state.subject_id:
        return
    state.chunks = [
        chunk
        for chunk in state.chunks
        if chunk.acl != "patient" or chunk.subject_id == state.subject_id
    ]
