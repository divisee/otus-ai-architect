from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date


@dataclass(frozen=True)
class Actor:
    id: str
    login: str
    role: str


@dataclass(frozen=True)
class AccessDecision:
    allowed: bool
    via: str | None
    reason: str = ""


def years_between(born: date, today: date) -> int:
    years = today.year - born.year
    if (today.month, today.day) < (born.month, born.day):
        years -= 1
    return years


class PolicyGate:
    """Пересечение retrieved ∩ acl роли. Отклонённый фрагмент в модель не идёт."""

    def __init__(self, crm, today: date | None = None) -> None:
        self.crm = crm
        self.today = today or date.today()

    def decide(self, actor: Actor, acl: str, subject_id: str | None) -> AccessDecision:
        if acl == "public" or not acl:
            return AccessDecision(True, "public")
        if acl == "staff":
            if actor.role == "staff":
                return AccessDecision(True, "staff")
            return AccessDecision(False, None, "staff_only")
        if not subject_id:
            return AccessDecision(False, None, "missing_subject")
        if subject_id == actor.id:
            return AccessDecision(True, "self")
        if self.crm.is_guardian(actor.id, subject_id):
            patient = self.crm.get_patient(subject_id)
            if patient is None:
                return AccessDecision(False, None, "unknown_subject")
            age = years_between(patient.birth_date, self.today)
            if age < 15 or patient.share_with_guardian:
                return AccessDecision(True, "guardian")
            return AccessDecision(False, None, "guardian_needs_consent")
        return AccessDecision(False, None, "no_relation")

    def decide_crm(self, actor: Actor, subject_id: str | None) -> AccessDecision:
        """Учётные сведения визита: слот, услуга, филиал, код из направления.

        Роль ``staff`` ведёт расписание в объёме должностных обязанностей
        (323-ФЗ ст. 13 ч. 4 п. 1). Медицинские документы карты под это правило
        не попадают: для чанков остаётся общий :meth:`decide`.
        """
        if actor.role == "staff":
            return AccessDecision(True, "staff_duty")
        return self.decide(actor, "patient", subject_id)

    def filter_chunks(self, actor: Actor, chunks: list) -> list:
        """Основание пишется в копию: объект фрагмента живёт в индексе и общий
        для всех запросов, а ``via`` относится к конкретному актору."""
        kept = []
        for chunk in chunks:
            decision = self.decide(actor, chunk.acl, chunk.subject_id)
            if decision.allowed:
                kept.append(replace(chunk, via=decision.via))
        return kept

    def filter_nodes(self, actor: Actor, nodes: list) -> list:
        kept = []
        for node in nodes:
            decision = self.decide(actor, node.props.get("acl", "public"), node.props.get("subject_id"))
            if decision.allowed:
                kept.append(node)
        return kept
