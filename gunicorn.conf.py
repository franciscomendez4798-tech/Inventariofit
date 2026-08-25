# gunicorn.conf.py — Configuración de Gunicorn para producción
# Se carga automáticamente con: gunicorn "wsgi:app"

import os
import multiprocessing

# ── Workers ───────────────────────────────────────────────────────────────────
# Fórmula recomendada: (2 × CPU) + 1
# En hosting gratuito (1 CPU) → 3 workers máximo, pero 2 es más seguro en RAM limitada
workers = int(os.environ.get('WEB_CONCURRENCY', 2))
threads = int(os.environ.get('GUNICORN_THREADS', 2))
worker_class = 'sync'

# ── Red ───────────────────────────────────────────────────────────────────────
bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"
timeout = 120          # 120s por request (subida de archivos, PDFs)
keepalive = 5

# ── Logs ──────────────────────────────────────────────────────────────────────
accesslog  = '-'       # stdout (visible en paneles de Render/Railway)
errorlog   = '-'       # stderr
loglevel   = os.environ.get('LOG_LEVEL', 'info')
access_log_format = '%(h)s "%(r)s" %(s)s %(b)s %(T)ss'

# ── Seguridad ─────────────────────────────────────────────────────────────────
limit_request_line   = 8190
limit_request_fields = 100
forwarded_allow_ips  = '*'   # Necesario cuando hay un proxy/load-balancer delante

# ── Hooks de ciclo de vida ────────────────────────────────────────────────────
def on_starting(server):
    """Se ejecuta cuando gunicorn arranca (antes de los workers)."""
    server.log.info("Iniciando servidor WSGI — Sistema de Inventarios FING")

def post_fork(server, worker):
    """Se ejecuta en cada worker hijo."""
    pass

def worker_exit(server, worker):
    """Limpieza cuando un worker termina."""
    pass
