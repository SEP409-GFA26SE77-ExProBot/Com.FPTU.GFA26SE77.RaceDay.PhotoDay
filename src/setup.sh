#!/usr/bin/env bash
# Bootstrap OCR service (Linux/macOS)
set -euo pipefail
cd "$(dirname "$0")"

echo "== RaceDay OCR setup =="
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi
echo "OK. Run: source .venv/bin/activate && uvicorn app.main:app --host 127.0.0.1 --port 8089"
