#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -r requirements.txt
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example (demo mode works without keys)."
fi
echo "SignalField: http://127.0.0.1:${SIGNALFIELD_PORT:-8790}"
exec .venv/bin/python -m app
