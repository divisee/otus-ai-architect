# Платформа голосового ИИ-ассистента МЦ «Северная линия»

On-premise мультиагентный ассистент медицинского центра: GraphRAG, разграничение доступа, соблюдение 152-ФЗ и врачебной тайны.

Голосовой канал (ASR → оркестратор → TTS) использует тот же граф состояний, что и текстовый API.

## Состав репозитория

| Часть | Каталог |
|-------|---------|
| Архитектура (ADR, C4, Deployment, Sequence, ER, Data Flow) | [`docs/`](docs/README.md) |
| Агенты и API | [`backend/`](backend/README.md) |
| Стенд | [`infra/`](infra/README.md) |

## Назначение контура

Пациент обращается голосом или текстом. Система не ставит диагноз. Ответы опираются на связанные знания клиники (услуги, врачи, подготовка, филиалы) и инструменты записи. Доступ к персональным сведениям ограничен политикой ADR-0002. Вычислительный контур замкнут: внешние API LLM и STT не используются.

Границы объёма — [`docs/mvp.md`](docs/mvp.md). Решения по стеку — [`docs/adr/`](docs/adr/README.md).

## Стек

| Слой | Решение | ADR |
|------|---------|-----|
| Контур | self-hosted | [0001](docs/adr/0001-closed-contour.md) |
| LLM | T-pro-it-2.1 (база Qwen3-32B) | [0003](docs/adr/0003-llm-t-pro.md) |
| GPU | 2× H100 FP8, 1× L40S | [0004](docs/adr/0004-gpu-budget.md) |
| Инференс LLM | vLLM | [0005](docs/adr/0005-inference-engine.md) |
| Эмбеддинги | bge-m3, reranker | [0006](docs/adr/0006-embeddings.md) |
| GraphRAG | Neo4j, Qdrant | [0007](docs/adr/0007-graph-and-vectors.md) |
| Оркестрация | LangGraph | [0008](docs/adr/0008-orchestration.md) |
| ASR, диаризация, TTS | Whisper large-v3-turbo, WhisperX, Silero | [0009](docs/adr/0009-voice-gigaam-diarization.md) |
| Доступ | RBAC, `GUARDIAN_OF` | [0002](docs/adr/0002-acl-rebac.md) |

Control Plane — API и агенты. Data Plane — граф, векторы, модели, заглушка CRM.

## Очередность работ

1. Документация и корпус знаний — выполнено.
2. Загрузка документов и МКБ в Neo4j и Qdrant.
3. LangGraph: Router, Knowledge, CRM, Policy.
4. Проверка ACL (в том числе представитель и ребёнок).
5. Голосовой адаптер.
6. Наблюдаемость и нагрузочные измерения.
