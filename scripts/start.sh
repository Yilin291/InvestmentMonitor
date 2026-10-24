#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
export APP_ENV="${APP_ENV:-production}"
export PRODUCT_HOST="${PRODUCT_HOST:-0.0.0.0}"
export PORT="${PORT:-9000}"
exec .venv/bin/python -m backend.serve
