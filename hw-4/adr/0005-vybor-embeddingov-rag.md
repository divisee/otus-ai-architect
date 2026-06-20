---
ADR: 0005
Название: Выбор модели эмбеддингов для RAG
Статус: Предложено
Дата: 2026-06-20
Авторы: Команда архитектуры
Связан с: ADR-0001 (self-hosted в периметре), ADR-0002 (LLM), PRD §4 (FR-7), §5
---

# Выбор модели эмбеддингов для RAG

## Статус

**Предложено** — основной кандидат **BAAI/bge-m3**; запасной — **Qwen3-Embedding-4B**
и ру-тюн **deepvk/USER-bge-m3**. Финал — по retrieval-метрикам на golden-датасете.

## Контекст

RAG индексирует **Confluence (публичная часть)** и **БД материалов/ТТХ** (FR-6,
FR-7). Заказы идут **прямым SQL**, не эмбеддятся (§5: «знания о заказах не
пересекаются с Confluence/Материалами») — значит эмбеддинги работают по
неперсональным доменным текстам.

Требования к эмбеддингам:
- **русский язык** + смешанные RU+EN термины (артикулы, ТТХ);
- **гибридный поиск**: данные содержат точные токены (номера артикулов,
  обозначения материалов) → нужен лексический (sparse) компонент рядом с dense;
- длина контекста под наши чанки (Confluence-страницы бывают длинными);
- **self-hosted в периметре** (консистентно с ADR-0001 — без внешнего API);
- разумные VRAM/латентность и размерность вектора (стоимость индекса);
- одинаковая модель на индексации и на запросе.

## Рассматриваемые варианты

| Модель | Парам. | Dim | Контекст | Лиценз. | Русский | Примечание |
|---|---|---|---|---|---|---|
| **BAAI/bge-m3** | 568M | 1024 | **8192** | MIT | Хороший | **Гибрид dense+sparse+multivector** «из коробки»; лёгкая (~1.4 ГБ FP16) |
| **deepvk/USER-bge-m3** | 568M | 1024 | 8192 | Apache-2.0 | **Лучше на ru-доменах** | Fine-tune bge-m3; сильнее на узких ru (юр./мед.), слабее на смешанных RU+EN |
| **intfloat/multilingual-e5-large-instruct** | 560M | 1024 | **512** | MIT | Хороший | Сильный baseline, но **контекст 512** — режет длинные чанки |
| **Qwen3-Embedding-0.6B** | 0.6B | до 1024 (MRL) | длинный | Apache-2.0 | Хороший | Эффективная; **Matryoshka** (усечение размерности) |
| **Qwen3-Embedding-4B / 8B** | 4–8B | до 4096 | длинный | Apache-2.0 | **Очень хороший** (8B — №1 MMTEB, 70.6) | Топ-качество, но дороже по VRAM/латентности |

**Ссылки (Hugging Face):**
- BAAI/bge-m3 — https://huggingface.co/BAAI/bge-m3
- deepvk/USER-bge-m3 — https://huggingface.co/deepvk/USER-bge-m3
- intfloat/multilingual-e5-large-instruct — https://huggingface.co/intfloat/multilingual-e5-large-instruct
- Qwen3-Embedding-0.6B — https://huggingface.co/Qwen/Qwen3-Embedding-0.6B · 4B — https://huggingface.co/Qwen/Qwen3-Embedding-4B · 8B — https://huggingface.co/Qwen/Qwen3-Embedding-8B
- FRIDA (ru, ai-forever) — https://huggingface.co/ai-forever/FRIDA
- Реранкер (в пару): BAAI/bge-reranker-v2-m3 — https://huggingface.co/BAAI/bge-reranker-v2-m3

## Решение

**Основная модель — BAAI/bge-m3.** Причины:
1. **Гибридный поиск (dense+sparse) в одной модели** — критично для наших данных:
   точные артикулы/обозначения материалов ловятся лексическим компонентом, а
   смысл — плотным. Это повышает recall без отдельного BM25-движка.
2. **Контекст 8192** покрывает длинные Confluence-страницы без агрессивного
   нарезания чанков.
3. Лёгкая (568M, ~1.4 ГБ FP16) → дёшево по VRAM/латентности, можно крутить даже
   на CPU/малом GPU отдельно от LLM; лицензия MIT.

**Запасные варианты:**
- **deepvk/USER-bge-m3** — если на ru-доменных текстах нужен выше recall (тот же
  пайплайн, drop-in замена).
- **Qwen3-Embedding-4B/8B** — если bge-m3 не вытягивает целевую точность на
  golden-датасете (ценой VRAM/латентности; MRL у Qwen позволяет урезать размерность).

**В пару — реранкер `bge-reranker-v2-m3`** (cross-encoder, top-k → top-n): заметно
поднимает precision RAG (как в ADR-0003 по hw-3). Эмбеддер и реранкер — из одной
M3-линейки, что упрощает эксплуатацию.

Финал закрепляем по retrieval-метрикам (Recall@k / nDCG) на golden-датасете (AC-4).

## Последствия

### Плюсы
- Гибридный retrieval из коробки → выше recall на терминах/артикулах.
- Длинный контекст 8192 и низкая стоимость; MIT-лицензия; работает в периметре.
- Drop-in замена на ру-тюн или Qwen без переработки пайплайна (одинаковый интерфейс).

### Минусы (trade-offs)
- bge-m3 по чистому MMTEB уступает Qwen3-Embedding-8B → возможен потолок качества
  на сложных запросах; купируется реранкером и/или переходом на Qwen.
- **Смена эмбеддера = переиндексация всей БЗ** (вектора несовместимы) — менять
  модель только осознанно; зафиксировать версию модели в метаданных индекса.
- Гибридный (dense+sparse) индекс сложнее в настройке весов, чем чисто dense.
- Отдельный сервис эмбеддингов/реранкера — доп. операционная нагрузка.

### Проверка
На golden-датасете заказчика сравнить bge-m3 (dense vs hybrid) ± reranker против
USER-bge-m3 и Qwen3-Embedding-4B по **Recall@k / nDCG**; выбрать по факту, не по
лидерборду. Зафиксировать выбранную модель и размерность в Vector DB.

## Дополнительно
- Лидерборд: [MTEB/MMTEB (HF Spaces)](https://huggingface.co/spaces/mteb/leaderboard)
  (фильтр Language=Russian, Task=Retrieval).
- Сравнение ru-эмбеддеров: [bge-m3 vs USER-bge-m3 vs multilingual-e5 (AGmind)](https://prem.agmind.dev/blog/embedding-modeli-russkiy-yazyk-bge-m3-e5/) ·
  [Qwen3-Embedding (GitHub)](https://github.com/QwenLM/Qwen3-Embedding).
- Реранкер в пару: [BAAI/bge-reranker-v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3).
- Vector DB и стратегия чанкинга — см. RAG-flow hw-3; хранить `vector + текст +
  метаданные (источник, версия эмбеддера)`.
