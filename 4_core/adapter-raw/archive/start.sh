#!/bin/sh
# Railway injects PORT env var; fall back to 8000 for local dev
PORT="${PORT:-8000}"
echo "Starting OmniMemora Adapter on port $PORT"
exec uvicorn app.main:app --host "0.0.0.0" --port "$PORT"
