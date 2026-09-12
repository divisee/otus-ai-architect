from __future__ import annotations

import re
from dataclasses import dataclass


PHONE_RE = re.compile(r"\+?\d[\d\-\s()]{8,}\d")

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


def inspect_input(text: str) -> InputDecision:
    lowered = text.lower().replace("ё", "е")
    reject = any(cue in lowered for cue in DIAGNOSIS_DIRECT)
    if not reject and any(cue in lowered for cue in SYMPTOM) and any(cue in lowered for cue in DIAGNOSIS_Q):
        reject = True
    tokens: dict[str, str] = {}
    sanitized = text
    for index, match in enumerate(PHONE_RE.findall(text)):
        token = f"[PHONE_{index}]"
        tokens[token] = match
        sanitized = sanitized.replace(match, token)
    return InputDecision(reject_diagnosis=reject, sanitized=sanitized, tokens=tokens)
