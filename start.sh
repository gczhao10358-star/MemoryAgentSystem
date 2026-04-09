#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
FRONTEND_DIR="$ROOT_DIR/frontend"
FRONTEND_DIST_INDEX="$FRONTEND_DIR/dist/index.html"

usage() {
  cat <<'EOF'
Usage:
  ./start.sh           Start the web app on http://localhost:8000/app
  ./start.sh --port N Start on a custom port
  ./start.sh --rebuild Rebuild the frontend before starting
  ./start.sh --help    Show this help message
EOF
}

ensure_backend_python() {
  if [[ ! -x "$PYTHON_BIN" ]]; then
    echo "[error] Missing virtualenv python: $PYTHON_BIN"
    echo "Create it first, for example:"
    echo "  python3 -m venv .venv"
    echo "  .venv/bin/pip install -r requirements.txt"
    exit 1
  fi
}

ensure_directories() {
  mkdir -p "$ROOT_DIR/data" "$ROOT_DIR/logs"
}

load_env_file() {
  if [[ -f "$ROOT_DIR/.env" ]]; then
    echo "[info] Loading environment variables from .env"
    set -a
    # shellcheck disable=SC1091
    source "$ROOT_DIR/.env"
    set +a
  fi
}

ensure_port_available() {
  local port="$1"

  if command -v lsof >/dev/null 2>&1 && lsof -tiTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "[error] Port $port is already in use."
    echo "Use another port, for example:"
    echo "  bash start.sh --port 8001"
    exit 1
  fi
}

ensure_frontend_dependencies() {
  if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
    echo "[info] Installing frontend dependencies..."
    (cd "$FRONTEND_DIR" && npm install)
  fi
}

build_frontend() {
  ensure_frontend_dependencies
  echo "[info] Building frontend..."
  (cd "$FRONTEND_DIR" && npm run build)
}

main() {
  local rebuild_frontend="false"
  local port="8000"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --rebuild)
        rebuild_frontend="true"
        shift
        ;;
      --port)
        if [[ $# -lt 2 ]]; then
          echo "[error] --port requires a value"
          exit 1
        fi
        port="$2"
        shift 2
        ;;
      --help|-h)
        usage
        exit 0
        ;;
      *)
        echo "[error] Unknown option: $1"
        usage
        exit 1
        ;;
    esac
  done

  cd "$ROOT_DIR"
  ensure_backend_python
  ensure_directories
  load_env_file
  ensure_port_available "$port"

  if [[ "$rebuild_frontend" == "true" || ! -f "$FRONTEND_DIST_INDEX" ]]; then
    build_frontend
  fi

  echo "[info] Starting MemoryAssistant..."
  echo "[info] API docs: http://localhost:$port/docs"
  echo "[info] Web app:  http://localhost:$port/app"
  exec "$PYTHON_BIN" -m uvicorn api:app --host 0.0.0.0 --port "$port"
}

main "$@"
