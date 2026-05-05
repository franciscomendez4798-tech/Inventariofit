# app/admin/routes.py
from datetime import datetime
from functools import wraps
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, jsonify, abort)
from flask_login import login_required, current_user
from sqlalchemy import text, func, desc
from ..models import (Material, Categoria, Proveedor, Pedido, DetallePedido,
                      MovimientoInventario, Departamento, Usuario,
                      ReservaAuditorio, db)

admin_bp = Blueprint('admin', __name__,
                     template_folder='../templates/admin')


def solo_admin(f):
    """Decorador: restringe la ruta solo a usuarios con rol administrador."""
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.es_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated

def solo_admin_o_mantenimiento(f):
    """Decorador: admin o mantenimiento."""
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.es_admin_o_mantenimiento:
            abort(403)
        return f(*args, **kwargs)
    return decorated


# ═══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════

@admin_bp.route('/')
@admin_bp.route('/dashboard')
@solo_admin_o_mantenimiento
def dashboard():
    """
    Prepara estadísticas clave para la vista del dashboard.
    Los datos detallados para Chart.js se sirven vía /api/dashboard (JSON).
    """
    total_materiales  = Material.query.count()
    total_pedidos_hoy = (Pedido.query
                         .filter(func.date(Pedido.fecha_solicitud)
                                 == datetime.utcnow().date())
                         .count())
    pedidos_pendientes = Pedido.query.filter_by(estado='pendiente').count()
    materiales_bajo_stock = (Material.query
                             .filter(Material.stock_actual <= Material.stock_minimo)
                             .count())

    return render_template(
        'admin/dashboard.html',
        stats={
            'total_materiales':       total_materiales,
            'total_pedidos_hoy':      total_pedidos_hoy,
            'pedidos_pendientes':     pedidos_pendientes,
            'materiales_bajo_stock':  materiales_bajo_stock,
        }
    )


# ═══════════════════════════════════════════════════════════════════════════════
# INVENTARIO — CRUD DE MATERIALES
# ═══════════════════════════════════════════════════════════════════════════════

@admin_bp.route('/inventario')
@solo_admin_o_mantenimiento
def inventario():
    """Lista todos los materiales con sus categorías y estado de stock."""
    materiales = (Material.query
                  .join(Categoria)
                  .order_by(Categoria.nombre, Material.nombre)
                  .all())
    return render_template('admin/inventario.html', materiales=materiales)


@admin_bp.route('/material/nuevo', methods=['GET', 'POST'])
@admin_bp.route('/material/<int:mat_id>/editar', methods=['GET', 'POST'])
@solo_admin_o_mantenimiento
def material_form(mat_id=None):
    """Alta y edición de materiales (mismo formulario)."""
    import os
    from werkzeug.utils import secure_filename

    material    = Material.query.get_or_404(mat_id) if mat_id else Material()
    categorias  = Categoria.query.filter_by(activo=True).all()
    proveedores = Proveedor.query.filter_by(activo=True).all()

    EXTENSIONES = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

    if request.method == 'POST':
        material.nombre          = request.form['nombre'].strip()
        material.descripcion     = request.form.get('descripcion', '')
        material.unidad_medida   = request.form['unidad_medida']
        material.stock_actual    = int(request.form.get('stock_actual', 0))
        material.stock_minimo    = int(request.form.get('stock_minimo', 5))
        material.precio_unitario = float(request.form.get('precio_unitario', 0))
        material.id_categoria    = int(request.form['id_categoria'])
        material.id_proveedor    = request.form.get('id_proveedor') or None
        material.publicado       = 'publicado' in request.form

        # ── Manejo de imagen → Supabase Storage ───────────────
        archivo = request.files.get('imagen')
        if archivo and archivo.filename:
            ext = archivo.filename.rsplit('.', 1)[-1].lower()
            if ext in EXTENSIONES:
                import requests as req
                nombre_archivo = secure_filename(
                    f"mat_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{archivo.filename}"
                )
                supabase_url = os.environ.get('SUPABASE_URL', '')
                supabase_key = os.environ.get('SUPABASE_ANON_KEY', '')
                if not supabase_url:
                    flash('SUPABASE_URL no configurada. Imagen no subida.', 'warning')
                    supabase_url = None
                content_type = f'image/{ext}' if ext != 'jpg' else 'image/jpeg'
                upload_url = (
                    f"{supabase_url}/storage/v1/object/materiales/{nombre_archivo}"
                    if supabase_url else None
                )
                if upload_url:
                    resp = req.put(
                        upload_url,
                        data=archivo.read(),
                        headers={
                            'Authorization': f'Bearer {supabase_key}',
                            'Content-Type': content_type,
                            'x-upsert': 'true',
                        },
                        timeout=15,
                    )
                    if resp.status_code in (200, 201):
                        material.imagen_url = (
                            f"{supabase_url}/storage/v1/object/public"
                            f"/materiales/{nombre_archivo}"
                        )
                    else:
                        flash(
                            f'No se pudo subir la imagen (Storage {resp.status_code}).',
                            'warning'
                        )
            else:
                flash('Formato no válido. Usa PNG, JPG, GIF o WebP.', 'warning')

        # Eliminar imagen si se marcó el checkbox
        if request.form.get('eliminar_imagen') and material.imagen_url:
            # Borrar del Storage si es una URL de Supabase
            if 'supabase.co' in (material.imagen_url or ''):
                import requests as req
                supabase_url = os.environ.get('SUPABASE_URL', '')
                supabase_key = os.environ.get('SUPABASE_ANON_KEY', '')
                nombre = material.imagen_url.split('/materiales/')[-1]
                req.delete(
                    f"{supabase_url}/storage/v1/object/materiales/{nombre}",
                    headers={'Authorization': f'Bearer {supabase_key}'},
                    timeout=10,
                )
            material.imagen_url = None

        if not mat_id:
            db.session.add(material)

        db.session.commit()
        flash(f'Material "{material.nombre}" guardado correctamente.', 'success')
        return redirect(url_for('admin.inventario'))

    return render_template(
        'admin/material_form.html',
        material=material,
        categorias=categorias,
        proveedores=proveedores,
    )


@admin_bp.route('/material/<int:mat_id>/toggle-publicado', methods=['POST'])
@solo_admin_o_mantenimiento
def toggle_publicado(mat_id):
    """Alterna la visibilidad de un material en el catálogo de solicitantes."""
    material = Material.query.get_or_404(mat_id)
    material.publicado = not material.publicado
    db.session.commit()
    estado = 'publicado' if material.publicado else 'ocultado'
    flash(f'"{material.nombre}" {estado} del catálogo.', 'info')
    return redirect(url_for('admin.inventario'))


@admin_bp.route('/material/<int:mat_id>/entrada-stock', methods=['POST'])
@solo_admin_o_mantenimiento
def entrada_stock(mat_id):
    """Registra una entrada de stock (compra, donación, etc.)."""
    material = Material.query.get_or_404(mat_id)
    cantidad = int(request.form.get('cantidad', 0))
    motivo   = request.form.get('motivo', 'Entrada manual')

    if cantidad <= 0:
        flash('La cantidad debe ser mayor a cero.', 'warning')
        return redirect(url_for('admin.inventario'))

    material.stock_actual += cantidad

    movimiento = MovimientoInventario(
        id_material      = material.id,
        tipo_movimiento  = 'entrada',
        cantidad         = cantidad,
        stock_resultante = material.stock_actual,
        id_usuario       = current_user.id,
        motivo           = motivo,
    )
    db.session.add(movimiento)
    db.session.commit()
    flash(f'Entrada de {cantidad} {material.unidad_medida} '
          f'de "{material.nombre}" registrada.', 'success')
    return redirect(url_for('admin.inventario'))


# ═══════════════════════════════════════════════════════════════════════════════
# PEDIDOS — APROBACIÓN INTELIGENTE
# ═══════════════════════════════════════════════════════════════════════════════

@admin_bp.route('/pedidos')
@solo_admin_o_mantenimiento
def pedidos():
    """Cola de pedidos pendientes y en revisión."""
    estado_filtro = request.args.get('estado', 'pendiente')
    query = Pedido.query.order_by(Pedido.fecha_solicitud.asc())

    if estado_filtro != 'todos':
        query = query.filter_by(estado=estado_filtro)

    pedidos_lista = query.all()
    return render_template(
        'admin/pedidos.html',
        pedidos=pedidos_lista,
        estado_filtro=estado_filtro,
        estados=Pedido.ESTADOS,
    )


@admin_bp.route('/pedidos/<int:pedido_id>/revisar', methods=['GET', 'POST'])
@solo_admin_o_mantenimiento
def revisar_pedido(pedido_id):
    """
    Vista central de aprobación inteligente.

    Al cargar (GET), ejecuta una consulta SQL que calcula:
      - El último pedido del mismo departamento para cada artículo solicitado.
      - Cuántos días han pasado desde ese último pedido.
      - Qué cantidad se pidió entonces.
    Esto genera alertas contextuales para que el admin tome mejores decisiones.

    Al guardar (POST), aplica cantidades aprobadas y descuenta del stock.
    """
    pedido = Pedido.query.get_or_404(pedido_id)

    if request.method == 'POST':
        accion = request.form.get('accion')  # 'aprobar' | 'rechazar'

        if accion == 'rechazar':
            pedido.estado           = 'rechazado'
            pedido.notas_admin      = request.form.get('notas_admin', '')
            pedido.fecha_resolucion = datetime.utcnow()
            db.session.commit()
            flash(f'Pedido {pedido.folio} rechazado.', 'warning')
            return redirect(url_for('admin.pedidos'))

        if accion == 'aprobar':
            pedido.notas_admin = request.form.get('notas_admin', '')
            hubo_modificacion  = False

            for detalle in pedido.detalles:
                campo = f'cant_aprobada_{detalle.id}'
                try:
                    cant_aprobada = int(request.form.get(campo, 0))
                except ValueError:
                    cant_aprobada = 0

                if cant_aprobada <= 0:
                    # Si el admin pone 0, ese ítem no se entrega
                    detalle.cantidad_aprobada = 0
                    continue

                material = detalle.material

                # ── Validar stock suficiente ───────────────────────
                if material.stock_actual < cant_aprobada:
                    flash(
                        f'Stock insuficiente para "{material.nombre}". '
                        f'Disponible: {material.stock_actual}, '
                        f'solicitado: {cant_aprobada}.',
                        'danger'
                    )
                    return redirect(
                        url_for('admin.revisar_pedido', pedido_id=pedido_id)
                    )

                # ── Registrar si hay modificación ──────────────────
                if cant_aprobada != detalle.cantidad_solicitada:
                    hubo_modificacion = True

                detalle.cantidad_aprobada = cant_aprobada

                # ── Descontar stock ────────────────────────────────
                material.stock_actual -= cant_aprobada

                # ── Registrar movimiento en bitácora ───────────────
                movimiento = MovimientoInventario(
                    id_material      = material.id,
                    tipo_movimiento  = 'salida',
                    cantidad         = cant_aprobada,
                    stock_resultante = material.stock_actual,
                    id_pedido        = pedido.id,
                    id_usuario       = current_user.id,
                    motivo           = f'Pedido aprobado: {pedido.folio}',
                )
                db.session.add(movimiento)

            pedido.estado           = 'modificado' if hubo_modificacion else 'aprobado'
            pedido.fecha_resolucion = datetime.utcnow()
            db.session.commit()

            # ── Generar formato de salida de almacén ──────────
            try:
                from ..utils.formatos import generar_formato_salida
                generar_formato_salida(pedido)
            except Exception as e:
                print(f'[WARN] No se pudo generar formato de salida: {e}')

            flash(
                f'Pedido {pedido.folio} '
                f'{"modificado y aprobado" if hubo_modificacion else "aprobado"}.',
                'success'
            )
            return redirect(url_for('admin.pedidos'))

    # ── GET: cargar pedido + historial de consumo ──────────────────────────
    # Cambiar estado a "en revisión" si estaba pendiente
    if pedido.estado == 'pendiente':
        pedido.estado = 'en_revision'
        db.session.commit()

    historial_consumo = _obtener_historial_consumo(pedido)

    return render_template(
        'admin/pedido_revisar.html',
        pedido=pedido,
        historial_consumo=historial_consumo,
    )


def _obtener_historial_consumo(pedido: Pedido) -> dict:
    """
    Para cada material en el pedido, busca el ÚLTIMO pedido aprobado
    del MISMO departamento y calcula cuántos días han pasado.

    Retorna un dict  {id_material: {folio, dias, cantidad, fecha}}
    que el template usa para generar alertas contextuales.

    Consulta SQL equivalente (SQLite/MySQL compatible):
        SELECT
            dp2.id_material,
            p2.folio,
            dp2.cantidad_aprobada,
            p2.fecha_resolucion,
            CAST(
              (julianday('now') - julianday(p2.fecha_resolucion))
              AS INTEGER
            ) AS dias_transcurridos
        FROM Detalle_Pedido dp2
        JOIN Pedidos p2 ON p2.id = dp2.id_pedido
        WHERE p2.id_departamento = :depto_id
          AND p2.estado IN ('aprobado', 'entregado')
          AND p2.id != :pedido_actual_id
          AND dp2.id_material IN (:ids_materiales)
          AND p2.fecha_resolucion = (
              SELECT MAX(p3.fecha_resolucion)
              FROM Pedidos p3
              JOIN Detalle_Pedido dp3 ON dp3.id_pedido = p3.id
              WHERE p3.id_departamento = :depto_id
                AND p3.estado IN ('aprobado', 'entregado')
                AND p3.id != :pedido_actual_id
                AND dp3.id_material = dp2.id_material
          )
    """
    ids_materiales = [d.id_material for d in pedido.detalles]
    if not ids_materiales:
        return {}

    # Construir placeholders individuales para IN clause (SQLite compatible)
    in_placeholders = ', '.join([f':mat_{i}' for i in range(len(ids_materiales))])
    params = {
        'depto_id':  pedido.id_departamento,
        'pedido_id': pedido.id,
    }
    for i, mid in enumerate(ids_materiales):
        params[f'mat_{i}'] = mid

    sql = text(f"""
        SELECT
            dp2.id_material,
            p2.folio                AS ultimo_folio,
            dp2.cantidad_aprobada   AS ultima_cantidad,
            p2.fecha_resolucion     AS ultima_fecha,
            CAST(
                (julianday('now') - julianday(p2.fecha_resolucion))
            AS INTEGER)             AS dias_transcurridos
        FROM  Detalle_Pedido dp2
        JOIN  Pedidos p2 ON p2.id = dp2.id_pedido
        WHERE p2.id_departamento = :depto_id
          AND p2.estado IN ('aprobado', 'entregado')
          AND p2.id    != :pedido_id
          AND dp2.id_material IN ({in_placeholders})
          AND p2.fecha_resolucion = (
                SELECT MAX(p3.fecha_resolucion)
                FROM   Pedidos p3
                JOIN   Detalle_Pedido dp3 ON dp3.id_pedido = p3.id
                WHERE  p3.id_departamento = :depto_id
                  AND  p3.estado IN ('aprobado', 'entregado')
                  AND  p3.id    != :pedido_id
                  AND  dp3.id_material = dp2.id_material
          )
    """)

    rows = db.session.execute(sql, params).fetchall()

    # Convertir a dict indexado por id_material
    historial = {}
    for row in rows:
        historial[row.id_material] = {
            'folio':     row.ultimo_folio,
            'cantidad':  row.ultima_cantidad,
            'fecha':     row.ultima_fecha,
            'dias':      row.dias_transcurridos,
        }
    return historial


@admin_bp.route('/pedidos/<int:pedido_id>/entregar', methods=['POST'])
@solo_admin_o_mantenimiento
def confirmar_entrega(pedido_id):
    """Marca un pedido aprobado como entregado físicamente."""
    pedido = Pedido.query.get_or_404(pedido_id)
    if pedido.estado not in ('aprobado', 'modificado'):
        flash('Solo se pueden marcar como entregados pedidos aprobados.', 'warning')
        return redirect(url_for('admin.pedidos'))

    pedido.estado        = 'entregado'
    pedido.fecha_entrega = datetime.utcnow()
    db.session.commit()

    # ── Regenerar formato de salida con fecha de entrega ──
    try:
        from ..utils.formatos import generar_formato_salida
        generar_formato_salida(pedido)
    except Exception as e:
        print(f'[WARN] No se pudo regenerar formato de salida: {e}')

    flash(f'Pedido {pedido.folio} marcado como entregado.', 'success')
    return redirect(url_for('admin.pedidos'))


# ═══════════════════════════════════════════════════════════════════════════════
# PROVEEDORES
# ═══════════════════════════════════════════════════════════════════════════════

@admin_bp.route('/proveedores')
@solo_admin
def proveedores():
    lista = Proveedor.query.order_by(Proveedor.nombre).all()
    return render_template('admin/proveedores.html', proveedores=lista)


@admin_bp.route('/proveedor/nuevo', methods=['GET', 'POST'])
@admin_bp.route('/proveedor/<int:prov_id>/editar', methods=['GET', 'POST'])
@solo_admin
def proveedor_form(prov_id=None):
    proveedor = Proveedor.query.get_or_404(prov_id) if prov_id else Proveedor()

    if request.method == 'POST':
        proveedor.nombre    = request.form['nombre'].strip()
        proveedor.contacto  = request.form.get('contacto', '')
        proveedor.telefono  = request.form.get('telefono', '')
        proveedor.email     = request.form.get('email', '')
        proveedor.direccion = request.form.get('direccion', '')
        proveedor.rfc       = request.form.get('rfc', '')
        proveedor.notas     = request.form.get('notas', '')

        if not prov_id:
            db.session.add(proveedor)

        db.session.commit()
        flash(f'Proveedor "{proveedor.nombre}" guardado.', 'success')
        return redirect(url_for('admin.proveedores'))

    return render_template('admin/proveedor_form.html', proveedor=proveedor)


# ═══════════════════════════════════════════════════════════════════════════════
# DEPARTAMENTOS — CRUD + ESTADÍSTICAS
# ═══════════════════════════════════════════════════════════════════════════════

@admin_bp.route('/departamentos')
@solo_admin
def departamentos():
    """Lista todos los departamentos con su encargado y número de pedidos."""
    deptos = (Departamento.query
              .order_by(Departamento.nombre)
              .all())

    # Pre-calcular stats rápidos por departamento
    stats = {}
    for d in deptos:
        total_pedidos = Pedido.query.filter_by(id_departamento=d.id).count()
        encargado = Usuario.query.filter_by(
            id_departamento=d.id, rol='solicitante', activo=True
        ).first()
        stats[d.id] = {
            'total_pedidos': total_pedidos,
            'encargado': encargado,
            'categorias': [c.nombre for c in d.categorias],
        }

    return render_template('admin/departamentos.html',
                           departamentos=deptos, stats=stats)


@admin_bp.route('/departamento/nuevo', methods=['GET', 'POST'])
@admin_bp.route('/departamento/<int:depto_id>/editar', methods=['GET', 'POST'])
@solo_admin
def departamento_form(depto_id=None):
    """Crear o editar departamento. Al crear, genera cuenta automáticamente."""
    import secrets
    import string

    depto = Departamento.query.get_or_404(depto_id) if depto_id else Departamento()
    categorias = Categoria.query.filter_by(activo=True).all()
    es_nuevo = depto.id is None

    cuenta_generada = None  # Se llena solo al crear

    if request.method == 'POST':
        depto.nombre      = request.form['nombre'].strip()
        depto.codigo      = request.form['codigo'].strip().upper()
        depto.descripcion = request.form.get('descripcion', '')

        # Verificar que el código no esté en uso por otro departamento
        duplicado = Departamento.query.filter(
            Departamento.codigo == depto.codigo,
            Departamento.id != (depto.id or 0),
        ).first()
        if duplicado:
            flash(
                f'El código "{depto.codigo}" ya está asignado al departamento '
                f'"{duplicado.nombre}". Usa un código distinto.',
                'danger'
            )
            return render_template(
                'admin/departamento_form.html',
                departamento=depto,
                categorias=categorias,
                es_nuevo=es_nuevo,
            )

        # Categorías permitidas
        ids_cats = request.form.getlist('categorias')
        depto.categorias = Categoria.query.filter(
            Categoria.id.in_(ids_cats)
        ).all()

        if es_nuevo:
            db.session.add(depto)
            db.session.flush()  # Necesitamos depto.id

            # ── Generar cuenta automática ──────────────────────
            nombre_encargado = request.form.get('nombre_encargado', '').strip()
            if not nombre_encargado:
                nombre_encargado = f'Encargado {depto.nombre}'

            # Email basado en código: contabilidad@inventario.fing.mx
            codigo_limpio = depto.codigo.lower().replace('-', '').replace('_', '')
            email = f'{codigo_limpio}@inventario.fing.mx'

            # Contraseña aleatoria segura
            chars = string.ascii_letters + string.digits + '!@#$'
            password = ''.join(secrets.choice(chars) for _ in range(10))

            # Verificar que no exista el email
            if Usuario.query.filter_by(email=email).first():
                email = f'{codigo_limpio}{depto.id}@inventario.fing.mx'

            usuario = Usuario(
                nombre_completo=nombre_encargado,
                email=email,
                rol='solicitante',
                id_departamento=depto.id,
            )
            usuario.set_password(password)
            db.session.add(usuario)

            cuenta_generada = {
                'nombre': nombre_encargado,
                'email': email,
                'password': password,
            }

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash(
                f'No se pudo guardar el departamento. '
                f'Verifica que el código "{depto.codigo}" no esté duplicado.',
                'danger'
            )
            return render_template(
                'admin/departamento_form.html',
                departamento=depto,
                categorias=categorias,
                es_nuevo=es_nuevo,
            )

        if cuenta_generada:
            flash(
                f'Departamento "{depto.nombre}" creado. '
                f'Cuenta generada: {cuenta_generada["email"]} / '
                f'{cuenta_generada["password"]}',
                'success'
            )
            return render_template(
                'admin/departamento_creado.html',
                departamento=depto,
                cuenta=cuenta_generada,
            )
        else:
            flash(f'Departamento "{depto.nombre}" actualizado.', 'success')
            return redirect(url_for('admin.departamentos'))

    return render_template(
        'admin/departamento_form.html',
        departamento=depto,
        categorias=categorias,
        es_nuevo=es_nuevo,
    )


@admin_bp.route('/departamento/<int:depto_id>')
@solo_admin
def departamento_detalle(depto_id):
    """Vista detallada con estadísticas del departamento."""
    depto = Departamento.query.get_or_404(depto_id)

    # Encargado(s)
    encargados = Usuario.query.filter_by(
        id_departamento=depto.id, rol='solicitante'
    ).all()

    # Historial de pedidos
    pedidos = (Pedido.query
               .filter_by(id_departamento=depto.id)
               .order_by(Pedido.fecha_solicitud.desc())
               .all())

    # Estadísticas
    total_pedidos = len(pedidos)
    pedidos_aprobados = sum(1 for p in pedidos if p.estado in ('aprobado', 'modificado', 'entregado'))
    pedidos_pendientes = sum(1 for p in pedidos if p.estado == 'pendiente')
    pedidos_rechazados = sum(1 for p in pedidos if p.estado == 'rechazado')

    # Costo total por pedido aprobado
    costo_total = 0
    costos_por_pedido = []
    for p in pedidos:
        if p.estado in ('aprobado', 'modificado', 'entregado'):
            costo_pedido = sum(
                (d.cantidad_aprobada or 0) * float(d.precio_unitario_ref or 0)
                for d in p.detalles
            )
            costo_total += costo_pedido
            costos_por_pedido.append({
                'folio': p.folio,
                'fecha': p.fecha_solicitud,
                'estado': p.estado,
                'costo': costo_pedido,
                'items': len(p.detalles),
            })

    return render_template(
        'admin/departamento_detalle.html',
        departamento=depto,
        encargados=encargados,
        pedidos=pedidos,
        total_pedidos=total_pedidos,
        pedidos_aprobados=pedidos_aprobados,
        pedidos_pendientes=pedidos_pendientes,
        pedidos_rechazados=pedidos_rechazados,
        costo_total=costo_total,
        costos_por_pedido=costos_por_pedido,
    )


@admin_bp.route('/departamento/<int:depto_id>/eliminar', methods=['POST'])
@solo_admin
def departamento_eliminar(depto_id):
    """Desactiva un departamento y sus usuarios asociados."""
    depto = Departamento.query.get_or_404(depto_id)

    # Verificar que no tenga pedidos pendientes
    pendientes = Pedido.query.filter(
        Pedido.id_departamento == depto.id,
        Pedido.estado.in_(['pendiente', 'en_revision'])
    ).count()

    if pendientes > 0:
        flash(f'No se puede eliminar "{depto.nombre}": tiene {pendientes} '
              'pedido(s) pendiente(s).', 'danger')
        return redirect(url_for('admin.departamentos'))

    # Desactivar usuarios del departamento
    for u in depto.usuarios:
        u.activo = False

    depto.activo = False
    db.session.commit()
    flash(f'Departamento "{depto.nombre}" desactivado.', 'info')
    return redirect(url_for('admin.departamentos'))


# ═══════════════════════════════════════════════════════════════════════════════
# REQUISICIONES — Panel del admin (Salida de Almacén)
# ═══════════════════════════════════════════════════════════════════════════════

@admin_bp.route('/requisiciones')
@solo_admin
def requisiciones():
    """Panel de requisiciones del admin: formatos de salida de almacén."""
    import os

    filtro_depto = request.args.get('departamento', '', type=str)

    query = (Pedido.query
             .filter(Pedido.estado.in_(['aprobado', 'modificado', 'entregado']))
             .order_by(Pedido.fecha_resolucion.desc()))

    if filtro_depto:
        query = query.filter_by(id_departamento=int(filtro_depto))

    pedidos = query.all()
    departamentos_lista = Departamento.query.filter_by(activo=True).order_by(
        Departamento.nombre).all()

    # Verificar existencia de archivos
    base_salidas = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'static', 'uploads', 'requisiciones', 'salidas'
    )

    formatos = {}
    for p in pedidos:
        salida_path = os.path.join(base_salidas, f'{p.folio}_salida.xlsx')

        # Auto-regenerar si no existe
        if not os.path.exists(salida_path):
            try:
                from ..utils.formatos import generar_formato_salida
                generar_formato_salida(p)
            except Exception:
                pass

        formatos[p.id] = os.path.exists(salida_path)

    return render_template('admin/requisiciones.html',
                           pedidos=pedidos,
                           formatos=formatos,
                           departamentos=departamentos_lista,
                           filtro_depto=filtro_depto)


@admin_bp.route('/requisiciones/<int:pedido_id>/salida.xlsx')
@solo_admin
def descargar_salida_admin_xlsx(pedido_id):
    """Descarga el formato de salida de almacén (.xlsx)."""
    import os
    from flask import send_file

    pedido = Pedido.query.get_or_404(pedido_id)

    ruta = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'static', 'uploads', 'requisiciones', 'salidas',
        f'{pedido.folio}_salida.xlsx'
    )

    if not os.path.exists(ruta):
        try:
            from ..utils.formatos import generar_formato_salida
            generar_formato_salida(pedido)
        except Exception:
            flash('No se pudo generar el formato.', 'danger')
            return redirect(url_for('admin.requisiciones'))

    return send_file(ruta, as_attachment=True,
                     download_name=f'{pedido.folio}_salida.xlsx')


@admin_bp.route('/requisiciones/pdf')
@solo_admin
def descargar_salidas_pdf():
    """Descarga PDF consolidado de todas las salidas de almacén."""
    from flask import send_file
    from ..utils.formatos import generar_pdf_requisiciones

    filtro_depto = request.args.get('departamento', '', type=str)

    query = (Pedido.query
             .filter(Pedido.estado.in_(['aprobado', 'modificado', 'entregado']))
             .order_by(Pedido.fecha_resolucion.desc()))

    if filtro_depto:
        query = query.filter_by(id_departamento=int(filtro_depto))

    pedidos = query.all()

    if not pedidos:
        flash('No hay salidas para descargar.', 'warning')
        return redirect(url_for('admin.requisiciones'))

    buffer = generar_pdf_requisiciones(pedidos, tipo='salida')
    return send_file(buffer, as_attachment=True,
                     download_name='Salidas_Almacen.pdf',
                     mimetype='application/pdf')


# ═══════════════════════════════════════════════════════════════════════════════
# VISTA ADMIN — Stock de Mantenimiento (solo lectura)
# ═══════════════════════════════════════════════════════════════════════════════

@admin_bp.route('/mantenimiento/stock')
@solo_admin
def admin_stock_mantenimiento():
    """Vista de solo lectura del stock propio del departamento de Mantenimiento."""
    from ..models import StockMantenimiento, MovimientoStockMant, PedidoEquipo, Trabajador

    q         = request.args.get('q', '').strip()
    solo_bajo = request.args.get('bajo_stock', '')

    query = StockMantenimiento.query.filter_by(activo=True).order_by(StockMantenimiento.nombre)
    if q:
        query = query.filter(StockMantenimiento.nombre.ilike(f'%{q}%'))
    if solo_bajo:
        query = query.filter(StockMantenimiento.cantidad <= StockMantenimiento.cantidad_min)

    items = query.all()

    # KPIs rápidos
    stats = {
        'total_items':   StockMantenimiento.query.filter_by(activo=True).count(),
        'bajo_stock':    StockMantenimiento.query.filter(
                             StockMantenimiento.activo == True,
                             StockMantenimiento.cantidad <= StockMantenimiento.cantidad_min
                         ).count(),
        'pedidos_pend':  PedidoEquipo.query.filter_by(estado='pendiente').count(),
        'total_movs':    MovimientoStockMant.query.count(),
    }

    ultimos = (MovimientoStockMant.query
               .order_by(desc(MovimientoStockMant.fecha))
               .limit(10).all())

    return render_template('admin/mantenimiento_stock.html',
                           items=items, stats=stats, ultimos=ultimos,
                           q=q, solo_bajo=solo_bajo)



# ═══════════════════════════════════════════════════════════════════════════════
# ÓRDENES DE SERVICIO — Solo lectura para Admin
# ═══════════════════════════════════════════════════════════════════════════════

@admin_bp.route('/ordenes-servicio')
@solo_admin
def ordenes_servicio_admin():
    """Vista de solo lectura de todas las órdenes de servicio de mantenimiento."""
    from ..models import OrdenServicio
    from sqlalchemy import desc
    estado_f = request.args.get('estado', '')
    q        = request.args.get('q', '').strip()

    query = OrdenServicio.query.order_by(desc(OrdenServicio.fecha_solicitud))
    if estado_f in OrdenServicio.ESTADOS:
        query = query.filter_by(estado=estado_f)
    if q:
        query = query.join(Usuario, OrdenServicio.id_solicitante == Usuario.id).filter(
            Usuario.nombre_completo.ilike(f'%{q}%')
        )
    ordenes = query.all()
    return render_template('admin/ordenes_servicio.html',
                           ordenes=ordenes, estado_f=estado_f, q=q,
                           ESTADOS=OrdenServicio.ESTADOS)


@admin_bp.route('/ordenes-servicio/<int:orden_id>/descargar')
@solo_admin
def descargar_orden_admin(orden_id):
    """Descarga el .docx de la orden de servicio."""
    import os
    from flask import send_file
    from ..models import OrdenServicio
    orden = OrdenServicio.query.get_or_404(orden_id)
    if not orden.archivo_docx_path:
        flash('Documento no disponible aún.', 'warning')
        return redirect(url_for('admin.ordenes_servicio_admin'))
    ruta = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), orden.archivo_docx_path
    )
    if not os.path.exists(ruta):
        flash('Archivo no encontrado.', 'danger')
        return redirect(url_for('admin.ordenes_servicio_admin'))
    return send_file(ruta, as_attachment=True,
                     mimetype='application/pdf',
                     download_name=f'{orden.folio}_OrdenServicio.pdf')


# ═══════════════════════════════════════════════════════════════════════════════
# AUDITORIO INTERACTIVO FIT
# ═══════════════════════════════════════════════════════════════════════════════

@admin_bp.route('/auditorio')
@solo_admin
def auditorio():
    """Vista principal: calendario + próximas reservas."""
    from datetime import date
    hoy = date.today()
    proximas = (ReservaAuditorio.query
                .filter(ReservaAuditorio.fecha_inicio >= datetime.combine(hoy, datetime.min.time()),
                        ReservaAuditorio.estado.in_(['reservado', 'en_uso']))
                .order_by(ReservaAuditorio.fecha_inicio)
                .limit(10)
                .all())
    return render_template('admin/auditorio.html', proximas=proximas)


@admin_bp.route('/auditorio/api/eventos')
@solo_admin
def auditorio_eventos_json():
    """JSON para FullCalendar — devuelve todas las reservas activas."""
    reservas = ReservaAuditorio.query.filter(
        ReservaAuditorio.estado != 'cancelado'
    ).all()

    COLOR_MAP = {
        'reservado':  '#0d6efd',
        'en_uso':     '#198754',
        'completado': '#6c757d',
    }
    eventos = []
    for r in reservas:
        color = COLOR_MAP.get(r.estado, '#0d6efd')
        if r.es_externo and not r.pago_verificado and r.estado == 'reservado':
            color = '#ffc107'
        eventos.append({
            'id':    r.id,
            'title': r.nombre_evento,
            'start': r.fecha_inicio.isoformat(),
            'end':   r.fecha_fin.isoformat(),
            'color': color,
            'extendedProps': {
                'tipo':   r.tipo_usuario,
                'nombre': r.nombre,
                'estado': r.estado,
                'pago':   r.pago_verificado,
            },
            'url': url_for('admin.auditorio_editar', reserva_id=r.id),
        })
    return jsonify(eventos)


@admin_bp.route('/auditorio/nueva', methods=['GET', 'POST'])
@solo_admin
def auditorio_nueva():
    """Registrar una nueva reserva del auditorio."""
    if request.method == 'POST':
        tipo         = request.form.get('tipo_usuario')
        nombre       = request.form.get('nombre', '').strip()
        matricula    = request.form.get('matricula', '').strip()
        departamento = request.form.get('departamento', '').strip()
        telefono     = request.form.get('telefono', '').strip()
        correo       = request.form.get('correo', '').strip()
        nombre_evento = request.form.get('nombre_evento', '').strip()
        descripcion  = request.form.get('descripcion', '').strip()
        notas        = request.form.get('notas', '').strip()

        fecha_inicio_str = request.form.get('fecha_inicio', '')
        fecha_fin_str    = request.form.get('fecha_fin', '')

        errores = []
        if not nombre:        errores.append('El nombre es requerido.')
        if not departamento:  errores.append('El departamento es requerido.')
        if not nombre_evento: errores.append('El nombre del evento es requerido.')
        if not fecha_inicio_str or not fecha_fin_str:
            errores.append('Las fechas de inicio y fin son requeridas.')

        fecha_inicio = fecha_fin = None
        if fecha_inicio_str and fecha_fin_str:
            try:
                fecha_inicio = datetime.fromisoformat(fecha_inicio_str)
                fecha_fin    = datetime.fromisoformat(fecha_fin_str)
                if fecha_fin <= fecha_inicio:
                    errores.append('La fecha de fin debe ser posterior al inicio.')
            except ValueError:
                errores.append('Formato de fecha inválido.')

        if tipo == 'externo' and not correo:
            errores.append('El correo es requerido para usuarios externos.')

        if not errores:
            # Verificar traslape
            traslape = ReservaAuditorio.query.filter(
                ReservaAuditorio.estado.in_(['reservado', 'en_uso']),
                ReservaAuditorio.fecha_inicio < fecha_fin,
                ReservaAuditorio.fecha_fin   > fecha_inicio,
            ).first()
            if traslape:
                errores.append(
                    f'El horario se traslapa con la reserva '
                    f'"{traslape.nombre_evento}" '
                    f'({traslape.fecha_inicio.strftime("%d/%m %H:%M")} – '
                    f'{traslape.fecha_fin.strftime("%H:%M")}).'
                )

        if errores:
            for e in errores:
                flash(e, 'danger')
            return render_template('admin/auditorio_form.html',
                                   accion='nueva', form=request.form)

        reserva = ReservaAuditorio(
            tipo_usuario    = tipo,
            nombre          = nombre,
            matricula       = matricula or None,
            departamento    = departamento,
            telefono        = telefono or None,
            correo          = correo or None,
            nombre_evento   = nombre_evento,
            descripcion     = descripcion or None,
            fecha_inicio    = fecha_inicio,
            fecha_fin       = fecha_fin,
            notas           = notas or None,
            registrado_por  = current_user.id,
        )
        db.session.add(reserva)
        db.session.commit()
        flash(f'Reserva "{nombre_evento}" registrada correctamente.', 'success')
        return redirect(url_for('admin.auditorio'))

    return render_template('admin/auditorio_form.html', accion='nueva', form={})


@admin_bp.route('/auditorio/<int:reserva_id>/editar', methods=['GET', 'POST'])
@solo_admin
def auditorio_editar(reserva_id):
    """Editar una reserva existente."""
    reserva = ReservaAuditorio.query.get_or_404(reserva_id)

    if request.method == 'POST':
        tipo         = request.form.get('tipo_usuario')
        nombre       = request.form.get('nombre', '').strip()
        matricula    = request.form.get('matricula', '').strip()
        departamento = request.form.get('departamento', '').strip()
        telefono     = request.form.get('telefono', '').strip()
        correo       = request.form.get('correo', '').strip()
        nombre_evento = request.form.get('nombre_evento', '').strip()
        descripcion  = request.form.get('descripcion', '').strip()
        notas        = request.form.get('notas', '').strip()
        estado       = request.form.get('estado', reserva.estado)
        fecha_inicio_str = request.form.get('fecha_inicio', '')
        fecha_fin_str    = request.form.get('fecha_fin', '')

        errores = []
        fecha_inicio = fecha_fin = None
        if fecha_inicio_str and fecha_fin_str:
            try:
                fecha_inicio = datetime.fromisoformat(fecha_inicio_str)
                fecha_fin    = datetime.fromisoformat(fecha_fin_str)
                if fecha_fin <= fecha_inicio:
                    errores.append('La fecha de fin debe ser posterior al inicio.')
            except ValueError:
                errores.append('Formato de fecha inválido.')
        else:
            errores.append('Las fechas son requeridas.')

        if tipo == 'externo' and not correo:
            errores.append('El correo es requerido para usuarios externos.')

        if not errores:
            traslape = ReservaAuditorio.query.filter(
                ReservaAuditorio.id != reserva_id,
                ReservaAuditorio.estado.in_(['reservado', 'en_uso']),
                ReservaAuditorio.fecha_inicio < fecha_fin,
                ReservaAuditorio.fecha_fin   > fecha_inicio,
            ).first()
            if traslape:
                errores.append(
                    f'El horario se traslapa con la reserva '
                    f'"{traslape.nombre_evento}" '
                    f'({traslape.fecha_inicio.strftime("%d/%m %H:%M")} – '
                    f'{traslape.fecha_fin.strftime("%H:%M")}).'
                )

        if errores:
            for e in errores:
                flash(e, 'danger')
            return render_template('admin/auditorio_form.html',
                                   accion='editar', reserva=reserva, form=request.form)

        reserva.tipo_usuario  = tipo
        reserva.nombre        = nombre
        reserva.matricula     = matricula or None
        reserva.departamento  = departamento
        reserva.telefono      = telefono or None
        reserva.correo        = correo or None
        reserva.nombre_evento = nombre_evento
        reserva.descripcion   = descripcion or None
        reserva.fecha_inicio  = fecha_inicio
        reserva.fecha_fin     = fecha_fin
        reserva.estado        = estado
        reserva.notas         = notas or None
        db.session.commit()
        flash('Reserva actualizada.', 'success')
        return redirect(url_for('admin.auditorio'))

    return render_template('admin/auditorio_form.html',
                           accion='editar', reserva=reserva, form={})


@admin_bp.route('/auditorio/<int:reserva_id>/verificar-pago', methods=['POST'])
@solo_admin
def auditorio_verificar_pago(reserva_id):
    """Marcar/desmarcar pago verificado (solo externos)."""
    reserva = ReservaAuditorio.query.get_or_404(reserva_id)
    if reserva.tipo_usuario != 'externo':
        abort(400)
    reserva.pago_verificado = not reserva.pago_verificado
    db.session.commit()
    estado_texto = 'verificado' if reserva.pago_verificado else 'pendiente'
    flash(f'Pago marcado como {estado_texto}.', 'success')
    return redirect(request.referrer or url_for('admin.auditorio'))


@admin_bp.route('/auditorio/<int:reserva_id>/cancelar', methods=['POST'])
@solo_admin
def auditorio_cancelar(reserva_id):
    """Cancelar una reserva."""
    reserva = ReservaAuditorio.query.get_or_404(reserva_id)
    reserva.estado = 'cancelado'
    db.session.commit()
    flash(f'Reserva "{reserva.nombre_evento}" cancelada.', 'warning')
    return redirect(request.referrer or url_for('admin.auditorio'))


@admin_bp.route('/auditorio/historial')
@solo_admin
def auditorio_historial():
    """Historial completo de reservas con filtros."""
    estado_f = request.args.get('estado', '')
    tipo_f   = request.args.get('tipo', '')
    q        = request.args.get('q', '').strip()

    query = ReservaAuditorio.query

    if estado_f:
        query = query.filter(ReservaAuditorio.estado == estado_f)
    if tipo_f:
        query = query.filter(ReservaAuditorio.tipo_usuario == tipo_f)
    if q:
        like = f'%{q}%'
        query = query.filter(
            db.or_(
                ReservaAuditorio.nombre.ilike(like),
                ReservaAuditorio.nombre_evento.ilike(like),
                ReservaAuditorio.departamento.ilike(like),
            )
        )

    reservas = query.order_by(ReservaAuditorio.fecha_inicio.desc()).all()
    return render_template('admin/auditorio_historial.html',
                           reservas=reservas,
                           estado_f=estado_f, tipo_f=tipo_f, q=q,
                           ESTADOS=ReservaAuditorio.ESTADOS,
                           TIPOS=ReservaAuditorio.TIPOS)
