#!/bin/sh
set -e

echo "=== Inventario FIT ==="
echo "PORT=${PORT}"
echo "FLASK_ENV=${FLASK_ENV}"

# Migración one-shot: se ejecuta solo si RUN_MIGRATION=1
if [ "${RUN_MIGRATION}" = "1" ]; then
  python3 run_migration.py
fi

flask --app run init-db

echo "=== Arrancando Gunicorn en 0.0.0.0:${PORT:-8080} ==="
exec gunicorn \
  --bind "0.0.0.0:${PORT:-8080}" \
  --workers 2 \
  --timeout 120 \
  --log-level info \
  --access-logfile - \
  --error-logfile - \
  run:app
