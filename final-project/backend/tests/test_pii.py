"""Обнаружение и токенизация персональных данных (ADR-0010)."""

from app.guardrails.input import inspect_input, restore


def test_rules_tokenize_contacts_and_documents():
    text = "Телефон +7 916 123-45-67, полис 1234567890123456, снилс 112-233-445 95, почта a.b@mail.ru"
    decision = inspect_input(text)

    assert "+7 916 123-45-67" not in decision.sanitized
    assert "1234567890123456" not in decision.sanitized
    assert "112-233-445 95" not in decision.sanitized
    assert "a.b@mail.ru" not in decision.sanitized
    assert set(decision.entities) == {"PHONE", "OMS", "SNILS", "EMAIL"}


def test_registry_names_are_tokenized():
    decision = inspect_input("Это Соколова Анна, запишите на УЗИ", ["Соколова Анна"])

    assert "Соколова Анна" not in decision.sanitized
    assert "[NAME_0]" in decision.sanitized
    assert decision.tokens["[NAME_0]"] == "Соколова Анна"


def test_restore_returns_only_own_values():
    decision = inspect_input(
        "Соколова Анна, телефон +7 916 123-45-67, а также Орлов Борис",
        ["Соколова Анна", "Орлов Борис"],
    )
    allowed = {"Соколова Анна", "+7 916 123-45-67"}

    restored = restore(decision.sanitized, decision.tokens, allowed)

    assert "Соколова Анна" in restored
    assert "+7 916 123-45-67" in restored
    assert "Орлов Борис" not in restored


def test_clinic_terms_are_not_tokenized():
    decision = inspect_input("Сколько стоит УЗИ брюшной полости по коду K29.5 в филиале Лесная")

    assert decision.sanitized == "Сколько стоит УЗИ брюшной полости по коду K29.5 в филиале Лесная"
    assert decision.tokens == {}
