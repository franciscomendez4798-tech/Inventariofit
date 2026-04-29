"""app/extensions.py — Instancias de extensiones Flask (sin circular imports)."""
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate

db           = SQLAlchemy()
login_manager = LoginManager()
migrate      = Migrate()


@login_manager.user_loader
def load_user(user_id):
    from .models import Usuario
    return Usuario.query.get(int(user_id))
