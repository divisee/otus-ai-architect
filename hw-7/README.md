# ДЗ №7. Sizing: ресурсы и стоимость инференса LLM

**Задача:** Llama-3-70B (FP16 / INT4), нагрузка **1000 RPM** — VRAM, GPU, аренда (Yandex Cloud / Cloud.ru), эффект vLLM/батчинга, **покупка vs аренда**.

Теория — [конспект](summary/README.md). Расчёты: [`sizing-calculations.csv`](sizing-calculations.csv) → импорт в Google Sheets (*Файл → Импорт*).

> **➡️ [Google Таблица](https://docs.google.com/spreadsheets/d/1L5QwOGFtQzOdr4XhA6QnUcB91sLUZCQ2GJgGgBcBMgI/edit?usp=sharing)** (доступ «всем по ссылке»)

---

## 1. Исходные данные

**Модель** — [Meta-Llama-3-70B `config.json`](https://huggingface.co/meta-llama/Meta-Llama-3-70B/blob/main/config.json):

| Параметр | Значение |
|----------|:---:|
| Параметры | 70B |
| `n_layers` | 80 |
| `d_model` / голов внимания | 8192 / 64 |
| `n_kv_heads` (GQA) / `head_dim` | 8 / 128 |
| Контекст | 8192 ток. |

**Нагрузка** (допущения трафика):

| Параметр | Значение | Как считать       |
|----------|:---:|-------------------|
| Нагрузка | 1000 RPM = **16.67 RPS** | 1000 / 60         |
| Input / output / средний ctx | 500 / 250 / **750** ток. | допущение         |
| Throughput | **4167** ток/с | 16.67 × 250       |
| Concurrent | **167** | 16.67 RPS × ~10 с |
| Часов/мес | **730** | 24 × 365 / 12     |

VRAM-проверка: [NyxKrage](https://huggingface.co/spaces/NyxKrage/LLM-Model-VRAM-Calculator), [APXML](https://apxml.com/tools/vram-calculator).

---

## 2. Hardware Sizing (VRAM)

Формула: `VRAM = Параметры × байт + KV cache + Overhead`.

### Веса

| Точность | Байт/пар. | Веса | Как |
|----------|:---:|:---:|-----|
| FP16 | 2 | **140 GB** | 70e9 × 2 / 1e9 |
| INT8 | 1 | 70 GB | 70e9 × 1 / 1e9 |
| **INT4** | 0.5 | **35 GB** | 70e9 × 0.5 / 1e9 |

### KV cache (FP16)

`KV/токен = 2 × 80 × 8 × 128 × 2 / 1024² = 0.313 MiB`

| Показатель | Значение | Как |
|------------|:---:|-----|
| KV на запрос (ctx 8192) | 2.5 GiB | 0.313 × 8192 / 1024 |
| KV на запрос (ctx 750) | 0.229 GiB | 0.313 × 750 / 1024 |
| KV на нагрузку (167 × 750) | **38.2 GiB** | 167 × 750 × 0.313 / 1024 |

### Итоговый VRAM (формула критерия: Параметры × Вес + KV cache)

```
VRAM = (Параметры × байт/параметр) + KV cache + Overhead(20%)
```

| Вариант | Параметры × Вес | Overhead 20% | Веса+OH | KV на нагрузку | **VRAM итого** |
|---------|:---:|:---:|:---:|:---:|:---:|
| FP16 | 70B × 2 = **140 GB** | +28 | 168 GB | 38.2 GiB | **168 + 38.2 ≈ 206 GB** на систему |
| **INT4 ✅** | 70B × 0.5 = **35 GB** | +7 | 42 GB | 38.2 GiB | **42 + 38.2 ≈ 80.2 GB** на систему |

### Рекомендуемая конфигурация: INT4, 3×A100-80GB — сколько ест и какой запас

KV делится на 3 реплики: `38.2 / 3 ≈ **12.7 GiB**/GPU`.

| На 1× A100 (реплика) | GB | Как |
|----------------------|:---:|-----|
| Веса INT4 | 35 | 70B × 0.5 |
| Overhead 20% | 7 | 35 × 0.2 |
| KV (доля нагрузки) | 12.7 | 38.2 / 3 |
| **Итого занято** | **≈ 54.7** | 35 + 7 + 12.7 |
| VRAM карты | **80** | A100-80GB |
| **Запас** | **≈ 25.3 GB (~32%)** | 80 − 54.7 |

> **Вывод по памяти:** на выбранной конфигурации одна карта заполнена ~**55/80 GB**, запас **~25 GB** — на пик concurrent, более длинный контекст и буферы vLLM. FP16 (~206 GB на систему) на одну карту не влезает → нужен TP (4×A100 на реплику).

---

## 3. Сколько GPU

Спеки карт: [Yandex Cloud GPU](https://yandex.cloud/ru/docs/compute/concepts/gpus) — A100 80 GB, T4 16 GB; L4 24 GB (NVIDIA Ada).

### По памяти

| Вариант | A100-80 | L4-24 | T4-16 |
|---------|:---:|:---:|:---:|
| FP16 (168 GB) | ⌈168/80⌉=**3** (на практике TP=4) | 7 | 11 |
| INT4 (42 GB) | **1** | 2 | 3 |

### По пропускной способности (4167 ток/с)

`реплик = ⌈4167 / ток_с_реплики⌉`, `GPU = реплик × GPU_на_реплику`. Ток/с реплики — оценка vLLM.

**Откуда 4167 ток/с:**

| Шаг | Расчёт | Результат |
|-----|--------|:---:|
| 1. RPM → RPS | 1000 RPM / 60 | **16.67 RPS** |
| 2. Средний ответ | допущение | **250** ток./запрос |
| 3. Нужный throughput | 16.67 × 250 | **4167 ток/с** |

| Конфигурация | Ток/с на реплику | Реплик | **GPU** | Как |
|--------------|:---:|:---:|:---:|-----|
| FP16, 4×A100 (TP=4) | 3000 | ⌈4167/3000⌉=2 | **8× A100** | 2 × 4 |
| INT4, 1×A100 (AWQ) | 1800 | ⌈4167/1800⌉=3 | **3× A100** | 3 × 1 |
| INT4, 2×L4 | 700 | ⌈4167/700⌉=6 | 12× L4 | 6 × 2 |
| INT4, 3×T4 | 300 | ⌈4167/300⌉=14 | 42× T4 ❌ | 14 × 3 |

**Итог:** 8×A100 (FP16) или **3×A100 (INT4)**. T4 исключаем (нет FlashAttention, слишком много карт).

---

## 4. Аренда: Yandex Cloud vs Cloud.ru

Срез цен **28.07.2026**, **с НДС 22%**, без CVoS/скидок. Диски/трафик не учтены.

| SKU | ₽/час | Состав | Источник |
|-----|:---:|--------|----------|
| **YC DataSphere `g2.1`** | **542.88** | 28 vCPU + 1×A100 | [тарифы DataSphere](https://yandex.cloud/ru/docs/datasphere/pricing) |
| **Cloud.ru Evolution 1×A100** | **317.20** | 20 vCPU / 125 GB / 1×A100 | [тариф Evolution GPU](https://cloud.ru/documents/tariffs/evolution/evolution-compute-gpu), [PDF 260619](https://cdn.cloud.ru/docs/legal/tariffs/evolution/current-version/evolution-compute-gpu.pdf) |
| YC `gt4.1` (справочно) | 168.48 | 4 vCPU + 1×T4 | [DataSphere](https://yandex.cloud/ru/docs/datasphere/pricing) |

Месяц = 730 ч. Формула: `GPU × ₽/час × 730`.

| Конфиг | GPU | Yandex, ₽/мес | Cloud.ru, ₽/мес |
|--------|:---:|:---:|:---:|
| FP16 | 8 | 8 × 542.88 × 730 = **3 170 419** | 8 × 317.20 × 730 = **1 852 448** |
| **INT4** | 3 | 3 × 542.88 × 730 = **1 188 907** | 3 × 317.20 × 730 = **694 668** |
| INT4 + HA (N+1) | 4 | 1 585 210 | **926 224** |

INT4 vs FP16: **−62.5%**. Cloud.ru дешевле YC ≈ **в 1.71×**.

---

## 5. Оптимизация: батчинг / vLLM

INT4, 1×A100, цена Cloud.ru 317.20 ₽/час.

| Уровень | Ток/с | GPU | ₽/мес Cloud.ru | Как |
|---------|:---:|:---:|:---:|-----|
| Наивно (batch=1) | 90 | 47 | **10 883 132** | 47 × 317.20 × 730 |
| Статический батч | 450 | 10 | **2 315 560** | 10 × 317.20 × 730 |
| **vLLM** | 1800 | **3** | **694 668** | 3 × 317.20 × 730 |

vLLM vs наивно: **−93.6%** GPU. Теория — [конспект](summary/README.md) (PagedAttention, continuous batching, FlashAttention).

---

## 6. Покупка GPU vs аренда (окупаемость)

Цена покупки **A100 80GB PCIe** (ориентир РФ, с НДС, только карта без сервера/стойки):

| Источник | Цена, ₽ |
|----------|:---:|
| [T-Bazar](https://t-bazar.ru/catalog/servernoe-oborudovanie/videokarty/videokarta-nvidia-a100-80gb/) | ~713 400 |
| [3DImport](https://3dimport.ru/shop/graphics-cards/nvidia-a100-80gb/) | ~794 700 |
| [Servermall](https://servermall.ru/catalog/videokarty/nvidia-a100-80gb/) | ~1 008 214 |
| **В расчёте** | **800 000** (середина диапазона) |

Аренда 1×A100 Cloud.ru: `317.20 × 730 = **231 556** ₽/мес`.  
Окупаемость 1 карты: `800 000 / 231 556 ≈ **3.5 мес**`.

| Конфиг | Купить, ₽ | Аренда Cloud.ru, ₽/мес | Окупаемость | Аренда YC, ₽/мес | Окупаемость vs YC |
|--------|:---:|:---:|:---:|:---:|:---:|
| INT4, 3×A100 | 3 × 800k = **2 400 000** | 694 668 | **3.5 мес** | 1 188 907 | **2.0 мес** |
| INT4+HA, 4×A100 | **3 200 000** | 926 224 | **3.5 мес** | 1 585 210 | **2.0 мес** |
| FP16, 8×A100 | **6 400 000** | 1 852 448 | **3.5 мес** | 3 170 419 | **2.0 мес** |

> Покупка окупается за **~2–3.5 мес** непрерывной аренды. В расчёт **не входят** сервер, PSU, сеть, ЦОД, электричество (~0.3–1 кВт/карту), админы — on-prem дороже «голой» карты. Имеет смысл при горизонте **>6–12 мес** и своей инфраструктуре; иначе — аренда.

---

## 7. Вывод

| Вариант | GPU | ₽/мес аренда (Cloud.ru) | Когда |
|---------|:---:|:---:|------|
| **INT4 + vLLM ✅** | **3× A100** (4 с HA) | **694 668** (926 224 с HA) | база: цена/качество |
| FP16 + vLLM | 8× A100 | 1 852 448 | нужно макс. качество |
| Покупка INT4 | 3× A100, CAPEX 2.4 млн | окуп. ~3.5 мес | горизонт >6–12 мес, свой ЦОД |
| T4 / L4 | 42 / 12 | — | не рекомендуем / ограничено в РФ |

**Рекомендация:** Llama-3-70B **INT4 (AWQ)** + **vLLM**, **3×A100** (4 с HA), аренда **Cloud.ru** (~695 тыс. ₽/мес). На карте занято **~55/80 GB** (запас **~25 GB / 32%**). Покупка окупается vs аренда за ~3.5 мес, но с учётом сервера/ЦОД — смотреть горизонт эксплуатации.

---

## Источники

| Что | Ссылка |
|-----|--------|
| Конфиг модели | [Meta-Llama-3-70B config.json](https://huggingface.co/meta-llama/Meta-Llama-3-70B/blob/main/config.json) |
| VRAM-калькуляторы | [NyxKrage](https://huggingface.co/spaces/NyxKrage/LLM-Model-VRAM-Calculator), [APXML](https://apxml.com/tools/vram-calculator) |
| Yandex Cloud цены | [DataSphere pricing](https://yandex.cloud/ru/docs/datasphere/pricing), [GPU](https://yandex.cloud/ru/docs/compute/concepts/gpus), [прайс](https://yandex.cloud/ru/prices) |
| Cloud.ru цены | [тарифы Evolution GPU](https://cloud.ru/documents/tariffs/evolution/evolution-compute-gpu), [PDF](https://cdn.cloud.ru/docs/legal/tariffs/evolution/current-version/evolution-compute-gpu.pdf) |
| Покупка A100 | [T-Bazar](https://t-bazar.ru/catalog/servernoe-oborudovanie/videokarty/videokarta-nvidia-a100-80gb/), [3DImport](https://3dimport.ru/shop/graphics-cards/nvidia-a100-80gb/), [Servermall](https://servermall.ru/catalog/videokarty/nvidia-a100-80gb/) |
