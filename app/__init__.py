"""app/__init__.py — Application Factory."""
from flask import Flask, session, redirect, url_for, flash, request
from flask_login import current_user, logout_user
from datetime import datetime, timezone
from config import config
from .extensions import db, login_manager, migrate


def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Las sesiones deben ser permanentes para respetar PERMANENT_SESSION_LIFETIME
    app.config['SESSION_PERMANENT'] = True

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Por favor inicia sesión para continuar.'
    login_manager.login_message_category = 'warning'

    # ── Hook: cierre de sesión por inactividad ────────────────────────────
    @app.before_request
    def verificar_inactividad():
        """Cierra la sesión si el usuario lleva más de SESSION_INACTIVITY_TIMEOUT
        segundos sin realizar ninguna petición al servidor.
        Se ignoran: archivos estáticos, la propia ruta de logout y usuarios
        no autenticados."""
        # Ignorar archivos estáticos y rutas sin autenticación
        if request.endpoint in (None, 'static', 'auth.logout', 'auth.login'):
            return
        if not current_user.is_authenticated:
            return

        timeout = app.config.get('SESSION_INACTIVITY_TIMEOUT', 10800)
        ahora = datetime.now(timezone.utc)
        ultima = session.get('_last_activity')

        if ultima:
            try:
                ultima_dt = datetime.fromisoformat(ultima)
                # Asegurar que sea tz-aware para comparar con ahora
                if ultima_dt.tzinfo is None:
                    ultima_dt = ultima_dt.replace(tzinfo=timezone.utc)
                inactivo_seg = (ahora - ultima_dt).total_seconds()
                if inactivo_seg > timeout:
                    logout_user()
                    session.clear()
                    flash(
                        'Tu sesión fue cerrada automáticamente por inactividad. '
                        'Por favor inicia sesión nuevamente.',
                        'warning'
                    )
                    return redirect(url_for('auth.login'))
            except (ValueError, TypeError):
                pass  # timestamp corrupto → se sobreescribe abajo

        # Actualizar timestamp en cada petición válida
        session['_last_activity'] = ahora.isoformat()
        session.modified = True

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

    # ── Filtro Jinja2: imagen_url puede ser URL absoluta (Supabase) o ruta local
    from flask import url_for as _url_for

    @app.template_filter('img_url')
    def img_url_filter(imagen_url):
        """Devuelve la URL correcta para una imagen: absoluta si es de Supabase,
        o generada por url_for('static') si es una ruta local heredada."""
        if not imagen_url:
            return ''
        if imagen_url.startswith('http://') or imagen_url.startswith('https://'):
            return imagen_url
        return _url_for('static', filename=imagen_url)

    return app
