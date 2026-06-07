workspace "TechnoMart Recommendations" "C4-модель системы умных рекомендаций: контекст (C1), контейнеры (C2) и компоненты AI-сервиса (C3)" {

    model {
        customer = person "Покупатель" "Веб/мобильное приложение; залогинен или аноним по cookie"

        oneC = softwareSystem "1С" "Чеки и заказы: онлайн + офлайн" {
            tags "External"
        }
        catalogFeed = softwareSystem "Каталог (XML)" "Выгрузка каталога раз в сутки" {
            tags "External"
        }

        technomart = softwareSystem "TechnoMart Recommendations" "Платформа умных рекомендаций TechnoMart" {

            frontend = container "Frontend" "Сайт и мобильное приложение, блок рекомендаций" "SPA / Mobile" {
                tags "Frontend"
            }
            backend = container "Backend-монолит" "Каталог, корзина, заказы; BFF для рекомендаций" "PHP, Bitrix" {
                tags "Backend"
            }
            legacyReco = container "Rule-based Recommendations (legacy)" "Старый блок «с этим товаром часто покупают»; fallback при сбое/таймауте AI" "PHP, в монолите" {
                tags "Backend"
            }
            mysql = container "SQL DB магазина" "Каталог, пользователи, заказы" "MySQL" {
                tags "Database"
            }

            aiService = container "AI Recommendation Service" "Выдача рекомендаций + генеративные тексты" "Python, FastAPI" {
                tags "AI"

                controller = component "Recommendation Controller" "REST-эндпоинт, валидация, оркестрация пайплайна, сборка ответа" "FastAPI"
                cacheClient = component "Cache Client" "Быстрый путь: готовая подборка из Redis (<200 мс)" "Python"
                profileProvider = component "Profile Provider" "Профиль и фичи по user_id / session_id" "Python"
                ragManager = component "RAG Manager" "Сбор кандидатов: история + семантика, запрос к Vector DB" "Python"
                omnichannelFilter = component "Omnichannel Filter" "Исключает уже купленное (онлайн + офлайн)" "Python"
                ranker = component "Ranker / Scorer" "ML-ранжирование кандидатов" "Python, ML"
                promptFactory = component "Prompt Template Factory" "Шаблоны промптов + маскирование PII" "Python"
                llmClient = component "LLM Client" "Вызов Private LLM, ретраи, фолбэк на шаблон" "Python"
                responseAssembler = component "Response Assembler" "Финальный DTO: товары + тексты + meta" "Python"
                observability = component "Observability" "Логи, трассировка, метрики latency" "OpenTelemetry"
            }

            featureStore = container "Feature Store / SQL DB" "Профили, фичи, готовые подборки" "PostgreSQL" {
                tags "Database"
            }
            vectorDb = container "Vector DB" "Эмбеддинги товаров и сессий" "Qdrant / pgvector" {
                tags "Database"
            }
            cache = container "Cache" "Предрассчитанные подборки, TTL" "Redis" {
                tags "Database"
            }
            etl = container "Data Ingestion / ETL" "Каталог, заказы, клики -> фичи и эмбеддинги" "Python, Airflow" {
                tags "AI"
            }
            eventCollector = container "Event Collector" "Клики и просмотры в реальном времени" "Kafka / HTTP" {
                tags "AI"
            }
            privateLlm = container "Private LLM Service" "Генерация заголовков и описаний; PII не уходит наружу" "self-hosted LLM" {
                tags "AI"
            }
        }

        # --- Связи уровня контекста / контейнеров (C1 / C2) ---
        customer -> frontend "Открывает страницы" "HTTPS"
        frontend -> backend "Запрос блока рекомендаций" "HTTPS/JSON"
        frontend -> eventCollector "События клик/просмотр" "HTTPS"
        backend -> mysql "Чтение каталога/заказов" "SQL"
        backend -> aiService "POST /get_recommendation" "HTTPS/JSON"
        backend -> legacyReco "Fallback при сбое/таймауте AI (503)"
        legacyReco -> mysql "Чтение каталога/заказов" "SQL"

        aiService -> featureStore "Чтение профиля/фич"
        aiService -> vectorDb "Поиск кандидатов top-k"
        aiService -> cache "Чтение/запись подборок"
        aiService -> privateLlm "Генерация текста (без PII)"

        oneC -> etl "Заказы, синк 15 мин"
        catalogFeed -> etl "Каталог, раз в сутки"
        eventCollector -> etl "Поток событий"
        mysql -> etl "Справочники"
        etl -> featureStore "Фичи, профили"
        etl -> vectorDb "Эмбеддинги товаров"
        etl -> cache "Прогрев подборок"

        # --- Связи уровня компонентов (C3, внутри AI Recommendation Service) ---
        backend -> controller "POST /get_recommendation" "HTTPS/JSON"
        controller -> cacheClient "1/9. Проверить и записать кэш"
        controller -> profileProvider "2. Профиль/фичи"
        controller -> ragManager "3. Кандидаты"
        ragManager -> omnichannelFilter "4. Фильтр купленного"
        omnichannelFilter -> ranker "5. Ранжирование"
        ranker -> promptFactory "6. Сбор промпта"
        promptFactory -> llmClient "7. Генерация"
        llmClient -> responseAssembler "8. Товары + тексты"
        cacheClient -> responseAssembler "Hit -> сразу ответ"
        responseAssembler -> backend "JSON-ответ"

        cacheClient -> cache "GET/SET" "Redis"
        profileProvider -> featureStore "SELECT" "SQL"
        ragManager -> vectorDb "top-k поиск"
        llmClient -> privateLlm "Запрос генерации"

        controller -> observability "trace"
        ragManager -> observability "trace"
        ranker -> observability "trace"
        llmClient -> observability "trace"
    }

    views {
        systemContext technomart "C1_Context" "Контекст: система и внешнее окружение" {
            include *
            autolayout lr
        }

        container technomart "C2_Containers" "Контейнеры всей системы" {
            include *
            autolayout lr
        }

        component aiService "C3_Components" "Компоненты внутри AI Recommendation Service" {
            include *
            autolayout lr
        }

        styles {
            element "Person" {
                shape Person
                background #08427b
                color #ffffff
            }
            element "Container" {
                color #ffffff
            }
            element "Frontend" {
                background #e76f51
                color #ffffff
            }
            element "Backend" {
                background #bf360c
                color #ffffff
            }
            element "AI" {
                background #1565c0
                color #ffffff
            }
            element "Database" {
                shape Cylinder
                background #6a1b9a
                color #ffffff
            }
            element "External" {
                background #8d99ae
                color #ffffff
            }
            element "Component" {
                background #1f6feb
                color #ffffff
            }
        }
    }
}
