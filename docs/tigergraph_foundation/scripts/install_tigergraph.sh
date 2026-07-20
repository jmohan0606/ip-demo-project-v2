#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GSQL_CMD="${GSQL_CMD:-gsql}"

echo "[1/3] Installing schema"
(cd "$ROOT/tigergraph/schema" && "$GSQL_CMD" 00_install_schema.gsql)

echo "[2/3] Creating fallback GSQL loading jobs"
(cd "$ROOT/tigergraph/loading" && "$GSQL_CMD" install_all_loading_jobs.gsql)

echo "[3/3] Creating and installing 43 queries"
(cd "$ROOT/tigergraph/queries" && "$GSQL_CMD" install_all_queries.gsql)

echo "TigerGraph install commands completed. Run scripts/live_tigergraph_validation.py next."
