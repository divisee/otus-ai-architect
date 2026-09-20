"""Порт генерации для демонстрационного стенда.

Правило контура сохраняется: guardrails и проверка прав остаются в коде, модель
только формулирует ответ по уже допущенному контексту. Отказы (диагноз, чужая
карта) модель не формулирует и отменить не может — их возвращает код.

Три исполнителя:

``stub``        — детерминированный сборщик из репозитория, без сети и ключей;
``ollama``      — локальная модель на этом же MacBook, ничего не уходит наружу;
``openrouter``  — внешний API, только для показа: данные стенда синтетические.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from app.agents.generator import GroundedGenerator, _format_node
from app.agents.state import GraphState
from app.guardrails.output import ACL_REFUSAL, REFUSAL, apply_output_guardrails
from app.ingest.bootstrap import Runtime

# Общая часть: она про права и границы, а не про форму ответа.
SYSTEM_BASE = (
    "Ты — справочная медицинского центра. Отвечай по-русски и только по "
    "сведениям из блока КОНТЕКСТ. Если сведений не хватает — скажи, что "
    "передаёшь запрос оператору регистратуры, и не придумывай. "
    "Не ставь диагноз и не толкуй коды МКБ: код можно только прочитать так, "
    "как он записан в направлении. "
    "Внутренние коды услуг вида USI-01 и PED-01 не произноси — называй услугу словами. "
    "Токены вида [PHONE_0] и [NAME_0] оставляй как есть: подставляет система."
)

# Голос: ответ уйдёт в синтез речи, поэтому текст должен читаться вслух.
SYSTEM_VOICE = SYSTEM_BASE + (
    " Ты говоришь с человеком в телефонном разговоре, твой ответ будет "
    "озвучен вслух. Поэтому: одна-две короткие фразы, без списков, таблиц, "
    "разметки, ссылок и скобок. "
    "Числа, даты и время пиши словами так, как их произносят: "
    "«три тысячи двести рублей», а не «3200 ₽»; "
    "«восемнадцатого сентября», а не «18.09.2026»; "
    "«в восемь утра», а не «08:00»; «шесть часов», а не «6 ч». "
    "Сокращения разворачивай: «УЗИ органов брюшной полости» вместо «УЗИ ОБП», "
    "«гастроскопия» вместо «ЭГДС». Аббревиатуру УЗИ произносить можно. "
    "Символы ₽, №, %, — заменяй словами. "
    "Заканчивай коротким вопросом, если разговор требует продолжения."
)

# Чат: то же по сути, но числом и датой читателю удобнее в цифрах.
SYSTEM_TEXT = SYSTEM_BASE + (
    " Отвечай коротко: две-три фразы. Числа, цены и даты оставляй цифрами. "
    "Сокращения раскрывай при первом упоминании."
)


@dataclass
class Trace:
    """Что именно ушло в модель — панель «Что видит модель» в интерфейсе."""

    backend: str = "stub"
    model: str = ""
    system: str = ""
    prompt: str = ""
    context: list[str] = field(default_factory=list)
    answer_raw: str = ""
    error: str = ""


class DemoGenerator:
    def __init__(self, backend: str = "stub", model: str = "", api_key: str = "") -> None:
        self.backend = backend
        self.model = model
        self.api_key = api_key
        self.stub = GroundedGenerator()
        self.trace = Trace()

    def generate(self, state: GraphState, runtime: Runtime) -> str:
        self.trace = Trace(backend=self.backend, model=self.model)

        # Отказы формулирует код, а не модель: их нельзя переубедить промптом.
        if state.intent == "reject_diagnosis":
            self.trace.answer_raw = REFUSAL
            return REFUSAL
        refusal = self._acl_refusal(state)
        if refusal:
            self.trace.answer_raw = refusal
            return refusal

        context = _context_lines(state)
        self.trace.context = context
        if self.backend == "stub" or not context:
            return self.stub.generate(state, runtime)

        question = state.extra.get("sanitized") or state.text
        prompt = "КОНТЕКСТ:\n" + "\n".join(f"- {line}" for line in context) + f"\n\nВОПРОС: {question}"
        system = SYSTEM_VOICE if state.channel == "voice" else SYSTEM_TEXT
        self.trace.system = system
        self.trace.prompt = prompt

        try:
            answer = self._call(prompt, system)
        except Exception as error:  # noqa: BLE001 — на стенде показываем причину в интерфейсе
            self.trace.error = f"{type(error).__name__}: {error}"
            return self.stub.generate(state, runtime)

        self.trace.answer_raw = answer
        allowed = {state.actor.id}
        if state.subject_id and not state.acl_denied:
            allowed.add(state.subject_id)
        return apply_output_guardrails(answer, state.actor, runtime.crm, allowed)

    # ---------- исполнители ----------

    def _call(self, prompt: str, system: str) -> str:
        if self.backend == "ollama":
            return self._post(
                os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434") + "/api/chat",
                {
                    "model": self.model or "qwen2.5:7b",
                    "stream": False,
                    "options": {"temperature": 0.2},
                    "messages": _messages(prompt, system),
                },
                headers={},
                pick=lambda data: data["message"]["content"],
            )
        if self.backend == "openrouter":
            if not self.api_key:
                raise RuntimeError("не задан ключ OpenRouter")
            return self._post(
                "https://openrouter.ai/api/v1/chat/completions",
                {
                    "model": self.model or "openai/gpt-4o-mini",
                    "temperature": 0.2,
                    "max_tokens": 400,
                    "messages": _messages(prompt, system),
                },
                headers={"Authorization": f"Bearer {self.api_key}"},
                pick=lambda data: data["choices"][0]["message"]["content"],
            )
        raise RuntimeError(f"неизвестный исполнитель: {self.backend}")

    @staticmethod
    def _post(url: str, payload: dict, headers: dict, pick) -> str:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", **headers},
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return pick(json.loads(response.read().decode("utf-8"))).strip()
        except urllib.error.HTTPError as error:
            raise RuntimeError(f"{error.code} {error.read().decode('utf-8')[:200]}") from error

    @staticmethod
    def _acl_refusal(state: GraphState) -> str:
        if state.acl_denied and state.subject_id and state.subject_id != state.actor.id:
            return ACL_REFUSAL
        if state.acl_denied and not state.chunks and not state.nodes and not state.crm_facts:
            return ACL_REFUSAL
        return ""


def _messages(prompt: str, system: str) -> list[dict[str, str]]:
    return [{"role": "system", "content": system}, {"role": "user", "content": prompt}]


def _context_lines(state: GraphState) -> list[str]:
    """Только то, что прошло проверку прав: узлы графа, фрагменты, факты CRM."""
    lines = [line for line in (_format_node(node) for node in state.nodes[:10]) if line]
    for chunk in state.chunks[:4]:
        excerpt = " ".join(chunk.text.split())
        lines.append(excerpt[:280] + "…" if len(excerpt) > 280 else excerpt)
    lines.extend(state.crm_facts)
    return lines
