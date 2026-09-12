# Infra

Compose целевого Data Plane. Описание системы — в [`../README.md`](../README.md).

Профиль `data`. Control Plane запускается на хосте: `uvicorn app.main:app` из `backend/`.

```text
docker compose --profile data up -d
```

| Сервис | Профиль | Назначение |
|--------|---------|------------|
| Neo4j, Qdrant, Postgres | `data` | целевые хранилища ADR-0007 |
| vLLM, Whisper | не в Compose CPU | GPU-контур, ADR-0004 |

На CPU-стенде API использует in-memory порты тех же контрактов (граф из Cypher, лексический индекс, CRM stub). Секреты в git не кладём.
