from __future__ import annotations

import re

from app.agents.state import GraphState, Intent
from app.guardrails.input import inspect_input


ICD_RE = re.compile(r"\b([A-ZА-Я]\d{2}(?:\.\d+)?)\b", re.I)

CRM_CUES = ("запис", "слот", "перенес", "отмен", "окно", "свободн", "подтверд")
KNOWLEDGE_CUES = (
    "подготов",
    "цен",
    "врач",
    "филиал",
    "узи",
    "код",
    "мкб",
    "направл",
    "гастроскоп",
    "анализ",
    "прайс",
    "услуг",
    "как готов",
    "педиатр",
    "лесн",
    "южн",
)
CHILD_CUES = ("сын", "доч", "миш", "ребен", "ребён", "ребенк")
ANNA_CUES = ("анна", "соколов")
BORIS_CUES = ("борис", "орлов")


def route(state: GraphState, known_names: list[str] | None = None) -> GraphState:
    decision = inspect_input(state.text, known_names)
    state.extra["pii_tokens"] = decision.tokens
    state.extra["pii_entities"] = decision.entities
    state.extra["sanitized"] = decision.sanitized
    if decision.reject_diagnosis:
        state.intent = "reject_diagnosis"
        return state

    if state.session.pending and _is_confirm(state.text):
        state.intent = "crm"
        state.subject_id = state.session.pending.get("subject_id") or state.session.last_subject_id
        return state

    lowered = state.text.lower().replace("ё", "е")
    want_crm = any(cue in lowered for cue in CRM_CUES)
    want_knowledge = any(cue in lowered for cue in KNOWLEDGE_CUES) or bool(ICD_RE.search(state.text))
    if want_crm and want_knowledge:
        state.intent = "both"
    elif want_crm:
        state.intent = "crm"
    else:
        state.intent = "knowledge"

    state.subject_id = resolve_subject(state, lowered)
    return state


def resolve_subject(state: GraphState, lowered: str) -> str | None:
    actor = state.actor
    if any(cue in lowered for cue in CHILD_CUES):
        return "misha"
    if actor.id != "anna" and any(cue in lowered for cue in ANNA_CUES):
        return "anna"
    if actor.id != "boris" and any(cue in lowered for cue in BORIS_CUES):
        return "boris"
    if actor.role == "patient":
        return actor.id
    return state.session.last_subject_id


def _is_confirm(text: str) -> bool:
    lowered = text.lower().strip()
    return lowered in {"да", "да.", "подтверждаю", "подтверждаю.", "ок", "хорошо"} or "подтвержд" in lowered


def next_after_router(state: GraphState) -> Intent:
    return state.intent
