#!/usr/bin/env bash
# Run the Ebook Factory server as a supervised background process with logs.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd -P)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." >/dev/null 2>&1 && pwd -P)"

HOST="127.0.0.1"
PORT="8765"
DATA_DIR="$REPO_ROOT/data"
LOG_DIR="$REPO_ROOT/deploy/logs"

usage() {
  cat <<'USAGE'
Usage: start-production.sh [--host HOST] [--port PORT] [--data-dir DIR] [--log-dir DIR]

Starts the Ebook Factory FastAPI server in the background, bound to the
given host/port, storing its SQLite database and project artifacts under
--data-dir. Writes a PID file and log file under --log-dir and refuses to
start a second instance while one is already running against that log dir.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      HOST="$2"
      shift 2
      ;;
    --port)
      PORT="$2"
      shift 2
      ;;
    --data-dir)
      DATA_DIR="$2"
      shift 2
      ;;
    --log-dir)
      LOG_DIR="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

PYTHON_BIN="$REPO_ROOT/.venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3)"
fi

mkdir -p "$LOG_DIR" "$DATA_DIR"

PID_FILE="$LOG_DIR/server.pid"
LOG_FILE="$LOG_DIR/server.log"

if [[ -f "$PID_FILE" ]]; then
  existing_pid="$(cat "$PID_FILE")"
  if kill -0 "$existing_pid" 2>/dev/null; then
    echo "server already running with pid $existing_pid (log: $LOG_FILE)" >&2
    exit 1
  fi
  rm -f "$PID_FILE"
fi

nohup "$PYTHON_BIN" "$REPO_ROOT/scripts/run_server.py" \
  --host "$HOST" --port "$PORT" --data-dir "$DATA_DIR" \
  >>"$LOG_FILE" 2>&1 &
server_pid=$!
disown "$server_pid" 2>/dev/null || true
echo "$server_pid" > "$PID_FILE"

echo "started ebook-factory server pid=$server_pid host=$HOST port=$PORT data_dir=$DATA_DIR"
echo "logs: $LOG_FILE"
echo "pid file: $PID_FILE"
