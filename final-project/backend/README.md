# Backend

Данные уже лежат здесь, кода агентов ещё нет.

| Путь | Что |
|------|-----|
| [`data/kb/`](data/kb/manifest.yaml) | синтетические документы клиники + ACL |
| [`data/kb/reference/`](data/kb/reference/README.md) | МКБ-10 (~12k кодов) |
| [`data/crm/seed.json`](data/crm/seed.json) | Анна, Миша, Борис, `GUARDIAN_OF` |
| [`data/graph/seed.cypher`](data/graph/seed.cypher) | публичный граф для Neo4j |

Дальше по слоям: ingest → LangGraph → `/v1/chat` → ACL-тесты (Борис / Анна+Миша) → `/v1/voice`.
