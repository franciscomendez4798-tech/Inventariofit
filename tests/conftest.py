"""
tests/conftest.py
=================
Fixtures compartidas para toda la suite de pruebas.
Usa SQLite en memoria para aislamiento total entre tests.
"""
import pytest
from app import create_app
from app.extensions import db as _db
from app.models import (
    Usuario, Departamento, Categoria, Proveedor,
    Material, Pedido, DetallePedido,
)


# ── App y cliente ────────────────────────────────────────────────────────────

@pytest.fixture(scope='session')
def app():
    """Instancia de Flask configurada para testing (SQLite en memoria)."""
    application = create_app('testing')
    with application.app_context():
        _db.create_all()
        _sembrar_datos_base()
        yield application
        _db.drop_all()


@pytest.fixture()
def client(app):
    """Cliente HTTP de pruebas."""
    return app.test_client()


@pytest.fixture()
def runner(app):
    """CLI runner para comandos Flask."""
    return app.test_cli_runner()


# ── Helpers de autenticación ────────────────────────────────────────────────

@pytest.fixture()
def login_admin(client):
    """Loguea como administrador y devuelve el cliente autenticado."""
    client.post('/login', data={
        'email':    'admin@test.edu.mx',
        'password': 'Admin123!',
    }, follow_redirects=True)
    return client


@pytest.fixture()
def login_solicitante(client):
    """Loguea como solicitante (Secretaría Académica) y devuelve el cliente."""
    client.post('/login', data={
        'email':    'sol@test.edu.mx',
        'password': 'Sol123!',
    }, follow_redirects=True)
    return client


# ── Fixtures de objetos de dominio ──────────────────────────────────────────

@pytest.fixture()
def categoria_papeleria(app):
    with app.app_context():
        return Categoria.query.filter_by(nombre='Papelería').first()


@pytest.fixture()
def categoria_limpieza(app):
    with app.app_context():
        return Categoria.query.filter_by(nombre='Limpieza').first()


@pytest.fixture()
def departamento_academica(app):
    with app.app_context():
        return Departamento.query.filter_by(codigo='SEC-ACA').first()


@pytest.fixture()
def departamento_mant(app):
    with app.app_context():
        return Departamento.query.filter_by(codigo='MANT').first()


@pytest.fixture()
def material_hojas(app):
    with app.app_context():
        return Material.query.filter_by(nombre='Resma de papel bond').first()


@pytest.fixture()
def material_cloro(app):
    with app.app_context():
        return Material.query.filter_by(nombre='Cloro 1L').first()


# ── Seed de datos de prueba ──────────────────────────────────────────────────

def _sembrar_datos_base():
    """Crea el conjunto mínimo de datos para que los tests funcionen."""
    # Categorías
    cat_papel   = Categoria(nombre='Papelería', descripcion='Artículos de oficina')
    cat_limpieza = Categoria(nombre='Limpieza',  descripcion='Artículos de aseo')
    cat_computo  = Categoria(nombre='Cómputo',   descripcion='Artículos de cómputo')
    _db.session.add_all([cat_papel, cat_limpieza, cat_computo])
    _db.session.flush()

    # Departamentos + permisos
    dep_aca  = Departamento(nombre='Secretaría Académica',      codigo='SEC-ACA')
    dep_mant = Departamento(nombre='Mantenimiento y Servicios', codigo='MANT')
    dep_dir  = Departamento(nombre='Dirección General',         codigo='DIR-GEN')

    dep_aca.categorias.extend([cat_papel, cat_computo])
    dep_mant.categorias.extend([cat_limpieza])
    dep_dir.categorias.extend([cat_papel, cat_computo, cat_limpieza])
    _db.session.add_all([dep_aca, dep_mant, dep_dir])
    _db.session.flush()

    # Usuarios
    admin = Usuario(
        nombre_completo='Admin Test',
        email='admin@test.edu.mx',
        rol='administrador',
    )
    admin.set_password('Admin123!')

    sol = Usuario(
        nombre_completo='Solicitante Test',
        email='sol@test.edu.mx',
        rol='solicitante',
        id_departamento=dep_aca.id,
    )
    sol.set_password('Sol123!')

    sol_mant = Usuario(
        nombre_completo='Mantenimiento Test',
        email='mant@test.edu.mx',
        rol='solicitante',
        id_departamento=dep_mant.id,
    )
    sol_mant.set_password('Mant123!')
    _db.session.add_all([admin, sol, sol_mant])
    _db.session.flush()

    # Proveedor
    prov = Proveedor(nombre='Proveedor Test SA', contacto='Contacto X', activo=True)
    _db.session.add(prov)
    _db.session.flush()

    # Materiales
    m1 = Material(
        nombre='Resma de papel bond',
        unidad_medida='resma',
        stock_actual=50,
        stock_minimo=5,
        precio_unitario=85.00,
        id_categoria=cat_papel.id,
        id_proveedor=prov.id,
        publicado=True,
    )
    m2 = Material(
        nombre='Cloro 1L',
        unidad_medida='litro',
        stock_actual=30,
        stock_minimo=3,
        precio_unitario=22.50,
        id_categoria=cat_limpieza.id,
        publicado=True,
    )
    m3 = Material(
        nombre='Folder Manila',
        unidad_medida='pieza',
        stock_actual=0,         # Sin stock — no debe aparecer en catálogo
        stock_minimo=10,
        precio_unitario=4.50,
        id_categoria=cat_papel.id,
        publicado=True,
    )
    m4 = Material(
        nombre='Pluma BIC',
        unidad_medida='pieza',
        stock_actual=100,
        stock_minimo=20,
        precio_unitario=3.00,
        id_categoria=cat_papel.id,
        publicado=False,        # Oculto — no debe aparecer en catálogo
    )
    _db.session.add_all([m1, m2, m3, m4])
    _db.session.commit()
