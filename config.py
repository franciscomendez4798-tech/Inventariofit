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
    # Tiempo máximo de inactividad (sin ninguna petición al servidor): 3 horas
    SESSION_INACTIVITY_TIMEOUT = int(os.environ.get('SESSION_INACTIVITY_TIMEOUT', 3 * 60 * 60))
    # Tiempo de vida absoluto máximo de la cookie de sesión
    PERMANENT_SESSION_LIFETIME = timedelta(hours=4)

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL', 'sqlite:///inventario_dev.db'
    )

class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')

class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

config = {
    'development': DevelopmentConfig,
    'production':  ProductionConfig,
    'testing':     TestingConfig,
    'default':     DevelopmentConfig,
}
