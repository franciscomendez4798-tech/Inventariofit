"""
tests/test_api.py
=================
Tests del endpoint /api/dashboard y endpoints auxiliares JSON.
"""
import json


class TestDashboardAPI:
    """Tests del endpoint de datos para Chart.js."""

    def test_api_dashboard_requiere_auth(self, client):
        """Sin sesión → 302 al login."""
        r = client.get('/api/dashboard')
        assert r.status_code == 302

    def test_api_dashboard_solicitante_recibe_403(self, login_solicitante):
        """Solicitante autenticado → 403 Forbidden."""
        r = login_solicitante.get('/api/dashboard')
        assert r.status_code == 403

    def test_api_dashboard_admin_recibe_json(self, login_admin):
        """Admin → 200 con JSON válido."""
        r = login_admin.get('/api/dashboard')
        assert r.status_code == 200
        assert r.content_type == 'application/json'

    def test_api_dashboard_estructura_correcta(self, login_admin):
        """JSON debe tener las tres claves esperadas por Chart.js."""
        r    = login_admin.get('/api/dashboard')
        data = json.loads(r.data)

        assert 'entradas_salidas'    in data
        assert 'top_departamentos'   in data
        assert 'top_materiales'      in data

        # Cada sección debe tener 'labels' y 'data' (o 'entradas'/'salidas')
        es = data['entradas_salidas']
        assert 'labels'   in es
        assert 'entradas' in es
        assert 'salidas'  in es
        assert isinstance(es['labels'],   list)
        assert isinstance(es['entradas'], list)
        assert isinstance(es['salidas'],  list)

        td = data['top_departamentos']
        assert 'labels' in td
        assert 'data'   in td

        tm = data['top_materiales']
        assert 'labels' in tm
        assert 'data'   in tm

    def test_api_dashboard_labels_y_data_misma_longitud(self, login_admin):
        """Labels y datasets deben tener la misma longitud (Chart.js lo requiere)."""
        data = json.loads(login_admin.get('/api/dashboard').data)

        td = data['top_departamentos']
        assert len(td['labels']) == len(td['data'])

        tm = data['top_materiales']
        assert len(tm['labels']) == len(tm['data'])

        es = data['entradas_salidas']
        assert len(es['labels']) == len(es['entradas'])
        assert len(es['labels']) == len(es['salidas'])


class TestPedidosPendientesAPI:
    """Tests del badge de pedidos pendientes."""

    def test_badge_requiere_auth(self, client):
        r = client.get('/api/pedidos-pendientes')
        assert r.status_code == 302

    def test_badge_admin_devuelve_count(self, login_admin):
        r = login_admin.get('/api/pedidos-pendientes')
        assert r.status_code == 200
        data = json.loads(r.data)
        assert 'count' in data
        assert isinstance(data['count'], int)
        assert data['count'] >= 0

    def test_badge_solicitante_devuelve_cero(self, login_solicitante):
        """Solicitante recibe count=0 (no admin)."""
        r    = login_solicitante.get('/api/pedidos-pendientes')
        data = json.loads(r.data)
        assert data['count'] == 0
