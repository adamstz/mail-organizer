#!/usr/bin/env bash
set -euo pipefail

case "${1-}" in
  backend-server)
    python -m src.cli run-server
    ;;
  backend-subscriber)
    python -m src.cli run-subscriber
    ;;
  *)
    echo "Usage: $0 {backend-server|backend-subscriber}"
    exit 2
    ;;
esac
