---
ADR: 0004
Название: Выбор движка инференса для T-pro-it-2.1 (vLLM / SGLang / TGI / TensorRT-LLM)
Статус: Предложено
Дата: 2026-06-20
Авторы: Команда архитектуры
Связан с: ADR-0002 (модель T-pro-it-2.1), ADR-0003 (GPU)
---

# Выбор движка инференса для основной модели

## Статус

**Предложено** — Prod: **SGLang**; Dev/fallback: **vLLM**. Оба за
OpenAI-совместимым роутером (ADR-0002) → взаимозаменяемы.

## Контекст

Модель — **T-pro-it-2.1** (на базе Qwen3-32B); её карточка рекомендует **SGLang**.
Профиль нагрузки специфичен:
- **RAG**: у запросов общий префикс (system-prompt + инструкции + повторяющиеся
  фрагменты БЗ) → высокая доля **prefix reuse**.
- **Агентный roadmap (FR-18)**: tool-calling и **структурированный вывод (JSON)**.
- Низкий RPS (5–10), latency p95 ≤ 15 с, 1 GPU (ADR-0003).

Для таких профилей ключевые свойства движка — кэш общих префиксов и эффективный
constrained-decoding для JSON/tool-calls, а не только пиковый throughput.

## Рассматриваемые варианты

| Движок | Сильные стороны | Слабые стороны | Под наш профиль |
|---|---|---|---|
| **SGLang** | **RadixAttention** (точный prefix-reuse → до ~6× на RAG/multi-turn); **xGrammar** для JSON/tool-calls (~3–5× throughput, ~99.8% валидность); ниже p95 TTFT под нагрузкой; рекомендован карточкой T-pro | NVIDIA-центричность; нужен прогрев кэша; экосистема младше vLLM | **Лучший**: RAG-префиксы + агентный JSON |
| **vLLM** | PagedAttention, огромная экосистема, простая эксплуатация, OpenAI-API, **лучший TTFT при c=1**; AWQ/GPTQ+Marlin, FP8 | На RAG/structured-output уступает SGLang | Отличный **fallback/Dev** |
| **TGI** | Интеграция с HF, простой деплой, гибкая квантизация (INT4) | Ниже throughput; 1 LoRA на сервер | Только если деплой на HF Endpoints |
| **TensorRT-LLM** | Максимальная плотность на H100 (FP8) | **Компиляция движка 25–40 мин на версию**, сложность, нужна экспертиза | Избыточно для 5–10 RPS |

## Решение

**Prod — SGLang.** Причины:
1. Карточка T-pro-it-2.1 прямо рекомендует SGLang (нативная поддержка
   tool-call-parser для Qwen).
2. **RadixAttention** даёт основной выигрыш именно на нашем RAG-профиле
   (одинаковый префикс у тысяч запросов) — экономия GPU и снижение TTFT.
3. **xGrammar** под будущие агентные JSON/tool-calls — высокая валидность и
   throughput структурированного вывода.

**Dev/Stage и fallback — vLLM**: проще в эксплуатации, лучший TTFT при низкой
конкурентности, широкая экосистема. Благодаря OpenAI-совместимому роутеру
(ADR-0002) переключение SGLang ↔ vLLM не затрагивает ядро.

**TGI** — не выбираем (нет деплоя на HF Endpoints). **TensorRT-LLM** — отклонён:
выигрыш не оправдывает сложность компиляции при 5–10 RPS.

Во всех вариантах: квантизация **AWQ/GPTQ INT4 (+Marlin)** или **FP8** (на H100),
**continuous batching**, **FP8 KV-cache**, **prefix caching**.

## Последствия

### Плюсы
- Максимальная утилизация RAG-префиксов и дешёвый структурированный вывод под агентов.
- Низкий p95 TTFT под нагрузкой → запас по SLA (p95 ≤ 15 с).
- Роутер делает движок сменяемым — решение обратимо при низкой стоимости.

### Минусы (trade-offs)
- SGLang **моложе** vLLM: меньше документации/готовых рецептов, NVIDIA-центричность.
- Нужен **прогрев** RadixAttention — холодный старт без выигрыша на первых запросах
  (учесть в health-check и нагрузочном тесте).
- Поддержка двух движков (SGLang + vLLM) — дополнительная операционная сложность.

### Проверка
На целевом GPU (ADR-0003) сравнить SGLang vs vLLM на нашем трафике (RAG-префиксы +
JSON tool-calls): **после прогрева** SGLang должен дать ниже p95 TTFT и/или выше
throughput при p95 ≤ 15 с. Иначе остаёмся на vLLM.

## Дополнительно
- Движки: [SGLang](https://github.com/sgl-project/sglang) (RadixAttention, xGrammar) ·
  [vLLM](https://github.com/vllm-project/vllm) (PagedAttention) ·
  [TGI](https://github.com/huggingface/text-generation-inference) ·
  [TensorRT-LLM](https://github.com/NVIDIA/TensorRT-LLM).
- Рекомендация SGLang в карточке модели: [`t-tech/T-pro-it-2.1`](https://huggingface.co/t-tech/T-pro-it-2.1).
- Бенчмарки 2026 (SGLang +10–29% throughput, ниже p95 TTFT; на RAG/structured —
  3–6× при высоком prefix reuse; vLLM лидирует по TTFT при c=1 и по экосистеме):
  [TURION.AI](https://turion.ai/blog/vllm-vs-sglang-inference-comparison-2026/) ·
  [TECHSY](https://techsy.io/en/blog/vllm-vs-sglang) ·
  [inference-bench (GitHub)](https://github.com/ree2raz/inference-bench).
