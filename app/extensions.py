"""app/extensions.py — Instancias de extensiones Flask (sin circular imports)."""
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

db            = SQLAlchemy()
login_manager = LoginManager()
migrate       = Migrate()
csrf          = CSRFProtect()
limiter       = Limiter(key_func=get_remote_address, default_limits=['300/hour'])


@login_manager.user_loader
def load_user(user_id):
    from .models import Usuario
    return Usuario.query.get(int(user_id))
