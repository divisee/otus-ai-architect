#!/usr/bin/env bash
# Разворачивает весь стенд hw-6-1 в minikube:
#   FastAPI (llm-gateway) -> Prometheus -> Grafana -> Telegram (alerts)
#
# Требуется: docker (запущен), minikube, kubectl, helm.
# Запуск: ./setup.sh
set -euo pipefail

CLUSTER="llm-alerting"
RELEASE="kps"
APP_NS="app"
MON_NS="monitoring"
IMAGE="llm-gateway-sim:0.1"
HERE="$(cd "$(dirname "$0")" && pwd)"

echo "==> [1/6] (Пере)создание кластера minikube ($CLUSTER) — лёгкий профиль"
# minikube НЕ умеет менять RAM у существующего кластера, поэтому для применения
# нового лимита памяти пересоздаём кластер с нуля. Это также чинит возможный
# прерванный helm-релиз с прошлого запуска.
# Всегда удаляем профиль (если он есть) перед стартом: minikube не меняет
# RAM/CPU у существующего кластера (в т.ч. остановленного), а чистый старт
# заодно сбрасывает возможный застрявший helm-релиз. Безопасно, если кластера нет.
minikube delete -p "$CLUSTER" >/dev/null 2>&1 || true
minikube start -p "$CLUSTER" --driver=docker --cpus=2 --memory=2000

echo "==> [2/6] Сборка образа приложения внутри Docker minikube"
# Собираем образ прямо в docker-демоне minikube, чтобы не пушить в реестр.
eval "$(minikube -p "$CLUSTER" docker-env)"
docker build -t "$IMAGE" "$HERE"
eval "$(minikube -p "$CLUSTER" docker-env -u)"

echo "==> [3/6] Установка kube-prometheus-stack (Prometheus + Grafana + Alerting)"
kubectl get ns "$MON_NS" >/dev/null 2>&1 || kubectl create ns "$MON_NS"
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts >/dev/null 2>&1 || true
helm repo update >/dev/null
helm upgrade --install "$RELEASE" prometheus-community/kube-prometheus-stack \
  --namespace "$MON_NS" \
  -f "$HERE/monitoring/values.yaml" \
  --wait --timeout 10m

echo "==> [4/6] Импорт дашборда Grafana (через ConfigMap + sidecar)"
kubectl -n "$MON_NS" create configmap llm-gateway-dashboard \
  --from-file=llm-gateway.json="$HERE/monitoring/dashboard.json" \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl -n "$MON_NS" label configmap llm-gateway-dashboard grafana_dashboard=1 --overwrite

echo "==> [5/6] Деплой приложения llm-gateway"
kubectl apply -f "$HERE/k8s/namespace.yaml"
kubectl apply -f "$HERE/k8s/deployment.yaml"
kubectl apply -f "$HERE/k8s/service.yaml"
kubectl apply -f "$HERE/k8s/servicemonitor.yaml"
kubectl -n "$APP_NS" rollout status deploy/llm-gateway --timeout=120s

echo "==> [6/6] Готово. Проброс портов: ./port_forwards.sh start"
echo "    Grafana:    http://localhost:3000  (admin/admin)"
echo "    Prometheus: http://localhost:9090"
echo "    App:        http://localhost:8080"
