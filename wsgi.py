"""
wsgi.py — Punto de entrada para servidores WSGI de producción.

Uso:
    gunicorn "wsgi:app"                          # Básico
    gunicorn "wsgi:app" --workers 2 --threads 2  # Multi-worker
    gunicorn "wsgi:app" --bind 0.0.0.0:8000      # Puerto explícito
"""
import os
from app import create_app

# Usar FLASK_ENV si está definido, si no asumir producción
env = os.environ.get('FLASK_ENV', 'production')
app = create_app(env)

# Validar configuración de producción
if env == 'production':
    from config import ProductionConfig
    try:
        ProductionConfig.validate()
    except RuntimeError as e:
        import sys
        print(f"[ERROR CRÍTICO] {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    # Solo para pruebas locales directas; en producción usar gunicorn
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port)
