"""config.py — Configuración por entorno."""
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-CAMBIAR-en-produccion')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ITEMS_POR_PAGINA = 20

    # ── Cierre de sesión por inactividad ──────────────────────────────────
    SESSION_INACTIVITY_TIMEOUT = int(os.environ.get('SESSION_INACTIVITY_TIMEOUT', 3 * 60 * 60))
    PERMANENT_SESSION_LIFETIME = timedelta(hours=4)

    # ── Seguridad ─────────────────────────────────────────────────────────
    # Tamaño máximo de request (imágenes, firmas, etc.)
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024   # 10 MB

    # CSRF
    WTF_CSRF_ENABLED    = True
    WTF_CSRF_TIME_LIMIT = 3600              # tokens válidos 1 hora

    # Clave dedicada para firmas HMAC de órdenes de servicio.
    # Separada del SECRET_KEY de sesiones para poder rotar cada una
    # de forma independiente sin invalidar la otra.
    FIRMA_SECRET_KEY = os.environ.get(
        'FIRMA_SECRET_KEY',
        os.environ.get('SECRET_KEY', 'dev-key-CAMBIAR-en-produccion')
    )

    # Rate limiting (flask-limiter). En producción usar Redis:
    # RATELIMIT_STORAGE_URI = "redis://..."
    RATELIMIT_STORAGE_URI    = os.environ.get('REDIS_URL', 'memory://')
    RATELIMIT_DEFAULT        = '300/hour'
    RATELIMIT_HEADERS_ENABLED = True

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL', 'sqlite:///inventario_dev.db'
    )

class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')

class TestingConfig(Config):
    TESTING          = True
    WTF_CSRF_ENABLED = False   # desactivado en tests para no requerir tokens
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

config = {
    'development': DevelopmentConfig,
    'production':  ProductionConfig,
    'testing':     TestingConfig,
    'default':     DevelopmentConfig,
}
