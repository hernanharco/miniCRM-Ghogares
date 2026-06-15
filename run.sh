#!/usr/bin/env bash
set -euo pipefail

# Arranca el CRM Bayiva en modo desarrollo
# Crea el venv si no existe

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d ".venv" ]; then
    echo "🔧 Creando virtualenv..."
    python3 -m venv .venv
fi

echo "📦 Instalando dependencias..."
.venv/bin/pip install --quiet -r requirements.txt

UVICORN_PORT="${PORT:-8002}"
echo "🚀 Arrancando CRM Bayiva en http://localhost:$UVICORN_PORT"
exec .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port "$UVICORN_PORT" --reload
