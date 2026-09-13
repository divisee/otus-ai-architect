"""Входные guardrails: запрет диагноза и обнаружение персональных данных.

Обнаружение выполняется слоями (ADR-0010):

1. правила — телефон, полис ОМС, СНИЛС, дата рождения, адрес электронной почты;
2. распознавание именованных сущностей — в целевом контуре, каркас Presidio;
3. справочник — точные ФИО из реестра CRM.

На стенде без GPU работают слои 1 и 3: этого достаточно, чтобы проверить контракт
«модель видит токен, значение остаётся в состоянии диалога».
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


PHONE_RE = re.compile(r"\+?\d[\d\-\s()]{8,}\d")
OMS_RE = re.compile(r"\b\d{16}\b")
SNILS_RE = re.compile(r"\b\d{3}-\d{3}-\d{3}\s?\d{2}\b")
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[A-Za-zА-Яа-я]{2,}\b")
BIRTH_DATE_RE = re.compile(r"\b(0?[1-9]|[12]\d|3[01])[.\-/](0?[1-9]|1[0-2])[.\-/](19|20)\d{2}\b")

# Порядок важен: длинные и однозначные сущности снимаются первыми,
# иначе номер полиса распадётся на «телефон» плюс хвост.
RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("OMS", OMS_RE),
    ("SNILS", SNILS_RE),
    ("EMAIL", EMAIL_RE),
    ("BIRTHDATE", BIRTH_DATE_RE),
    ("PHONE", PHONE_RE),
)

DIAGNOSIS_DIRECT = (
    "поставь диагноз",
    "поставьте диагноз",
    "какой у меня диагноз",
    "подбери код",
    "подберите код",
    "что у меня за болезнь",
)

SYMPTOM = ("болит", "сыпь", "тошнит", "температура", "изжога", "рвота", "кашель")
DIAGNOSIS_Q = ("что это", "что со мной", "какой диагноз", "поставь", "что такое у")


@dataclass
class InputDecision:
    reject_diagnosis: bool
    sanitized: str
    tokens: dict[str, str]
    entities: list[str] = field(default_factory=list)


def inspect_input(text: str, known_names: list[str] | None = None) -> InputDecision:
    lowered = text.lower().replace("ё", "е")
    reject = any(cue in lowered for cue in DIAGNOSIS_DIRECT)
    if not reject and any(cue in lowered for cue in SYMPTOM) and any(cue in lowered for cue in DIAGNOSIS_Q):
        reject = True

    tokens: dict[str, str] = {}
    entities: list[str] = []
    sanitized = text

    for label, pattern in RULES:
        index = 0
        while True:
            found = pattern.search(sanitized)
            if found is None:
                break
            token = f"[{label}_{index}]"
            tokens[token] = found.group(0)
            entities.append(label)
            sanitized = sanitized[: found.start()] + token + sanitized[found.end() :]
            index += 1

    for name in _name_variants(known_names or []):
        if name.lower() not in sanitized.lower():
            continue
        token = f"[NAME_{sum(1 for key in tokens if key.startswith('[NAME_'))}]"
        tokens[token] = name
        entities.append("NAME")
        sanitized = re.sub(re.escape(name), token, sanitized, flags=re.I)

    return InputDecision(reject_diagnosis=reject, sanitized=sanitized, tokens=tokens, entities=entities)


def restore(text: str, tokens: dict[str, str], allowed: set[str] | None = None) -> str:
    """Развернуть токены обратно — только те значения, что разрешены актору."""
    restored = text
    for token, value in tokens.items():
        if allowed is not None and value not in allowed:
            continue
        restored = restored.replace(token, value)
    return restored


def _name_variants(names: list[str]) -> list[str]:
    """Полное ФИО ловим целиком; порядок — от длинного к короткому."""
    return sorted({name.strip() for name in names if name.strip()}, key=len, reverse=True)
