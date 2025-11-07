#!/bin/bash
# Production startup script for PDF Extraction API
# Uses Gunicorn with Uvicorn workers for production-grade performance

set -e

# Default values (can be overridden by environment variables)
WORKERS=${WORKERS:-4}
LOG_LEVEL=${LOG_LEVEL:-info}
TIMEOUT=${REQUEST_TIMEOUT:-300}
GRACEFUL_TIMEOUT=30
KEEP_ALIVE=5

echo "Starting PDF Extraction API in PRODUCTION mode"
echo "Workers: $WORKERS"
echo "Log Level: $LOG_LEVEL"
echo "Timeout: $TIMEOUT seconds"

# Start Gunicorn with Uvicorn workers
exec gunicorn src.main:app \
  --workers "$WORKERS" \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout "$TIMEOUT" \
  --graceful-timeout "$GRACEFUL_TIMEOUT" \
  --keep-alive "$KEEP_ALIVE" \
  --access-logfile - \
  --error-logfile - \
  --log-level "$LOG_LEVEL" \
  --worker-tmp-dir /dev/shm
