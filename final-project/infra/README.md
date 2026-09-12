# Infra

Цель — `docker compose up` для Data Plane и обвязки:

- Neo4j
- Qdrant
- Langfuse (self-host)
- Prometheus / Grafana
- vLLM — на машине с GPU (профиль `demo-gpu`)

Control Plane (API + агенты) можно гонять с хоста в dev. Секреты в git не кладём.
