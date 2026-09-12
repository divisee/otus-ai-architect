# Deployment

Размещение вычислительного контура, сегментация сети и управление секретами.

```mermaid
flowchart TB
    subgraph INET["Вне контура"]
        TEL[АТС / микрофон]
        ADM[Админ по VPN]
    end

    subgraph DMZ["DMZ"]
        WAF[WAF / TLS terminate]
        SIP[Voice SBC — later]
        GW[API Gateway]
    end

    subgraph INT["Internal — Control Plane"]
        ORCH[Orchestrator + агенты]
        ING[Ingest job]
        LF[Langfuse]
        PROM[Prometheus / Grafana]
    end

    subgraph DATA["Internal — Data Plane"]
        NEO[(Neo4j)]
        QD[(Qdrant)]
        PG[(Postgres: сессии, ACL, CRM stub)]
        VAULT[HashiCorp Vault]
    end

    subgraph GPU["GPU VLAN — Data Plane"]
        VLLM[vLLM T-pro-32B FP8<br/>2× H100 80GB]
        WHIS[Whisper + WhisperX + bge-m3<br/>1× L40S]
    end

    TEL --> WAF
    TEL --> SIP
    SIP --> GW
    WAF --> GW
    GW --> ORCH
    ORCH --> NEO
    ORCH --> QD
    ORCH --> PG
    ORCH --> VLLM
    GW --> WHIS
    ING --> NEO
    ING --> QD
    ING --> WHIS
    ORCH --> LF
    ORCH -.-> VAULT
    VLLM -.-> VAULT
    ADM --> VAULT
```

## Железо (целевой контур клиники)

| Узел | Роль | Зачем отдельно |
|------|------|----------------|
| 2× H100 80GB | vLLM, FP8, prefix/KV-cache | агентный цикл, HA: второй GPU — горячий резерв / второй реплика |
| 1× L40S 48GB | Whisper, WhisperX, эмбеддинги | речь и индекс изолированы от KV LLM |
| CPU-ноды | API, LangGraph, Neo4j, Qdrant, Postgres, Langfuse | Control ≠ infer |

Расчётная нагрузка — до 30 голосовых обращений в минуту. ASR и генерация размещаются на разных ускорителях.

Баланс: два vLLM за внутренним LB (least-conn). Сессии LangGraph — в Postgres, чтобы реплика подхватила HITL.

## Сеть и секреты

| Зона | Что стоит | Кто ходит |
|------|-----------|-----------|
| DMZ | TLS, gateway, будущий SBC | пациент / АТС |
| Internal | агенты, БД, наблюдаемость | только gateway и админы |
| GPU VLAN | vLLM, Whisper | только Control Plane |
| Vault | пароли БД, токены | JIT, не в env на диске прод-нод |

Из GPU VLAN **нет** маршрута в интернет. Веса моделей — зеркало внутри периметра. OpenAI/Anthropic не резолвятся.

## Dev vs prod

В репозитории `docker compose` поднимает Neo4j, Qdrant, Postgres, Langfuse. vLLM в промышленной среде — systemd или Kubernetes на узлах с H100.
