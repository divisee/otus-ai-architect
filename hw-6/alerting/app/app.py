"""Inference service for python app"""

import os
import random
import time

import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from prometheus_client import Counter, Histogram
from prometheus_fastapi_instrumentator import Instrumentator


class Features(BaseModel):
    features: list[float]


def predict_raw(x: np.ndarray) -> int:
    logits = x @ coef_.T + intercept_
    return int(np.argmax(logits, axis=1)[0])


MODEL_PATH = os.getenv("MODEL_PATH", "/app/model.npz")
data = np.load(MODEL_PATH)
coef_ = data["coef_"]
intercept_ = data["intercept_"]


ERROR_RATE = float(os.getenv("ERROR_RATE", "0.1")) # 10% 500-ок
MAX_DELAY = float(os.getenv("MAX_DELAY", "1.0")) # максимальная задержка 1 сек


REQUESTS = Counter("prediction_requests_total", "Total prediction requests")
ERRORS = Counter("prediction_errors_total", "Total 5xx injected errors")
SCORES = Histogram(
    "prediction_latency_seconds",
    "Latency of /predict handler",
    buckets=(0.01, 0.1, 0.5, 1, 1.5, 2, 3, 4, 5)
)


app = FastAPI(title="ML Iris Inference (FastAPI)")


Instrumentator().instrument(app).expose(app, include_in_schema=False)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/predict")
@SCORES.time()
def predict(payload: Features):
    REQUESTS.inc()

    if random.random() < ERROR_RATE:
        ERRORS.inc()
        raise HTTPException(status_code=500, detail="Injected failure for demo")

    delay = random.random() * MAX_DELAY
    time.sleep(delay)

    x = np.array(payload.features, dtype=float).reshape(1, -1)
    cls = predict_raw(x)
    return {"class": cls, "delay": round(delay, 3)}
