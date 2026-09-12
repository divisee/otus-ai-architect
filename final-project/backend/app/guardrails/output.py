from __future__ import annotations

from app.policy.acl import Actor
from app.stores.crm import CrmStub


REFUSAL = (
    "Не могу ставить диагноз или подбирать код МКБ по симптомам. "
    "Могу записать к врачу клиники или прочитать код из уже выданного направления."
)

ACL_REFUSAL = "Эти сведения закрыты политикой доступа. Могу помочь с публичными услугами или вашей картой."


def apply_output_guardrails(text: str, actor: Actor, crm: CrmStub, allowed_subjects: set[str]) -> str:
    cleaned = text
    for patient in crm.patients.values():
        if patient.id in allowed_subjects or patient.id == actor.id:
            continue
        if patient.full_name.split()[0].lower() in cleaned.lower() and patient.id != actor.id:
            if patient.full_name.lower() in cleaned.lower():
                cleaned = ACL_REFUSAL
                break
    return cleaned.strip()
