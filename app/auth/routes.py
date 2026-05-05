"""app/auth/routes.py — Autenticación."""
from urllib.parse import urlparse
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from ..models import Usuario
from ..extensions import limiter


def _es_url_interna(url: str) -> bool:
    """Devuelve True solo si la URL es relativa al mismo host.
    Bloquea open redirects como ?next=https://evil.com o ?next=//evil.com
    """
    if not url:
        return False
    parsed = urlparse(url)
    # URL segura: sin scheme ni netloc (relativa pura como /admin/dashboard)
    return not parsed.scheme and not parsed.netloc

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(_url_por_rol())
    return redirect(url_for('auth.login'))


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit('15/minute', methods=['POST'], error_message='Demasiados intentos. Espera un minuto.')
def login():
    if current_user.is_authenticated:
        return redirect(_url_por_rol())

    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))

        usuario = Usuario.query.filter_by(email=email, activo=True).first()
        if usuario and usuario.check_password(password):
            login_user(usuario, remember=remember)
            flash(f'Bienvenido, {usuario.nombre_completo.split()[0]}.', 'success')
            # ── Validación de open redirect ────────────────────────────────
            # Solo permite ?next= con URLs relativas internas (/ruta/...).
            # Rechaza https://evil.com, //evil.com, javascript:, etc.
            next_page = request.args.get('next')
            if _es_url_interna(next_page):
                return redirect(next_page)
            return redirect(_url_por_rol())

        flash('Correo o contraseña incorrectos.', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Sesión cerrada correctamente.', 'info')
    return redirect(url_for('auth.login'))


def _url_por_rol():
    if current_user.es_admin:
        return url_for('admin.dashboard')
    if current_user.es_mantenimiento:
        return url_for('mantenimiento.panel')
    return url_for('solicitante.panel')
