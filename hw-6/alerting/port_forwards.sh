#!/usr/bin/env bash

PID_FILE=".port_forwards.pid"
LOG_DIR="logs"

start() {
  if [ -f "$PID_FILE" ]; then
    echo "Port forwards are already running (PIDs in $PID_FILE)."
    exit 1
  fi

  mkdir -p "$LOG_DIR"
  echo "Starting port-forwards..."

  # 1. Grafana (Port 3000)
  nohup kubectl -n monitoring port-forward svc/kps-grafana 3000:80 > "$LOG_DIR/grafana_pf.log" 2>&1 &
  GRAFANA_PID=$!
  echo "Grafana port-forward started on port 3000 (PID: $GRAFANA_PID)"

  # 2. Prometheus (Port 9090)
  nohup kubectl -n monitoring port-forward svc/kps-kube-prometheus-stack-prometheus 9090:9090 > "$LOG_DIR/prometheus_pf.log" 2>&1 &
  PROMETHEUS_PID=$!
  echo "Prometheus port-forward started on port 9090 (PID: $PROMETHEUS_PID)"

  # 3. Application (Port 8080)
  nohup kubectl port-forward svc/ml-infer 8080:8000 > "$LOG_DIR/app_pf.log" 2>&1 &
  APP_PID=$!
  echo "Application port-forward started on port 8080 (PID: $APP_PID)"

  echo "$GRAFANA_PID $PROMETHEUS_PID $APP_PID" > "$PID_FILE"
  echo "All port-forwards started successfully."
}

stop() {
  if [ ! -f "$PID_FILE" ]; then
    echo "No running port forwards found."
    exit 0
  fi

  PIDS=$(cat "$PID_FILE")
  echo "Stopping port forwards (PIDs: $PIDS)..."
  kill $PIDS 2>/dev/null
  rm -f "$PID_FILE"
  echo "Port forwards stopped."
}

status() {
  if [ -f "$PID_FILE" ]; then
    echo "Port forwards are running. PIDs: $(cat $PID_FILE)"
    echo "Grafana: http://localhost:3000"
    echo "Prometheus: http://localhost:9090"
    echo "App: http://localhost:8080"
  else
    echo "Port forwards are NOT running."
  fi
}

case "$1" in
  start)
    start
    ;;
  stop)
    stop
    ;;
  status)
    status
    ;;
  *)
    echo "Usage: $0 {start|stop|status}"
    exit 1
    ;;
esac
