# Backend

Control Plane: ingest корпуса, Policy, машина состояний, HTTP API.

| Путь | Что |
|------|-----|
| [`app/`](app/) | Gateway, оркестратор, порты хранилищ |
| [`data/kb/`](data/kb/manifest.yaml) | синтетические документы клиники + ACL |
| [`data/kb/reference/`](data/kb/reference/README.md) | МКБ-10 (~12k кодов) |
| [`data/crm/seed.json`](data/crm/seed.json) | Анна, Миша, Борис, `GUARDIAN_OF` |
| [`data/graph/seed.cypher`](data/graph/seed.cypher) | публичный граф для Neo4j |
| [`tests/`](tests/) | ACL, диагностика, запись, HTTP |

## Запуск

```text
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
uvicorn app.main:app --port 8080
```

Заголовок `X-Actor-Id`: `patient:anna`, `patient:boris`, `staff:registrar`.

```text
curl -s localhost:8080/v1/chat \
  -H 'Content-Type: application/json' \
  -H 'X-Actor-Id: patient:anna' \
  -d '{"text":"Когда УЗИ у сына и что за код N28.1?"}'
```
