# Data Flow

Два контура: загрузка документов в знания и обработка запроса. Персональные данные не покидают периметр.

```mermaid
flowchart TB
    subgraph IN["Ingest — редкий поток"]
        PDF[PDF / MD клиники + МКБ CSV] --> PARSE[парсинг + чанки]
        PARSE --> META[acl из манифеста]
        META --> EMB[bge-m3]
        EMB --> QD[(Qdrant chunks)]
        META --> EXT[узлы и рёбра]
        EXT --> NEO[(Neo4j)]
    end

    subgraph RT["Runtime — каждый запрос"]
        U[Речь или текст] --> ASR[ASR опционально]
        ASR --> GW[Gateway: subject_id]
        GW --> SAN[PII → токены]
        GW --> REL[свои + GUARDIAN_OF]
        SAN --> RET[retrieve: graph + vector<br/>фильтр acl ∩ subjects]
        REL --> RET
        RET --> LOOP[Agent loop + tools]
        LOOP --> GEN[vLLM]
        GEN --> DLP[Output: тайна, grounding]
        DLP --> REH[токены → значения<br/>только свои]
        REH --> OUT[текст / TTS]
    end

    QD --> RET
    NEO --> RET
    CRM[(CRM stub)] --> LOOP

    subgraph AUD["Аудит"]
        SAN -.-> L[Decision log: hash, chunk_ids, acl]
        DLP -.-> L
        L --> LF[Langfuse]
    end
```

## Правила движения данных

| Данные | Куда можно | Куда нельзя |
|--------|------------|-------------|
| Публичный прайс, памятки | граф, векторы, промпт | внешний API |
| Внутренний регламент регистратуры | граф/векторы с `acl=staff` | промпт пациента |
| Направление Анны | чанк `patient:anna` | промпт Бориса, логи в открытом виде |
| Направление Миши | Анна как `GUARDIAN_OF` | промпт Бориса, общий прайс |
| Телефон, ФИО в реплике | Token Vault на время запроса | сырьём в vLLM и в Langfuse |
| Аудио | диск контура / tmp, TTL | облачный Speech API |

Регистратор видит `public` + `staff`. Пациент — `public` + своя карта + карты, где он активный законный представитель. Оператор HITL работает в UI клиники, не через «расскажи всё модели».
