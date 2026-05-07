#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
#  run_bot.sh — Jalankan Discord Bot
# ─────────────────────────────────────────────────────────
set -e
cd "$(dirname "$0")"

echo "🤖 Starting Discord Bot..."
source venv/bin/activate 2>/dev/null || true
python -m bot.main
