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
