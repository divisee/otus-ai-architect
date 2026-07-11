"""LLM Gateway Simulator.

Мини-сервис, имитирующий шлюз к LLM-провайдеру. Он НЕ ходит в реальную модель,
а симулирует её поведение: задержку генерации, потребление токенов, стоимость
запроса и периодические сбои (500 — ошибка провайдера, 429 — rate limit).

Сервис нужен только для иллюстрации наблюдаемости (metrics -> Prometheus ->
Grafana -> Telegram alert). Все "проблемы" внедряются искусственно и настраиваются
через переменные окружения, чтобы можно было наглядно ловить срабатывание алертов.
"""

import os
import random
import time

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from prometheus_client import Counter, Gauge, Histogram
from prometheus_fastapi_instrumentator import Instrumentator

# --- Настройки симуляции (крутим через env в Deployment) ---------------------

# Доля запросов, падающих с 500 (ошибка "провайдера").
ERROR_RATE = float(os.getenv("ERROR_RATE", "0.08"))
# Доля запросов, отбитых rate-limit'ом провайдера (429).
RATE_LIMIT_RATE = float(os.getenv("RATE_LIMIT_RATE", "0.05"))
# Максимальная дополнительная задержка генерации, сек.
MAX_DELAY = float(os.getenv("MAX_DELAY", "1.5"))
# Базовая задержка "первого токена" (TTFT), сек.
BASE_LATENCY = float(os.getenv("BASE_LATENCY", "0.05"))

# Цены за 1K токенов ($), чтобы считать симулированную стоимость запроса.
MODEL_PRICES = {
    "gpt-4o-mini": {"prompt": 0.00015, "completion": 0.0006},
    "gpt-4o": {"prompt": 0.005, "completion": 0.015},
    "llama-3-8b": {"prompt": 0.00005, "completion": 0.0001},
}
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gpt-4o-mini")

# --- Prometheus-метрики -------------------------------------------------------

REQUESTS = Counter(
    "llm_requests_total",
    "Всего запросов к шлюзу LLM",
    ["model", "status"],
)
ERRORS = Counter(
    "llm_errors_total",
    "Ошибки шлюза LLM по типам",
    ["model", "type"],
)
LATENCY = Histogram(
    "llm_request_latency_seconds",
    "Латентность обработки /chat (сек)",
    ["model"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 1.5, 2, 3, 5),
)
TOKENS = Counter(
    "llm_tokens_total",
    "Потреблённые токены",
    ["model", "kind"],  # kind = prompt | completion
)
COST = Counter(
    "llm_cost_usd_total",
    "Симулированная стоимость запросов, USD",
    ["model"],
)
INFLIGHT = Gauge(
    "llm_inflight_requests",
    "Запросы в обработке прямо сейчас",
)


class ChatRequest(BaseModel):
    prompt: str
    model: str | None = None
    max_tokens: int = 128


app = FastAPI(title="LLM Gateway Simulator")

# Стандартные http_* метрики (http_requests_total, latency и т.д.).
Instrumentator().instrument(app).expose(app, include_in_schema=False)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return {
        "service": "llm-gateway-sim",
        "models": list(MODEL_PRICES.keys()),
        "hint": "POST /chat {prompt, model, max_tokens}",
    }


@app.post("/chat")
def chat(req: ChatRequest):
    model = req.model or DEFAULT_MODEL
    if model not in MODEL_PRICES:
        raise HTTPException(status_code=400, detail=f"Unknown model: {model}")

    INFLIGHT.inc()
    start = time.perf_counter()
    try:
        # 429: rate limit провайдера.
        if random.random() < RATE_LIMIT_RATE:
            ERRORS.labels(model=model, type="rate_limit").inc()
            REQUESTS.labels(model=model, status="429").inc()
            LATENCY.labels(model=model).observe(time.perf_counter() - start)
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded (simulated)"},
            )

        # 500: сбой апстрима.
        if random.random() < ERROR_RATE:
            ERRORS.labels(model=model, type="upstream").inc()
            REQUESTS.labels(model=model, status="500").inc()
            LATENCY.labels(model=model).observe(time.perf_counter() - start)
            raise HTTPException(status_code=500, detail="Upstream LLM failure (simulated)")

        # Симуляция генерации: TTFT + время, пропорциональное числу токенов.
        completion_tokens = random.randint(16, max(16, req.max_tokens))
        prompt_tokens = max(1, len(req.prompt.split()))
        gen_delay = BASE_LATENCY + random.random() * MAX_DELAY * (completion_tokens / 128)
        time.sleep(gen_delay)

        prices = MODEL_PRICES[model]
        cost = (prompt_tokens * prices["prompt"] + completion_tokens * prices["completion"]) / 1000
        TOKENS.labels(model=model, kind="prompt").inc(prompt_tokens)
        TOKENS.labels(model=model, kind="completion").inc(completion_tokens)
        COST.labels(model=model).inc(cost)
        REQUESTS.labels(model=model, status="200").inc()
        LATENCY.labels(model=model).observe(time.perf_counter() - start)

        return {
            "model": model,
            "completion": f"[simulated answer to: {req.prompt[:40]}]",
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
            "cost_usd": round(cost, 6),
            "latency_s": round(time.perf_counter() - start, 3),
        }
    finally:
        INFLIGHT.dec()
