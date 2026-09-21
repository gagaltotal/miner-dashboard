#!/usr/bin/env bash

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

if [ ! -d ".venv" ]; then
    echo "Membuat virtual environment Python di .venv/ (hanya sekali)..."
    python3 -m venv .venv
    
    # shellcheck disable=SC1091
    source .venv/bin/activate

    pip install --upgrade pip
    pip install -r requirements.txt
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

export MINER_DASH_HOST="${MINER_DASH_HOST:-0.0.0.0}"
export MINER_DASH_PORT="${MINER_DASH_PORT:-8420}"

exec python3 -m app.main