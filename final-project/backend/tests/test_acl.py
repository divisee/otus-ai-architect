from datetime import date

from app.agents.orchestrator import Orchestrator
from app.policy.acl import PolicyGate, years_between


def test_misha_age_under_15(runtime):
    patient = runtime.crm.get_patient("misha")
    assert years_between(patient.birth_date, date(2026, 9, 12)) == 8


def test_anna_reads_misha_card(runtime):
    policy = PolicyGate(runtime.crm, today=date(2026, 9, 12))
    anna = runtime.crm.actor_from_login("patient:anna")
    assert policy.decide(anna, "patient", "misha").via == "guardian"


def test_boris_cannot_read_misha_or_anna(runtime):
    policy = PolicyGate(runtime.crm, today=date(2026, 9, 12))
    boris = runtime.crm.actor_from_login("patient:boris")
    assert policy.decide(boris, "patient", "misha").allowed is False
    assert policy.decide(boris, "patient", "anna").allowed is False


def test_patient_cannot_read_staff_chunk(runtime):
    policy = PolicyGate(runtime.crm)
    anna = runtime.crm.actor_from_login("patient:anna")
    assert policy.decide(anna, "staff", None).allowed is False


def test_boris_denied_anna_referral(orchestrator: Orchestrator, runtime):
    boris = runtime.crm.actor_from_login("patient:boris")
    state = orchestrator.run(
        boris,
        "Какое направление у Анны Соколовой и когда её УЗИ?",
        session_id=None,
        channel="text",
    )
    assert state.acl_denied is True
    assert "K80.1" not in state.answer
    assert "111-00-01" not in state.answer
    assert "закрыты" in state.answer.lower() or "доступ" in state.answer.lower()


def test_anna_reads_son_icd(orchestrator: Orchestrator, runtime):
    anna = runtime.crm.actor_from_login("patient:anna")
    state = orchestrator.run(
        anna,
        "Когда УЗИ у сына и что за код N28.1 в его направлении?",
        session_id=None,
        channel="text",
    )
    assert state.acl_denied is False
    assert state.acl_via == "guardian"
    assert state.subject_id == "misha"
    assert "N28.1" in state.answer
    assert "киста" in state.answer.lower()
    assert "111-00-02" not in state.answer


def test_registrar_sees_visits_but_not_card_documents(runtime):
    policy = PolicyGate(runtime.crm, today=date(2026, 9, 12))
    registrar = runtime.crm.actor_from_login("staff:registrar")
    assert policy.decide_crm(registrar, "anna").via == "staff_duty"
    assert policy.decide(registrar, "patient", "anna").allowed is False


def test_registrar_reads_referral_code_from_crm(orchestrator: Orchestrator, runtime):
    registrar = runtime.crm.actor_from_login("staff:registrar")
    state = orchestrator.run(
        registrar,
        "Когда УЗИ у Анны Соколовой и на какое окно её записать?",
        session_id=None,
        channel="text",
    )
    assert state.acl_denied is False
    assert state.acl_via == "staff_duty"
    assert "USI-01" in state.answer
    assert "1234 5678" not in state.answer


def test_journal_basis_matches_the_context(runtime, orchestrator):
    """Основание в журнале называет только то, чем реально открыли фрагмент.

    BM25 по слову «УЗИ» достаёт направление ребёнка, и Policy справедливо
    допускает его по опеке. Но субъект этой реплики — сама Анна, фрагмент
    ребёнка в контекст не идёт, и «guardian» в журнале означал бы основание
    для того, чего в ответе нет.
    """
    anna = runtime.crm.actor_from_login("patient:anna")
    state = orchestrator.run(anna, "Сколько стоит УЗИ и как к нему готовиться?", None, "text")

    assert "guardian" not in state.acl_vias
    assert set(state.acl_vias) == {chunk.via for chunk in state.chunks if chunk.via}


def test_refusal_carries_no_access_basis(runtime, orchestrator):
    """Отказ не записывается с основанием доступа."""
    anna = runtime.crm.actor_from_login("patient:anna")
    state = orchestrator.run(anna, "Покажи визиты пациента Орлова Бориса", None, "text")

    assert state.acl_denied is True
    assert "guardian" not in state.acl_vias
    assert all(chunk.subject_id != "boris" for chunk in state.chunks)


def test_policy_does_not_mark_the_shared_index(runtime):
    """`via` относится к актору, а фрагмент живёт в индексе и общий для всех."""
    policy = PolicyGate(runtime.crm, today=date(2026, 9, 12))
    anna = runtime.crm.actor_from_login("patient:anna")
    raw = runtime.vectors.search("направление УЗИ", limit=10)

    policy.filter_chunks(anna, raw)

    assert all(chunk.via is None for chunk in raw)
