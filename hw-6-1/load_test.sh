#!/usr/bin/env bash
# Генератор нагрузки на LLM-шлюз, чтобы наполнить метрики и вызвать алерты.
# Usage: ./load_test.sh [PORT] [REQUESTS] [MAX_TOKENS]
PORT="${1:-8080}"
N="${2:-400}"
MAX_TOKENS="${3:-256}"
URL="http://localhost:${PORT}/chat"
MODELS=("gpt-4o-mini" "gpt-4o" "llama-3-8b")
PROMPTS=("Расскажи про Kubernetes" "Объясни PromQL" "Что такое SLO" "Напиши хайку про метрики")

echo "Отправляю $N запросов на $URL ..."
for i in $(seq 1 "$N"); do
  m=${MODELS[$((RANDOM % ${#MODELS[@]}))]}
  p=${PROMPTS[$((RANDOM % ${#PROMPTS[@]}))]}
  code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$URL" \
    -H "Content-Type: application/json" \
    -d "{\"prompt\":\"$p\",\"model\":\"$m\",\"max_tokens\":$MAX_TOKENS}")
  if [ $((i % 25)) -eq 0 ]; then
    echo "  [$i/$N] last=$code model=$m"
  fi
done
echo "Готово."
