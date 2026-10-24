#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
python3 -m venv .venv
.venv/bin/python -m pip install --disable-pip-version-check -r backend/requirements.txt
npm --prefix frontend ci --ignore-scripts --no-audit --no-fund
npm --prefix frontend run build
.venv/bin/python -m compileall -q backend
