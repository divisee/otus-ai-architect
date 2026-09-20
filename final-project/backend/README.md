# Backend

Код Control Plane. Описание системы и схемы — в [`../README.md`](../README.md).

| Путь | Что |
|------|-----|
| [`app/`](app/) | Gateway, оркестратор, порты хранилищ |
| [`data/kb/`](data/kb/manifest.yaml) | синтетические документы клиники + ACL |
| [`data/kb/reference/`](data/kb/reference/README.md) | МКБ-10 (~12k кодов) |
| [`data/crm/seed.json`](data/crm/seed.json) | пациент 1, пациент 2, пациент 3, опека |
| [`data/graph/seed.cypher`](data/graph/seed.cypher) | публичный граф для Neo4j |
| [`tests/`](tests/) | ACL, диагностика, запись, HTTP |

## Запуск

```text
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
uvicorn app.main:app --port 8080
```

Заголовок `X-Actor-Id` в сценариях: `patient:anna` (пациент 1), `patient:boris` (пациент 3), `staff:registrar` (регистратор).

```text
curl -s localhost:8080/v1/chat \
  -H 'Content-Type: application/json' \
  -H 'X-Actor-Id: patient:anna' \
  -d '{"text":"Когда УЗИ у сына и что за код N28.1?"}'
```
