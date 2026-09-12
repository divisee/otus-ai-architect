# Документация

Architecture Decision Records, модель C4 и схемы потоков данных.

## ADR

Индекс: [`adr/README.md`](adr/README.md).

| ADR | Решение |
|-----|---------|
| [0001](adr/0001-closed-contour.md) | контур self-hosted |
| [0002](adr/0002-acl-rebac.md) | RBAC и ReBAC, законный представитель |
| [0003](adr/0003-llm-t-pro.md) | T-pro-it-2.1 |
| [0004](adr/0004-gpu-budget.md) | 2× H100, 1× L40S |
| [0005](adr/0005-inference-engine.md) | vLLM |
| [0006](adr/0006-embeddings.md) | bge-m3 |
| [0007](adr/0007-graph-and-vectors.md) | Neo4j, Qdrant |
| [0008](adr/0008-orchestration.md) | LangGraph |
| [0009](adr/0009-voice-gigaam-diarization.md) | Whisper large-v3-turbo, WhisperX, Silero |

## Схемы

| Документ | Статус |
|----------|--------|
| [План и реестр требований](plan.md) | принято |
| [Рамка MVP](mvp.md) | принято |
| [C4 Context](architecture/c4-context.md) | принято |
| [C4 Container](architecture/c4-container.md) | принято |
| [C4 Component](architecture/c4-component.md) | принято |
| [Deployment](architecture/deployment.md) | принято |
| [Sequence](architecture/sequence.md) | принято |
| [Data Flow](architecture/data-flow.md) | принято |
| [Граф и ER](architecture/graph-schema.md) | принято |
| [Внешние порты](architecture/external-ports.md) | принято |
| [Нагрузка](architecture/load.md) | принято |
| [Когнитивная схема](diagrams/cognitive-architecture.mmd) | принято |

Корпус знаний: [`backend/data/kb/`](../backend/data/kb/manifest.yaml). МКБ-10: [`reference/`](../backend/data/kb/reference/README.md).
