"""app/auth/routes.py — Autenticación."""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from ..models import Usuario

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(_url_por_rol())
    return redirect(url_for('auth.login'))


@auth_bp.route('/login', methods=['GET', 'POST'])
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
            next_page = request.args.get('next')
            return redirect(next_page or _url_por_rol())

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
