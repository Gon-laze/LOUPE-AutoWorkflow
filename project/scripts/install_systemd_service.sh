#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SERVICE_SRC="$ROOT_DIR/deploy/autoworkflow.service"
SERVICE_NAME="${AUTOWORKFLOW_SERVICE_NAME:-autoworkflow}"
SERVICE_DST="/etc/systemd/system/${SERVICE_NAME}.service"
TMP_FILE="$(mktemp)"

cleanup() {
  rm -f "$TMP_FILE"
}
trap cleanup EXIT

if [ ! -f "$SERVICE_SRC" ]; then
  echo "Service template not found: $SERVICE_SRC" >&2
  exit 1
fi

sed \
  -e "s|__WORKDIR__|$ROOT_DIR|g" \
  -e "s|__USER__|${SUDO_USER:-$USER}|g" \
  "$SERVICE_SRC" >"$TMP_FILE"

sudo cp "$TMP_FILE" "$SERVICE_DST"
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"
sudo systemctl status "$SERVICE_NAME" --no-pager
