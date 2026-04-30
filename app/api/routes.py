# app/api/routes.py
"""
Rutas de datos JSON para el dashboard de gastos.
Consumidas por Chart.js en el frontend.
"""
from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func, extract, case
from ..models import (MovimientoInventario, Pedido, DetallePedido,
                      Departamento, Material, Categoria, db)
from ..admin.routes import solo_admin
from datetime import datetime, timedelta

api_bp = Blueprint('api', __name__)


@api_bp.route('/dashboard')
@solo_admin
def dashboard_data():
    """
    Retorna JSON con tres datasets listos para Chart.js:
      1. entradas_salidas_mensual  → gráfica de barras apiladas (últimos 6 meses)
      2. top_departamentos         → gráfica de dona (por gasto total)
      3. materiales_mas_solicitados → ranking de barras horizontales
    """
    hoy     = datetime.utcnow()
    hace_6m = hoy - timedelta(days=180)

    # ── 1. Entradas y salidas por mes (últimos 6 meses) ──────────────────────
    # Usamos extract(year/month) para compatibilidad SQLite y PostgreSQL
    movimientos = (db.session.query(
            extract('year',  MovimientoInventario.fecha).label('anio'),
            extract('month', MovimientoInventario.fecha).label('mes_num'),
            MovimientoInventario.tipo_movimiento,
            func.sum(MovimientoInventario.cantidad).label('total')
        )
        .filter(MovimientoInventario.fecha >= hace_6m)
        .group_by('anio', 'mes_num', MovimientoInventario.tipo_movimiento)
        .order_by('anio', 'mes_num')
        .all()
    )

    # Construye etiquetas "YYYY-MM" en Python (compatible con cualquier BD)
    meses_set  = sorted({f"{int(r.anio)}-{int(r.mes_num):02d}" for r in movimientos})
    entradas   = {m: 0 for m in meses_set}
    salidas    = {m: 0 for m in meses_set}

    for r in movimientos:
        mes_key = f"{int(r.anio)}-{int(r.mes_num):02d}"
        if r.tipo_movimiento == 'entrada':
            entradas[mes_key] = r.total
        elif r.tipo_movimiento == 'salida':
            salidas[mes_key]  = r.total

    # ── 2. Departamentos que más consumen (por cantidad de ítems entregados) ─
    top_deptos = (db.session.query(
            Departamento.nombre,
            func.sum(DetallePedido.cantidad_aprobada).label('total_items')
        )
        .join(Pedido, Pedido.id_departamento == Departamento.id)
        .join(DetallePedido, DetallePedido.id_pedido == Pedido.id)
        .filter(Pedido.estado.in_(['aprobado', 'entregado', 'modificado']))
        .group_by(Departamento.nombre)
        .order_by(func.sum(DetallePedido.cantidad_aprobada).desc())
        .limit(8)
        .all()
    )

    # ── 3. Materiales más solicitados ────────────────────────────────────────
    top_materiales = (db.session.query(
            Material.nombre,
            func.sum(DetallePedido.cantidad_aprobada).label('total')
        )
        .join(DetallePedido, DetallePedido.id_material == Material.id)
        .join(Pedido, Pedido.id == DetallePedido.id_pedido)
        .filter(Pedido.estado.in_(['aprobado', 'entregado', 'modificado']))
        .group_by(Material.nombre)
        .order_by(func.sum(DetallePedido.cantidad_aprobada).desc())
        .limit(10)
        .all()
    )

    return jsonify({
        'entradas_salidas': {
            'labels':   meses_set,
            'entradas': [entradas[m] for m in meses_set],
            'salidas':  [salidas[m]  for m in meses_set],
        },
        'top_departamentos': {
            'labels': [r.nombre       for r in top_deptos],
            'data':   [r.total_items  for r in top_deptos],
        },
        'top_materiales': {
            'labels': [r.nombre for r in top_materiales],
            'data':   [r.total  for r in top_materiales],
        },
    })


@api_bp.route('/pedidos-pendientes')
@login_required
def pedidos_pendientes():
    """Badge de pedidos pendientes para el sidebar (solo admin)."""
    if not current_user.es_admin:
        return jsonify({'count': 0})
    count = Pedido.query.filter(
        Pedido.estado.in_(['pendiente', 'en_revision'])
    ).count()
    return jsonify({'count': count})
