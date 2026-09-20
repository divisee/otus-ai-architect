"""Демонстрационный стенд: разговор с ассистентом и разбор того, что внутри.

Запуск описан в demo/README.md. Интерфейс намеренно показывает не только ответ,
но и решение о доступе, допущенный контекст и то, что реально ушло в модель:
именно это и есть предмет работы, а ответ — следствие.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent / "backend"))

from app.agents.orchestrator import Orchestrator  # noqa: E402
from app.ingest.bootstrap import load_runtime  # noqa: E402
from generator import DemoGenerator  # noqa: E402
import speech  # noqa: E402

ACTORS = {
    "patient:anna": ("Соколова Анна", "пациент, законный представитель сына Михаила (8 лет)"),
    "patient:boris": ("Орлов Борис", "другой пациент клиники, связи с Михаилом нет"),
    "staff:registrar": ("Регистратор", "сотрудник: служебные материалы и учётные сведения визита"),
}

SCENARIOS = [
    ("Открытые материалы", "Сколько стоит УЗИ брюшной полости и как к нему готовиться?", "patient:anna"),
    ("Доступ по опеке", "Когда УЗИ у сына и что за код N28.1 в направлении?", "patient:anna"),
    ("Отказ в диагнозе", "У меня болит живот, что со мной и какой диагноз?", "patient:anna"),
    ("Отказ по доступу", "Покажи визиты пациента Орлова Бориса", "patient:anna"),
    ("Запись с подтверждением", "Запишите меня на гастроскопию, какие есть окна?", "patient:anna"),
    ("Токенизация ПДн", "Это Соколова Анна, телефон +7 916 123-45-67, запишите на УЗИ", "patient:anna"),
    ("Обязанности регистратуры", "Какой код направления у пациента Орлова Бориса?", "staff:registrar"),
]

VIA = {
    "public": "открытый материал клиники",
    "staff": "служебный материал, роль staff",
    "self": "своя карта",
    "guardian": "законное представительство, ребёнок до 15 лет",
    "staff_duty": "обязанности регистратуры, 323-ФЗ ст. 13 ч. 4 п. 1",
}

st.set_page_config(page_title="Ассистент медицинского центра — стенд", page_icon="🩺", layout="wide")


@st.cache_data(ttl=30, show_spinner=False)
def _ollama_up() -> bool:
    """Поднята ли локальная модель. Если да — она и формулирует по умолчанию:
    сборщик остаётся запасным ходом и включается сам при любой ошибке."""
    import urllib.request

    try:
        with urllib.request.urlopen("http://127.0.0.1:11434", timeout=1):
            return True
    except Exception:  # noqa: BLE001 — недоступна, значит работает сборщик
        return False


@st.cache_resource(show_spinner="Загружаю граф, корпус и реестр…")
def boot():
    runtime = load_runtime()
    return runtime, Orchestrator(runtime)


runtime, orchestrator = boot()

# ---------- панель управления ----------

with st.sidebar:
    st.header("Стенд")
    login = st.selectbox("От чьего имени", list(ACTORS), format_func=lambda key: ACTORS[key][0])
    st.caption(ACTORS[login][1])

    st.divider()
    backends = ["stub", "ollama", "openrouter"]
    backend = st.radio(
        "Кто формулирует ответ",
        backends,
        index=backends.index("ollama") if _ollama_up() else 0,
        format_func=lambda key: {
            "stub": "Сборщик из репозитория — без сети",
            "ollama": "Локальная модель — Ollama",
            "openrouter": "Внешний API — OpenRouter",
        }[key],
    )
    model, api_key = "", ""
    if backend == "ollama":
        model = st.text_input("Модель Ollama", value="gemma3:27b")
        st.caption("Считается на этом хосте, наружу ничего не уходит. Если модель недоступна, ответ соберёт код.")
    if backend == "openrouter":
        model = st.text_input("Модель OpenRouter", value="openai/gpt-4o-mini")
        api_key = st.text_input("Ключ OpenRouter", type="password")
        st.warning(
            "Реплика и допущенный контекст уйдут во внешний сервис. На стенде это "
            "допустимо: карточки синтетические. В промышленном контуре такой режим "
            "запрещён (ADR-0001).",
            icon="⚠️",
        )

    st.divider()
    voice_in = st.toggle("Речевой ввод", value=speech.asr_available(), disabled=not speech.asr_available())
    asr_size = st.selectbox("Чекпоинт распознавания", list(speech.MODELS), index=1, disabled=not voice_in)
    if voice_in:
        st.caption(speech.MODELS[asr_size])
    voice_out = st.toggle(
        "Озвучивать ответ",
        value=speech.tts_available(),
        disabled=not speech.tts_available(),
        help="Штатный голос macOS Milena. В целевом контуре — Silero на L40S (ADR-0009).",
    )

    st.divider()
    if st.button("Начать разговор заново", use_container_width=True):
        st.session_state.pop("session_id", None)
        st.session_state["turns"] = []
        st.rerun()

orchestrator.generator = DemoGenerator(backend=backend, model=model, api_key=api_key)
st.session_state.setdefault("turns", [])

# ---------- ввод ----------

st.title("🩺 Ассистент медицинского центра")
st.caption(
    "Данные стенда синтетические. Проверка прав, запрет диагноза и подтверждение записи "
    "выполняются кодом до обращения к модели."
)

st.subheader("Готовые сценарии")
columns = st.columns(4)
asked = None
for index, (title, text, want_login) in enumerate(SCENARIOS):
    with columns[index % 4]:
        if st.button(title, use_container_width=True, help=text):
            if want_login != login:
                st.session_state["pending_login"] = want_login
            asked = text

if st.session_state.pop("pending_login", None):
    st.info("Сценарий рассчитан на другую роль — выберите её в панели слева и нажмите ещё раз.")

typed = st.chat_input("Реплика пациента или сотрудника")
if typed:
    asked = typed

if voice_in:
    audio = st.audio_input("Или скажите вслух")
    if audio is not None and audio != st.session_state.get("last_audio"):
        st.session_state["last_audio"] = audio
        with st.spinner("Распознаю…"):
            text, seconds = speech.transcribe(audio.getvalue(), asr_size)
        if text:
            st.session_state["asr_seconds"] = seconds
            asked = text
        else:
            st.warning("Не разобрала реплику — попробуйте ещё раз или наберите текстом.")

# ---------- прогон ----------

if asked:
    actor = runtime.crm.actor_from_login(login)
    state = orchestrator.run(actor, asked, st.session_state.get("session_id"), "voice" if voice_in else "text")
    st.session_state["session_id"] = state.session.session_id
    st.session_state["turns"].append(
        {
            "question": asked,
            "answer": state.answer,
            "state": state,
            "trace": orchestrator.generator.trace,
            "audio": speech.synthesize(state.answer) if voice_out else None,
        }
    )

# ---------- разговор и разбор ----------

last = len(st.session_state["turns"]) - 1
for index, turn in enumerate(st.session_state["turns"]):
    state, trace = turn["state"], turn["trace"]
    with st.chat_message("user"):
        st.write(turn["question"])
    with st.chat_message("assistant"):
        st.write(turn["answer"])
        if turn["audio"]:
            # Сам звучит только свежий ответ: иначе каждая перерисовка страницы
            # проигрывала бы весь разговор заново.
            st.audio(turn["audio"], format="audio/wav", autoplay=index == last)

        badges = [f"маршрут: **{state.intent}**"]
        if state.subject_id:
            badges.append(f"чья карта: **{state.subject_id}**")
        if state.acl_via:
            badges.append(f"основание: **{VIA.get(state.acl_via, state.acl_via)}**")
        if len(state.acl_vias) > 1:
            others = ", ".join(VIA.get(via, via) for via in state.acl_vias[1:])
            badges.append(f"также сработали: {others}")
        if state.acl_denied:
            badges.append("**в доступе отказано**")
        if state.pending_confirm:
            badges.append("**ждём подтверждения** — ответьте «да»")
        if state.escalate:
            badges.append("**передано оператору**")
        st.caption(" · ".join(badges))

        with st.expander("Что произошло внутри"):
            left, right = st.columns(2)
            with left:
                st.markdown("**Допущено в контекст**")
                st.write(f"узлов графа: {len(state.nodes)}, фрагментов: {len(state.chunks)}")
                for node in state.nodes[:8]:
                    st.markdown(f"- `{node.id}` · {node.label}")
                for chunk in state.chunks[:4]:
                    st.markdown(f"- `{chunk.chunk_id}` · acl={chunk.acl}")
                if state.crm_facts:
                    st.markdown("**Из CRM**")
                    for fact in state.crm_facts:
                        st.markdown(f"- {fact}")
            with right:
                st.markdown("**Персональные данные**")
                tokens = state.extra.get("pii_tokens") or {}
                if tokens:
                    st.write({token: "скрыто" for token in tokens})
                    st.caption(f"найдено сущностей: {', '.join(state.extra.get('pii_entities', []))}")
                    st.markdown("**Реплика, как её видит модель**")
                    st.code(state.extra.get("sanitized", ""), language=None)
                else:
                    st.caption("в реплике персональных данных не найдено")

            st.markdown("**Что ушло в модель**")
            if trace.backend == "stub":
                st.caption("Отвечал сборщик из репозитория: обращения к модели не было.")
            elif trace.error:
                st.error(f"Модель недоступна ({trace.error}) — ответ собрал сборщик из репозитория.")
            else:
                st.code(f"system: {trace.system}\n\n{trace.prompt}", language=None)

            st.markdown("**Журнал доступа**")
            event = runtime.audit.get(state.request_id)
            st.json(event.__dict__ if event else {}, expanded=False)

if st.session_state.get("asr_seconds"):
    st.sidebar.metric("Распознавание, с", f"{st.session_state['asr_seconds']:.1f}")
