#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
.venv/bin/python -m flask --app app db upgrade
exec .venv/bin/waitress-serve --listen=127.0.0.1:5000 app:app
