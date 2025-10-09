#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALLER="${SCRIPT_DIR}/../install.sh"
if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  exec sudo bash "$INSTALLER" "$@"
else
  exec bash "$INSTALLER" "$@"
fi
