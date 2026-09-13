from __future__ import annotations

from app.agents.router import BOOKING_CUES
from app.agents.state import GraphState
from app.ingest.bootstrap import Runtime


def run_crm(state: GraphState, runtime: Runtime) -> GraphState:
    if state.subject_id is None:
        state.escalate = True
        state.crm_facts.append("Нужен идентификатор пациента для записи.")
        return state

    access = runtime.policy.decide_crm(state.actor, state.subject_id)
    if not access.allowed:
        state.acl_denied = True
        state.crm_facts.append("Запись по чужой карте недоступна.")
        return state
    state.acl_via = access.via

    if state.session.pending and _confirm(state.text):
        pending = state.session.pending
        appointment = runtime.crm.book(
            patient_id=pending["subject_id"],
            service_id=pending["service_id"],
            branch_id=pending["branch_id"],
            slot=pending["slot"],
        )
        state.session.pending = None
        state.pending_confirm = False
        state.crm_facts.append(
            f"Запись подтверждена: {appointment.service_id}, {appointment.branch_id}, {appointment.slot}."
        )
        return state

    service_id, branch_id = _guess_service_branch(state)
    visits = runtime.crm.appointments_for(state.subject_id)
    if visits:
        state.crm_facts.append(
            "Текущие визиты: "
            + "; ".join(f"{item.service_id} {item.slot} ({item.status})" for item in visits)
        )

    if any(cue in state.text.lower() for cue in BOOKING_CUES):
        slots = runtime.crm.list_slots(service_id, branch_id)
        if slots:
            state.session.pending = {
                "subject_id": state.subject_id,
                "service_id": service_id,
                "branch_id": branch_id,
                "slot": slots[0],
            }
            state.pending_confirm = True
            state.crm_facts.append(
                f"Свободные окна {service_id} / {branch_id}: {', '.join(slots)}. "
                "Подтвердите первое окно ответом «да»."
            )
    return state


def _guess_service_branch(state: GraphState) -> tuple[str, str]:
    text = state.text.lower()
    service = "USI-02" if state.subject_id == "misha" else "USI-01"
    if "гастроскоп" in text:
        service = "END-01"
    if "педиатр" in text:
        service = "PED-01"
    branch = "yuzhny" if "южн" in text else "lesnaya"
    return service, branch


def _confirm(text: str) -> bool:
    lowered = text.lower().strip()
    return lowered in {"да", "да.", "подтверждаю", "подтверждаю.", "ок", "хорошо"} or "подтвержд" in lowered
