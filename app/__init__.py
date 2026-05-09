"""app/__init__.py — Application Factory."""
from flask import Flask, session, redirect, url_for, flash, request
from flask_login import current_user, logout_user
from datetime import datetime, timezone
from config import config
from .extensions import db, login_manager, migrate, csrf, limiter


def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Las sesiones deben ser permanentes para respetar PERMANENT_SESSION_LIFETIME
    app.config['SESSION_PERMANENT'] = True

    # Falla explícitamente en producción si las claves secretas son las de desarrollo
    if not app.debug and not app.testing:
        cfg_obj = config[config_name]
        if hasattr(cfg_obj, 'validate'):
            cfg_obj.validate()

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    limiter.init_app(app)

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
    from .firma import firma_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp,   url_prefix='/admin')
    app.register_blueprint(sol_bp,     url_prefix='/portal')
    app.register_blueprint(api_bp,     url_prefix='/api')
    app.register_blueprint(mantenimiento_bp, url_prefix='/mantenimiento')
    # Ruta pública sin sesión — CSRF global excluido explícitamente.
    # La protección anti-CSRF se implementa con token en body (compare_digest).
    csrf.exempt(firma_bp)
    app.register_blueprint(firma_bp, url_prefix='/firma')

    # ── Cabeceras de seguridad HTTP ───────────────────────────────────────
    @app.after_request
    def aplicar_cabeceras_seguridad(response):
        # Evita que la app se incruste en iframes (clickjacking)
        response.headers['X-Frame-Options'] = 'DENY'
        # Previene que el navegador cambie el Content-Type (MIME sniffing)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        # Limita referrer a mismo origen para no filtrar URLs internas
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        # Fuerza HTTPS en producción (1 año)
        if not app.debug:
            response.headers['Strict-Transport-Security'] = (
                'max-age=31536000; includeSubDomains'
            )
        # CSP: solo recursos del mismo origen + CDNs explícitos usados en el proyecto
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com "
            "https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com "
            "https://cdn.jsdelivr.net https://fonts.googleapis.com; "
            "font-src 'self' https://cdnjs.cloudflare.com https://fonts.gstatic.com; "
            "img-src 'self' data: https://*.supabase.co; "
            "connect-src 'self';"
        )
        return response

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
