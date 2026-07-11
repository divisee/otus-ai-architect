#!/usr/bin/env bash
# Полная очистка стенда hw-6-1.
set -euo pipefail
CLUSTER="llm-alerting"

[ -f ".port_forwards.pid" ] && ./port_forwards.sh stop || true

echo "==> Удаляю кластер minikube ($CLUSTER)"
minikube delete -p "$CLUSTER"
echo "Готово."
