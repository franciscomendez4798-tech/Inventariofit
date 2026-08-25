"""config.py — Configuración por entorno."""
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


def _parse_database_url(url: str) -> str:
    """
    Render y Railway entregan 'postgres://...' pero SQLAlchemy 1.4+
    requiere 'postgresql://...'. Esta función normaliza la URL.
    """
    if url and url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    return url


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-CAMBIAR-en-produccion')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ITEMS_POR_PAGINA = 20

    # ── Cierre de sesión por inactividad ──────────────────────────────────
    SESSION_INACTIVITY_TIMEOUT = int(os.environ.get('SESSION_INACTIVITY_TIMEOUT', 3 * 60 * 60))
    PERMANENT_SESSION_LIFETIME = timedelta(hours=4)

    # ── Seguridad ─────────────────────────────────────────────────────────
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024   # 10 MB
    WTF_CSRF_ENABLED    = True
    WTF_CSRF_TIME_LIMIT = 3600

    # Clave dedicada para firmas HMAC de órdenes de servicio.
    FIRMA_SECRET_KEY = os.environ.get(
        'FIRMA_SECRET_KEY',
        os.environ.get('SECRET_KEY', 'dev-key-CAMBIAR-en-produccion')
    )

    # Rate limiting — en producción usar Redis si está disponible
    RATELIMIT_STORAGE_URI     = os.environ.get('REDIS_URL', 'memory://')
    RATELIMIT_DEFAULT         = '300/hour'
    RATELIMIT_HEADERS_ENABLED = True


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = _parse_database_url(
        os.environ.get('DATABASE_URL', 'sqlite:///inventario_dev.db')
    )
    # En desarrollo mostrar queries lentas (> 0.5s)
    SQLALCHEMY_RECORD_QUERIES = True


class ProductionConfig(Config):
    DEBUG = False

    # ── Base de datos ──────────────────────────────────────────────────────
    _raw_db_url = os.environ.get('DATABASE_URL')
    if _raw_db_url:
        SQLALCHEMY_DATABASE_URI = _parse_database_url(_raw_db_url)
    else:
        # Ruta absoluta del directorio del proyecto (donde está config.py)
        _base_dir = os.path.abspath(os.path.dirname(__file__))
        # Usar /data si existe (Render Disk), si no usar instance/ del proyecto
        if os.path.isdir('/data'):
            _db_path = '/data/inventario_prod.db'
        else:
            _instance_dir = os.path.join(_base_dir, 'instance')
            os.makedirs(_instance_dir, exist_ok=True)   # Crea la carpeta si no existe
            _db_path = os.path.join(_instance_dir, 'inventario_prod.db')
        SQLALCHEMY_DATABASE_URI = f'sqlite:///{_db_path}'

    # ── Pool de conexiones (PostgreSQL) ───────────────────────────────────
    # Solo aplica si se usa PostgreSQL; SQLite las ignora.
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,      # Reconecta si la conexión fue cerrada
        'pool_recycle': 300,        # Recicla conexiones cada 5 min
        'pool_size': 5,
        'max_overflow': 10,
    } if _raw_db_url else {}

    # ── Cookies seguras ───────────────────────────────────────────────────
    SESSION_COOKIE_SECURE   = True   # Solo HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    @classmethod
    def validate(cls):
        _DEV_KEY = 'dev-key-CAMBIAR-en-produccion'
        if cls.SECRET_KEY == _DEV_KEY:
            raise RuntimeError(
                "SECRET_KEY debe estar definida en variables de entorno en producción. "
                "No se puede arrancar con la clave de desarrollo."
            )
        # En PythonAnywhere y servidores con disco persistente, SQLite es válido.
        # Solo advertir si se está en Render (sin disco /data).
        if not os.environ.get('DATABASE_URL') and not os.path.isdir('/data'):
            import platform
            # Detectar si estamos en PythonAnywhere (tienen pythonanywhere en el hostname)
            hostname = platform.node()
            if 'pythonanywhere' not in hostname.lower():
                import warnings
                warnings.warn(
                    "No se encontró DATABASE_URL ni /data. "
                    "Se usará SQLite en instance/inventario_prod.db. "
                    "En Render Free los datos se pierden en cada redeploy.",
                    stacklevel=2
                )


class TestingConfig(Config):
    TESTING          = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


config = {
    'development': DevelopmentConfig,
    'production':  ProductionConfig,
    'testing':     TestingConfig,
    'default':     DevelopmentConfig,
}
