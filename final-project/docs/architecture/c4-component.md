# C4 Level 3 — Component (агент)

Внутренности Orchestrator. Это одно приложение LangGraph: узлы графа состояний, не микросервис на каждый субагент.

```mermaid
flowchart TB
    REQ[Входящее сообщение<br/>text + subject_id + role] --> MEM[Memory<br/>сессия, последние реплики]

    MEM --> PLN[Planner / Router<br/>intent: knowledge / crm / both / reject]

    PLN --> TOOLS[Tools interface]
    TOOLS --> T1[graph_search]
    TOOLS --> T2[vector_search]
    TOOLS --> T3[crm_slots / book / cancel]
    TOOLS --> T4[escalate_operator]

    T1 --> POL[Policy gate<br/>фильтр узлов и чанков по ACL]
    T2 --> POL
    T3 --> HITL{подтверждение?}
    HITL -->|нет| WAIT[Ждём пользователя]
    HITL -->|да| EXEC[Tool execution]
    POL --> EXEC

    EXEC --> GEN[Generator<br/>вызов vLLM только с допущенным контекстом]
    GEN --> OUT[Output Guardrails<br/>тайна, grounding, антидиагностика]
```

## Модули

| Модуль | Что делает | Чего не делает |
|--------|------------|----------------|
| **Memory** | короткое окно диалога, `subject_id`, уже названный филиал/услуга | долговременную медкарту в промпте |
| **Planner / Router** | один или два шага: знания и/или CRM; отказ, если это диагностика | «ответить из весов модели» |
| **Tools interface** | стабильные контракты к графу, векторам, CRM | SQL в обход ACL |
| **Policy gate** | пересечение retrieved ∩ `acl` роли | «модель сама не расскажет» |
| **Generator** | текст ответа / реплика для TTS | вызов внешнего API |
| **Output Guardrails** | нет чужого ФИО, нет диагноза, есть опора на узлы | косметический фильтр мата |

Memory в MVP — таблица `sessions` + checkpoint LangGraph. Не отдельная векторная «память пациента»: это дыра в тайне.
