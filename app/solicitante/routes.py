# app/auth/routes.py
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from ..models import Usuario

auth_bp = Blueprint('auth', __name__, template_folder='../templates/auth')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return _redirigir_por_rol()

    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))

        usuario = Usuario.query.filter_by(email=email, activo=True).first()

        if usuario and usuario.check_password(password):
            login_user(usuario, remember=remember)
            flash(f'Bienvenido, {usuario.nombre_completo}.', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or _redirigir_por_rol())

        flash('Correo o contraseña incorrectos.', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Sesión cerrada correctamente.', 'info')
    return redirect(url_for('auth.login'))


def _redirigir_por_rol():
    """Redirige al dashboard según el rol del usuario."""
    if current_user.es_admin:
        return url_for('admin.dashboard')
    if current_user.es_mantenimiento:
        return url_for('mantenimiento.panel')
    return url_for('solicitante.panel')


# ─────────────────────────────────────────────────────────────────────────────
# app/solicitante/routes.py
# ─────────────────────────────────────────────────────────────────────────────
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_required, current_user
from sqlalchemy import and_
from ..models import Material, Categoria, Pedido, DetallePedido, db
from ..extensions import db as _db
from functools import wraps

sol_bp = Blueprint('solicitante', __name__,
                   template_folder='../templates/solicitante')


def solo_solicitante(f):
    """Decorador: bloquea acceso a administradores en rutas de solicitante.
    Mantenimiento SÍ puede acceder (para solicitar material al almacén)."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if current_user.es_admin:
            flash('Acceso no permitido para administradores.', 'warning')
            return redirect(url_for('admin.dashboard'))
        return f(*args, **kwargs)
    return decorated


@sol_bp.route('/')
@login_required
@solo_solicitante
def panel():
    """
    Panel personalizado del Personal Administrativo.
    Muestra resumen de actividad, accesos rápidos y
    placeholder para el módulo de Requisiciones.
    """
    from sqlalchemy import func

    depto = current_user.departamento

    # Estadísticas rápidas del usuario
    total_pedidos = Pedido.query.filter_by(
        id_solicitante=current_user.id
    ).count()

    pedidos_pendientes = Pedido.query.filter_by(
        id_solicitante=current_user.id,
        estado='pendiente'
    ).count()

    pedidos_aprobados = Pedido.query.filter(
        Pedido.id_solicitante == current_user.id,
        Pedido.estado.in_(['aprobado', 'modificado', 'entregado'])
    ).count()

    # Últimos 5 pedidos
    ultimos_pedidos = (Pedido.query
                       .filter_by(id_solicitante=current_user.id)
                       .order_by(Pedido.fecha_solicitud.desc())
                       .limit(5)
                       .all())

    # Categorías disponibles para este departamento
    categorias_permitidas = depto.categorias if depto else []

    # Estadísticas de órdenes de servicio
    from ..models import OrdenServicio
    ordenes_activas = OrdenServicio.query.filter(
        OrdenServicio.id_solicitante == current_user.id,
        OrdenServicio.estado.in_(['solicitada', 'programada', 'en_proceso', 'completada'])
    ).count()
    ordenes_pendiente_encuesta = OrdenServicio.query.filter_by(
        id_solicitante=current_user.id,
        estado='entregada',
        encuesta_completada=False,
    ).count()

    orden_encuesta_pendiente = OrdenServicio.query.filter_by(
        id_solicitante=current_user.id,
        estado='entregada',
        encuesta_completada=False,
    ).order_by(OrdenServicio.fecha_solicitud.asc()).first()

    from ..models import Notificacion
    notificaciones_no_leidas = (Notificacion.query
                                .filter_by(id_usuario=current_user.id, leida=False)
                                .order_by(Notificacion.creada_en.desc())
                                .all())

    return render_template(
        'solicitante/panel.html',
        departamento=depto,
        total_pedidos=total_pedidos,
        pedidos_pendientes=pedidos_pendientes,
        pedidos_aprobados=pedidos_aprobados,
        ultimos_pedidos=ultimos_pedidos,
        categorias_permitidas=categorias_permitidas,
        ordenes_activas=ordenes_activas,
        ordenes_pendiente_encuesta=ordenes_pendiente_encuesta,
        orden_encuesta_pendiente=orden_encuesta_pendiente,
        notificaciones=notificaciones_no_leidas,
    )


@sol_bp.route('/catalogo')
@login_required
@solo_solicitante
def catalogo():
    """
    Catálogo filtrado: muestra ÚNICAMENTE los materiales cuya categoría
    pertenece a los permisos del departamento del solicitante actual,
    con stock > 0 y marcados como publicados.

    Consulta SQL equivalente:
        SELECT m.*
        FROM   Materiales m
        JOIN   Categorias c ON c.id = m.id_categoria
        JOIN   Permisos_Visibilidad pv
               ON pv.id_categoria = c.id
               AND pv.id_departamento = :depto_id
        WHERE  m.publicado = 1
          AND  m.stock_actual > 0
        ORDER BY c.nombre, m.nombre;
    """
    depto = current_user.departamento

    if not depto:
        flash('Tu usuario no tiene un departamento asignado. '
              'Contacta al administrador.', 'danger')
        return render_template('solicitante/catalogo.html',
                               materiales=[], categorias=[])

    # Obtener IDs de categorías permitidas para este departamento
    ids_categorias_permitidas = [c.id for c in depto.categorias]

    # Consulta con filtro de permisos, stock y publicación
    materiales = (Material.query
                  .join(Categoria)
                  .filter(
                      Material.id_categoria.in_(ids_categorias_permitidas),
                      Material.publicado == True,
                      Material.stock_actual > 0,
                  )
                  .order_by(Categoria.nombre, Material.nombre)
                  .all())

    # Agrupar por categoría para el template
    catalogo_agrupado = {}
    for mat in materiales:
        cat_nombre = mat.categoria.nombre
        catalogo_agrupado.setdefault(cat_nombre, []).append(mat)

    return render_template(
        'solicitante/catalogo.html',
        catalogo=catalogo_agrupado,
        departamento=depto,
    )


@sol_bp.route('/pedido/nuevo', methods=['GET', 'POST'])
@login_required
@solo_solicitante
def nuevo_pedido():
    """
    Crea un nuevo pedido.
    El formulario envía una lista de pares (id_material, cantidad).
    Se valida que los materiales pertenezcan a categorías permitidas.
    """
    if request.method == 'POST':
        # Recopilar ítems del formulario: material_id[] y cantidad[]
        ids_materiales = request.form.getlist('material_id')
        cantidades     = request.form.getlist('cantidad')
        notas          = request.form.get('notas_solicitante', '')

        if not ids_materiales:
            flash('El pedido no puede estar vacío.', 'warning')
            return redirect(url_for('solicitante.catalogo'))

        depto = current_user.departamento
        ids_categorias_ok = {c.id for c in depto.categorias}

        # ── Crear cabecera del pedido ─────────────────────────
        pedido = Pedido(
            folio           = Pedido.generar_folio(),
            id_solicitante  = current_user.id,
            id_departamento = depto.id,
            estado          = 'pendiente',
            notas_solicitante = notas,
        )
        db.session.add(pedido)
        db.session.flush()  # Obtener pedido.id antes del commit

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

            # Verificar que el material sea de una categoría permitida
            if material.id_categoria not in ids_categorias_ok:
                errores.append(f'{material.nombre}: sin permiso.')
                continue

            if material.stock_actual < cant:
                errores.append(
                    f'{material.nombre}: stock insuficiente '
                    f'(disponible: {material.stock_actual}).'
                )
                continue

            detalle = DetallePedido(
                id_pedido           = pedido.id,
                id_material         = material.id,
                cantidad_solicitada = cant,
                precio_unitario_ref = material.precio_unitario,
            )
            db.session.add(detalle)

        if errores:
            db.session.rollback()
            for e in errores:
                flash(e, 'danger')
            return redirect(url_for('solicitante.catalogo'))

        db.session.commit()

        # ── Generar formato de requisición automáticamente ────
        try:
            from ..utils.formatos import generar_formato_pedido
            generar_formato_pedido(pedido)
        except Exception as e:
            # No bloquear el pedido si falla la generación
            print(f'[WARN] No se pudo generar formato: {e}')

        flash(f'Pedido {pedido.folio} enviado correctamente. '
              'El administrador lo revisará pronto.', 'success')
        return redirect(url_for('solicitante.mis_pedidos'))

    return redirect(url_for('solicitante.catalogo'))


@sol_bp.route('/mis-pedidos')
@login_required
@solo_solicitante
def mis_pedidos():
    """Lista los pedidos del solicitante con su estado actual."""
    pedidos = (Pedido.query
               .filter_by(id_solicitante=current_user.id)
               .order_by(Pedido.fecha_solicitud.desc())
               .all())
    return render_template('solicitante/mis_pedidos.html', pedidos=pedidos)


# ═══════════════════════════════════════════════════════════════════════════════
# REQUISICIONES — Historial de formatos
# ═══════════════════════════════════════════════════════════════════════════════

@sol_bp.route('/requisiciones')
@login_required
@solo_solicitante
def requisiciones():
    """
    Historial de requisiciones del solicitante.
    Muestra todos los pedidos con sus formatos generados.
    Los pedidos entregados también muestran el formato de salida.
    """
    import os

    pedidos = (Pedido.query
               .filter_by(id_solicitante=current_user.id)
               .order_by(Pedido.fecha_solicitud.desc())
               .all())

    # Verificar qué formatos existen en disco
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

        # Auto-regenerar formatos faltantes
        if not os.path.exists(pedido_path):
            try:
                from ..utils.formatos import generar_formato_pedido
                generar_formato_pedido(p)
            except Exception:
                pass

        if not os.path.exists(salida_path) and p.estado in ('aprobado', 'entregado', 'modificado'):
            try:
                from ..utils.formatos import generar_formato_salida
                generar_formato_salida(p)
            except Exception:
                pass

        formatos[p.id] = {
            'tiene_pedido': os.path.exists(pedido_path),
            'tiene_salida': os.path.exists(salida_path) and p.estado in ('aprobado', 'entregado', 'modificado'),
        }

    return render_template('solicitante/requisiciones.html',
                           pedidos=pedidos, formatos=formatos)


@sol_bp.route('/requisiciones/<int:pedido_id>/pedido.xlsx')
@login_required
@solo_solicitante
def descargar_requisicion_xlsx(pedido_id):
    """Descarga el formato de requisición de material (.xlsx) de un pedido."""
    import os
    from flask import send_file

    pedido = Pedido.query.get_or_404(pedido_id)
    if pedido.id_solicitante != current_user.id:
        flash('No tienes acceso a este pedido.', 'danger')
        return redirect(url_for('solicitante.requisiciones'))

    ruta = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'static', 'uploads', 'requisiciones', 'pedidos',
        f'{pedido.folio}_requisicion.xlsx'
    )

    if not os.path.exists(ruta):
        # Regenerar si no existe
        try:
            from ..utils.formatos import generar_formato_pedido
            generar_formato_pedido(pedido)
        except Exception:
            flash('No se pudo generar el formato.', 'danger')
            return redirect(url_for('solicitante.requisiciones'))

    return send_file(ruta, as_attachment=True,
                     download_name=f'{pedido.folio}_requisicion.xlsx')


@sol_bp.route('/requisiciones/<int:pedido_id>/salida.xlsx')
@login_required
@solo_solicitante
def descargar_salida_xlsx(pedido_id):
    """Descarga el formato de salida de almacén (.xlsx) — solo si entregado."""
    import os
    from flask import send_file

    pedido = Pedido.query.get_or_404(pedido_id)
    if pedido.id_solicitante != current_user.id:
        flash('No tienes acceso a este pedido.', 'danger')
        return redirect(url_for('solicitante.requisiciones'))

    if pedido.estado not in ('aprobado', 'entregado', 'modificado'):
        flash('El formato de salida aún no está disponible.', 'warning')
        return redirect(url_for('solicitante.requisiciones'))

    ruta = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'static', 'uploads', 'requisiciones', 'salidas',
        f'{pedido.folio}_salida.xlsx'
    )

    if not os.path.exists(ruta):
        flash('El formato de salida aún no ha sido generado.', 'warning')
        return redirect(url_for('solicitante.requisiciones'))

    return send_file(ruta, as_attachment=True,
                     download_name=f'{pedido.folio}_salida.xlsx')


# ═══════════════════════════════════════════════════════════════════════════════
# ÓRDENES DE SERVICIO DE MANTENIMIENTO
# ═══════════════════════════════════════════════════════════════════════════════

@sol_bp.route('/mantenimiento/solicitar', methods=['GET', 'POST'])
@login_required
@solo_solicitante
def solicitar_mantenimiento():
    """Formulario para que el solicitante cree una Orden de Servicio."""
    from ..models import OrdenServicio, FirmaUsuario

    if request.method == 'POST':
        tipo_mant    = request.form.get('tipo_mantenimiento', '').strip()
        servicios    = request.form.getlist('servicios')
        otro         = request.form.get('otro_servicio', '').strip()
        descripcion  = request.form.get('descripcion', '').strip()

        if not tipo_mant or tipo_mant not in OrdenServicio.TIPOS_MANT:
            flash('Selecciona el tipo de mantenimiento.', 'warning')
        elif not servicios:
            flash('Selecciona al menos un tipo de servicio.', 'warning')
        elif not descripcion:
            flash('Describe el servicio solicitado.', 'warning')
        else:
            if 'otro' in servicios and not otro:
                flash('Especifica el servicio "Otro".', 'warning')
            else:
                orden = OrdenServicio(
                    folio              = OrdenServicio.generar_folio(),
                    id_solicitante     = current_user.id,
                    id_departamento    = current_user.id_departamento,
                    tipo_mantenimiento = tipo_mant,
                    otro_servicio      = otro,
                    descripcion        = descripcion,
                )
                orden.set_servicios(servicios)
                db.session.add(orden)
                db.session.commit()
                flash(f'Orden de servicio {orden.folio} enviada a Mantenimiento.', 'success')
                return redirect(url_for('solicitante.mis_ordenes_servicio'))

    depto = current_user.departamento
    return render_template('solicitante/solicitar_mantenimiento.html', depto=depto)


@sol_bp.route('/mantenimiento/mis-ordenes')
@login_required
@solo_solicitante
def mis_ordenes_servicio():
    """Lista las órdenes de servicio del solicitante."""
    from ..models import OrdenServicio, Notificacion
    ordenes = (OrdenServicio.query
               .filter_by(id_solicitante=current_user.id)
               .order_by(OrdenServicio.fecha_solicitud.desc())
               .all())
    notificaciones_no_leidas = (Notificacion.query
                                .filter_by(id_usuario=current_user.id, leida=False)
                                .order_by(Notificacion.creada_en.desc())
                                .all())
    return render_template('solicitante/mis_ordenes_servicio.html',
                           ordenes=ordenes,
                           notificaciones=notificaciones_no_leidas)


@sol_bp.route('/notificacion/<int:notif_id>/leer', methods=['POST'])
@login_required
@solo_solicitante
def marcar_notificacion_leida(notif_id):
    from ..models import Notificacion
    notif = Notificacion.query.get_or_404(notif_id)
    if notif.id_usuario == current_user.id:
        notif.leida = True
        db.session.commit()
    next_url = request.form.get('next') or url_for('solicitante.mis_ordenes_servicio')
    return redirect(next_url)


@sol_bp.route('/mantenimiento/orden/<int:orden_id>/encuesta', methods=['GET', 'POST'])
@login_required
@solo_solicitante
def encuesta_satisfaccion(orden_id):
    """Formulario de encuesta de satisfacción tras la entrega del servicio."""
    from ..models import OrdenServicio
    orden = OrdenServicio.query.get_or_404(orden_id)
    if orden.id_solicitante != current_user.id:
        flash('No tienes acceso a esta orden.', 'danger')
        return redirect(url_for('solicitante.mis_ordenes_servicio'))
    if orden.estado != 'entregada':
        flash('La encuesta está disponible una vez entregado el servicio.', 'warning')
        return redirect(url_for('solicitante.mis_ordenes_servicio'))
    if orden.encuesta_completada:
        flash('Ya completaste la encuesta de esta orden.', 'info')
        return redirect(url_for('solicitante.mis_ordenes_servicio'))

    if request.method == 'POST':
        def _enc(field):
            v = request.form.get(field, type=int)
            return max(1, min(5, v)) if v is not None else None

        orden.enc_experiencia      = _enc('experiencia')
        orden.enc_profesionalismo  = _enc('profesionalismo')
        orden.enc_tiempo_respuesta = _enc('tiempo_respuesta')
        orden.enc_calidad          = _enc('calidad')
        orden.enc_comunicacion     = _enc('comunicacion')
        orden.enc_comentarios      = request.form.get('comentarios', '')[:2000].strip()
        orden.encuesta_completada  = True
        db.session.commit()
        flash('¡Gracias por tu retroalimentación!', 'success')
        return redirect(url_for('solicitante.mis_ordenes_servicio'))

    return render_template('solicitante/encuesta_satisfaccion.html', orden=orden)


@sol_bp.route('/mantenimiento/orden/<int:orden_id>/descargar')
@login_required
@solo_solicitante
def descargar_orden_servicio(orden_id):
    """Descarga el .docx de la orden de servicio completada."""
    import os
    from flask import send_file
    from ..models import OrdenServicio
    orden = OrdenServicio.query.get_or_404(orden_id)
    if orden.id_solicitante != current_user.id:
        flash('No tienes acceso a esta orden.', 'danger')
        return redirect(url_for('solicitante.mis_ordenes_servicio'))
    if orden.estado != 'entregada':
        flash('El documento aún no está disponible.', 'warning')
        return redirect(url_for('solicitante.mis_ordenes_servicio'))
    from ..utils.orden_servicio_pdf import generar_pdf_orden
    buf = generar_pdf_orden(orden)
    return send_file(buf, as_attachment=True,
                     mimetype='application/pdf',
                     download_name=f'{orden.folio}_OrdenServicio.pdf')


@sol_bp.route('/requisiciones/pdf')
@login_required
@solo_solicitante
def descargar_requisiciones_pdf():
    """Descarga un PDF con todos los formatos de requisición de material."""
    from flask import send_file
    from ..utils.formatos import generar_pdf_requisiciones

    pedidos = (Pedido.query
               .filter_by(id_solicitante=current_user.id)
               .order_by(Pedido.fecha_solicitud.desc())
               .all())

    if not pedidos:
        flash('No hay requisiciones para descargar.', 'warning')
        return redirect(url_for('solicitante.requisiciones'))

    buffer = generar_pdf_requisiciones(pedidos, tipo='pedido')
    return send_file(buffer, as_attachment=True,
                     download_name='Requisiciones_Material.pdf',
                     mimetype='application/pdf')
