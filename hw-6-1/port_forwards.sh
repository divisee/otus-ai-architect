#!/usr/bin/env bash
# Проброс портов сервисов кластера на localhost.
PID_FILE=".port_forwards.pid"
LOG_DIR="logs"

start() {
  if [ -f "$PID_FILE" ]; then
    echo "Проброс портов уже запущен (PID в $PID_FILE)."
    exit 1
  fi
  mkdir -p "$LOG_DIR"
  echo "Запуск проброса портов..."

  # Grafana (3000)
  nohup kubectl -n monitoring port-forward svc/kps-grafana 3000:80 > "$LOG_DIR/grafana_pf.log" 2>&1 &
  G=$!
  echo "Grafana -> http://localhost:3000 (PID $G)"

  # Prometheus (9090)
  nohup kubectl -n monitoring port-forward svc/kps-prometheus 9090:9090 > "$LOG_DIR/prometheus_pf.log" 2>&1 &
  P=$!
  echo "Prometheus -> http://localhost:9090 (PID $P)"

  # App (8080 -> 8000)
  nohup kubectl -n app port-forward svc/llm-gateway 8080:8000 > "$LOG_DIR/app_pf.log" 2>&1 &
  A=$!
  echo "App -> http://localhost:8080 (PID $A)"

  echo "$G $P $A" > "$PID_FILE"
  echo "Готово."
}

stop() {
  if [ ! -f "$PID_FILE" ]; then
    echo "Проброс портов не запущен."
    exit 0
  fi
  PIDS=$(cat "$PID_FILE")
  echo "Останавливаю проброс портов (PID: $PIDS)..."
  kill $PIDS 2>/dev/null || true
  rm -f "$PID_FILE"
  echo "Остановлено."
}

status() {
  if [ -f "$PID_FILE" ]; then
    echo "Запущен. PID: $(cat $PID_FILE)"
    echo "Grafana: http://localhost:3000 | Prometheus: http://localhost:9090 | App: http://localhost:8080"
  else
    echo "Не запущен."
  fi
}

case "${1:-}" in
  start) start ;;
  stop) stop ;;
  status) status ;;
  *) echo "Usage: $0 {start|stop|status}"; exit 1 ;;
esac
