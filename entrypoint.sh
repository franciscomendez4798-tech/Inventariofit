#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# entrypoint.sh — Script de arranque para producción (Render / Railway / Docker)
# ═══════════════════════════════════════════════════════════════════════════════
set -e

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║    Sistema de Inventarios — Facultad de Ingeniería   ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "  FLASK_ENV : ${FLASK_ENV:-production}"
echo "  PORT      : ${PORT:-8000}"
echo "  DATABASE  : ${DATABASE_URL:+PostgreSQL configurada}${DATABASE_URL:-SQLite (local)}"
echo ""

# ── 1. Verificar variables críticas ───────────────────────────────────────────
if [ "${FLASK_ENV}" = "production" ]; then
    if [ -z "${SECRET_KEY}" ] || [ "${SECRET_KEY}" = "dev-key-CAMBIAR-en-produccion" ]; then
        echo "❌ ERROR: SECRET_KEY no está configurada o usa el valor de desarrollo."
        echo "   Configúrala en las variables de entorno del hosting."
        exit 1
    fi
    echo "✅ SECRET_KEY: configurada"
fi

# ── 2. Inicializar / actualizar base de datos ─────────────────────────────────
echo ""
echo "▶ Inicializando base de datos..."
FLASK_APP=wsgi.py flask init-db
echo "✅ Base de datos lista"

# ── 3. Seed opcional de trabajadores ─────────────────────────────────────────
if [ "${SEED_TRABAJADORES:-0}" = "1" ]; then
    echo ""
    echo "▶ Insertando plantilla de personal (SEED_TRABAJADORES=1)..."
    FLASK_APP=wsgi.py flask seed-trabajadores
    echo "✅ Personal cargado"
fi

# ── 4. Iniciar Gunicorn ───────────────────────────────────────────────────────
echo ""
echo "▶ Iniciando servidor Gunicorn..."
echo "  Bind   : 0.0.0.0:${PORT:-8000}"
echo "  Workers: ${WEB_CONCURRENCY:-2}"
echo ""

exec gunicorn "wsgi:app" \
    --config gunicorn.conf.py \
    --bind "0.0.0.0:${PORT:-8000}"
