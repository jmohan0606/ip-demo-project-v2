#!/usr/bin/env bash
set -e
# Host/port are env-driven so the SAME script works in Codespaces (0.0.0.0, reachable through
# port forwarding) and on a client machine (set API_HOST=127.0.0.1 for loopback-only if desired).
# Default 0.0.0.0 — a 127.0.0.1-only bind is NOT reachable by the Codespaces forwarder / external
# browser. See TROUBLESHOOTING.md "Backend unreachable from the browser".
HOST="${API_HOST:-0.0.0.0}"
PORT="${API_PORT:-8000}"
uv run uvicorn app.api.main:app --reload --host "$HOST" --port "$PORT"
