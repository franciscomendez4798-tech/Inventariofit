"""
tests/test_auth.py
==================
Suite de pruebas para el módulo de autenticación y control de roles.
Cubre: login exitoso/fallido, logout, redirección por rol, protección de rutas.
"""
import pytest


class TestLogin:
    """Tests del formulario de inicio de sesión."""

    def test_get_login_renderiza(self, client):
        """La página de login debe responder 200."""
        r = client.get('/login')
        assert r.status_code == 200
        assert b'Iniciar sesi' in r.data   # "Iniciar sesión"

    def test_login_admin_exitoso_redirige_dashboard(self, client):
        """Admin con credenciales correctas → redirige a /admin/."""
        r = client.post('/login', data={
            'email':    'admin@test.edu.mx',
            'password': 'Admin123!',
        }, follow_redirects=False)
        assert r.status_code == 302
        assert '/admin' in r.headers['Location']

    def test_login_solicitante_redirige_catalogo(self, client):
        """Solicitante → redirige a /portal/catalogo."""
        r = client.post('/login', data={
            'email':    'sol@test.edu.mx',
            'password': 'Sol123!',
        }, follow_redirects=False)
        assert r.status_code == 302
        assert '/portal' in r.headers['Location']

    def test_login_password_incorrecto(self, client):
        """Contraseña incorrecta → se queda en login con mensaje de error."""
        r = client.post('/login', data={
            'email':    'admin@test.edu.mx',
            'password': 'wrongpassword',
        }, follow_redirects=True)
        assert r.status_code == 200
        assert b'incorrectos' in r.data

    def test_login_email_inexistente(self, client):
        """Email que no existe → mensaje de error."""
        r = client.post('/login', data={
            'email':    'noexiste@test.edu.mx',
            'password': 'cualquier',
        }, follow_redirects=True)
        assert r.status_code == 200
        assert b'incorrectos' in r.data

    def test_login_email_vacio(self, client):
        """Email vacío → HTML validation, no crash del servidor."""
        r = client.post('/login', data={
            'email':    '',
            'password': 'Admin123!',
        })
        # Flask no hace crash — devuelve 200 o 302
        assert r.status_code in (200, 302, 400)

    def test_logout(self, login_admin):
        """Logout cierra sesión y redirige a login."""
        r = login_admin.get('/logout', follow_redirects=False)
        assert r.status_code == 302
        assert '/login' in r.headers['Location']

    def test_logout_sin_sesion_redirige_login(self, client):
        """Intentar logout sin estar logueado redirige a login."""
        r = client.get('/logout', follow_redirects=False)
        assert r.status_code == 302
        assert 'login' in r.headers['Location']


class TestProteccionRutas:
    """Verifica que las rutas protegidas rechacen accesos no autenticados."""

    RUTAS_ADMIN = [
        '/admin/',
        '/admin/dashboard',
        '/admin/inventario',
        '/admin/pedidos',
        '/admin/proveedores',
    ]
    RUTAS_PORTAL = [
        '/portal/catalogo',
        '/portal/mis-pedidos',
    ]

    @pytest.mark.parametrize('ruta', RUTAS_ADMIN)
    def test_rutas_admin_sin_auth_redirigen(self, client, ruta):
        """Rutas admin sin sesión → 302 hacia login."""
        r = client.get(ruta)
        assert r.status_code == 302
        assert 'login' in r.headers['Location'].lower()

    @pytest.mark.parametrize('ruta', RUTAS_PORTAL)
    def test_rutas_portal_sin_auth_redirigen(self, client, ruta):
        """Rutas del portal sin sesión → 302 hacia login."""
        r = client.get(ruta)
        assert r.status_code == 302
        assert 'login' in r.headers['Location'].lower()

    def test_solicitante_no_accede_a_admin(self, login_solicitante):
        """Solicitante autenticado intentando acceder a admin → 403."""
        r = login_solicitante.get('/admin/inventario')
        assert r.status_code == 403

    def test_admin_puede_acceder_dashboard(self, login_admin):
        """Admin autenticado puede acceder al dashboard."""
        r = login_admin.get('/admin/dashboard', follow_redirects=True)
        assert r.status_code == 200


class TestModelos:
    """Tests unitarios sobre los modelos de Usuario."""

    def test_hash_password_no_es_texto_plano(self, app):
        from app.models import Usuario
        with app.app_context():
            u = Usuario(nombre_completo='Test', email='x@x.com', rol='solicitante')
            u.set_password('secreto')
            assert u.password_hash != 'secreto'
            assert len(u.password_hash) > 20

    def test_check_password_correcto(self, app):
        from app.models import Usuario
        with app.app_context():
            u = Usuario(nombre_completo='T', email='t@t.com', rol='solicitante')
            u.set_password('mipassword')
            assert u.check_password('mipassword') is True

    def test_check_password_incorrecto(self, app):
        from app.models import Usuario
        with app.app_context():
            u = Usuario(nombre_completo='T', email='t2@t.com', rol='solicitante')
            u.set_password('correcto')
            assert u.check_password('incorrecto') is False

    def test_propiedad_es_admin(self, app):
        from app.models import Usuario
        with app.app_context():
            admin = Usuario.query.filter_by(rol='administrador').first()
            sol   = Usuario.query.filter_by(rol='solicitante').first()
            assert admin.es_admin is True
            assert sol.es_admin   is False
