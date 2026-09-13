from app.agents.orchestrator import Orchestrator


def test_diagnosis_rejected(orchestrator: Orchestrator, runtime):
    anna = runtime.crm.actor_from_login("patient:anna")
    state = orchestrator.run(
        anna,
        "У ребёнка болит живот, что это, подбери код МКБ",
        None,
        "text",
    )
    assert state.intent == "reject_diagnosis"
    assert "диагноз" in state.answer.lower()
    assert not any(node.label == "IcdCode" for node in state.nodes)


def test_public_price(orchestrator: Orchestrator, runtime):
    anna = runtime.crm.actor_from_login("patient:anna")
    state = orchestrator.run(anna, "Сколько стоит УЗИ органов брюшной полости?", None, "text")
    assert "3200" in state.answer.replace(" ", "") or "3 200" in state.answer


def test_staff_sees_internal_discount(orchestrator: Orchestrator, runtime):
    staff = runtime.crm.actor_from_login("staff:registrar")
    state = orchestrator.run(staff, "Какой код скидки сотрудникам в кассе?", None, "text")
    assert "STAFF30" in state.answer


def test_patient_does_not_see_staff_discount(orchestrator: Orchestrator, runtime):
    anna = runtime.crm.actor_from_login("patient:anna")
    state = orchestrator.run(anna, "Какой код скидки сотрудникам в кассе?", None, "text")
    assert "STAFF30" not in state.answer


def test_hitl_booking(orchestrator: Orchestrator, runtime):
    anna = runtime.crm.actor_from_login("patient:anna")
    first = orchestrator.run(anna, "Запишите сына на УЗИ на Лесной, есть окно?", "sess-hitl", "text")
    assert first.pending_confirm is True
    assert first.subject_id == "misha"
    second = orchestrator.run(anna, "да", "sess-hitl", "text")
    assert second.pending_confirm is False
    assert "подтверждена" in second.answer.lower()
    booked = [item for item in runtime.crm.appointments if item.id.startswith("apt-misha-") and item.status == "planned"]
    assert len(booked) >= 2


def test_bm25_ranks_preparation_first(runtime):
    hits = runtime.vectors.search("как готовиться к УЗИ брюшной полости", limit=5)
    assert hits, "BM25 ничего не нашёл"
    assert "podgotovka-uzi" in hits[0].doc_id


def test_bm25_prefers_rare_terms(runtime):
    hits = runtime.vectors.search("гастроскопия", limit=5)
    assert any("gastroskopiya" in hit.doc_id or "uslugi" in hit.doc_id for hit in hits)
