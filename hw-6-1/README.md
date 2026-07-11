# hw-6-1 — Метрики и алертинг в Kubernetes

Дополнительное задание к ДЗ №6 (Observability). Стенд обеспечивает end-to-end
наблюдаемость мини-сервиса в локальном кластере **minikube** по схеме:

```
FastAPI  --metrics-->  Prometheus  --metrics-->  Grafana  --alerts-->  Telegram
                    (всё внутри K8S Cluster [minikube])
```

Прикладной компонент — **LLM Gateway Simulator**. Кластер разворачивается на
minikube; приложение устанавливается через `kubectl`, стек мониторинга — через
Helm-релиз `kps`.

---

## Содержание

- [Доступы и ссылки](#доступы-и-ссылки)
- [Приложение: LLM Gateway Simulator](#приложение-llm-gateway-simulator)
- [Структура проекта](#структура-проекта)
- [Требования](#требования)
- [Профиль ресурсов](#профиль-ресурсов)
- [Развёртывание](#развёртывание)
- [Настройка Telegram](#настройка-telegram)
- [Ручная настройка и проверка](#ручная-настройка-и-проверка)
- [Правила алертов](#правила-алертов)
- [Генерация нагрузки](#генерация-нагрузки)
- [Путь алерта в Telegram](#путь-алерта-в-telegram)
- [Полный путь метрики](#полный-путь-метрики)
- [Добавление новой метрики](#добавление-новой-метрики)
- [Проверка пути метрик](#проверка-пути-метрик)
- [Очистка](#очистка)

---

## Доступы и ссылки

Ссылки доступны после проброса портов командой `./port_forwards.sh start`
(Grafana — 3000, Prometheus — 9090, приложение — 8080). До проброса портов
`localhost` недоступен.

| Ресурс | URL | Назначение |
|--------|-----|------------|
| Grafana UI | http://localhost:3000 | учётные данные `admin` / `admin` |
| Grafana → дашборд *LLM Gateway Observability* | http://localhost:3000/d/llm-gateway-obs | графики метрик приложения |
| Grafana → Alerting (правила) | http://localhost:3000/alerting/list | состояние алертов (Normal/Pending/Firing) |
| Grafana → Contact points (Telegram) | http://localhost:3000/alerting/notifications | проверка Telegram-получателя |
| Prometheus UI | http://localhost:9090 | интерфейс Prometheus |
| Prometheus → Targets | http://localhost:9090/targets | статус scrape (`llm-gateway` = `UP`) |
| Prometheus → Graph (PromQL) | http://localhost:9090/graph | выполнение запросов PromQL |
| App — корень | http://localhost:8080/ | информация о сервисе и моделях |
| App → health | http://localhost:8080/health | liveness/readiness |
| App → metrics | http://localhost:8080/metrics | метрики Prometheus |
| App → docs (Swagger) | http://localhost:8080/docs | OpenAPI-документация |

---

## Приложение: LLM Gateway Simulator

`app/app.py` — FastAPI-сервис, имитирующий шлюз к LLM-провайдеру без реальных
вызовов модели. На каждый `POST /chat` сервис:

- симулирует задержку генерации (TTFT + время, пропорциональное числу токенов);
- рассчитывает потреблённые токены (prompt/completion) и стоимость запроса (USD);
- периодически возвращает ошибки `500` (сбой апстрима) и `429` (rate limit); доли
  задаются через переменные окружения.

Метрики покрывают Golden Signals (Latency, Traffic, Errors) и специфичные для LLM
показатели (Token usage, Cost per request).

### Эндпоинты

| Метод | Путь | Назначение |
|-------|------|------------|
| GET | `/health` | liveness/readiness |
| GET | `/` | информация о сервисе и списке моделей |
| POST | `/chat` | симуляция ответа LLM `{prompt, model, max_tokens}` |
| GET | `/metrics` | метрики Prometheus |

### Экспортируемые метрики

| Метрика | Тип | Смысл |
|---------|-----|-------|
| `llm_requests_total{model,status}` | counter | запросы по модели и статусу |
| `llm_errors_total{model,type}` | counter | ошибки: `upstream` (500) / `rate_limit` (429) |
| `llm_request_latency_seconds{model}` | histogram | латентность `/chat` |
| `llm_tokens_total{model,kind}` | counter | токены prompt/completion |
| `llm_cost_usd_total{model}` | counter | симулированная стоимость, USD |
| `llm_inflight_requests` | gauge | запросы в обработке |

Параметры симуляции (env в `k8s/deployment.yaml`): `ERROR_RATE`,
`RATE_LIMIT_RATE`, `MAX_DELAY`, `BASE_LATENCY`.

---

## Структура проекта

```
hw-6-1/
├── app/app.py               # FastAPI LLM Gateway Simulator
├── Dockerfile
├── requirements.txt
├── k8s/                     # манифесты приложения
│   ├── namespace.yaml
│   ├── deployment.yaml      # 1 реплика, env-параметры симуляции
│   ├── service.yaml
│   └── servicemonitor.yaml  # обнаружение метрик Prometheus
├── monitoring/
│   ├── values.yaml          # Helm values: Grafana + Telegram alerting (плейсхолдеры токена)
│   └── dashboard.json       # дашборд Grafana
├── setup.sh                 # развёртывание стенда
├── port_forwards.sh         # проброс портов на localhost
├── load_test.sh             # генератор нагрузки
├── teardown.sh              # удаление кластера
└── diagrams/                # схемы (mermaid)
```

---

## Требования

- **Docker Desktop** (запущенный демон) — драйвер для minikube.
- **minikube**, **kubectl**, **helm** (установка: `brew install minikube helm`).

---

## Профиль ресурсов

Стенд рассчитан на минимальный расход ресурсов:

- **minikube**: 2 CPU / 2 GB RAM (задаётся в `setup.sh`). minikube не изменяет
  память существующего кластера, поэтому `setup.sh` пересоздаёт кластер.
- **Приложение**: 1 реплика, лимиты 150m CPU / 128Mi RAM.
- **Grafana**: лимит памяти 512Mi (движок Unified Alerting не помещается в 256Mi).
- **Prometheus**: `scrapeInterval` 30s, `retention` 1h.
- **Отключено**: Alertmanager, node-exporter, kube-state-metrics, scrape системных
  компонентов кластера (kubelet, apiserver, controller-manager, scheduler, kube-proxy,
  etcd, CoreDNS), дефолтные правила и дефолтные дашборды Grafana.
- Активная часть стека соответствует схеме: **app → Prometheus → Grafana → Telegram**.

---

## Развёртывание

```bash
cd hw-6-1

# 1. Развернуть стенд (minikube + Prometheus/Grafana + приложение)
./setup.sh

# 2. Пробросить порты на localhost
./port_forwards.sh start

# 3. Сгенерировать нагрузку
./load_test.sh 8080 400 256
```

Доставка алертов в Telegram требует предварительной установки токена и chat_id
(раздел [Настройка Telegram](#настройка-telegram)).

Доступы после проброса портов:

- **Grafana**: http://localhost:3000 (`admin` / `admin`) → дашборд *LLM Gateway Observability*.
- **Prometheus**: http://localhost:9090 → Status → Targets (`llm-gateway` = `UP`).
- **App**: http://localhost:8080 → `GET /`, `POST /chat`.

---

## Настройка Telegram

Контакт-пойнт `telegram` в `monitoring/values.yaml` содержит плейсхолдеры,
которые необходимо заменить реальными значениями до начала доставки алертов:

```yaml
bottoken: "REPLACE_WITH_TELEGRAM_BOT_TOKEN"
chatid:   "REPLACE_WITH_TELEGRAM_CHAT_ID"
```

Порядок получения и установки значений:

1. Создать бота через [@BotFather](https://t.me/BotFather): команда `/newbot`.
   Результат — `bottoken` вида `123456789:AAExxxxxxxxxxxxxxxxxxxxxxxxx`.
2. Определить `chat_id`: отправить сообщение боту и открыть
   `https://api.telegram.org/bot<ТОКЕН>/getUpdates`, взять значение `chat.id`
   (альтернатива — [@userinfobot](https://t.me/userinfobot)).
3. Установить значения одним из способов:
   - заменить плейсхолдеры в `monitoring/values.yaml` и выполнить `./setup.sh`;
   - обновить уже развёрнутый релиз без правки файла:

```bash
helm upgrade kps prometheus-community/kube-prometheus-stack \
  -n monitoring -f monitoring/values.yaml \
  --set-string grafana.alerting."contactpoints\.yaml".contactPoints[0].receivers[0].settings.bottoken="<ТОКЕН>" \
  --set-string grafana.alerting."contactpoints\.yaml".contactPoints[0].receivers[0].settings.chatid="<CHAT_ID>"
```

До установки значений алерты формируются в Grafana, но не доставляются в Telegram.

---

## Ручная настройка и проверка

Развёртывание автоматизировано. Ручных действий требуют установка Telegram-токена
и проверка конфигурации в интерфейсе Grafana.

### 1. Telegram-бот и chat_id

Шаги описаны в разделе [Настройка Telegram](#настройка-telegram). Кратко: создать
бота у [@BotFather](https://t.me/BotFather), определить `chat_id`, заменить
`REPLACE_WITH_TELEGRAM_BOT_TOKEN` / `REPLACE_WITH_TELEGRAM_CHAT_ID` в
`monitoring/values.yaml` и выполнить `./setup.sh` либо `helm upgrade ... --set-string ...`.

### 2. Проверка в Grafana UI

Интерфейс: http://localhost:3000 (`admin` / `admin`).

| Объект | Раздел | Ожидаемое состояние |
|--------|--------|---------------------|
| Contact point | [Alerting → Contact points](http://localhost:3000/alerting/notifications) | присутствует получатель `telegram`; действие **Test** доставляет тестовое сообщение |
| Notification policy | [Alerting → Notification policies](http://localhost:3000/alerting/routes) | уведомления маршрутизируются в получатель `telegram` |
| Alert rules | [Alerting → Alert rules](http://localhost:3000/alerting/list) | в папке **LLM Gateway** — два правила (*High error rate*, *High latency p95*) с состоянием `Normal` / `Pending` / `Firing` |
| Dashboard | [Dashboards → LLM Gateway Observability](http://localhost:3000/d/llm-gateway-obs) | дашборд открывается; источник данных — Prometheus |

Сбой действия **Test** означает, что `bottoken`/`chatid` не установлены или
некорректны.

### 3. Смена пароля admin в Grafana (опционально)

Значение по умолчанию — `admin` / `admin`. Смена в UI (профиль → Change password)
или через API:

```bash
curl -s -u admin:admin -X PUT http://localhost:3000/api/user/password \
  -H "Content-Type: application/json" \
  -d '{"oldPassword":"admin","newPassword":"<НОВЫЙ_ПАРОЛЬ>","confirmNew":"<НОВЫЙ_ПАРОЛЬ>"}'
```

### 4. Генерация нагрузки и проверка алертов

1. Подать нагрузку:

```bash
./load_test.sh 8080 400 256
```

2. Через ~2 минуты (окно `for` у правил) правило *High error rate* переходит в
   `Firing`, уведомление доставляется в Telegram.
3. Для перевода правил в состояние resolved установить нулевые доли ошибок:

```bash
kubectl -n app set env deploy/llm-gateway ERROR_RATE=0.0 RATE_LIMIT_RATE=0.0
```

---

## Правила алертов

Provisioning алертов задан в `monitoring/values.yaml` (Grafana Unified Alerting),
папка *LLM Gateway*:

| Алерт | Условие (PromQL) | Порог | Severity |
|-------|------------------|-------|----------|
| High error rate | `sum(rate(llm_errors_total[5m])) / sum(rate(llm_requests_total[5m]))` | > 0.05 за 2м | warning |
| High latency p95 | `histogram_quantile(0.95, sum(rate(llm_request_latency_seconds_bucket[5m])) by (le))` | > 1.5s за 2м | critical |

При параметрах по умолчанию (`ERROR_RATE=0.08`, `RATE_LIMIT_RATE=0.05`) под
нагрузкой доля ошибок составляет ~9–13%, p95 — ~2s; оба правила переходят в
`Firing` и доставляются в Telegram. Перевод в resolved:

```bash
kubectl -n app set env deploy/llm-gateway ERROR_RATE=0.0 RATE_LIMIT_RATE=0.0
```

Возврат исходных значений (`0.08` / `0.05`) восстанавливает срабатывание.

---

## Генерация нагрузки

Приложение не генерирует трафик самостоятельно; оно обрабатывает входящие
запросы. Симуляция выполняется внутри каждого `POST /chat`: сервис выжидает
задержку генерации, рассчитывает токены и стоимость, случайно возвращает
`500` / `429`. Без запросов счётчики не изменяются, графики остаются плоскими, а
правила алертов находятся в состоянии **NoData**.

Prometheus скрейпит `/metrics` каждые 30с независимо от наличия трафика (см.
[Полный путь метрики](#полный-путь-метрики)), однако без запросов счётчики не
растут — необходим трафик.

Способы подачи трафика:

- Swagger: http://localhost:8080/docs → `POST /chat` → *Try it out* → *Execute*.
- curl:

```bash
curl -s -X POST http://localhost:8080/chat \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"привет","model":"gpt-4o-mini","max_tokens":128}'
```

- Скрипт (аргументы: порт, число запросов, `max_tokens`):

```bash
./load_test.sh 8080 400 256
```

Постоянная нагрузка (цикл):

```bash
while true; do ./load_test.sh 8080 200 256; sleep 5; done
```

Постоянная нагрузка увеличивает потребление ресурсов приложением и стеком
мониторинга; на слабом оборудовании рекомендуется подавать нагрузку сериями.

---

## Путь алерта в Telegram

Цепочка **FastAPI → Prometheus → Grafana → Telegram**:

1. Приложение отдаёт метрики на `/metrics`; Prometheus скрейпит их каждые 30с и
   хранит как временные ряды.
2. В Grafana Unified Alerting заданы два правила (папка **LLM Gateway**,
   provisioning из `monitoring/values.yaml`):
   - **High error rate**:
     `sum(rate(llm_errors_total[5m])) / sum(rate(llm_requests_total[5m]))` выше
     порога из `values.yaml` (по умолчанию `0.05`);
   - **High latency p95**:
     `histogram_quantile(0.95, sum(rate(llm_request_latency_seconds_bucket[5m])) by (le))`
     выше `1.5s`.
3. Каждое правило вычисляет свой PromQL раз в минуту. При непрерывном выполнении
   условия в течение 2 минут (`for: 2m`) состояние проходит
   `Normal → Pending → Firing`.
4. В состоянии `Firing` Grafana по notification policy отправляет алерт в contact
   point `telegram` (доставка в чат по `bottoken` + `chatid`). При снятии условия
   доставляется **resolved**-уведомление.

Доставка в Telegram работает только после установки `bottoken` и `chatid` вместо
плейсхолдеров в `monitoring/values.yaml`; шаги приведены в разделе
[Настройка Telegram](#настройка-telegram). Без трафика правила находятся в
состоянии NoData (см. [Генерация нагрузки](#генерация-нагрузки)).

Проверка end-to-end:

1. Установить `bottoken` + `chatid` в `monitoring/values.yaml` и переприменить
   (`./setup.sh` или `helm upgrade ... --set-string ...`).
2. Grafana → Alerting → Contact points → `telegram` → **Test** — доставка тестового
   сообщения.
3. Подать нагрузку: `./load_test.sh 8080 400 256`.
4. Через ~2–3 минуты правило переходит в `Firing`, сообщение доставляется в чат.
5. Перевод в resolved:

```bash
kubectl -n app set env deploy/llm-gateway ERROR_RATE=0.0 RATE_LIMIT_RATE=0.0
```

---

## Полный путь метрики

Путь метрики от объявления в коде до графика в Grafana и алерта. Приложение
рассчитывает и экспортирует значения; агрегация и визуализация выполняются
Prometheus и Grafana.

### Шаг 1. Объявление метрики

В `app/app.py` создаются объекты из `prometheus_client`. При создании объект
регистрируется в глобальном реестре процесса. Список меток (labels) задаёт
измерения: каждой уникальной комбинации значений меток соответствует отдельный
временной ряд.

```python
REQUESTS = Counter("llm_requests_total", "Всего запросов к шлюзу LLM", ["model", "status"])
ERRORS   = Counter("llm_errors_total",   "Ошибки шлюза LLM по типам",  ["model", "type"])
LATENCY  = Histogram("llm_request_latency_seconds", "Латентность /chat (сек)",
                     ["model"], buckets=(0.05, 0.1, 0.25, 0.5, 1, 1.5, 2, 3, 5))
INFLIGHT = Gauge("llm_inflight_requests", "Запросы в обработке прямо сейчас")
```

### Шаг 2. Изменение значений на запросе

В обработчике `/chat` метрики изменяются по мере событий:

- **Counter** — `.inc()` / `.inc(n)`: монотонно растущий счётчик событий (запросы,
  ошибки, токены).
- **Gauge** — `.inc()` / `.dec()` / `.set(x)`: мгновенное значение, изменяемое в
  обе стороны (например, число запросов в обработке).
- **Histogram** — `.observe(x)`: распределение замеров `x` (например, латентности)
  по корзинам.

```python
INFLIGHT.inc()
...
REQUESTS.labels(model=model, status="200").inc()
LATENCY.labels(model=model).observe(time.perf_counter() - start)
...
INFLIGHT.dec()
```

### Шаг 2b. Устройство гистограммы

`observe(0.7)` не хранит значение «0.7»; вместо этого обновляются ряды:

- `llm_request_latency_seconds_bucket{le="..."}` — кумулятивные корзины (число
  замеров ≤ значения `le`);
- `llm_request_latency_seconds_sum` — сумма всех замеров;
- `llm_request_latency_seconds_count` — общее число замеров.

По этим рядам функция `histogram_quantile` оценивает перцентиль (например, p95).

### Шаг 3. Экспорт (pull-модель)

`Instrumentator().instrument(app).expose(app)` открывает эндпоинт `GET /metrics`.
При запросе `prometheus_client` сериализует реестр в текстовый формат. Приложение
не отправляет метрики самостоятельно — источник опрашивается (pull).

```text
# HELP llm_requests_total Всего запросов к шлюзу LLM
# TYPE llm_requests_total counter
llm_requests_total{model="gpt-4o-mini",status="200"} 227.0
llm_requests_total{model="gpt-4o-mini",status="500"} 12.0
# TYPE llm_request_latency_seconds histogram
llm_request_latency_seconds_bucket{model="gpt-4o-mini",le="0.5"} 41.0
llm_request_latency_seconds_bucket{model="gpt-4o-mini",le="+Inf"} 239.0
llm_request_latency_seconds_sum{model="gpt-4o-mini"} 288.4
llm_request_latency_seconds_count{model="gpt-4o-mini"} 239.0
```

### Шаг 4. Обнаружение цели (ServiceMonitor)

`k8s/servicemonitor.yaml` задаёт источник метрик: селектор `app: llm-gateway`,
путь `/metrics`, интервал `30s`. Prometheus Operator обнаруживает ServiceMonitor
по метке `release: kps` и добавляет scrape job в конфигурацию Prometheus. Service
`llm-gateway` связывает под(ы) по метке.

### Шаг 5. Скрейп и хранение (TSDB)

Каждые 30с Prometheus выполняет `GET /metrics` у каждого пода и записывает данные
в TSDB. Временной ряд = имя метрики + набор меток (Prometheus добавляет
`namespace`, `pod`, `instance` и др.) → последовательность точек
`(timestamp, value)`. Counter представлен монотонно растущей линией. Проверка
целей: http://localhost:9090/targets (`llm-gateway` = `UP`).

### Шаг 6. Вычисления PromQL

PromQL вычисляется в момент запроса (от Grafana или из UI); предварительная
агрегация не выполняется.

```promql
# доля ошибок
sum(rate(llm_errors_total[5m])) / clamp_min(sum(rate(llm_requests_total[5m])), 0.001)

# p95 латентности
histogram_quantile(0.95, sum(rate(llm_request_latency_seconds_bucket[5m])) by (le))
```

- `rate(x[5m])` — средняя скорость роста counter в секунду за окно 5 минут.
- `sum(...)` — суммирование рядов (по подам/меткам).
- `histogram_quantile(0.95, ... by (le))` — оценка 95-го перцентиля по корзинам.
- `clamp_min(x, 0.001)` — защита от нулевого делителя (`0/0 = NaN` при отсутствии
  трафика).

### Шаг 7. Отрисовка в Grafana

В `monitoring/dashboard.json` у каждой панели задан `datasource` = Prometheus
(uid `prometheus`) и PromQL-выражение (`targets[].expr`). Grafana с интервалом
`refresh` 10s запрашивает Prometheus, получает точки `(timestamp, value)` и
отображает их с единицами измерения (reqps, percentunit, s, USD) и порогами.
Дашборд импортируется через ConfigMap с меткой `grafana_dashboard=1`, который
подхватывает sidecar Grafana.

### Шаг 8. PromQL в алертинге

Правила алертов используют те же PromQL-выражения — для сравнения с порогом и
отправки уведомлений (см. [Путь алерта в Telegram](#путь-алерта-в-telegram)).

### Схема пути

```text
переменная в app.py (Counter/Gauge/Histogram)
        │  .inc()/.observe() на каждом /chat
        ▼
глобальный реестр prometheus_client
        │  GET /metrics (pull, текстовый формат)
        ▼
Prometheus scrape (каждые 30с, по ServiceMonitor)
        │  запись в TSDB: ряд = имя+метки → (t, value)
        ▼
PromQL (rate / sum / histogram_quantile) — вычисляется на лету
        ├───────────► Grafana panels (dashboard.json) → графики
        └───────────► Grafana Alerting → Telegram (при Firing)
```

---

## Добавление новой метрики

Пример — счётчик попаданий в кэш ответов.

**1. Объявить объект метрики** в `app/app.py` рядом с остальными:

```python
CACHE_HITS = Counter("llm_cache_hits_total", "Попадания в кэш ответов", ["model"])
```

**2. Изменять значение в обработчике** `/chat` в точке наступления события:

```python
CACHE_HITS.labels(model=model).inc()
```

**3. Пересобрать образ и перекатить приложение:**

```bash
./setup.sh
# либо точечно, без пересоздания кластера:
eval $(minikube -p llm-alerting docker-env)
docker build -t llm-gateway-sim:0.1 .
kubectl -n app rollout restart deploy/llm-gateway
```

Изменение `ServiceMonitor` не требуется: новая метрика появляется на `/metrics` и
подхватывается Prometheus при следующем скрейпе.

**4. Проверить наличие метрики** после подачи трафика:

```bash
./load_test.sh 8080 200 256
curl -s http://localhost:8080/metrics | grep llm_cache_hits_total
```

Запрос в Prometheus (http://localhost:9090/graph):

```promql
sum by (model) (rate(llm_cache_hits_total[5m]))
```

**5. Добавить панель в Grafana** одним из способов:

- UI: *New panel* → datasource Prometheus → PromQL → *Save*.
- Код: добавить объект панели в `monitoring/dashboard.json` (`datasource {type: prometheus, uid: prometheus}`,
  `targets[].expr`, уникальные `id` и `gridPos`), затем переимпортировать дашборд
  через `./setup.sh`.

**6. Добавить алерт (опционально)** — правило в
`grafana.alerting."rules.yaml"` в `monitoring/values.yaml` по образцу двух
существующих (query `refId A` с PromQL + threshold-выражение `refId C`), затем
`./setup.sh`.

### Выбор типа метрики

| Тип | Применение | Пример |
|-----|-----------|--------|
| Counter | подсчёт событий, значение только растёт | запросы, ошибки, токены |
| Gauge | мгновенное значение, изменяемое в обе стороны | запросы в обработке, длина очереди |
| Histogram | распределение значений | латентность, размер ответа |

Метки высокой кардинальности (`user_id`, `request_id`, полный URL и т.п.)
недопустимы: каждая уникальная комбинация меток создаёт отдельный ряд и повышает
расход памяти Prometheus.

---

## Проверка пути метрик

1. **Prometheus Targets**: http://localhost:9090 → Status → Targets →
   `serviceMonitor/monitoring/llm-gateway` в статусе `UP` (1 под).
2. **PromQL** в Prometheus, например: `sum by (status) (rate(llm_requests_total[1m]))`.
3. **Grafana** → дашборд *LLM Gateway Observability*: request rate, error rate,
   latency p95/p50, tokens/s, cost/min, in-flight.
4. **Grafana Alerting** → Alert rules → папка *LLM Gateway* → состояние правил.

---

## Очистка

```bash
./port_forwards.sh stop
./teardown.sh          # minikube delete -p llm-alerting
```
