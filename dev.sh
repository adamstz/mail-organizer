#!/usr/bin/env bash
set -euo pipefail

case "${1-}" in
  backend-server)
    python -m organize_mail.cli run-server
    ;;
  backend-subscriber)
    python -m organize_mail.cli run-subscriber
    ;;
  *)
    echo "Usage: $0 {backend-server|backend-subscriber}"
    exit 2
    ;;
esac
