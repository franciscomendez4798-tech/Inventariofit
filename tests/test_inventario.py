"""
tests/test_inventario.py
========================
Suite de pruebas para el módulo de inventario (CRUD de materiales,
control de stock, visibilidad, entradas).
"""
import pytest


class TestCatalogoFiltrado:
    """
    El catálogo del solicitante SOLO debe mostrar materiales de las
    categorías permitidas para su departamento, con stock > 0 y publicados.
    """

    def test_catalogo_muestra_materiales_de_categoria_permitida(self, login_solicitante):
        """SEC-ACA tiene permiso en Papelería → ve 'Resma de papel bond'."""
        r = login_solicitante.get('/portal/catalogo', follow_redirects=True)
        assert r.status_code == 200
        assert 'Resma de papel bond'.encode() in r.data

    def test_catalogo_no_muestra_categoria_prohibida(self, login_solicitante):
        """SEC-ACA NO tiene permiso en Limpieza → NO ve 'Cloro 1L'."""
        r = login_solicitante.get('/portal/catalogo', follow_redirects=True)
        assert r.status_code == 200
        assert b'Cloro 1L' not in r.data

    def test_catalogo_no_muestra_material_sin_stock(self, login_solicitante):
        """Folder Manila tiene stock=0 → no aparece en catálogo."""
        r = login_solicitante.get('/portal/catalogo', follow_redirects=True)
        assert b'Folder Manila' not in r.data

    def test_catalogo_no_muestra_material_no_publicado(self, login_solicitante):
        """Pluma BIC tiene publicado=False → no aparece en catálogo."""
        r = login_solicitante.get('/portal/catalogo', follow_redirects=True)
        assert b'Pluma BIC' not in r.data

    def test_admin_ve_inventario_completo(self, login_admin):
        """El admin ve TODOS los materiales en /admin/inventario."""
        r = login_admin.get('/admin/inventario', follow_redirects=True)
        assert r.status_code == 200
        # Todos los materiales (incluyendo sin stock y no publicados)
        for nombre in [b'Resma de papel bond', b'Cloro 1L',
                       b'Folder Manila', b'Pluma BIC']:
            assert nombre in r.data


class TestCRUDMateriales:
    """Tests de alta, edición y toggle de visibilidad de materiales."""

    def test_get_formulario_nuevo_material(self, login_admin):
        r = login_admin.get('/admin/material/nuevo')
        assert r.status_code == 200
        assert b'Nuevo material' in r.data

    def test_crear_material_exitoso(self, login_admin, app):
        """POST con datos válidos crea un material en la BD."""
        from app.models import Categoria
        with app.app_context():
            cat_id = Categoria.query.filter_by(nombre='Papelería').first().id

        r = login_admin.post('/admin/material/nuevo', data={
            'nombre':          'Grapas caja 26/6',
            'unidad_medida':   'caja',
            'stock_actual':    '20',
            'stock_minimo':    '3',
            'precio_unitario': '15.50',
            'id_categoria':    str(cat_id),
        }, follow_redirects=True)

        assert r.status_code == 200
        assert b'guardado' in r.data  # Flash de éxito

    def test_crear_material_sin_nombre_falla(self, login_admin, app):
        """POST sin nombre no crea material (validación HTML/servidor)."""
        from app.models import Categoria, Material
        with app.app_context():
            cat_id = Categoria.query.filter_by(nombre='Papelería').first().id
            inicial = Material.query.count()

        login_admin.post('/admin/material/nuevo', data={
            'nombre':        '',   # vacío
            'unidad_medida': 'pieza',
            'id_categoria':  str(cat_id),
            'stock_actual':  '0',
            'stock_minimo':  '0',
        })
        with app.app_context():
            # No debe haberse creado un material sin nombre
            nuevo_total = Material.query.count()
        assert nuevo_total == inicial

    def test_toggle_publicado_cambia_estado(self, login_admin, app):
        """POST a toggle-publicado invierte el campo publicado."""
        from app.models import Material
        with app.app_context():
            mat = Material.query.filter_by(nombre='Resma de papel bond').first()
            estado_inicial = mat.publicado
            mat_id = mat.id

        login_admin.post(f'/admin/material/{mat_id}/toggle-publicado')

        with app.app_context():
            mat = Material.query.get(mat_id)
            assert mat.publicado != estado_inicial

        # Revertir para no afectar otros tests
        login_admin.post(f'/admin/material/{mat_id}/toggle-publicado')


class TestEntradaStock:
    """Tests del registro de entradas de inventario."""

    def test_entrada_stock_incrementa_cantidad(self, login_admin, app):
        """Registrar una entrada debe sumar al stock_actual."""
        from app.models import Material
        with app.app_context():
            mat = Material.query.filter_by(nombre='Resma de papel bond').first()
            stock_antes = mat.stock_actual
            mat_id = mat.id

        login_admin.post(f'/admin/material/{mat_id}/entrada-stock', data={
            'cantidad': '10',
            'motivo':   'Compra de prueba',
        }, follow_redirects=True)

        with app.app_context():
            mat = Material.query.get(mat_id)
            assert mat.stock_actual == stock_antes + 10

    def test_entrada_stock_crea_movimiento(self, login_admin, app):
        """Una entrada debe registrar un MovimientoInventario tipo 'entrada'."""
        from app.models import Material, MovimientoInventario
        with app.app_context():
            mat = Material.query.filter_by(nombre='Cloro 1L').first()
            mov_antes = MovimientoInventario.query.filter_by(
                id_material=mat.id, tipo_movimiento='entrada'
            ).count()
            mat_id = mat.id

        login_admin.post(f'/admin/material/{mat_id}/entrada-stock', data={
            'cantidad': '5',
            'motivo':   'Test entrada',
        })

        with app.app_context():
            mov_despues = MovimientoInventario.query.filter_by(
                id_material=mat_id, tipo_movimiento='entrada'
            ).count()
            assert mov_despues == mov_antes + 1

    def test_entrada_cantidad_cero_no_modifica_stock(self, login_admin, app):
        """Entrada con cantidad=0 no debe modificar el stock."""
        from app.models import Material
        with app.app_context():
            mat = Material.query.filter_by(nombre='Cloro 1L').first()
            stock_antes = mat.stock_actual
            mat_id = mat.id

        login_admin.post(f'/admin/material/{mat_id}/entrada-stock', data={
            'cantidad': '0',
        }, follow_redirects=True)

        with app.app_context():
            mat = Material.query.get(mat_id)
            assert mat.stock_actual == stock_antes


class TestModeloMaterial:
    """Tests unitarios del modelo Material."""

    def test_propiedad_bajo_stock(self, app):
        from app.models import Material
        with app.app_context():
            mat = Material.query.filter_by(nombre='Folder Manila').first()
            # stock_actual=0, stock_minimo=10 → bajo_stock=True
            assert mat.bajo_stock is True

    def test_propiedad_stock_normal(self, app):
        from app.models import Material
        with app.app_context():
            mat = Material.query.filter_by(nombre='Resma de papel bond').first()
            # stock_actual=50, stock_minimo=5 → bajo_stock=False
            assert mat.bajo_stock is False
