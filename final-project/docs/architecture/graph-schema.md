# Онтология GraphRAG и ER

Знания клиники — граф. Справочник МКБ-10 — тоже граф (код → родитель). Карточки пациентов в граф **целиком не кладём**: ПДн живут в CRM/чанке с ACL, в Neo4j максимум идентификатор визита.

## Узлы знаний (5 типов)

| Тип | Пример | acl |
|-----|--------|-----|
| `Branch` | Лесная, Южный | public |
| `Doctor` | Морозова А.П., УЗИ | public |
| `Service` | УЗИ ОБП, гастроскопия | public |
| `Preparation` | «не есть 6 часов» | public |
| `IcdCode` | K21.0 «Гастроэзофагеальный рефлюкс с эзофагитом» | public |

Связи:

```
(:Doctor)-[:PROVIDES]->(:Service)
(:Service)-[:REQUIRES]->(:Preparation)
(:Service)-[:AVAILABLE_AT]->(:Branch)
(:Doctor)-[:WORKS_AT]->(:Branch)
(:Service)-[:OFTEN_CODED_AS]->(:IcdCode)
(:IcdCode)-[:PARENT]->(:IcdCode)
```

`OFTEN_CODED_AS` — подсказка регистратору («гастроскопию часто ставят рядом с K21»), **не** диагноз пациента. Ассистент не говорит «у вас K21».

## МКБ-10 в контуре

Полный классификатор лежит в [`backend/data/kb/reference/mkb10-parsed.csv`](../../backend/data/kb/reference/mkb10-parsed.csv) (~12k строк: code, name, parent, level). Источник парсинга публичного справочника; в проде холдинг берёт выгрузку НСИ Минздрава (`1.2.643.5.1.13.13.11.1005`).

Зачем голосовому ассистенту:

- понять «рефлюкс-эзофагит» / «K21.0» и связать с услугой и врачом;
- ответить «что означает код в направлении» **как справочник**, не как постановка диагноза.

Guardrail: симптомы («у ребёнка болит живот, что это») → отказ в диагностике + запись к педиатру. Обход графа МКБ для такого запроса **не** запускаем как «подбери код».

## Карточки и права (не граф знаний)

```mermaid
erDiagram
    TENANT ||--o{ USER : has
    USER ||--o{ GUARDIAN_LINK : parent
    USER ||--o{ PATIENT : "is / represents"
    PATIENT ||--o{ GUARDIAN_LINK : child
    PATIENT ||--o{ DOCUMENT : owns
    DOCUMENT ||--o{ CHUNK : splits
    CHUNK ||--o{ EMBEDDING : has
    USER ||--o{ SESSION : opens
    SESSION ||--o{ AUDIT_EVENT : logs
    PATIENT ||--o{ APPOINTMENT : books

    TENANT {
        string id PK
        string name
    }
    USER {
        string id PK
        string role
        string login
    }
    PATIENT {
        string id PK
        date birth_date
        bool share_with_guardian
    }
    GUARDIAN_LINK {
        string parent_user_id FK
        string child_patient_id FK
        string relation
        bool active
    }
    DOCUMENT {
        string id PK
        string acl
        string subject_id
        string source_path
    }
    CHUNK {
        string id PK
        string acl
        string subject_id
        string text
        string node_ids
    }
    EMBEDDING {
        string chunk_id FK
        vector vec
    }
    APPOINTMENT {
        string id PK
        string patient_id FK
        string service_id
        datetime slot
        string status
    }
    SESSION {
        string id PK
        string actor_id
        string channel
    }
    AUDIT_EVENT {
        string request_id
        string via
        string acl_result
    }
```

Qdrant хранит `vector + payload{chunk_id, acl, subject_id, doc_id}`. Фильтр ACL — **до** LLM, на retrieve.

## Пример обхода

«Запишите сына на УЗИ на Лесной, как готовить и что за код N28 в направлении?»

1. Policy: Анна `GUARDIAN_OF` Миша → карта Миши доступна.
2. Graph: `Service:УЗИ ОБП` → `Preparation` → `Branch:Лесная` → `Doctor:Морозова`.
3. `IcdCode:N28` → название из справочника (публичное).
4. CRM: слоты УЗИ, `patient_id=misha`.
5. В промпт не попадают направление Анны и карта Бориса.
