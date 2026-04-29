# ================================================================
#  Dockerfile — Sistema de Inventarios Universitario
#  Build multistage: dependencias → runtime
# ================================================================

# ── Stage 1: builder (instala deps con pip) ──────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Solo copiamos requirements para cachear la capa de dependencias
COPY requirements.txt .

RUN pip install --upgrade pip \
 && pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: runtime (imagen final ligera) ──────────────────────
FROM python:3.12-slim AS runtime

# Metadatos
LABEL maintainer="Secretaría Administrativa"
LABEL description="Sistema de Control y Registro de Inventarios"

# Variables de entorno base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_ENV=production \
    PORT=5000

WORKDIR /app

# Copiar dependencias del stage builder
COPY --from=builder /install /usr/local

# Copiar código fuente
COPY . .

# Crear usuario no-root por seguridad
RUN addgroup --system appgroup \
 && adduser  --system --ingroup appgroup appuser \
 && chown -R appuser:appgroup /app

USER appuser

# Crear directorio para la BD SQLite si se usa en desarrollo
RUN mkdir -p /app/instance

EXPOSE ${PORT}

# Healthcheck: verifica que Flask responda
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT}/login')" || exit 1

# Entrypoint: gunicorn en producción, flask en dev
CMD ["sh", "-c", "flask --app run init-db && gunicorn --bind 0.0.0.0:${PORT} --workers 2 --timeout 60 'run:app'"]
