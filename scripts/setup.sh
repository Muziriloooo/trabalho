#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv
export PIP_CACHE_DIR="${PIP_CACHE_DIR:-/tmp/sentinela-pip-cache}"
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python -m pip check
.venv/bin/python -m flask --app app db upgrade
.venv/bin/python -m flask --app app db check
.venv/bin/python -m pytest -q
