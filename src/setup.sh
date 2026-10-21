#!/usr/bin/env bash
# Bootstrap OCR service (Linux/macOS) — English messages only
set -euo pipefail
cd "$(dirname "$0")"

echo "== RaceDay OCR setup =="

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found. Install Python 3.10-3.12." >&2
  exit 1
fi

VER="$(python3 -c 'import sys; print("%d.%d" % (sys.version_info.major, sys.version_info.minor))')"
echo "Python: $VER"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip
echo "Installing requirements (first run may take 5-15 minutes)..."
pip install -r requirements.txt

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example"
else
  echo ".env already exists - keeping it"
fi

echo "OK. Next:"
echo "  source .venv/bin/activate"
echo "  uvicorn app.main:app --host 127.0.0.1 --port 8089"
echo "Or open demo after start: http://127.0.0.1:8089/demo"
