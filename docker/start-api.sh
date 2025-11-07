#!/bin/sh
set -e

if [ "${ENABLE_DEBUGPY}" = "1" ]; then
    echo "Launching API with debugpy (port 5678)..."
    exec python -m debugpy --listen 0.0.0.0:5678 -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
fi

exec uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
