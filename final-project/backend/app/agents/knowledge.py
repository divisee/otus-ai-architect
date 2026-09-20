from __future__ import annotations

import re

from app.agents.state import GraphState
from app.ingest.bootstrap import Runtime
from app.stores.graph import GraphNode


ICD_RE = re.compile(r"\b([A-Z]\d{2}(?:\.\d+)?)\b", re.I)

# От самого узкого основания к самому широкому: аудитора интересует,
# чем открыли закрытое, а не то, что нашлось общедоступное.
VIA_PRIORITY = ("guardian", "staff_duty", "self", "staff", "public")


def retrieve_knowledge(state: GraphState, runtime: Runtime) -> GraphState:
    query = state.text
    seeds = runtime.graph.search(query)
    for code in ICD_RE.findall(query):
        node = runtime.graph.get(code.upper())
        if node:
            seeds.append(node)
    if state.subject_id:
        for appointment in runtime.crm.appointments_for(state.subject_id):
            if appointment.icd_on_referral:
                node = runtime.graph.get(appointment.icd_on_referral)
                if node:
                    seeds.append(node)
            service = runtime.graph.get(appointment.service_id)
            if service:
                seeds.append(service)

    walked = runtime.graph.walk(seeds, hops=2) if seeds else []
    raw_chunks = runtime.vectors.search(query, limit=10)
    state.nodes = runtime.policy.filter_nodes(state.actor, _unique_nodes(walked))
    state.chunks = runtime.policy.filter_chunks(state.actor, raw_chunks)

    denied_card = False
    if state.subject_id and state.subject_id != state.actor.id:
        card = runtime.policy.decide(state.actor, "patient", state.subject_id)
        if card.allowed:
            state.acl_via = card.via
        elif state.actor.role == "staff":
            # роль staff ведёт расписание, но медицинские документы карты не читает
            state.chunks = [chunk for chunk in state.chunks if chunk.subject_id != state.subject_id]
            state.acl_via = "staff_duty"
        else:
            denied_card = True
            state.chunks = [chunk for chunk in state.chunks if chunk.subject_id != state.subject_id]

    public_or_own = [chunk for chunk in state.chunks if chunk.acl in {"public", "staff"} or chunk.subject_id]
    state.chunks = public_or_own
    # Сузить по субъекту запроса нужно ДО расчёта оснований: иначе в журнал
    # попадёт основание фрагмента, который в контекст модели не вошёл.
    _scope_patient_chunks(state)
    vias = {chunk.via for chunk in state.chunks if chunk.via}
    if state.acl_via:
        vias.add(state.acl_via)
    # Журнал хранит все основания, по которым что-то было допущено, а `acl_via`
    # называет главное — то, которым открыли закрытые сведения. Порядок задан
    # явно: из множества основание брать нельзя, оно не упорядочено.
    state.acl_vias = sorted(vias, key=lambda via: VIA_PRIORITY.index(via) if via in VIA_PRIORITY else 99)
    if state.acl_vias:
        state.acl_via = state.acl_vias[0]
    if denied_card:
        state.acl_denied = True
        if not state.acl_via:
            state.acl_via = None
    return state


def _scope_patient_chunks(state: GraphState) -> None:
    """Документы карты — только того субъекта, о ком идёт речь в реплике."""
    if not state.subject_id:
        return
    state.chunks = [
        chunk
        for chunk in state.chunks
        if chunk.acl != "patient" or chunk.subject_id == state.subject_id
    ]


def _unique_nodes(nodes: list[GraphNode]) -> list[GraphNode]:
    seen: set[str] = set()
    result: list[GraphNode] = []
    for node in nodes:
        if node.key in seen:
            continue
        seen.add(node.key)
        result.append(node)
    return result
