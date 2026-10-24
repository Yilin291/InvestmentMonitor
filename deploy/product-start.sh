#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
export APP_ENV="${APP_ENV:-development}"
export PRODUCT_HOST="${PRODUCT_HOST:-127.0.0.1}"
exec .venv/bin/python -m backend.serve
