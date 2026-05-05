# app/mantenimiento/routes.py
from datetime import datetime
from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, jsonify
from flask_login import login_required, current_user
from sqlalchemy import desc
from ..models import (db, Trabajador, Prestamo, PedidoEquipo,
                       StockMantenimiento, MovimientoStockMant, Material, MovimientoInventario,
                       Herramienta, OrdenServicio, FirmaTrabajador, FirmaUsuario,
                       DispositivoAV, PrestamoAV)

mantenimiento_bp = Blueprint('mantenimiento', __name__, template_folder='../templates/mantenimiento')

def solo_admin_o_mantenimiento(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.es_admin_o_mantenimiento:
            abort(403)
        return f(*args, **kwargs)
    return decorated


# ═══════════════════════════════════════════════════════════════════════════════
# PANEL PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════

@mantenimiento_bp.route('/')
@mantenimiento_bp.route('/panel')
@solo_admin_o_mantenimiento
def panel():
    hoy = datetime.utcnow().date()
    stats = {
        'total_items':          StockMantenimiento.query.filter_by(activo=True).count(),
        'personal_activo':      Trabajador.query.filter_by(activo=True).count(),
        'prestamos_activos':    Prestamo.query.filter_by(estado='prestado').count(),
        'prestamos_devueltos':  Prestamo.query.filter_by(estado='devuelto').count(),
        'bajo_stock':           StockMantenimiento.query.filter(
                                    StockMantenimiento.activo == True,
                                    StockMantenimiento.cantidad <= StockMantenimiento.cantidad_min
                                ).count(),
        'entradas_hoy':         MovimientoStockMant.query.filter(
                                    MovimientoStockMant.tipo == 'entrada',
                                    db.func.date(MovimientoStockMant.fecha) == hoy
                                ).count(),
        'salidas_hoy':          MovimientoStockMant.query.filter(
                                    MovimientoStockMant.tipo == 'salida',
                                    db.func.date(MovimientoStockMant.fecha) == hoy
                                ).count(),
        'pedidos_pendientes':   PedidoEquipo.query.filter_by(estado='pendiente').count(),
    }
    ultimos_movimientos = (MovimientoStockMant.query
                           .order_by(desc(MovimientoStockMant.fecha))
                           .limit(5).all())
    return render_template('mantenimiento/panel.html',
                           stats=stats,
                           ultimos_movimientos=ultimos_movimientos)


# ═══════════════════════════════════════════════════════════════════════════════
# STOCK PROPIO — Inventario exclusivo de Mantenimiento
# ═══════════════════════════════════════════════════════════════════════════════

@mantenimiento_bp.route('/stock')
@solo_admin_o_mantenimiento
def stock():
    """Stock propio de Mantenimiento (separado del almacén general)."""
    q         = request.args.get('q', '').strip()
    solo_bajo = request.args.get('bajo_stock', '')

    query = StockMantenimiento.query.filter_by(activo=True).order_by(StockMantenimiento.nombre)
    if q:
        query = query.filter(StockMantenimiento.nombre.ilike(f'%{q}%'))
    if solo_bajo:
        query = query.filter(StockMantenimiento.cantidad <= StockMantenimiento.cantidad_min)

    items = query.all()
    trabajadores = Trabajador.query.filter_by(activo=True).order_by(Trabajador.nombre).all()
    pedidos_aprobados = PedidoEquipo.query.filter_by(estado='aprobado').all()

    return render_template('mantenimiento/stock.html',
                           items=items,
                           trabajadores=trabajadores,
                           pedidos_aprobados=pedidos_aprobados,
                           q=q,
                           solo_bajo=solo_bajo)


@mantenimiento_bp.route('/stock/entrada', methods=['POST'])
@solo_admin_o_mantenimiento
def stock_entrada():
    """Registra manualmente una entrada al stock propio de Mantenimiento."""
    nombre       = request.form.get('nombre', '').strip()
    unidad       = request.form.get('unidad_medida', 'pza').strip()
    cantidad     = request.form.get('cantidad', type=int)
    precio_ref   = request.form.get('precio_ref', 0.0, type=float)
    id_pedido    = request.form.get('id_pedido_equipo', None, type=int)
    motivo       = request.form.get('motivo', 'Carga manual tras recepción').strip()
    item_id      = request.form.get('item_id', None, type=int)  # si se suma a existente

    if not nombre or not cantidad or cantidad <= 0:
        flash('Indica el nombre del artículo y una cantidad válida.', 'warning')
        return redirect(url_for('mantenimiento.stock'))

    if item_id:
        item = StockMantenimiento.query.get_or_404(item_id)
    else:
        item = StockMantenimiento(
            nombre         = nombre,
            unidad_medida  = unidad,
            cantidad       = 0,
            precio_ref     = precio_ref,
            id_pedido_equipo = id_pedido,
            id_usuario_alta  = current_user.id,
        )
        db.session.add(item)
        db.session.flush()  # get item.id

    item.cantidad += cantidad
    mov = MovimientoStockMant(
        id_item        = item.id,
        tipo           = 'entrada',
        cantidad       = cantidad,
        cantidad_result = item.cantidad,
        id_usuario     = current_user.id,
        motivo         = motivo,
    )
    db.session.add(mov)

    # Marcar pedido como entregado si se vinculó
    if id_pedido:
        pe = PedidoEquipo.query.get(id_pedido)
        if pe and pe.estado == 'aprobado':
            pe.estado = 'entregado'
            pe.fecha_resolucion = datetime.utcnow()

    db.session.commit()
    flash(f'Entrada de {cantidad} {item.unidad_medida} de "{item.nombre}" registrada.', 'success')
    return redirect(url_for('mantenimiento.stock'))


@mantenimiento_bp.route('/stock/<int:item_id>/salida', methods=['POST'])
@solo_admin_o_mantenimiento
def stock_salida(item_id):
    """Registra una salida/consumo del stock propio hacia un trabajador."""
    item          = StockMantenimiento.query.get_or_404(item_id)
    cantidad      = request.form.get('cantidad', type=int)
    id_trabajador = request.form.get('id_trabajador', type=int)
    motivo        = request.form.get('motivo', '').strip()

    if not cantidad or cantidad <= 0:
        flash('Cantidad inválida.', 'warning')
        return redirect(url_for('mantenimiento.stock'))
    if item.cantidad < cantidad:
        flash(f'Stock insuficiente. Disponible: {item.cantidad} {item.unidad_medida}.', 'danger')
        return redirect(url_for('mantenimiento.stock'))

    if id_trabajador:
        t = Trabajador.query.get(id_trabajador)
        if t:
            motivo = f'{motivo} — Técnico: {t.nombre}'.strip(' —')

    item.cantidad -= cantidad
    mov = MovimientoStockMant(
        id_item        = item.id,
        tipo           = 'salida',
        cantidad       = cantidad,
        cantidad_result = item.cantidad,
        id_trabajador  = id_trabajador,
        id_usuario     = current_user.id,
        motivo         = motivo or 'Consumo',
    )
    db.session.add(mov)
    db.session.commit()
    flash(f'Salida de {cantidad} {item.unidad_medida} de "{item.nombre}" registrada.', 'success')
    return redirect(url_for('mantenimiento.stock'))


@mantenimiento_bp.route('/stock/bitacora')
@solo_admin_o_mantenimiento
def stock_bitacora():
    """Bitácora completa de movimientos del stock propio de Mantenimiento."""
    tipo  = request.args.get('tipo', '')
    q     = request.args.get('q', '').strip()
    fecha = request.args.get('fecha', '')

    query = MovimientoStockMant.query.order_by(desc(MovimientoStockMant.fecha))
    if tipo in ('entrada', 'salida', 'ajuste'):
        query = query.filter_by(tipo=tipo)
    if q:
        query = query.join(StockMantenimiento).filter(
            StockMantenimiento.nombre.ilike(f'%{q}%')
        )
    if fecha:
        try:
            fd = datetime.strptime(fecha, '%Y-%m-%d').date()
            query = query.filter(db.func.date(MovimientoStockMant.fecha) == fd)
        except ValueError:
            pass

    movimientos = query.all()
    totales = {
        'entradas': MovimientoStockMant.query.filter_by(tipo='entrada').count(),
        'salidas':  MovimientoStockMant.query.filter_by(tipo='salida').count(),
    }
    return render_template('mantenimiento/stock_bitacora.html',
                           movimientos=movimientos, totales=totales,
                           tipo=tipo, q=q, fecha=fecha)



# ─── RECEPCIONES — entradas al stock propio de Mantenimiento ──────────────
@mantenimiento_bp.route('/recepciones')
@solo_admin_o_mantenimiento
def recepciones():
    """Historial de entradas (recepciones) al stock propio de Mantenimiento."""
    q           = request.args.get('q', '').strip()
    fecha_desde = request.args.get('fecha_desde', '')
    fecha_hasta = request.args.get('fecha_hasta', '')

    query = (MovimientoStockMant.query
             .filter_by(tipo='entrada')
             .order_by(desc(MovimientoStockMant.fecha)))

    if q:
        query = query.join(StockMantenimiento).filter(
            StockMantenimiento.nombre.ilike(f'%{q}%')
        )
    if fecha_desde:
        try:
            fd = datetime.strptime(fecha_desde, '%Y-%m-%d')
            query = query.filter(MovimientoStockMant.fecha >= fd)
        except ValueError:
            pass
    if fecha_hasta:
        try:
            from datetime import timedelta
            fh = datetime.strptime(fecha_hasta, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(MovimientoStockMant.fecha < fh)
        except ValueError:
            pass

    recepciones_list = query.all()
    total_entradas = MovimientoStockMant.query.filter_by(tipo='entrada').count()
    return render_template('mantenimiento/recepciones.html',
                           recepciones=recepciones_list,
                           total_entradas=total_entradas,
                           q=q,
                           fecha_desde=fecha_desde,
                           fecha_hasta=fecha_hasta)


@mantenimiento_bp.route('/recepcion/nueva', methods=['GET', 'POST'])
@solo_admin_o_mantenimiento
def recepcion_form():
    """Redirige al stock para registrar una entrada."""
    return redirect(url_for('mantenimiento.stock'))


# ─── CONSUMOS — salidas del stock propio de Mantenimiento ─────────────────
@mantenimiento_bp.route('/consumos')
@solo_admin_o_mantenimiento
def consumos():
    """Historial de salidas/consumos del stock propio de Mantenimiento."""
    q             = request.args.get('q', '').strip()
    fecha         = request.args.get('fecha', '')
    id_trabajador = request.args.get('trabajador', '', type=str)

    query = (MovimientoStockMant.query
             .filter_by(tipo='salida')
             .order_by(desc(MovimientoStockMant.fecha)))
    if q:
        query = query.join(StockMantenimiento).filter(
            StockMantenimiento.nombre.ilike(f'%{q}%')
        )
    if fecha:
        try:
            fd = datetime.strptime(fecha, '%Y-%m-%d').date()
            query = query.filter(db.func.date(MovimientoStockMant.fecha) == fd)
        except ValueError:
            pass
    if id_trabajador:
        try:
            query = query.filter(MovimientoStockMant.id_trabajador == int(id_trabajador))
        except ValueError:
            pass

    consumos      = query.all()
    trabajadores  = Trabajador.query.filter_by(activo=True).order_by(Trabajador.nombre).all()
    materiales    = StockMantenimiento.query.filter(
        StockMantenimiento.activo == True,
        StockMantenimiento.cantidad > 0
    ).order_by(StockMantenimiento.nombre).all()
    total_salidas = MovimientoStockMant.query.filter_by(tipo='salida').count()
    return render_template('mantenimiento/consumos.html',
                           consumos=consumos,
                           trabajadores=trabajadores,
                           materiales=materiales,
                           total_salidas=total_salidas,
                           q=q, fecha=fecha, id_trabajador=id_trabajador)


@mantenimiento_bp.route('/consumo/nuevo', methods=['GET', 'POST'])
@solo_admin_o_mantenimiento
def consumo_form():
    """Formulario para registrar un consumo/salida del stock propio de Mantenimiento."""
    trabajadores = Trabajador.query.filter_by(activo=True).order_by(Trabajador.nombre).all()
    materiales   = StockMantenimiento.query.filter(
        StockMantenimiento.activo == True,
        StockMantenimiento.cantidad > 0
    ).order_by(StockMantenimiento.nombre).all()

    if request.method == 'POST':
        id_item       = request.form.get('id_material', type=int)
        cantidad      = request.form.get('cantidad', type=int)
        id_trabajador = request.form.get('id_trabajador', type=int)
        motivo        = request.form.get('motivo', '').strip()

        item = StockMantenimiento.query.get_or_404(id_item)
        if not cantidad or cantidad <= 0:
            flash('Cantidad inválida.', 'warning')
        elif item.cantidad < cantidad:
            flash(f'Stock insuficiente. Disponible: {item.cantidad} {item.unidad_medida}.', 'danger')
        else:
            if id_trabajador:
                t = Trabajador.query.get(id_trabajador)
                if t:
                    motivo = f'{motivo} — Técnico: {t.nombre}'.strip(' —')
            item.cantidad -= cantidad
            mov = MovimientoStockMant(
                id_item         = item.id,
                tipo            = 'salida',
                cantidad        = cantidad,
                cantidad_result = item.cantidad,
                id_trabajador   = id_trabajador,
                id_usuario      = current_user.id,
                motivo          = motivo or 'Consumo',
            )
            db.session.add(mov)
            db.session.commit()
            flash(f'Consumo de {cantidad} {item.unidad_medida} de "{item.nombre}" registrado.', 'success')
            return redirect(url_for('mantenimiento.consumos'))

    return render_template('mantenimiento/consumo_form.html',
                           materiales=materiales,
                           trabajadores=trabajadores)


# ─── AUDITORÍA (re-usa stock_bitacora) ────────────────────────────────────
@mantenimiento_bp.route('/auditoria')
@solo_admin_o_mantenimiento
def auditoria():
    return redirect(url_for('mantenimiento.stock_bitacora'))


# ═══════════════════════════════════════════════════════════════════════════════
# PERSONAL (TRABAJADORES)
# ═══════════════════════════════════════════════════════════════════════════════

@mantenimiento_bp.route('/personal')
@solo_admin_o_mantenimiento
def personal():
    trabajadores = Trabajador.query.order_by(Trabajador.nombre).all()
    return render_template('mantenimiento/personal.html', trabajadores=trabajadores)

@mantenimiento_bp.route('/personal/nuevo', methods=['GET', 'POST'])
@mantenimiento_bp.route('/personal/<int:trab_id>/editar', methods=['GET', 'POST'])
@solo_admin_o_mantenimiento
def personal_form(trab_id=None):
    trabajador = Trabajador.query.get_or_404(trab_id) if trab_id else Trabajador()
    if request.method == 'POST':
        trabajador.nombre = request.form['nombre'].strip()
        trabajador.cargo  = request.form['cargo'].strip()
        trabajador.area   = request.form.get('area', '').strip() or None
        trabajador.activo = 'activo' in request.form
        if not trab_id:
            db.session.add(trabajador)
        db.session.commit()
        flash(f'Trabajador "{trabajador.nombre}" guardado.', 'success')
        return redirect(url_for('mantenimiento.personal'))
    return render_template('mantenimiento/personal_form.html', trabajador=trabajador)

def _items_consumos_trabajador(trab_id):
    """Retorna lista de items agregados por material de los consumos del trabajador."""
    movs = (MovimientoStockMant.query
            .filter_by(id_trabajador=trab_id, tipo='salida')
            .order_by(MovimientoStockMant.fecha)
            .all())
    agregado = {}
    for m in movs:
        nombre = m.item.nombre if m.item else 'Sin nombre'
        unidad = m.item.unidad_medida if m.item else 'pza'
        if nombre in agregado:
            agregado[nombre]['cantidad'] += m.cantidad
        else:
            agregado[nombre] = {'cantidad': m.cantidad, 'unidad': unidad, 'descripcion': nombre}
    return list(agregado.values())


@mantenimiento_bp.route('/personal/<int:trab_id>/formato_pedido')
@solo_admin_o_mantenimiento
def formato_pedido_trabajador(trab_id):
    """Descarga el formato R-AP-33-01-01 (.xlsx) con los consumos del trabajador."""
    from flask import send_file
    from ..utils.formatos import generar_xlsx_pedido_trabajador
    trabajador = Trabajador.query.get_or_404(trab_id)
    items = _items_consumos_trabajador(trab_id)
    buffer = generar_xlsx_pedido_trabajador(trabajador.nombre, items=items, area=trabajador.area)
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f'R-AP-33-01-01_Requisicion_{trabajador.nombre}.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


@mantenimiento_bp.route('/personal/<int:trab_id>/formato_salida')
@solo_admin_o_mantenimiento
def formato_salida_trabajador(trab_id):
    """Descarga el formato R-AP-33-01-02 (.xlsx) con los consumos del trabajador."""
    from flask import send_file
    from ..utils.formatos import generar_xlsx_salida_trabajador
    trabajador = Trabajador.query.get_or_404(trab_id)
    items = _items_consumos_trabajador(trab_id)
    buffer = generar_xlsx_salida_trabajador(trabajador.nombre, items=items, area=trabajador.area)
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f'R-AP-33-01-02_Salida_{trabajador.nombre}.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


@mantenimiento_bp.route('/personal/<int:trab_id>/informe-general')
@solo_admin_o_mantenimiento
def informe_general_trabajador(trab_id):
    """Descarga un libro Excel con dos hojas (Entrada + Salida) con los consumos del trabajador."""
    from flask import send_file
    from ..utils.formatos import generar_xlsx_informe_general
    trabajador = Trabajador.query.get_or_404(trab_id)
    items = _items_consumos_trabajador(trab_id)
    buffer = generar_xlsx_informe_general(trabajador.nombre, area=trabajador.area, items=items)
    nombre_safe = trabajador.nombre.replace(' ', '_')
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f'Informe_General_{nombre_safe}.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )



# ═══════════════════════════════════════════════════════════════════════════════
# PRÉSTAMOS
# ═══════════════════════════════════════════════════════════════════════════════
# HERRAMIENTAS
# ═══════════════════════════════════════════════════════════════════════════════

@mantenimiento_bp.route('/herramientas')
@solo_admin_o_mantenimiento
def herramientas():
    lista = Herramienta.query.order_by(Herramienta.nombre).all()
    return render_template('mantenimiento/herramientas.html', herramientas=lista)

@mantenimiento_bp.route('/herramienta/nueva', methods=['GET', 'POST'])
@mantenimiento_bp.route('/herramienta/<int:id>/editar', methods=['GET', 'POST'])
@solo_admin_o_mantenimiento
def herramienta_form(id=None):
    herramienta = Herramienta.query.get_or_404(id) if id else Herramienta()
    if request.method == 'POST':
        herramienta.nombre = request.form['nombre'].strip()
        herramienta.marca = request.form.get('marca', '').strip()
        herramienta.modelo = request.form.get('modelo', '').strip()
        herramienta.codigo = request.form.get('codigo', '').strip()
        herramienta.estado_fisico = request.form.get('estado_fisico', 'bueno')
        
        if not id:
            db.session.add(herramienta)
        db.session.commit()
        flash(f'Herramienta "{herramienta.nombre}" guardada.', 'success')
        return redirect(url_for('mantenimiento.herramientas'))
    return render_template('mantenimiento/herramienta_form.html', herramienta=herramienta)


# ═══════════════════════════════════════════════════════════════════════════════
# PRÉSTAMOS DE HERRAMIENTAS
# ═══════════════════════════════════════════════════════════════════════════════

@mantenimiento_bp.route('/prestamos')
@solo_admin_o_mantenimiento
def prestamos():
    lista = Prestamo.query.order_by(Prestamo.fecha_prestamo.desc()).all()
    return render_template('mantenimiento/prestamos.html', prestamos=lista)

@mantenimiento_bp.route('/prestamo/nuevo', methods=['GET', 'POST'])
@solo_admin_o_mantenimiento
def prestamo_form():
    if request.method == 'POST':
        id_herramienta = int(request.form['id_herramienta'])
        id_trabajador  = int(request.form['id_trabajador'])
        notas          = request.form.get('notas', '')

        herramienta = Herramienta.query.get_or_404(id_herramienta)
        if not herramienta.disponible:
            flash(f'La herramienta ya está prestada.', 'danger')
            return redirect(url_for('mantenimiento.prestamo_form'))

        prestamo = Prestamo(
            id_herramienta    = id_herramienta,
            id_trabajador     = id_trabajador,
            id_usuario_presta = current_user.id,
            notas             = notas
        )
        herramienta.disponible = False
        db.session.add(prestamo)
        db.session.commit()
        flash('Préstamo registrado exitosamente.', 'success')
        return redirect(url_for('mantenimiento.prestamos'))

    herramientas = Herramienta.query.filter_by(disponible=True, activo=True).order_by(Herramienta.nombre).all()
    trabajadores = Trabajador.query.filter_by(activo=True).order_by(Trabajador.nombre).all()
    return render_template('mantenimiento/prestamo_form.html',
                           herramientas=herramientas, trabajadores=trabajadores)

@mantenimiento_bp.route('/prestamo/<int:prestamo_id>/devolver', methods=['POST'])
@solo_admin_o_mantenimiento
def devolver_prestamo(prestamo_id):
    prestamo = Prestamo.query.get_or_404(prestamo_id)
    if prestamo.estado == 'prestado':
        prestamo.estado           = 'devuelto'
        prestamo.fecha_devolucion = datetime.utcnow()
        prestamo.herramienta.disponible = True
        
        # Opcional: Actualizar el estado físico si se reporta en la devolución
        estado_fisico = request.form.get('estado_fisico')
        if estado_fisico:
            prestamo.herramienta.estado_fisico = estado_fisico

        db.session.commit()
        flash('Herramienta devuelta a la bodega.', 'success')
    return redirect(url_for('mantenimiento.prestamos'))


# ═══════════════════════════════════════════════════════════════════════════════
# API JSON — Stock en tiempo real (para badge/panel)
# ═══════════════════════════════════════════════════════════════════════════════

@mantenimiento_bp.route('/api/bajo-stock')
@solo_admin_o_mantenimiento
def api_bajo_stock():
    count = Material.query.filter(Material.stock_actual <= Material.stock_minimo).count()
    return jsonify({'count': count})


# ═══════════════════════════════════════════════════════════════════════════════
# ESTADÍSTICAS POR TRABAJADOR
# ═══════════════════════════════════════════════════════════════════════════════

@mantenimiento_bp.route('/personal/<int:trab_id>/estadisticas')
@solo_admin_o_mantenimiento
def estadisticas_trabajador(trab_id):
    """Muestra las estadísticas individuales de un trabajador:
       préstamos (Prestamo), salidas del stock propio (MovimientoStockMant)
       y gasto estimado basado en precio_ref del StockMantenimiento."""
    from decimal import Decimal

    trabajador = Trabajador.query.get_or_404(trab_id)

    # ─ Préstamos de herramientas (tabla Prestamos) ───────────────────────
    # NOTA: solo existen si se registraron manualmente desde la sección Préstamos.
    # Si no hay historial, todos los contadores quedarán en 0 (estado vacío correcto).
    prestamos_activos   = Prestamo.query.filter_by(
        id_trabajador=trab_id, estado='prestado').count()
    prestamos_devueltos = Prestamo.query.filter_by(
        id_trabajador=trab_id, estado='devuelto').count()
    prestamos_total     = prestamos_activos + prestamos_devueltos
    historial_prestamos = (Prestamo.query
                           .filter_by(id_trabajador=trab_id)
                           .order_by(Prestamo.fecha_prestamo.desc())
                           .limit(20).all())

    # Gasto estimado por préstamos de herramientas (si aplica, usualmente las herramientas no se consumen pero podemos omitirlo)
    # Ya que ahora las herramientas no tienen "precio_unitario" en este modelo o no se cobran igual.
    # Por ahora lo dejaremos en 0 o simplemente listaremos el historial.
    gasto_prestamos = Decimal('0.00')

    # ─ Consumos/salidas atribuidos — stock PROPIO de Mantenimiento ────────
    # Se usan MovimientoStockMant con tipo='salida' e id_trabajador directo.
    # Solo estarán disponibles una vez que se registren salidas en el stock.
    consumos_attr = (MovimientoStockMant.query
                     .filter_by(id_trabajador=trab_id, tipo='salida')
                     .order_by(desc(MovimientoStockMant.fecha))
                     .limit(20).all())
    num_consumos = len(consumos_attr)

    gasto_consumos = Decimal('0.00')
    for c in MovimientoStockMant.query.filter_by(
            id_trabajador=trab_id, tipo='salida').all():
        if c.item and c.item.precio_ref:
            gasto_consumos += Decimal(str(c.item.precio_ref)) * c.cantidad

    gasto_total = gasto_prestamos + gasto_consumos

    # ─ Pedidos de equipo ──────────────────────────────────────────────────
    pedidos_equipo = trabajador.pedidos_equipo

    # ─ ¿Hay historial de entregas (salidas) registradas? ─────────────────
    tiene_historial = (MovimientoStockMant.query
                       .filter(MovimientoStockMant.tipo == 'salida')
                       .first()) is not None

    return render_template('mantenimiento/estadisticas_trabajador.html',
                           trabajador=trabajador,
                           prestamos_activos=prestamos_activos,
                           prestamos_devueltos=prestamos_devueltos,
                           prestamos_total=prestamos_total,
                           historial_prestamos=historial_prestamos,
                           num_consumos=num_consumos,
                           consumos_attr=consumos_attr,
                           gasto_prestamos=gasto_prestamos,
                           gasto_consumos=gasto_consumos,
                           gasto_total=gasto_total,
                           pedidos_equipo=pedidos_equipo,
                           tiene_historial=tiene_historial)


# ═══════════════════════════════════════════════════════════════════════════════
# PEDIDOS DE EQUIPO — Solicitudes del personal al administrador
# ═══════════════════════════════════════════════════════════════════════════════

@mantenimiento_bp.route('/pedidos-equipo')
@solo_admin_o_mantenimiento
def pedidos_equipo():
    """Lista todos los pedidos de equipo al administrador."""
    estado_f = request.args.get('estado', '')
    q        = request.args.get('q', '').strip()

    query = PedidoEquipo.query.order_by(desc(PedidoEquipo.fecha_pedido))
    if estado_f in PedidoEquipo.ESTADOS:
        query = query.filter_by(estado=estado_f)
    if q:
        query = (query
                 .join(Trabajador)
                 .filter(Trabajador.nombre.ilike(f'%{q}%')))

    lista = query.all()
    trabajadores = Trabajador.query.filter_by(activo=True).order_by(Trabajador.nombre).all()

    # Para pedidos aprobados/entregados, cargar en una sola query los ítems de
    # stock vinculados a cada pedido (sin N+1).
    ids_pedidos = [p.id for p in lista]
    stock_por_pedido = {}
    if ids_pedidos:
        items_vinculados = (StockMantenimiento.query
                            .filter(StockMantenimiento.id_pedido_equipo.in_(ids_pedidos))
                            .order_by(StockMantenimiento.nombre)
                            .all())
        for item in items_vinculados:
            stock_por_pedido.setdefault(item.id_pedido_equipo, []).append(item)

    return render_template('mantenimiento/pedidos_equipo.html',
                           pedidos=lista,
                           estado_f=estado_f,
                           q=q,
                           trabajadores=trabajadores,
                           stock_por_pedido=stock_por_pedido)


@mantenimiento_bp.route('/pedidos-equipo/nuevo', methods=['GET', 'POST'])
@solo_admin_o_mantenimiento
def pedido_equipo_form():
    """Formulario para crear un nuevo pedido de equipo al administrador."""
    import json
    trabajadores = Trabajador.query.filter_by(activo=True).order_by(Trabajador.nombre).all()

    if request.method == 'POST':
        id_trabajador = request.form.get('id_trabajador', type=int)
        descripcion   = request.form.get('descripcion', '').strip()

        # Items dinámicos: qty[], unit[], desc[]
        qtys  = request.form.getlist('qty[]')
        units = request.form.getlist('unit[]')
        descs = request.form.getlist('desc[]')
        items = []
        for q_val, u_val, d_val in zip(qtys, units, descs):
            q_val = q_val.strip(); u_val = u_val.strip(); d_val = d_val.strip()
            if d_val:
                items.append({'cantidad': q_val or '1', 'unidad': u_val, 'descripcion': d_val})

        if not id_trabajador or not descripcion:
            flash('Selecciona un trabajador e ingresa una descripción del pedido.', 'warning')
            return render_template('mantenimiento/pedido_equipo_form.html',
                                   trabajadores=trabajadores)

        pedido = PedidoEquipo(
            folio         = PedidoEquipo.generar_folio(),
            id_trabajador = id_trabajador,
            id_usuario    = current_user.id,
            descripcion   = descripcion,
        )
        pedido.set_items(items)
        db.session.add(pedido)
        db.session.commit()
        flash(f'Pedido {pedido.folio} registrado y enviado al administrador.', 'success')
        return redirect(url_for('mantenimiento.pedidos_equipo'))

    return render_template('mantenimiento/pedido_equipo_form.html',
                           trabajadores=trabajadores)


@mantenimiento_bp.route('/pedidos-equipo/<int:pedido_id>/resolver', methods=['POST'])
@solo_admin_o_mantenimiento
def resolver_pedido_equipo(pedido_id):
    """El administrador aprueba, rechaza o marca como entregado un pedido de equipo."""
    pedido     = PedidoEquipo.query.get_or_404(pedido_id)
    nuevo_estado = request.form.get('estado', '')
    notas_admin  = request.form.get('notas_admin', '').strip()

    if nuevo_estado not in PedidoEquipo.ESTADOS:
        flash('Estado no válido.', 'warning')
        return redirect(url_for('mantenimiento.pedidos_equipo'))

    pedido.estado      = nuevo_estado
    pedido.notas_admin = notas_admin or pedido.notas_admin
    if nuevo_estado in ('aprobado', 'rechazado', 'entregado'):
        pedido.fecha_resolucion = datetime.utcnow()
    db.session.commit()
    flash(f'Pedido {pedido.folio} actualizado a “{nuevo_estado}”.', 'success')
    return redirect(url_for('mantenimiento.pedidos_equipo'))


@mantenimiento_bp.route('/pedidos-equipo/<int:pedido_id>/descargar-xlsx')
@solo_admin_o_mantenimiento
def descargar_xlsx_pedido_equipo(pedido_id):
    """Descarga el formato R-AP-33-01-01 real (.xlsx) pre-llenado con los items del pedido."""
    from flask import send_file
    from ..utils.formatos import generar_xlsx_pedido_trabajador

    pedido     = PedidoEquipo.query.get_or_404(pedido_id)
    trabajador = pedido.trabajador
    items      = pedido.get_items()  # list of {cantidad, unidad, descripcion}

    # Adaptar keys al formato esperado por la función
    items_fmt = [{'cantidad': i.get('cantidad', 1),
                  'unidad':   i.get('unidad', 'pza'),
                  'descripcion': i.get('descripcion', '')}
                 for i in items]

    buffer = generar_xlsx_pedido_trabajador(trabajador.nombre, items=items_fmt)
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f'{pedido.folio}_Requisicion_{trabajador.nombre}.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SOLICITAR MATERIAL AL ALMACÉN GENERAL — Mantenimiento como solicitante
# (Sin acceso a precios; reutiliza el flujo de Pedido/DetallePedido)
# ═══════════════════════════════════════════════════════════════════════════════

@mantenimiento_bp.route('/solicitar-material')
@solo_admin_o_mantenimiento
def solicitar_material():
    """Catálogo del almacén general para que Mantenimiento pueda hacer requisiciones.
    Se muestran materiales disponibles SIN precios."""
    from ..models import Material, Categoria, Pedido
    from sqlalchemy import and_

    depto = current_user.departamento

    if not depto:
        flash('Tu usuario no tiene un departamento asignado. Contacta al administrador.', 'danger')
        return render_template('mantenimiento/solicitar_material.html',
                               catalogo={}, departamento=None)

    ids_categorias = [c.id for c in depto.categorias]

    materiales = (Material.query
                  .join(Categoria)
                  .filter(
                      Material.id_categoria.in_(ids_categorias),
                      Material.publicado == True,
                      Material.stock_actual > 0,
                  )
                  .order_by(Categoria.nombre, Material.nombre)
                  .all())

    catalogo_agrupado = {}
    for mat in materiales:
        cat_nombre = mat.categoria.nombre
        catalogo_agrupado.setdefault(cat_nombre, []).append(mat)

    return render_template('mantenimiento/solicitar_material.html',
                           catalogo=catalogo_agrupado,
                           departamento=depto)


@mantenimiento_bp.route('/solicitar-material/nuevo', methods=['POST'])
@solo_admin_o_mantenimiento
def nueva_requisicion_mant():
    """Crea un Pedido (requisición) desde el módulo de mantenimiento.
    Igual que solicitante, pero sin precios expuestos."""
    from ..models import Material, Categoria, Pedido, DetallePedido

    ids_materiales = request.form.getlist('material_id')
    cantidades     = request.form.getlist('cantidad')
    notas          = request.form.get('notas_solicitante', '').strip()

    if not ids_materiales:
        flash('La requisición no puede estar vacía.', 'warning')
        return redirect(url_for('mantenimiento.solicitar_material'))

    depto = current_user.departamento
    if not depto:
        flash('Sin departamento asignado. Contacta al administrador.', 'danger')
        return redirect(url_for('mantenimiento.solicitar_material'))

    ids_categorias_ok = {c.id for c in depto.categorias}

    pedido = Pedido(
        folio             = Pedido.generar_folio(),
        id_solicitante    = current_user.id,
        id_departamento   = depto.id,
        estado            = 'pendiente',
        notas_solicitante = notas,
    )
    db.session.add(pedido)
    db.session.flush()

    errores = []
    for mat_id, cant_str in zip(ids_materiales, cantidades):
        try:
            cant = int(cant_str)
            if cant <= 0:
                continue
        except ValueError:
            continue

        material = Material.query.get(mat_id)
        if not material:
            errores.append(f'Material {mat_id} no existe.')
            continue
        if material.id_categoria not in ids_categorias_ok:
            errores.append(f'{material.nombre}: sin permiso.')
            continue
        if material.stock_actual < cant:
            errores.append(
                f'{material.nombre}: stock insuficiente (disponible: {material.stock_actual}).'
            )
            continue

        detalle = DetallePedido(
            id_pedido           = pedido.id,
            id_material         = material.id,
            cantidad_solicitada = cant,
            # No guardamos precio para mantenimiento, se deja en 0
            precio_unitario_ref = 0,
        )
        db.session.add(detalle)

    if errores:
        db.session.rollback()
        for e in errores:
            flash(e, 'danger')
        return redirect(url_for('mantenimiento.solicitar_material'))

    db.session.commit()

    try:
        from ..utils.formatos import generar_formato_pedido
        generar_formato_pedido(pedido)
    except Exception as e:
        print(f'[WARN] No se pudo generar formato: {e}')

    flash(f'Requisición {pedido.folio} enviada al administrador correctamente.', 'success')
    return redirect(url_for('mantenimiento.mis_requisiciones_mant'))


@mantenimiento_bp.route('/mis-requisiciones')
@solo_admin_o_mantenimiento
def mis_requisiciones_mant():
    """Historial de requisiciones generadas por el usuario de mantenimiento."""
    import os
    from ..models import Pedido

    pedidos = (Pedido.query
               .filter_by(id_solicitante=current_user.id)
               .order_by(Pedido.fecha_solicitud.desc())
               .all())

    base_pedidos = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'static', 'uploads', 'requisiciones', 'pedidos'
    )
    base_salidas = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'static', 'uploads', 'requisiciones', 'salidas'
    )

    formatos = {}
    for p in pedidos:
        pedido_path = os.path.join(base_pedidos, f'{p.folio}_requisicion.xlsx')
        salida_path = os.path.join(base_salidas, f'{p.folio}_salida.xlsx')

        if not os.path.exists(pedido_path):
            try:
                from ..utils.formatos import generar_formato_pedido
                generar_formato_pedido(p)
            except Exception:
                pass

        formatos[p.id] = {
            'tiene_pedido': os.path.exists(pedido_path),
            'tiene_salida': os.path.exists(salida_path) and p.estado in ('aprobado', 'entregado', 'modificado'),
        }

    return render_template('mantenimiento/mis_requisiciones.html',
                           pedidos=pedidos, formatos=formatos)


@mantenimiento_bp.route('/mis-requisiciones/<int:pedido_id>/pedido.xlsx')
@solo_admin_o_mantenimiento
def descargar_requisicion_mant_xlsx(pedido_id):
    """Descarga el formato xlsx de una requisición del módulo mantenimiento."""
    import os
    from flask import send_file
    from ..models import Pedido

    pedido = Pedido.query.get_or_404(pedido_id)
    if pedido.id_solicitante != current_user.id:
        flash('No tienes acceso a esta requisición.', 'danger')
        return redirect(url_for('mantenimiento.mis_requisiciones_mant'))

    ruta = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'static', 'uploads', 'requisiciones', 'pedidos',
        f'{pedido.folio}_requisicion.xlsx'
    )

    if not os.path.exists(ruta):
        try:
            from ..utils.formatos import generar_formato_pedido
            generar_formato_pedido(pedido)
        except Exception:
            flash('No se pudo generar el formato.', 'danger')
            return redirect(url_for('mantenimiento.mis_requisiciones_mant'))

    return send_file(ruta, as_attachment=True,
                     download_name=f'{pedido.folio}_requisicion.xlsx')


# ═══════════════════════════════════════════════════════════════════════════════
# ÓRDENES DE SERVICIO DE MANTENIMIENTO
# ═══════════════════════════════════════════════════════════════════════════════

@mantenimiento_bp.route('/ordenes-servicio')
@solo_admin_o_mantenimiento
def ordenes_servicio():
    """Lista todas las órdenes de servicio recibidas de solicitantes."""
    estado_f = request.args.get('estado', '')
    q        = request.args.get('q', '').strip()

    query = OrdenServicio.query.order_by(desc(OrdenServicio.fecha_solicitud))
    if estado_f in OrdenServicio.ESTADOS:
        query = query.filter_by(estado=estado_f)
    if q:
        from ..models import Usuario
        query = query.join(Usuario, OrdenServicio.id_solicitante == Usuario.id).filter(
            Usuario.nombre_completo.ilike(f'%{q}%')
        )

    ordenes = query.all()
    return render_template('mantenimiento/ordenes_servicio.html',
                           ordenes=ordenes, estado_f=estado_f, q=q,
                           ESTADOS=OrdenServicio.ESTADOS)


@mantenimiento_bp.route('/ordenes-servicio/<int:orden_id>/procesar', methods=['POST'])
@solo_admin_o_mantenimiento
def procesar_orden(orden_id):
    """Marca la orden como en_proceso."""
    orden = OrdenServicio.query.get_or_404(orden_id)
    if orden.estado == 'solicitada':
        orden.estado = 'en_proceso'
        db.session.commit()
        flash(f'Orden {orden.folio} marcada como en proceso.', 'success')
    return redirect(url_for('mantenimiento.ordenes_servicio'))


@mantenimiento_bp.route('/ordenes-servicio/<int:orden_id>/completar', methods=['GET', 'POST'])
@solo_admin_o_mantenimiento
def completar_orden(orden_id):
    """Formulario para registrar el resultado del servicio."""
    orden = OrdenServicio.query.get_or_404(orden_id)
    if orden.estado not in ('solicitada', 'en_proceso'):
        flash('Esta orden ya fue procesada.', 'info')
        return redirect(url_for('mantenimiento.ordenes_servicio'))

    trabajadores = Trabajador.query.filter_by(activo=True).order_by(Trabajador.nombre).all()

    if request.method == 'POST':
        fecha_str       = request.form.get('fecha_ejecucion', '').strip()
        realizado_str   = request.form.get('servicio_realizado', '')
        motivo          = request.form.get('motivo_no_realizado', '').strip()
        id_trab         = request.form.get('id_trabajador_realizo', type=int)
        notas           = request.form.get('notas_mantenimiento', '').strip()

        try:
            fecha_ej = datetime.strptime(fecha_str, '%Y-%m-%d') if fecha_str else datetime.utcnow()
        except ValueError:
            fecha_ej = datetime.utcnow()

        realizado = realizado_str == 'si'

        orden.fecha_ejecucion       = fecha_ej
        orden.servicio_realizado    = realizado
        orden.motivo_no_realizado   = motivo if not realizado else None
        orden.id_trabajador_realizo = id_trab
        orden.notas_mantenimiento   = notas
        orden.estado = 'completada' if realizado else 'no_realizada'
        db.session.commit()
        flash(f'Orden {orden.folio} registrada como {"completada" if realizado else "no realizada"}.', 'success')
        return redirect(url_for('mantenimiento.firmar_orden', orden_id=orden.id))

    return render_template('mantenimiento/completar_orden.html',
                           orden=orden, trabajadores=trabajadores, now=datetime.utcnow())


@mantenimiento_bp.route('/ordenes-servicio/<int:orden_id>/firmar', methods=['GET', 'POST'])
@solo_admin_o_mantenimiento
def firmar_orden(orden_id):
    """
    Permite al personal de mantenimiento seleccionar las firmas y 'Entregar' la orden.
    Firmas requeridas: Realizó (Trabajador), Supervisó (usuario actual), Conformidad (solicitante).
    """
    orden = OrdenServicio.query.get_or_404(orden_id)
    if orden.estado not in ('completada', 'no_realizada'):
        flash('La orden debe estar completada para firmar.', 'warning')
        return redirect(url_for('mantenimiento.ordenes_servicio'))

    trabajadores_con_firma = (Trabajador.query
                              .join(FirmaTrabajador,
                                    FirmaTrabajador.id_trabajador == Trabajador.id)
                              .filter(Trabajador.activo == True)
                              .order_by(Trabajador.nombre).all())
    # La firma del supervisó es la del usuario actual de mantenimiento
    mi_firma = FirmaUsuario.query.filter_by(id_usuario=current_user.id).first()
    # La firma del solicitante
    firma_solicitante = FirmaUsuario.query.filter_by(
        id_usuario=orden.id_solicitante
    ).first()

    if request.method == 'POST':
        accion = request.form.get('accion', '')

        if accion == 'entregar':
            id_trab_firma = request.form.get('id_trabajador_firma', type=int)

            # Firma del técnico que realizó
            firma_trab_obj = FirmaTrabajador.query.filter_by(
                id_trabajador=id_trab_firma
            ).first() if id_trab_firma else None

            if not firma_trab_obj:
                flash('Selecciona un técnico con firma registrada para "Realizó".', 'warning')
            elif not mi_firma:
                flash('Debes registrar tu firma primero (sección "Mi Firma").', 'warning')
            else:
                from flask import current_app
                from ..utils.firma_digital import firmar_orden as generar_hmac

                trab = Trabajador.query.get(id_trab_firma)
                orden.firma_realizo_b64      = firma_trab_obj.firma_b64
                orden.nombre_realizo         = trab.nombre if trab else ''
                orden.firma_superviso_b64    = mi_firma.firma_b64
                orden.nombre_superviso       = current_user.nombre_completo
                orden.firma_solicitante_b64  = firma_solicitante.firma_b64 if firma_solicitante else None
                orden.nombre_solicitante_firma = orden.solicitante.nombre_completo
                orden.estado         = 'entregada'
                orden.fecha_entrega  = datetime.utcnow()

                # Firma digital HMAC-SHA256 — usa clave dedicada separada de sesiones
                secret = current_app.config.get('FIRMA_SECRET_KEY', '')
                canonical, hmac_hex = generar_hmac(orden, secret)
                orden.firma_tipo      = 'hmac_sha256'
                orden.firma_hmac      = hmac_hex
                orden.firma_canonical = canonical

                # Generar PDF
                try:
                    from ..utils.orden_servicio_pdf import guardar_pdf_orden
                    import os
                    directorio = os.path.join(
                        os.path.dirname(os.path.dirname(__file__)),
                        'static', 'uploads', 'ordenes_servicio'
                    )
                    ruta_abs = guardar_pdf_orden(orden, directorio)
                    ruta_rel = os.path.relpath(
                        ruta_abs,
                        os.path.dirname(os.path.dirname(__file__))
                    )
                    orden.archivo_docx_path = ruta_rel
                except Exception as e:
                    flash(f'Orden entregada pero no se pudo generar el documento: {e}', 'warning')

                db.session.commit()
                flash(f'Orden {orden.folio} entregada y documento generado.', 'success')
                return redirect(url_for('mantenimiento.ordenes_servicio'))

    return render_template('mantenimiento/firmar_orden.html',
                           orden=orden,
                           trabajadores_con_firma=trabajadores_con_firma,
                           mi_firma=mi_firma,
                           firma_solicitante=firma_solicitante)


@mantenimiento_bp.route('/ordenes-servicio/<int:orden_id>/descargar')
@solo_admin_o_mantenimiento
def descargar_orden_docx(orden_id):
    """Descarga el PDF generado de la orden de servicio."""
    import os
    from flask import send_file
    orden = OrdenServicio.query.get_or_404(orden_id)
    if not orden.archivo_docx_path:
        flash('Documento no generado aún.', 'warning')
        return redirect(url_for('mantenimiento.ordenes_servicio'))
    ruta = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), orden.archivo_docx_path
    )
    if not os.path.exists(ruta):
        flash('Archivo no encontrado en disco.', 'danger')
        return redirect(url_for('mantenimiento.ordenes_servicio'))
    return send_file(ruta, as_attachment=True,
                     mimetype='application/pdf',
                     download_name=f'{orden.folio}_OrdenServicio.pdf')


@mantenimiento_bp.route('/mi-firma', methods=['GET', 'POST'])
@solo_admin_o_mantenimiento
def mi_firma_mant():
    """Guarda la firma digital del usuario de mantenimiento."""
    firma_obj = FirmaUsuario.query.filter_by(id_usuario=current_user.id).first()
    _MAX_FIRMA = 600_000
    if request.method == 'POST':
        firma_b64 = request.form.get('firma_b64', '').strip()
        if not firma_b64 or len(firma_b64) < 100:
            flash('Firma inválida.', 'warning')
        elif len(firma_b64) > _MAX_FIRMA:
            flash('La firma excede el tamaño máximo permitido.', 'danger')
        else:
            if firma_obj:
                firma_obj.firma_b64 = firma_b64
            else:
                firma_obj = FirmaUsuario(id_usuario=current_user.id, firma_b64=firma_b64)
                db.session.add(firma_obj)
            db.session.commit()
            flash('Firma guardada.', 'success')
            return redirect(url_for('mantenimiento.mi_firma_mant'))
    return render_template('mantenimiento/mi_firma.html', firma_obj=firma_obj)


@mantenimiento_bp.route('/trabajador/<int:trab_id>/firma', methods=['GET', 'POST'])
@solo_admin_o_mantenimiento
def firma_trabajador(trab_id):
    """Gestiona la firma digital de un trabajador (técnico)."""
    trabajador = Trabajador.query.get_or_404(trab_id)
    firma_obj  = FirmaTrabajador.query.filter_by(id_trabajador=trab_id).first()
    _MAX_FIRMA = 600_000
    if request.method == 'POST':
        firma_b64 = request.form.get('firma_b64', '').strip()
        if not firma_b64 or len(firma_b64) < 100:
            flash('Firma inválida.', 'warning')
        elif len(firma_b64) > _MAX_FIRMA:
            flash('La firma excede el tamaño máximo permitido.', 'danger')
        else:
            if firma_obj:
                firma_obj.firma_b64 = firma_b64
            else:
                firma_obj = FirmaTrabajador(id_trabajador=trab_id, firma_b64=firma_b64)
                db.session.add(firma_obj)
            db.session.commit()
            flash(f'Firma de {trabajador.nombre} guardada.', 'success')
            return redirect(url_for('mantenimiento.personal'))
    return render_template('mantenimiento/firma_trabajador.html',
                           trabajador=trabajador, firma_obj=firma_obj)



# ═══════════════════════════════════════════════════════════════════════════════
# PRÉSTAMO DE EQUIPO AUDIOVISUAL
# ═══════════════════════════════════════════════════════════════════════════════

@mantenimiento_bp.route('/audiovisual')
@solo_admin_o_mantenimiento
def audiovisual():
    """Lista todos los dispositivos AV con su disponibilidad actual."""
    dispositivos = DispositivoAV.query.filter_by(activo=True).order_by(
        DispositivoAV.aula, DispositivoAV.nombre).all()
    return render_template('mantenimiento/audiovisual.html', dispositivos=dispositivos)


@mantenimiento_bp.route('/audiovisual/dispositivo/nuevo', methods=['GET', 'POST'])
@solo_admin_o_mantenimiento
def audiovisual_dispositivo_form():
    """Alta de nuevo dispositivo AV."""
    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        aula   = request.form.get('aula', '').strip()
        if not nombre or not aula:
            flash('Nombre y aula son obligatorios.', 'warning')
        else:
            db.session.add(DispositivoAV(nombre=nombre, aula=aula))
            db.session.commit()
            flash(f'Dispositivo "{nombre}" registrado en {aula}.', 'success')
            return redirect(url_for('mantenimiento.audiovisual'))
    return render_template('mantenimiento/audiovisual_dispositivo_form.html')


@mantenimiento_bp.route('/audiovisual/prestamo/<int:disp_id>', methods=['GET', 'POST'])
@solo_admin_o_mantenimiento
def audiovisual_prestamo(disp_id):
    """Registra un nuevo préstamo de un dispositivo AV."""
    from datetime import timedelta
    disp = DispositivoAV.query.get_or_404(disp_id)

    if not disp.disponible:
        flash(f'"{disp.nombre}" ya está prestado.', 'warning')
        return redirect(url_for('mantenimiento.audiovisual'))

    if request.method == 'POST':
        nombre_alumno = request.form.get('nombre_alumno', '').strip()
        if not nombre_alumno:
            flash('El nombre del alumno es obligatorio.', 'warning')
        else:
            ahora = datetime.utcnow()
            prestamo = PrestamoAV(
                id_dispositivo          = disp.id,
                aula                    = request.form.get('aula', '').strip(),
                profesor                = request.form.get('profesor', '').strip(),
                nombre_alumno           = nombre_alumno,
                carrera                 = request.form.get('carrera', '').strip(),
                matricula               = request.form.get('matricula', '').strip(),
                telefono                = request.form.get('telefono', '').strip(),
                fecha_prestamo          = ahora,
                hora_devolucion_esperada= ahora + timedelta(hours=2),
                estado                  = 'prestado',
            )
            db.session.add(prestamo)
            db.session.commit()
            flash(f'Préstamo registrado. Devolución esperada a las '
                  f'{prestamo.hora_devolucion_esperada.strftime("%H:%M")}.', 'success')
            return redirect(url_for('mantenimiento.audiovisual'))

    return render_template('mantenimiento/audiovisual_prestamo_form.html', disp=disp)


@mantenimiento_bp.route('/audiovisual/devolucion/<int:prestamo_id>', methods=['GET', 'POST'])
@solo_admin_o_mantenimiento
def audiovisual_devolucion(prestamo_id):
    """Registra la devolución de un dispositivo; aplica sanción si hubo daño."""
    prestamo = PrestamoAV.query.get_or_404(prestamo_id)
    if prestamo.estado != 'prestado':
        flash('Este préstamo ya fue cerrado.', 'info')
        return redirect(url_for('mantenimiento.audiovisual'))

    if request.method == 'POST':
        condicion_ok = request.form.get('condicion') == 'ok'
        nota         = request.form.get('nota_sancion', '').strip()

        prestamo.fecha_devolucion_real = datetime.utcnow()
        prestamo.condicion_ok          = condicion_ok
        prestamo.nota_sancion          = nota if not condicion_ok else None
        prestamo.estado                = 'devuelto' if condicion_ok else 'sancionado'
        db.session.commit()

        if condicion_ok:
            flash('Devolución registrada correctamente.', 'success')
        else:
            flash(f'Sanción aplicada a {prestamo.nombre_alumno}.', 'warning')
        return redirect(url_for('mantenimiento.audiovisual'))

    return render_template('mantenimiento/audiovisual_devolucion.html',
                           prestamo=prestamo, now=datetime.utcnow())


@mantenimiento_bp.route('/audiovisual/historial')
@solo_admin_o_mantenimiento
def audiovisual_historial():
    """Historial completo de préstamos AV con filtros."""
    estado_f = request.args.get('estado', '')
    q        = request.args.get('q', '').strip()

    query = PrestamoAV.query.order_by(PrestamoAV.fecha_prestamo.desc())
    if estado_f in PrestamoAV.ESTADOS:
        query = query.filter_by(estado=estado_f)
    if q:
        query = query.filter(PrestamoAV.nombre_alumno.ilike(f'%{q}%'))

    prestamos = query.all()
    return render_template('mantenimiento/audiovisual_historial.html',
                           prestamos=prestamos, estado_f=estado_f, q=q,
                           ESTADOS=PrestamoAV.ESTADOS)


# ═══════════════════════════════════════════════════════════════════════════════
# ESTADÍSTICAS SEMESTRALES DE ENCUESTAS DE SATISFACCIÓN
# ═══════════════════════════════════════════════════════════════════════════════

@mantenimiento_bp.route('/encuestas/estadisticas')
@solo_admin_o_mantenimiento
def estadisticas_encuestas():
    """Estadísticas históricas semestrales de encuestas de satisfacción."""
    from sqlalchemy import func, extract, case

    # Calcular semestre: Ene-Jun = 1, Jul-Dic = 2
    ordenes = (OrdenServicio.query
               .filter(OrdenServicio.encuesta_completada == True)
               .order_by(OrdenServicio.fecha_solicitud.desc())
               .all())

    # Agrupar por año-semestre
    semestres = {}
    for o in ordenes:
        anio = o.fecha_solicitud.year
        sem  = 1 if o.fecha_solicitud.month <= 6 else 2
        clave = (anio, sem)
        if clave not in semestres:
            semestres[clave] = {
                'anio': anio, 'semestre': sem,
                'total': 0,
                'exp': [], 'prof': [], 'calidad': [], 'com': [], 'tiempo': [],
                'comentarios': [],
            }
        g = semestres[clave]
        g['total'] += 1
        if o.enc_experiencia:     g['exp'].append(o.enc_experiencia)
        if o.enc_profesionalismo: g['prof'].append(o.enc_profesionalismo)
        if o.enc_calidad:         g['calidad'].append(o.enc_calidad)
        if o.enc_comunicacion:    g['com'].append(o.enc_comunicacion)
        if o.enc_tiempo_respuesta:g['tiempo'].append(o.enc_tiempo_respuesta)
        if o.enc_comentarios:     g['comentarios'].append(o.enc_comentarios)

    def avg(lst): return round(sum(lst) / len(lst), 2) if lst else None

    sems = []
    for (anio, sem), g in sorted(semestres.items(), reverse=True):
        sems.append({
            'anio': anio, 'semestre': sem,
            'total': g['total'],
            'avg_experiencia':     avg(g['exp']),
            'avg_profesionalismo': avg(g['prof']),
            'avg_calidad':         avg(g['calidad']),
            'avg_comunicacion':    avg(g['com']),
            'avg_tiempo':          avg(g['tiempo']),
            'comentarios':         g['comentarios'],
        })

    # Totales: órdenes atendidas vs no atendidas (pendientes)
    total_ordenes     = OrdenServicio.query.count()
    total_completadas = OrdenServicio.query.filter(
        OrdenServicio.estado.in_(['completada', 'entregada'])
    ).count()
    total_encuestas   = OrdenServicio.query.filter_by(encuesta_completada=True).count()

    return render_template(
        'mantenimiento/estadisticas_encuestas.html',
        semestres=sems,
        total_ordenes=total_ordenes,
        total_completadas=total_completadas,
        total_encuestas=total_encuestas,
    )
