"""app/__init__.py — Application Factory."""
from flask import Flask
from config import config
from .extensions import db, login_manager, migrate


def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Por favor inicia sesión para continuar.'
    login_manager.login_message_category = 'warning'

    from .auth.routes      import auth_bp
    from .admin.routes     import admin_bp
    from .solicitante.routes import sol_bp
    from .api.routes       import api_bp
    from .mantenimiento.routes import mantenimiento_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp,   url_prefix='/admin')
    app.register_blueprint(sol_bp,     url_prefix='/portal')
    app.register_blueprint(api_bp,     url_prefix='/api')
    app.register_blueprint(mantenimiento_bp, url_prefix='/mantenimiento')

    return app
