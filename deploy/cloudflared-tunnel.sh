#!/usr/bin/env bash
# Expose a local Ebook Factory instance over HTTPS via a Cloudflare Quick Tunnel.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd -P)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." >/dev/null 2>&1 && pwd -P)"

PORT="8765"
LOG_DIR="$REPO_ROOT/deploy/logs"
WAIT_SECONDS="30"

usage() {
  cat <<'USAGE'
Usage: cloudflared-tunnel.sh [--port PORT] [--log-dir DIR] [--wait-seconds N]

Starts a Cloudflare Quick Tunnel pointing at http://127.0.0.1:PORT using an
installed `cloudflared` found on PATH, in ~/.local/bin or in ~/bin. This
script never fetches a binary itself: if cloudflared is not already
installed and verified by you, it exits with an error instead of running
unverified, unattended code. Requires no account and no API token. Prints
the public https://*.trycloudflare.com URL once cloudflared reports it, and
writes a PID file and log file under --log-dir.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)
      PORT="$2"
      shift 2
      ;;
    --log-dir)
      LOG_DIR="$2"
      shift 2
      ;;
    --wait-seconds)
      WAIT_SECONDS="$2"
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

find_cloudflared() {
  if command -v cloudflared >/dev/null 2>&1; then
    command -v cloudflared
    return 0
  fi
  if [[ -x "$HOME/.local/bin/cloudflared" ]]; then
    echo "$HOME/.local/bin/cloudflared"
    return 0
  fi
  if [[ -x "$HOME/bin/cloudflared" ]]; then
    echo "$HOME/bin/cloudflared"
    return 0
  fi
  return 1
}

mkdir -p "$LOG_DIR"
PID_FILE="$LOG_DIR/cloudflared.pid"
LOG_FILE="$LOG_DIR/cloudflared.log"

if [[ -f "$PID_FILE" ]]; then
  existing_pid="$(cat "$PID_FILE")"
  if kill -0 "$existing_pid" 2>/dev/null; then
    echo "tunnel already running with pid $existing_pid (log: $LOG_FILE)" >&2
    exit 1
  fi
  rm -f "$PID_FILE"
fi

CLOUDFLARED_BIN="$(find_cloudflared || true)"
if [[ -z "$CLOUDFLARED_BIN" ]]; then
  echo "cloudflared not found on PATH, in \$HOME/.local/bin, or in \$HOME/bin. This script refuses to fetch and run an unverified binary automatically; install a verified cloudflared build yourself (see the official Cloudflare releases) and re-run." >&2
  exit 1
fi

: > "$LOG_FILE"
nohup "$CLOUDFLARED_BIN" tunnel --url "http://127.0.0.1:$PORT" >>"$LOG_FILE" 2>&1 &
tunnel_pid=$!
disown "$tunnel_pid" 2>/dev/null || true
echo "$tunnel_pid" > "$PID_FILE"

deadline=$((SECONDS + WAIT_SECONDS))
public_url=""
while (( SECONDS < deadline )); do
  if [[ -s "$LOG_FILE" ]]; then
    public_url="$(grep -Eo 'https://[a-zA-Z0-9.-]+\.trycloudflare\.com' "$LOG_FILE" | head -n1 || true)"
    if [[ -n "$public_url" ]]; then
      break
    fi
  fi
  sleep 1
done

if [[ -z "$public_url" ]]; then
  echo "timed out waiting for tunnel URL, see $LOG_FILE" >&2
  exit 1
fi

echo "tunnel pid: $tunnel_pid"
echo "public url: $public_url"
echo "logs: $LOG_FILE"
