workspace "TechnoMart Recommendations" "C4-модель системы умных рекомендаций: контекст (C1), контейнеры (C2) и компоненты AI-сервиса (C3)" {

    model {
        customer = person "Покупатель" "Веб/мобильное приложение; залогинен или аноним по cookie"

        oneC = softwareSystem "1С" "Чеки и заказы: онлайн + офлайн" {
            tags "External"
        }
        catalogFeed = softwareSystem "Каталог (XML)" "Выгрузка каталога раз в сутки" {
            tags "External"
        }
        cloudLlm = softwareSystem "Cloud LLM Provider" "Внешняя облачная генеративная модель; получает только анонимизированные промпты без PII" {
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
                candidateGen = component "Candidate Generator (Retrieval)" "Отбор кандидатов из 50k SKU: CF + ANN-эмбеддинги + история; pre-filter (наличие/регион/категория) на этапе retrieval; over-fetch ~top-500" "Python"
                omnichannelFilter = component "Omnichannel Filter" "Вычитает уже купленное (онлайн+офлайн) быстрым set-difference (Redis SET / Bloom) до ранжирования" "Python"
                ranker = component "Ranker / Scorer (ML)" "ML-ранжирование по вероятности клика/покупки; ядро recsys вместе с Candidate Generator" "Python, ML"
                promptFactory = component "Prompt Template Factory" "Шаблоны промптов под тип подборки" "Python"
                llmClient = component "LLM Client" "Вызов облачной LLM через анонимизатор; ретраи, фолбэк на шаблон" "Python"
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
            anonymizer = container "PII Anonymizer / Rehydrator" "Маскирует PII в токены перед вызовом облачной LLM и восстанавливает их в ответе" "Python" {
                tags "AI"
            }
            tokenVault = container "Token Vault" "Короткоживущая карта токен <-> реальное значение PII" "Redis, короткий TTL" {
                tags "Database"
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
        aiService -> anonymizer "Промпт на генерацию (может содержать PII)"
        anonymizer -> tokenVault "Сохранить/прочитать карту токенов"
        anonymizer -> cloudLlm "Анонимизированный промпт БЕЗ PII" "HTTPS"

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
        controller -> candidateGen "3. Кандидаты"
        candidateGen -> omnichannelFilter "4. Фильтр купленного"
        omnichannelFilter -> ranker "5. Ранжирование"
        ranker -> promptFactory "6. Сбор промпта"
        promptFactory -> llmClient "7. Генерация"
        llmClient -> responseAssembler "8. Товары + тексты"
        cacheClient -> responseAssembler "Hit -> сразу ответ"
        responseAssembler -> backend "JSON-ответ"

        cacheClient -> cache "GET/SET" "Redis"
        profileProvider -> featureStore "SELECT" "SQL"
        candidateGen -> vectorDb "ANN-поиск + metadata-фильтр (наличие/регион)"
        llmClient -> anonymizer "Анонимизировать и вызвать облачную LLM"

        controller -> observability "trace"
        candidateGen -> observability "trace"
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
