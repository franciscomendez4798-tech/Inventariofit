"""
tests/test_pedidos.py
=====================
Suite de pruebas para el ciclo de vida completo de pedidos:
  creación → revisión → aprobación/rechazo → descuento de stock → entrega.
"""
import pytest


# ── Helper ────────────────────────────────────────────────────────────────────

def _crear_pedido(client, app, material_nombre='Resma de papel bond', cantidad=5):
    """Crea un pedido como solicitante y devuelve (pedido_id, folio)."""
    from app.models import Material, Pedido
    with app.app_context():
        mat = Material.query.filter_by(nombre=material_nombre).first()
        mat_id = mat.id

    client.post('/portal/pedido/nuevo', data={
        'material_id':       [str(mat_id)],
        'cantidad':          [str(cantidad)],
        'notas_solicitante': 'Pedido de prueba',
    }, follow_redirects=True)

    with app.app_context():
        pedido = Pedido.query.order_by(Pedido.id.desc()).first()
        return pedido.id, pedido.folio


# ══════════════════════════════════════════════════════════════════════════════

class TestCreacionPedido:
    """Tests de creación de pedidos por solicitante."""

    def test_nuevo_pedido_exitoso(self, login_solicitante, app):
        """Solicitante puede crear un pedido con materiales permitidos."""
        from app.models import Pedido
        with app.app_context():
            total_antes = Pedido.query.count()

        _crear_pedido(login_solicitante, app, 'Resma de papel bond', 3)

        with app.app_context():
            assert Pedido.query.count() == total_antes + 1

    def test_pedido_genera_folio_unico(self, login_solicitante, app):
        """Cada pedido debe tener un folio distinto con formato PED-YYYY-NNN."""
        from app.models import Pedido
        import re

        _crear_pedido(login_solicitante, app, cantidad=2)
        _crear_pedido(login_solicitante, app, cantidad=1)

        with app.app_context():
            pedidos = Pedido.query.order_by(Pedido.id.desc()).limit(2).all()
            folios  = [p.folio for p in pedidos]

        assert len(set(folios)) == 2   # Son distintos
        for folio in folios:
            assert re.match(r'PED-\d{4}-\d{3}', folio)

    def test_pedido_estado_inicial_es_pendiente(self, login_solicitante, app):
        """Un pedido recién creado debe tener estado 'pendiente'."""
        from app.models import Pedido
        _crear_pedido(login_solicitante, app, cantidad=1)
        with app.app_context():
            p = Pedido.query.order_by(Pedido.id.desc()).first()
            assert p.estado == 'pendiente'

    def test_pedido_material_categoria_no_permitida_falla(self, login_solicitante, app):
        """Solicitante de SEC-ACA no puede pedir 'Cloro 1L' (Limpieza)."""
        from app.models import Material, Pedido
        with app.app_context():
            cloro  = Material.query.filter_by(nombre='Cloro 1L').first()
            total  = Pedido.query.count()
            cloro_id = cloro.id

        login_solicitante.post('/portal/pedido/nuevo', data={
            'material_id': [str(cloro_id)],
            'cantidad':    ['2'],
        }, follow_redirects=True)

        with app.app_context():
            # No se debe haber creado ningún pedido
            assert Pedido.query.count() == total

    def test_pedido_cantidad_mayor_a_stock_falla(self, login_solicitante, app):
        """Pedir más unidades que el stock disponible debe fallar."""
        from app.models import Material, Pedido
        with app.app_context():
            mat   = Material.query.filter_by(nombre='Resma de papel bond').first()
            total = Pedido.query.count()
            mat_id, stock = mat.id, mat.stock_actual

        login_solicitante.post('/portal/pedido/nuevo', data={
            'material_id': [str(mat_id)],
            'cantidad':    [str(stock + 999)],   # Más del disponible
        }, follow_redirects=True)

        with app.app_context():
            assert Pedido.query.count() == total


class TestAprobacionPedido:
    """Tests del flujo de aprobación/rechazo por el administrador."""

    def test_aprobar_pedido_descuenta_stock(self, login_solicitante, login_admin, app):
        """
        Al aprobar un pedido, el stock del material debe disminuir
        exactamente en la cantidad aprobada.
        """
        from app.models import Material, Pedido, DetallePedido

        with app.app_context():
            mat         = Material.query.filter_by(nombre='Resma de papel bond').first()
            stock_antes = mat.stock_actual
            mat_id      = mat.id

        pedido_id, _ = _crear_pedido(login_solicitante, app, cantidad=4)

        # Admin aprueba con la cantidad solicitada (4)
        with app.app_context():
            detalle = DetallePedido.query.filter_by(id_pedido=pedido_id).first()
            det_id  = detalle.id

        login_admin.post(f'/admin/pedidos/{pedido_id}/revisar', data={
            f'cant_aprobada_{det_id}': '4',
            'notas_admin': '',
            'accion': 'aprobar',
        }, follow_redirects=True)

        with app.app_context():
            mat = Material.query.get(mat_id)
            assert mat.stock_actual == stock_antes - 4

    def test_aprobar_pedido_cambia_estado_a_aprobado(
            self, login_solicitante, login_admin, app):
        """Estado del pedido debe ser 'aprobado' tras la aprobación exacta."""
        from app.models import Pedido, DetallePedido

        pedido_id, _ = _crear_pedido(login_solicitante, app, cantidad=2)

        with app.app_context():
            det = DetallePedido.query.filter_by(id_pedido=pedido_id).first()
            det_id = det.id

        login_admin.post(f'/admin/pedidos/{pedido_id}/revisar', data={
            f'cant_aprobada_{det_id}': '2',
            'accion': 'aprobar',
        }, follow_redirects=True)

        with app.app_context():
            p = Pedido.query.get(pedido_id)
            assert p.estado == 'aprobado'

    def test_modificar_cantidad_al_aprobar_cambia_estado_a_modificado(
            self, login_solicitante, login_admin, app):
        """Si admin cambia la cantidad → estado 'modificado'."""
        from app.models import Pedido, DetallePedido

        pedido_id, _ = _crear_pedido(login_solicitante, app, cantidad=10)

        with app.app_context():
            det = DetallePedido.query.filter_by(id_pedido=pedido_id).first()
            det_id = det.id

        # Admin aprueba solo 5 de 10
        login_admin.post(f'/admin/pedidos/{pedido_id}/revisar', data={
            f'cant_aprobada_{det_id}': '5',
            'accion': 'aprobar',
        }, follow_redirects=True)

        with app.app_context():
            p = Pedido.query.get(pedido_id)
            assert p.estado == 'modificado'

    def test_rechazar_pedido_no_descuenta_stock(
            self, login_solicitante, login_admin, app):
        """Rechazar un pedido NO debe tocar el stock."""
        from app.models import Material, Pedido, DetallePedido

        with app.app_context():
            mat         = Material.query.filter_by(nombre='Resma de papel bond').first()
            stock_antes = mat.stock_actual

        pedido_id, _ = _crear_pedido(login_solicitante, app, cantidad=3)

        with app.app_context():
            det    = DetallePedido.query.filter_by(id_pedido=pedido_id).first()
            det_id = det.id

        login_admin.post(f'/admin/pedidos/{pedido_id}/revisar', data={
            f'cant_aprobada_{det_id}': '3',
            'notas_admin': 'No hay presupuesto',
            'accion': 'rechazar',
        }, follow_redirects=True)

        with app.app_context():
            mat = Material.query.filter_by(nombre='Resma de papel bond').first()
            assert mat.stock_actual == stock_antes

    def test_rechazar_pedido_cambia_estado(
            self, login_solicitante, login_admin, app):
        """Pedido rechazado debe tener estado 'rechazado'."""
        from app.models import Pedido, DetallePedido

        pedido_id, _ = _crear_pedido(login_solicitante, app, cantidad=1)

        with app.app_context():
            det = DetallePedido.query.filter_by(id_pedido=pedido_id).first()
            det_id = det.id

        login_admin.post(f'/admin/pedidos/{pedido_id}/revisar', data={
            f'cant_aprobada_{det_id}': '1',
            'accion': 'rechazar',
        }, follow_redirects=True)

        with app.app_context():
            p = Pedido.query.get(pedido_id)
            assert p.estado == 'rechazado'

    def test_aprobar_crea_movimiento_salida(
            self, login_solicitante, login_admin, app):
        """Aprobar un pedido genera un MovimientoInventario de tipo 'salida'."""
        from app.models import Material, Pedido, DetallePedido, MovimientoInventario

        with app.app_context():
            mat = Material.query.filter_by(nombre='Resma de papel bond').first()
            mov_antes = MovimientoInventario.query.filter_by(
                id_material=mat.id, tipo_movimiento='salida'
            ).count()

        pedido_id, _ = _crear_pedido(login_solicitante, app, cantidad=2)

        with app.app_context():
            det    = DetallePedido.query.filter_by(id_pedido=pedido_id).first()
            mat_id = det.id_material
            det_id = det.id

        login_admin.post(f'/admin/pedidos/{pedido_id}/revisar', data={
            f'cant_aprobada_{det_id}': '2',
            'accion': 'aprobar',
        })

        with app.app_context():
            mov_despues = MovimientoInventario.query.filter_by(
                id_material=mat_id, tipo_movimiento='salida'
            ).count()
            assert mov_despues == mov_antes + 1


class TestEntregaPedido:
    """Tests de la confirmación de entrega física."""

    def test_confirmar_entrega_cambia_estado(
            self, login_solicitante, login_admin, app):
        """Un pedido aprobado puede marcarse como entregado."""
        from app.models import Pedido, DetallePedido

        pedido_id, _ = _crear_pedido(login_solicitante, app, cantidad=1)

        with app.app_context():
            det    = DetallePedido.query.filter_by(id_pedido=pedido_id).first()
            det_id = det.id

        # Aprobar
        login_admin.post(f'/admin/pedidos/{pedido_id}/revisar', data={
            f'cant_aprobada_{det_id}': '1',
            'accion': 'aprobar',
        })

        # Entregar
        login_admin.post(f'/admin/pedidos/{pedido_id}/entregar',
                         follow_redirects=True)

        with app.app_context():
            p = Pedido.query.get(pedido_id)
            assert p.estado == 'entregado'
            assert p.fecha_entrega is not None


class TestGeneracionFolio:
    """Tests del generador de folios correlativo."""

    def test_folio_formato_correcto(self, app):
        """El folio debe tener el formato PED-YYYY-NNN."""
        import re
        from app.models import Pedido
        with app.app_context():
            folio = Pedido.generar_folio()
        assert re.match(r'PED-\d{4}-\d{3}', folio)
