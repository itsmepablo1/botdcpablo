#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
#  run_panel.sh — Jalankan Web Panel
# ─────────────────────────────────────────────────────────
set -e
cd "$(dirname "$0")"

echo "🌐 Starting Web Panel..."
source venv/bin/activate 2>/dev/null || true

HOST=${PANEL_HOST:-0.0.0.0}
PORT=${PANEL_PORT:-8080}

uvicorn panel.main:app --host "$HOST" --port "$PORT" --reload
