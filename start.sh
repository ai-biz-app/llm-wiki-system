#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

# Create virtual environment if missing
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate

echo "Installing dependencies..."
pip install -q -r requirements.txt

echo "Starting LLM Wiki server on http://0.0.0.0:8080"
python -m backend.main
