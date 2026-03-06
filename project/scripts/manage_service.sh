#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$ROOT_DIR/.venv"
PYTHON_BIN="$VENV_DIR/bin/python"
SERVICE_NAME="${AUTOWORKFLOW_SERVICE_NAME:-autoworkflow}"

ensure_environment() {
  if [ ! -d "$VENV_DIR" ]; then
    python -m venv "$VENV_DIR"
  fi

  if [ ! -x "$PYTHON_BIN" ]; then
    echo "Python virtual environment is incomplete: $PYTHON_BIN not found" >&2
    exit 1
  fi

  if ! "$PYTHON_BIN" -c "import uvicorn" >/dev/null 2>&1; then
    "$PYTHON_BIN" -m pip install -r "$ROOT_DIR/requirements.txt"
  fi
}

require_systemd() {
  if ! command -v systemctl >/dev/null 2>&1; then
    echo "systemctl not found. Use 'python run.py' for foreground run." >&2
    exit 1
  fi
}

usage() {
  cat <<'USAGE'
Usage: ./scripts/manage_service.sh <command>

Commands:
  run               Run python run.py in foreground (main startup)
  install-systemd   Install and enable systemd service
  status            Show systemd service status
  start             Start systemd service
  stop              Stop systemd service
  restart           Restart systemd service
  logs              Tail systemd journal logs
USAGE
}

main() {
  local command="${1:-}"
  case "$command" in
    run)
      ensure_environment
      cd "$ROOT_DIR"
      exec "$PYTHON_BIN" run.py
      ;;
    install-systemd)
      cd "$ROOT_DIR"
      exec ./scripts/install_systemd_service.sh
      ;;
    status)
      require_systemd
      exec systemctl status "$SERVICE_NAME" --no-pager
      ;;
    start)
      require_systemd
      exec sudo systemctl start "$SERVICE_NAME"
      ;;
    stop)
      require_systemd
      exec sudo systemctl stop "$SERVICE_NAME"
      ;;
    restart)
      require_systemd
      exec sudo systemctl restart "$SERVICE_NAME"
      ;;
    logs)
      require_systemd
      exec sudo journalctl -u "$SERVICE_NAME" -f -n 200
      ;;
    *)
      usage
      exit 1
      ;;
  esac
}

main "$@"
