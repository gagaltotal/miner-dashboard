#!/usr/bin/env bash
# Menjalankan dasbor. Jalankan skrip ini dari mana saja, mis: ./run.sh
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

if [ ! -d ".venv" ]; then
  echo "Membuat virtual environment Python di .venv/ (hanya sekali)..."
  python3 -m venv .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate
  pip install --upgrade pip -q
  pip install -r requirements.txt -q
else
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

exec python3 -m app.main
