#!/usr/bin/env bash
# Скрипт для нагрузки FastAPI сервиса предсказаний
# Использование:
#   ./load_test.sh <port> [requests]
#
# <port>     — порт, на котором работает сервис (обязателен)
# [requests] — количество запросов (по умолчанию 100)

if [ -z "$1" ]; then
  echo "Использование: $0 <port> [requests]"
  exit 1
fi

PORT=$1
REQS=${2:-100}

URL="http://localhost:${PORT}/predict"
DATA='{"features":[5.0,3.6,1.4,0.2]}'

echo "Отправляем $REQS запросов на $URL"

for i in $(seq 1 $REQS); do
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "$URL" \
    -H "Content-Type: application/json" \
    -d "$DATA")

  echo "[$i] status=$HTTP_CODE"
done
