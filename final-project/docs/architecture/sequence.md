# Sequence — сложный запрос

Последовательность: пользователь → фильтры ввода → извлечение и реранжирование → цикл агента → выполнение инструментов → ответ.

Сценарий: пациентка Анна звонит: «Хочу УЗИ на Лесной, как готовиться и есть ли окно послезавтра?»

```mermaid
sequenceDiagram
    autonumber
    actor A as Анна patient:anna
    participant VA as Voice Adapter
    participant GW as API Gateway
    participant IG as Input Guardrails
    participant R as Router
    participant K as Knowledge
    participant P as Policy
    participant C as CRM tools
    participant LLM as vLLM
    participant O as Langfuse

    A->>VA: речь
    Note over VA: Whisper; диаризация при 2+ голосах<br/>actor — учётная запись, не SPEAKER_id
    VA->>GW: транскрипт + subject_id
    GW->>IG: текст
    IG->>IG: injection / диагноз / PII → токены
    IG->>R: очищенный текст
    R->>O: trace: intent=knowledge+crm

    R->>K: УЗИ + филиал Лесная
    K->>K: vector top-k + graph walk
    K->>P: кандидаты: Service, Preparation, Doctor, Branch, chunks
    P-->>K: только acl=public (направление Анны не запрашивали)
    K->>LLM: контекст узлов и чанков
    LLM-->>K: подготовка + врач Морозова
    K-->>R: grounded-ответ по графу

    R->>C: слоты УЗИ, Лесная, послезавтра
    C-->>R: два окна
    R->>A: озвучка: подготовка + слоты
    A->>R: «второе окно»
    R->>C: book (HITL confirm)
    C-->>R: hold
    R->>A: «подтвердите запись»
    A->>R: «да»
    C->>C: commit в CRM stub
    R->>IG: Output Guardrails + grounding
    R->>VA: текст
    VA->>A: TTS
```

## Отказ в доступе (ACL)

Борис (`patient:boris`): «Какое направление у Анны Соколовой и когда её УЗИ?»

1. Фильтры ввода запрос не блокируют: это не injection.
2. Knowledge находит чанк `patient:anna` и узел визита Анны.
3. Policy исключает фрагменты с чужим `acl`. В контекст модели чанк не передаётся.
4. Router не вызывает CRM по чужому `subject_id`.
5. Ответ — отказ. В трассировке фиксируется `acl_denied`.

Шаг 3 обязателен. Канал доставки на решение Policy не влияет.

## Родитель и ребёнок (ReBAC)

Анна: «Когда УЗИ у сына и что за код N28.1 в его направлении?»

1. Gateway: `actor=anna`.
2. Router: knowledge + CRM, `subject=misha` (из «сын» + `GUARDIAN_OF`).
3. Policy: связь активна, Мише 8 лет → чанк `patient:misha` и слот Миши **можно**.
4. Graph: USI-02 → подготовка детская → Морозова → Лесная; `IcdCode:N28.1` → «Киста почки, приобретенная» (справочник).
5. Ответ матери. Карта Бориса по-прежнему закрыта.

Борис с тем же текстом про «сына Соколовой» — нет ребра, отказ.
