#!/bin/sh
set -e

echo "=== Inventario FIT ==="
echo "PORT=${PORT}"
echo "FLASK_ENV=${FLASK_ENV}"
echo "PYTHON=$(python --version 2>&1)"

flask --app run init-db

echo "=== Arrancando Gunicorn en 0.0.0.0:${PORT:-8080} ==="
exec gunicorn \
  --bind "0.0.0.0:${PORT:-8080}" \
  --workers 1 \
  --timeout 120 \
  --log-level debug \
  --access-logfile - \
  --error-logfile - \
  run:app
