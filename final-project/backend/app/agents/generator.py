from __future__ import annotations

from app.agents.state import GraphState
from app.guardrails.output import ACL_REFUSAL, REFUSAL, apply_output_guardrails
from app.ingest.bootstrap import Runtime
from app.stores.graph import GraphNode


class GroundedGenerator:
    """Стендовый порт генерации. Промышленный порт — vLLM (ADR-0005)."""

    def generate(self, state: GraphState, runtime: Runtime) -> str:
        if state.intent == "reject_diagnosis":
            return REFUSAL
        if state.acl_denied and state.subject_id and state.subject_id != state.actor.id:
            return ACL_REFUSAL
        if state.acl_denied and not state.chunks and not state.nodes and not state.crm_facts:
            return ACL_REFUSAL
        if state.acl_denied and not _has_public_support(state):
            return ACL_REFUSAL

        parts: list[str] = []
        if state.acl_denied:
            parts.append(ACL_REFUSAL)

        for node in state.nodes[:10]:
            line = _format_node(node)
            if line:
                parts.append(line)
        for chunk in state.chunks[:4]:
            excerpt = " ".join(chunk.text.split())
            if len(excerpt) > 280:
                excerpt = excerpt[:280].rsplit(" ", 1)[0] + "…"
            parts.append(excerpt)
        parts.extend(state.crm_facts)

        if not parts:
            return (
                "Не нашла опоры в знаниях клиники. Передаю запрос оператору регистратуры."
            )

        text = " ".join(parts)
        allowed = {state.actor.id}
        if state.subject_id and not state.acl_denied:
            allowed.add(state.subject_id)
        if state.acl_via == "guardian" and state.subject_id:
            allowed.add(state.subject_id)
        return apply_output_guardrails(text, state.actor, runtime.crm, allowed)


def _has_public_support(state: GraphState) -> bool:
    return any(node.props.get("acl", "public") == "public" for node in state.nodes) or any(
        chunk.acl == "public" for chunk in state.chunks
    )


def _format_node(node: GraphNode) -> str:
    if node.label == "IcdCode":
        return f"Код {node.id} в справочнике МКБ-10: {node.props.get('name')} (не диагноз)."
    if node.label == "Preparation":
        hours = node.props.get("hours_fasting")
        extra = f", не есть {hours} ч" if hours else ""
        return f"Подготовка: {node.props.get('title')}{extra}."
    if node.label == "Service":
        price = node.props.get("price")
        price_s = f", {int(price)} ₽" if price else ""
        return f"Услуга {node.id}: {node.props.get('name')}{price_s}."
    if node.label == "Doctor":
        return f"Врач {node.props.get('name')}, {node.props.get('specialty')}."
    if node.label == "Branch":
        return f"Филиал {node.props.get('name')}, {node.props.get('address')}."
    return ""
