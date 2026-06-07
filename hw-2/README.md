# ДЗ №2. Многоуровневое проектирование: от C4 Model до спецификации API

**Кейс:** система умных рекомендаций для ритейлера **TechnoMart** (продолжение ДЗ №1).

**Цель:** спроектировать многоуровневую архитектуру AI-сервиса с диаграммами **C4** (C2/C3),
**Sequence Diagram** для ключевого сценария и **OpenAPI**-спецификацией API для согласования
интеграции Backend ↔ AI Service.

## Файлы

| Файл | Что это |
|------|---------|
| `diagrams/c1-context.mmd` | C1 — контекст: система и окружение |
| `diagrams/c2-container.mmd` | C2 — контейнеры всей системы |
| `diagrams/c3-component.mmd` | C3 — компоненты внутри AI Service |
| `diagrams/sequence.mmd` | Sequence — «запрос рекомендации» |
| `diagrams/workspace.dsl` | Тот же C1+C2+C3 в Structurizr DSL ([playground](https://playground.structurizr.com/)) |
| `api/openapi.yaml` | OpenAPI 3.0.3 для `/get_recommendation` (валиден) |

PNG/PDF: открыть `.mmd` в [mermaid.live](https://mermaid.live) → Export. API — в [Swagger Editor](https://editor.swagger.io).

## Диаграммы

<details open>
<summary>🌍 C1 — System Context</summary>

```mermaid
flowchart TB
    customer([👤 Покупатель<br/>веб + мобильное приложение<br/>аноним по cookie или залогинен])

    SYS["🟦 Система умных рекомендаций TechnoMart<br/>персональная «Умная лента»<br/>+ генеративные описания товаров"]

    onec[("🧾 1С<br/>чеки и заказы<br/>онлайн + офлайн")]
    xml[("📦 Каталог-фид<br/>XML, выгрузка раз в сутки")]

    customer -->|"смотрит рекомендации на сайте/в приложении"| SYS
    SYS -.->|"персональные пуши с рекомендациями"| customer
    onec -->|"заказы для омниканальности, синк 15 мин"| SYS
    xml -->|"каталог товаров, раз в сутки"| SYS

    classDef person fill:#08427b,stroke:#052c54,color:#ffffff;
    classDef sys fill:#1565c0,stroke:#0d47a1,color:#ffffff;
    classDef ext fill:#8d99ae,stroke:#5c6b7a,color:#ffffff;
    class customer person;
    class SYS sys;
    class onec,xml ext;
```

Кто пользуется системой (Покупатель) и внешние источники данных (1С, каталог-фид).

</details>

<details>
<summary>📦 C2 — Container Diagram</summary>

```mermaid
flowchart TB
    User([👤 Покупатель<br/>веб + мобильное приложение<br/>залогинен или аноним по cookie])

    subgraph TM["🏢 Платформа TechnoMart"]
        direction TB
        FE["🖥 Frontend<br/>SPA / Mobile<br/>сайт и приложение, блок рекомендаций"]
        BE["🧱 Backend-монолит<br/>PHP, Bitrix<br/>каталог, корзина, заказы, BFF"]
        LEGACY["🛟 Rule-based Recommendations (legacy)<br/>PHP, в монолите<br/>fallback при сбое/таймауте AI"]
        MYSQL[("🗃 SQL DB магазина<br/>MySQL<br/>каталог, пользователи, заказы")]

        subgraph NEW["☁️ Новый AI-контур (облако, старт без GPU)"]
            direction TB
            AISVC["🤖 AI Recommendation Service<br/>Python, FastAPI<br/>рекомендации + генеративные тексты"]
            FS[("🧮 Feature Store / SQL DB<br/>PostgreSQL<br/>профили, фичи, подборки")]
            VDB[("🧱 Vector DB<br/>Qdrant / pgvector<br/>эмбеддинги товаров и сессий")]
            CACHE[("⚡ Cache<br/>Redis<br/>предрассчитанные подборки, TTL")]
            ETL["🔄 Data Ingestion / ETL<br/>Python, Airflow<br/>каталог, заказы, клики → фичи и эмбеддинги"]
            EVT["📡 Event Collector<br/>Kafka / HTTP<br/>клики и просмотры в реальном времени"]
            ANON["🛡 PII Anonymizer / Rehydrator<br/>Python<br/>маскирует PII перед облаком,<br/>восстанавливает в ответе"]
            VAULT[("🔐 Token Vault<br/>Redis, короткий TTL<br/>карта токен ↔ значение")]
        end
    end

    ONEC[("🧾 1С<br/>чеки и заказы<br/>онлайн + офлайн")]
    XML[("📦 Каталог-фид<br/>XML, раз в сутки")]
    CLOUD["☁️ Cloud LLM Provider<br/>внешний managed-сервис<br/>генерация текстов"]

    User -->|"HTTPS: открывает страницу"| FE
    FE -->|"HTTPS/JSON: запрос блока"| BE
    BE -->|"HTTPS/JSON: POST /get_recommendation"| AISVC
    FE -.->|"события клик/просмотр"| EVT
    BE -->|"fallback: AI down / timeout / 503"| LEGACY
    AISVC -.->|"5xx / медленнее 200мс"| BE
    LEGACY -->|"SQL"| MYSQL
    BE -->|"SQL"| MYSQL

    AISVC -->|"чтение профиля/фич"| FS
    AISVC -->|"поиск кандидатов top-k"| VDB
    AISVC -->|"чтение/запись кэша"| CACHE
    AISVC -->|"промпт (может содержать PII)"| ANON
    ANON -->|"карта токенов"| VAULT
    ANON -->|"анонимизированный промпт БЕЗ PII"| CLOUD
    CLOUD -.->|"текст с токенами"| ANON
    ANON -.->|"текст с восстановленными PII"| AISVC

    ONEC -->|"заказы, синк 15 мин"| ETL
    XML -->|"каталог, раз в сутки"| ETL
    EVT -->|"поток событий"| ETL
    MYSQL -.->|"справочники"| ETL
    ETL -->|"фичи, профили"| FS
    ETL -->|"эмбеддинги товаров"| VDB
    ETL -->|"прогрев подборок"| CACHE

    classDef ext fill:#eceff1,stroke:#607d8b,color:#263238;
    classDef be fill:#fff3e0,stroke:#e65100,color:#bf360c;
    classDef ai fill:#e3f2fd,stroke:#1565c0,color:#0d47a1;
    classDef data fill:#f3e5f5,stroke:#6a1b9a,color:#4a148c;
    class User,ONEC,XML,CLOUD ext;
    class FE,BE,LEGACY be;
    class AISVC,ETL,EVT,ANON ai;
    class MYSQL,FS,VDB,CACHE,VAULT data;
```

Контейнеры системы: Frontend, Backend (BFF), AI Service, Vector DB, SQL DB, кэш, ETL.
Особенности: **облачная LLM + анонимизация PII** (наружу уходит промпт без персональных данных) и **fallback** на старый rule-based блок при сбое/таймауте AI (≤200 мс).

</details>

<details>
<summary>🔬 C3 — Component Diagram (внутри AI Service)</summary>

```mermaid
flowchart TB
    BE([🧱 Backend-монолит<br/>POST /get_recommendation])

    subgraph AISVC["🤖 AI Recommendation Service — Python, FastAPI"]
        direction TB
        CTRL["🎛 Recommendation Controller<br/>REST-эндпоинт, валидация,<br/>оркестрация, сборка ответа"]
        CACHEC["⚡ Cache Client<br/>fast-path: готовая подборка <200мс"]
        PROF["👤 Profile Provider<br/>профиль и фичи по user/session"]
        RAG["📚 RAG Manager<br/>кандидаты: история + семантика,<br/>запрос к Vector DB"]
        OMNI["🔁 Omnichannel Filter<br/>убирает уже купленное"]
        RANK["📊 Ranker / Scorer<br/>ML-ранжирование"]
        PTF["🧩 Prompt Template Factory<br/>шаблоны промптов под тип подборки"]
        LLMC["🧠 LLM Client<br/>вызов облачной LLM через анонимизатор,<br/>ретраи, фолбэк"]
        ASM["📦 Response Assembler<br/>финальный DTO: товары + тексты + meta"]
        OBS["🔭 Observability<br/>логи, трассировка, метрики latency"]
    end

    CACHE[("⚡ Redis")]
    FS[("🧮 Feature Store<br/>PostgreSQL")]
    VDB[("🧱 Vector DB")]
    ANON["🛡 PII Anonymizer / Rehydrator"]
    CLOUD["☁️ Cloud LLM Provider"]

    BE -->|"JSON-запрос"| CTRL
    CTRL -->|"1. проверить кэш"| CACHEC
    CACHEC -->|"hit → сразу"| ASM
    CTRL -->|"2. профиль/фичи"| PROF
    CTRL -->|"3. кандидаты"| RAG
    RAG -->|"4. фильтр купленного"| OMNI
    OMNI -->|"5. ранжирование"| RANK
    RANK -->|"6. промпт"| PTF
    PTF -->|"7. генерация"| LLMC
    LLMC -->|"8. товары + тексты"| ASM
    CTRL -->|"9. записать кэш"| CACHEC
    ASM -->|"JSON-ответ"| BE

    CACHEC --> CACHE
    PROF --> FS
    RAG --> VDB
    LLMC -->|"7a. анонимизировать + облако"| ANON
    ANON -->|"7b. промпт БЕЗ PII"| CLOUD
    CLOUD -.->|"текст с токенами"| ANON
    ANON -.->|"восстановленный текст"| LLMC

    CTRL -.-> OBS
    RAG -.-> OBS
    RANK -.-> OBS
    LLMC -.-> OBS

    classDef comp fill:#e3f2fd,stroke:#1565c0,color:#0d47a1;
    classDef data fill:#f3e5f5,stroke:#6a1b9a,color:#4a148c;
    classDef ext fill:#eceff1,stroke:#607d8b,color:#263238;
    classDef obs fill:#e8f5e9,stroke:#2e7d32,color:#1b5e20;
    class CTRL,CACHEC,PROF,RAG,OMNI,RANK,PTF,LLMC,ASM comp;
    class CACHE,FS,VDB data;
    class BE,ANON,CLOUD ext;
    class OBS obs;
```

Внутренности AI Service: каждый компонент — одна зона ответственности (Single Responsibility). Пронумерованные шаги совпадают с Sequence-диаграммой.

</details>

<details>
<summary>🔁 Sequence — «Пользователь запрашивает рекомендацию»</summary>

```mermaid
sequenceDiagram
    autonumber
    actor U as 👤 Покупатель
    participant FE as 🖥 Frontend
    participant BE as 🧱 Backend (PHP)
    participant CTRL as 🎛 Controller
    participant CACHE as ⚡ Cache Client
    participant PROF as 👤 Profile Provider
    participant RAG as 📚 RAG Manager
    participant OMNI as 🔁 Omnichannel Filter
    participant RANK as 📊 Ranker
    participant PTF as 🧩 Prompt Factory
    participant LLM as 🧠 LLM Client
    participant ANON as 🛡 PII Anonymizer
    participant CLOUD as ☁️ Cloud LLM
    participant ASM as 📦 Response Assembler
    participant LEG as 🛟 Rule-based (legacy)

    U->>FE: Открывает страницу товара
    FE->>BE: GET блок рекомендаций (session_id, sku)
    BE->>CTRL: POST /get_recommendation (JSON, timeout 200 мс)
    alt AI Service ответил вовремя
        CTRL->>CTRL: Валидация запроса
        CTRL->>CACHE: Проверить готовую подборку
        alt Кэш-хит (быстрый путь, <200 мс)
            CACHE-->>CTRL: Готовые рекомендации
            CTRL->>ASM: Собрать ответ из кэша
        else Кэш-промах (полный путь)
            CTRL->>PROF: Профиль и фичи
            PROF-->>CTRL: Сегмент, история, предпочтения
            CTRL->>RAG: Подобрать кандидатов (top-k)
            RAG-->>CTRL: SKU-кандидаты
            CTRL->>OMNI: Убрать купленное (онлайн+офлайн из 1С)
            OMNI-->>CTRL: Очищенные кандидаты
            CTRL->>RANK: Ранжировать
            RANK-->>CTRL: Топ-N
            CTRL->>PTF: Собрать промпт
            PTF-->>CTRL: Готовый промпт (может содержать PII)
            CTRL->>LLM: Сгенерировать заголовок и описание
            LLM->>ANON: Анонимизировать PII (ФИО/телефон → токены)
            ANON->>CLOUD: Промпт БЕЗ PII
            CLOUD-->>ANON: Текст с токенами
            ANON-->>LLM: Текст с восстановленными PII
            LLM-->>CTRL: Тексты (или шаблон-фолбэк)
            CTRL->>ASM: Собрать ответ (товары + тексты + meta)
            CTRL->>CACHE: Сохранить подборку (TTL)
        end
        ASM-->>CTRL: Готовый DTO
        CTRL-->>BE: 200 OK (recommendations, meta)
    else AI недоступен / 5xx / таймаут >200 мс
        CTRL-->>BE: 503 upstream_unavailable (или таймаут)
        BE->>LEG: Запросить rule-based блок
        LEG-->>BE: «С этим товаром часто покупают»
    end
    BE-->>FE: JSON блока (AI или fallback)
    FE-->>U: Показывает ленту (страница не блокируется)
```

Быстрый путь — из кэша (держит SLA 200 мс). При кэш-промахе — полный пайплайн с генерацией через анонимизатор. При сбое/таймауте AI — fallback на старый rule-based блок.

</details>

## API Spec — `/get_recommendation`

Полный контракт: [`api/openapi.yaml`](api/openapi.yaml) (OpenAPI 3.0.3, валиден).

- **Метод/путь:** `POST /v1/get_recommendation` — контракт **Backend → AI Service**.
- **Аутентификация:** сервис-к-сервису по заголовку `X-Api-Key` (+ рекомендован mTLS во внутренней сети).
- **Таймаут:** Backend ждёт ≤ 200 мс; при `5xx`/`503`/таймауте — fallback на rule-based блок.

**Запрос** (`RecommendationRequest`):

| Поле | Тип | Обяз. | Описание |
|------|-----|-------|----------|
| `session_id` | string (uuid) | да | ID сессии из cookie — нужен даже для анонима |
| `user_id` | string \| null | нет | ID пользователя, если залогинен |
| `context.page_type` | enum: `home/product/category/cart/search` | да | Где показывается блок |
| `context.current_sku` | string \| null | нет | SKU текущего товара (для `product`) |
| `context.category_id` | string \| null | нет | Категория |
| `context.device` | enum: `desktop/mobile/app` | нет | Тип устройства |
| `limit` | integer `1..50` | нет | Сколько товаров вернуть (default 10) |
| `generate_text` | boolean | нет | Генерировать ли заголовок/описание (default true) |

**Ответ** (`RecommendationResponse`): `request_id`, массив `recommendations` и `meta`.

| Поле item | Тип | Описание |
|-----------|-----|----------|
| `sku` | string | Артикул |
| `title` | string | Название из каталога |
| `price` / `currency` | number / string | Цена и валюта |
| `score` | number `0..1` | Скор ранжирования |
| `reason` | enum | Причина: `complementary_to_viewed`, `frequently_bought_together`, `personalized`, `popular_in_segment` |
| `generated_title` / `generated_description` | string \| null | Генеративные тексты (null при фолбэке) |
| `image_url` | string (uri) | Картинка |

`meta`: `model_version`, `llm_model`, `cache_hit`, `latency_ms`, `generated`.

**Коды ответов:** `200` OK · `400` битый запрос · `401` нет/неверный ключ · `422` ошибка валидации ·
`429` rate limit (`Retry-After`) · `500` внутренняя · `503` зависимость недоступна → fallback.

**Пример запроса:**

```json
{
  "session_id": "a3f1c9e2-7b44-4d2a-9c11-2f0e8d6b1234",
  "user_id": null,
  "context": { "page_type": "product", "current_sku": "SKU-100500", "device": "mobile" },
  "limit": 6,
  "generate_text": true
}
```

**Пример ответа (фрагмент):**

```json
{
  "request_id": "f17c2b9a-0d3e-4a8b-bb12-91a6f0c7e001",
  "recommendations": [
    {
      "sku": "SKU-200300",
      "title": "Беспроводная мышь Logitech MX",
      "price": 4990.00, "currency": "RUB", "score": 0.92,
      "reason": "complementary_to_viewed",
      "generated_title": "Идеальная пара к вашему ноутбуку",
      "generated_description": "Иван, вы недавно смотрели ноутбуки — эта мышь повысит продуктивность."
    }
  ],
  "meta": { "model_version": "ranker-2.3.1", "llm_model": "cloud-llm-gpt", "cache_hit": false, "latency_ms": 173, "generated": true }
}
```

**Пример ошибки (`503` → fallback):**

```json
{
  "error": {
    "code": "upstream_unavailable",
    "message": "LLM timeout, fallback recommended",
    "request_id": "f17c2b9a-0d3e-4a8b-bb12-91a6f0c7e001"
  }
}
```
