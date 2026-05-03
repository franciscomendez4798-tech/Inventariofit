# app/models.py
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from .extensions import db


# ── Tabla de asociación: Departamento ↔ Categoría ──────────────────────────
permisos_visibilidad = db.Table(
    'Permisos_Visibilidad',
    db.Column('id_departamento', db.Integer,
              db.ForeignKey('Departamentos.id', ondelete='CASCADE'),
              primary_key=True),
    db.Column('id_categoria', db.Integer,
              db.ForeignKey('Categorias.id', ondelete='CASCADE'),
              primary_key=True),
)


class Departamento(db.Model):
    __tablename__ = 'Departamentos'

    id          = db.Column(db.Integer, primary_key=True)
    nombre      = db.Column(db.String(120), nullable=False, unique=True)
    codigo      = db.Column(db.String(20),  nullable=False, unique=True)
    descripcion = db.Column(db.Text)
    activo      = db.Column(db.Boolean, default=True, nullable=False)
    creado_en   = db.Column(db.DateTime, default=datetime.utcnow)

    # Relaciones
    usuarios    = db.relationship('Usuario', back_populates='departamento')
    pedidos     = db.relationship('Pedido',  back_populates='departamento')
    categorias  = db.relationship(
        'Categoria',
        secondary=permisos_visibilidad,
        back_populates='departamentos'
    )

    def __repr__(self):
        return f'<Departamento {self.codigo}>'


class Categoria(db.Model):
    __tablename__ = 'Categorias'

    id          = db.Column(db.Integer, primary_key=True)
    nombre      = db.Column(db.String(100), nullable=False, unique=True)
    descripcion = db.Column(db.Text)
    activo      = db.Column(db.Boolean, default=True)

    materiales   = db.relationship('Material', back_populates='categoria')
    departamentos = db.relationship(
        'Departamento',
        secondary=permisos_visibilidad,
        back_populates='categorias'
    )


class Usuario(UserMixin, db.Model):
    __tablename__ = 'Usuarios'

    id              = db.Column(db.Integer, primary_key=True)
    nombre_completo = db.Column(db.String(150), nullable=False)
    email           = db.Column(db.String(150), nullable=False, unique=True)
    password_hash   = db.Column(db.String(256), nullable=False)
    rol             = db.Column(db.String(20),  nullable=False, default='solicitante')
    id_departamento = db.Column(db.Integer, db.ForeignKey('Departamentos.id'),
                                nullable=True)
    activo          = db.Column(db.Boolean, default=True)
    creado_en       = db.Column(db.DateTime, default=datetime.utcnow)

    departamento = db.relationship('Departamento', back_populates='usuarios')
    pedidos      = db.relationship('Pedido', back_populates='solicitante')

    # ── Helpers de contraseña ───────────────────────────────
    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def es_admin(self) -> bool:
        return self.rol == 'administrador'

    @property
    def es_mantenimiento(self) -> bool:
        return self.rol == 'mantenimiento'

    @property
    def es_admin_o_mantenimiento(self) -> bool:
        return self.rol in ('administrador', 'mantenimiento')

    prestamos_realizados = db.relationship('Prestamo', back_populates='usuario_presta')

    def __repr__(self):
        return f'<Usuario {self.email}>'


class Proveedor(db.Model):
    __tablename__ = 'Proveedores'

    id        = db.Column(db.Integer, primary_key=True)
    nombre    = db.Column(db.String(150), nullable=False)
    contacto  = db.Column(db.String(150))
    telefono  = db.Column(db.String(30))
    email     = db.Column(db.String(150))
    direccion = db.Column(db.Text)
    rfc       = db.Column(db.String(20))
    notas     = db.Column(db.Text)
    activo    = db.Column(db.Boolean, default=True)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

    materiales   = db.relationship('Material',    back_populates='proveedor')
    cotizaciones = db.relationship('Cotizacion',  back_populates='proveedor')


class Trabajador(db.Model):
    __tablename__ = 'Trabajadores'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    cargo = db.Column(db.String(100), nullable=False)
    area = db.Column(db.String(100))  # área o zona de trabajo (editable, aparece en requisiciones)
    activo = db.Column(db.Boolean, default=True)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

    prestamos       = db.relationship('Prestamo',      back_populates='trabajador')
    pedidos_equipo  = db.relationship('PedidoEquipo',  back_populates='trabajador',
                                      order_by='PedidoEquipo.fecha_pedido.desc()')


class Herramienta(db.Model):
    __tablename__ = 'Herramientas'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200), nullable=False)
    marca = db.Column(db.String(100))
    modelo = db.Column(db.String(100))
    codigo = db.Column(db.String(50), unique=True)
    estado_fisico = db.Column(db.String(50), default='bueno') # bueno, regular, malo
    disponible = db.Column(db.Boolean, default=True)
    activo = db.Column(db.Boolean, default=True)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

    prestamos = db.relationship('Prestamo', back_populates='herramienta')

class Prestamo(db.Model):
    __tablename__ = 'Prestamos_Herramientas'

    id = db.Column(db.Integer, primary_key=True)
    id_herramienta = db.Column(db.Integer, db.ForeignKey('Herramientas.id'), nullable=False)
    id_trabajador = db.Column(db.Integer, db.ForeignKey('Trabajadores.id'), nullable=False)
    id_usuario_presta = db.Column(db.Integer, db.ForeignKey('Usuarios.id'), nullable=False)
    fecha_prestamo = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_devolucion = db.Column(db.DateTime, nullable=True)
    estado = db.Column(db.String(20), default='prestado') # prestado, devuelto
    notas = db.Column(db.Text)

    herramienta = db.relationship('Herramienta', back_populates='prestamos')
    trabajador = db.relationship('Trabajador', back_populates='prestamos')
    usuario_presta = db.relationship('Usuario', back_populates='prestamos_realizados')



class Material(db.Model):
    __tablename__ = 'Materiales'

    id              = db.Column(db.Integer, primary_key=True)
    nombre          = db.Column(db.String(200), nullable=False)
    descripcion     = db.Column(db.Text)
    unidad_medida   = db.Column(db.String(50), nullable=False)
    stock_actual    = db.Column(db.Integer, default=0, nullable=False)
    stock_minimo    = db.Column(db.Integer, default=5, nullable=False)
    precio_unitario = db.Column(db.Numeric(10, 2), default=0.00)
    id_categoria    = db.Column(db.Integer, db.ForeignKey('Categorias.id'),
                                nullable=False)
    id_proveedor    = db.Column(db.Integer, db.ForeignKey('Proveedores.id'),
                                nullable=True)
    publicado       = db.Column(db.Boolean, default=False)
    imagen_url      = db.Column(db.String(500))
    creado_en       = db.Column(db.DateTime, default=datetime.utcnow)
    actualizado_en  = db.Column(db.DateTime, default=datetime.utcnow,
                                onupdate=datetime.utcnow)

    categoria    = db.relationship('Categoria',  back_populates='materiales')
    proveedor    = db.relationship('Proveedor',  back_populates='materiales')
    detalles     = db.relationship('DetallePedido', back_populates='material')
    movimientos  = db.relationship('MovimientoInventario', back_populates='material')
    cotizaciones = db.relationship('Cotizacion', back_populates='material')
    @property
    def bajo_stock(self) -> bool:
        return self.stock_actual <= self.stock_minimo


class Cotizacion(db.Model):
    __tablename__ = 'Cotizaciones'

    id               = db.Column(db.Integer, primary_key=True)
    id_material      = db.Column(db.Integer, db.ForeignKey('Materiales.id'),
                                 nullable=False)
    id_proveedor     = db.Column(db.Integer, db.ForeignKey('Proveedores.id'),
                                 nullable=False)
    precio_cotizado  = db.Column(db.Numeric(10, 2), nullable=False)
    fecha_cotizacion = db.Column(db.Date, nullable=False)
    fecha_vigencia   = db.Column(db.Date)
    notas            = db.Column(db.Text)

    material  = db.relationship('Material',  back_populates='cotizaciones')
    proveedor = db.relationship('Proveedor', back_populates='cotizaciones')


class Pedido(db.Model):
    __tablename__ = 'Pedidos'

    ESTADOS = ['pendiente', 'en_revision', 'modificado',
               'aprobado', 'rechazado', 'entregado']

    id                = db.Column(db.Integer, primary_key=True)
    folio             = db.Column(db.String(20), unique=True, nullable=False)
    id_solicitante    = db.Column(db.Integer, db.ForeignKey('Usuarios.id'),
                                  nullable=False)
    id_departamento   = db.Column(db.Integer, db.ForeignKey('Departamentos.id'),
                                  nullable=False)
    estado            = db.Column(db.String(20), default='pendiente')
    notas_solicitante = db.Column(db.Text)
    notas_admin       = db.Column(db.Text)
    fecha_solicitud   = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_resolucion  = db.Column(db.DateTime)
    fecha_entrega     = db.Column(db.DateTime)

    solicitante  = db.relationship('Usuario',      back_populates='pedidos')
    departamento = db.relationship('Departamento', back_populates='pedidos')
    detalles     = db.relationship('DetallePedido',
                                   back_populates='pedido',
                                   cascade='all, delete-orphan')

    @classmethod
    def generar_folio(cls) -> str:
        """Genera folio correlativo: PED-YYYY-NNN"""
        from datetime import datetime
        anio = datetime.utcnow().year
        ultimo = (cls.query
                  .filter(cls.folio.like(f'PED-{anio}-%'))
                  .order_by(cls.id.desc())
                  .first())
        num = 1 if not ultimo else int(ultimo.folio.split('-')[-1]) + 1
        return f'PED-{anio}-{num:03d}'


class DetallePedido(db.Model):
    __tablename__ = 'Detalle_Pedido'

    id                  = db.Column(db.Integer, primary_key=True)
    id_pedido           = db.Column(db.Integer, db.ForeignKey('Pedidos.id'),
                                    nullable=False)
    id_material         = db.Column(db.Integer, db.ForeignKey('Materiales.id'),
                                    nullable=False)
    cantidad_solicitada = db.Column(db.Integer, nullable=False)
    cantidad_aprobada   = db.Column(db.Integer)
    precio_unitario_ref = db.Column(db.Numeric(10, 2), default=0.00)

    pedido   = db.relationship('Pedido',   back_populates='detalles')
    material = db.relationship('Material', back_populates='detalles')


class MovimientoInventario(db.Model):
    __tablename__ = 'Movimientos_Inventario'

    id               = db.Column(db.Integer, primary_key=True)
    id_material      = db.Column(db.Integer, db.ForeignKey('Materiales.id'),
                                 nullable=False)
    tipo_movimiento  = db.Column(db.String(15), nullable=False)  # entrada|salida|ajuste
    cantidad         = db.Column(db.Integer, nullable=False)
    stock_resultante = db.Column(db.Integer, nullable=False)
    id_pedido        = db.Column(db.Integer, db.ForeignKey('Pedidos.id'),
                                 nullable=True)
    id_usuario       = db.Column(db.Integer, db.ForeignKey('Usuarios.id'),
                                 nullable=True)
    motivo           = db.Column(db.Text)
    fecha            = db.Column(db.DateTime, default=datetime.utcnow)

    material = db.relationship('Material', back_populates='movimientos')


class PedidoEquipo(db.Model):
    """
    Pedido formal de equipo/material que el personal de mantenimiento
    dirige al administrador del almacén.
    """
    __tablename__ = 'Pedidos_Equipo'

    ESTADOS = ['pendiente', 'aprobado', 'rechazado', 'entregado']

    id             = db.Column(db.Integer, primary_key=True)
    folio          = db.Column(db.String(25), unique=True, nullable=False)
    id_trabajador  = db.Column(db.Integer, db.ForeignKey('Trabajadores.id'),
                               nullable=False)
    id_usuario     = db.Column(db.Integer, db.ForeignKey('Usuarios.id'),
                               nullable=True)   # usuario que registró el pedido
    estado         = db.Column(db.String(20), default='pendiente', nullable=False)
    descripcion    = db.Column(db.Text, nullable=False)  # descripción libre del pedido
    notas_admin    = db.Column(db.Text)
    fecha_pedido   = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_resolucion = db.Column(db.DateTime)

    # ---- items almacenados como líneas de texto (sin FK a Material) ----
    # Se guarda como texto para flexibilidad (puede pedir cosas que aún no
    # están en catálogo).
    items_json     = db.Column(db.Text, default='[]')  # JSON list of {qty, unit, desc}

    trabajador = db.relationship('Trabajador', back_populates='pedidos_equipo')
    usuario    = db.relationship('Usuario', foreign_keys=[id_usuario])

    @classmethod
    def generar_folio(cls) -> str:
        from datetime import datetime as _dt
        anio = _dt.utcnow().year
        ultimo = (cls.query
                  .filter(cls.folio.like(f'MANT-{anio}-%'))
                  .order_by(cls.id.desc())
                  .first())
        num = 1 if not ultimo else int(ultimo.folio.split('-')[-1]) + 1
        return f'MANT-{anio}-{num:03d}'

    def get_items(self):
        import json
        try:
            return json.loads(self.items_json or '[]')
        except Exception:
            return []

    def set_items(self, lista):
        import json
        self.items_json = json.dumps(lista, ensure_ascii=False)

    def __repr__(self):
        return f'<PedidoEquipo {self.folio}>'


# ── Stock propio del departamento de Mantenimiento ─────────────────────────
# Completamente separado del catálogo general (Material / Materiales).
# El personal de mantenimiento llena este stock MANUALMENTE una vez que
# el administrador aprueba y entrega el PedidoEquipo.

class StockMantenimiento(db.Model):
    """
    Ítem del inventario propio de Mantenimiento.
    No comparte tabla con Material; cada artículo es registrado
    manualmente por el personal tras recibir el equipo del almacén.
    """
    __tablename__ = 'Stock_Mantenimiento'

    id             = db.Column(db.Integer, primary_key=True)
    nombre         = db.Column(db.String(200), nullable=False)
    descripcion    = db.Column(db.Text)
    unidad_medida  = db.Column(db.String(50), nullable=False, default='pza')
    cantidad       = db.Column(db.Integer,   default=0, nullable=False)
    cantidad_min   = db.Column(db.Integer,   default=1, nullable=False)
    precio_ref     = db.Column(db.Numeric(10, 2), default=0.00)  # precio referencial
    # Trazabilidad al pedido origen (opcional)
    id_pedido_equipo = db.Column(db.Integer,
                                  db.ForeignKey('Pedidos_Equipo.id'),
                                  nullable=True)
    id_usuario_alta  = db.Column(db.Integer,
                                  db.ForeignKey('Usuarios.id'),
                                  nullable=True)
    fecha_alta       = db.Column(db.DateTime, default=datetime.utcnow)
    activo           = db.Column(db.Boolean, default=True)

    pedido_origen  = db.relationship('PedidoEquipo',
                                      foreign_keys=[id_pedido_equipo])
    usuario_alta   = db.relationship('Usuario',
                                      foreign_keys=[id_usuario_alta])
    movimientos    = db.relationship('MovimientoStockMant',
                                      back_populates='item',
                                      cascade='all, delete-orphan')

    @property
    def bajo_stock(self) -> bool:
        return self.cantidad <= self.cantidad_min

    def __repr__(self):
        return f'<StockMant {self.nombre} qty={self.cantidad}>'


class MovimientoStockMant(db.Model):
    """
    Bitácora de entradas y salidas del stock propio de Mantenimiento.
    Tipo: 'entrada' (carga manual) | 'salida' (consumo/préstamo a técnico) | 'ajuste'
    """
    __tablename__ = 'Movimientos_Stock_Mant'

    id               = db.Column(db.Integer, primary_key=True)
    id_item          = db.Column(db.Integer,
                                  db.ForeignKey('Stock_Mantenimiento.id'),
                                  nullable=False)
    tipo             = db.Column(db.String(15), nullable=False)  # entrada|salida|ajuste
    cantidad         = db.Column(db.Integer, nullable=False)
    cantidad_result  = db.Column(db.Integer, nullable=False)
    # A qué trabajador se le asignó (solo en salidas)
    id_trabajador    = db.Column(db.Integer,
                                  db.ForeignKey('Trabajadores.id'),
                                  nullable=True)
    id_usuario       = db.Column(db.Integer,
                                  db.ForeignKey('Usuarios.id'),
                                  nullable=True)
    motivo           = db.Column(db.Text)
    fecha            = db.Column(db.DateTime, default=datetime.utcnow)

    item       = db.relationship('StockMantenimiento', back_populates='movimientos')
    trabajador = db.relationship('Trabajador',  foreign_keys=[id_trabajador])
    usuario    = db.relationship('Usuario',     foreign_keys=[id_usuario])

    def __repr__(self):
        return f'<MovStockMant {self.tipo} qty={self.cantidad}>'


# ══════════════════════════════════════════════════════════════════════════════
# ÓRDENES DE SERVICIO DE MANTENIMIENTO
# ══════════════════════════════════════════════════════════════════════════════

class FirmaUsuario(db.Model):
    """Firma digital guardada por un Usuario (solicitante o personal de mantenimiento)."""
    __tablename__ = 'Firmas_Usuarios'

    id            = db.Column(db.Integer, primary_key=True)
    id_usuario    = db.Column(db.Integer, db.ForeignKey('Usuarios.id'),
                              nullable=False, unique=True)
    firma_b64     = db.Column(db.Text, nullable=False)   # PNG en base64
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow,
                               onupdate=datetime.utcnow)

    usuario = db.relationship('Usuario', foreign_keys=[id_usuario])


class FirmaTrabajador(db.Model):
    """Firma digital guardada por un Trabajador (técnico de mantenimiento)."""
    __tablename__ = 'Firmas_Trabajadores'

    id            = db.Column(db.Integer, primary_key=True)
    id_trabajador = db.Column(db.Integer, db.ForeignKey('Trabajadores.id'),
                              nullable=False, unique=True)
    firma_b64     = db.Column(db.Text, nullable=False)   # PNG en base64
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow,
                               onupdate=datetime.utcnow)

    trabajador = db.relationship('Trabajador', foreign_keys=[id_trabajador],
                                backref=db.backref('firma_trabajador', uselist=False))


class OrdenServicio(db.Model):
    """
    Orden de Servicio de Mantenimiento (R-AP-33-05-01).
    Solicitante → crea la orden. Mantenimiento → la procesa y firma. Admin → solo lectura.
    """
    __tablename__ = 'Ordenes_Servicio'

    ESTADOS = ['solicitada', 'en_proceso', 'completada', 'no_realizada', 'entregada']
    TIPOS_MANT = ['preventivo', 'correctivo']
    SERVICIOS_OPCIONES = [
        'plomeria', 'computo', 'electricidad',
        'pintura', 'jardineria', 'limpieza', 'ac', 'vehiculos', 'otro',
    ]
    SERVICIOS_LABELS = {
        'plomeria': 'Plomería', 'computo': 'Cómputo', 'electricidad': 'Electricidad',
        'pintura': 'Pintura', 'jardineria': 'Jardinería', 'limpieza': 'Limpieza',
        'ac': 'A/C', 'vehiculos': 'Vehículos', 'otro': 'Otro',
    }

    id                  = db.Column(db.Integer, primary_key=True)
    folio               = db.Column(db.String(25), unique=True, nullable=False)
    id_solicitante      = db.Column(db.Integer, db.ForeignKey('Usuarios.id'), nullable=False)
    id_departamento     = db.Column(db.Integer, db.ForeignKey('Departamentos.id'), nullable=False)
    fecha_solicitud     = db.Column(db.DateTime, default=datetime.utcnow)
    tipo_mantenimiento  = db.Column(db.String(20), nullable=False)   # preventivo|correctivo
    servicios_json      = db.Column(db.Text, nullable=False, default='[]')  # lista de servicios
    otro_servicio       = db.Column(db.String(200))
    descripcion         = db.Column(db.Text, nullable=False)
    estado              = db.Column(db.String(20), default='solicitada', nullable=False)

    # Llenado por mantenimiento al completar
    fecha_ejecucion         = db.Column(db.DateTime)
    servicio_realizado      = db.Column(db.Boolean)
    motivo_no_realizado     = db.Column(db.Text)
    id_trabajador_realizo   = db.Column(db.Integer, db.ForeignKey('Trabajadores.id'), nullable=True)
    notas_mantenimiento     = db.Column(db.Text)

    # Encuesta de satisfacción (llenada por solicitante tras entrega)
    encuesta_completada   = db.Column(db.Boolean, default=False)
    enc_experiencia       = db.Column(db.Integer)   # 1-5
    enc_profesionalismo   = db.Column(db.Integer)   # 1-5
    enc_tiempo_respuesta  = db.Column(db.Integer)   # 1-3
    enc_calidad           = db.Column(db.Integer)   # 1-5
    enc_comunicacion      = db.Column(db.Integer)   # 1-5
    enc_comentarios       = db.Column(db.Text)

    # Firmas en base64 (copiadas al momento de "Entregar")
    firma_realizo_b64      = db.Column(db.Text)   # Trabajador que realizó
    nombre_realizo         = db.Column(db.String(150))
    firma_superviso_b64    = db.Column(db.Text)   # Usuario que supervisó
    nombre_superviso       = db.Column(db.String(150))
    firma_solicitante_b64  = db.Column(db.Text)   # Solicitante conformidad
    nombre_solicitante_firma = db.Column(db.String(150))

    # Firma digital HMAC-SHA256 (nuevas órdenes)
    firma_tipo       = db.Column(db.String(20))   # 'png_legacy' | 'hmac_sha256'
    firma_hmac       = db.Column(db.Text)          # hex digest del HMAC
    firma_canonical  = db.Column(db.Text)          # cadena canónica firmada (auditoría)

    # Archivo generado
    archivo_docx_path  = db.Column(db.String(500))
    fecha_entrega      = db.Column(db.DateTime)

    solicitante         = db.relationship('Usuario', foreign_keys=[id_solicitante])
    departamento        = db.relationship('Departamento', foreign_keys=[id_departamento])
    trabajador_realizo  = db.relationship('Trabajador', foreign_keys=[id_trabajador_realizo])

    def get_servicios(self):
        import json
        try:
            return json.loads(self.servicios_json or '[]')
        except Exception:
            return []

    def set_servicios(self, lista):
        import json
        self.servicios_json = json.dumps(lista, ensure_ascii=False)

    def servicios_texto(self):
        labels = OrdenServicio.SERVICIOS_LABELS
        base = [labels.get(s, s) for s in self.get_servicios() if s != 'otro']
        if 'otro' in self.get_servicios() and self.otro_servicio:
            base.append(f'Otro: {self.otro_servicio}')
        return ', '.join(base)

    @classmethod
    def generar_folio(cls) -> str:
        from datetime import datetime as _dt
        anio = _dt.utcnow().year
        ultimo = (cls.query
                  .filter(cls.folio.like(f'OSM-{anio}-%'))
                  .order_by(cls.id.desc())
                  .first())
        num = 1 if not ultimo else int(ultimo.folio.split('-')[-1]) + 1
        return f'OSM-{anio}-{num:03d}'

    def __repr__(self):
        return f'<OrdenServicio {self.folio} [{self.estado}]>'


# ═══════════════════════════════════════════════════════════════════════════════
# PRÉSTAMO DE EQUIPO AUDIOVISUAL
# ═══════════════════════════════════════════════════════════════════════════════

class DispositivoAV(db.Model):
    """Dispositivo audiovisual registrado (control TV, cable HDMI, extensión, etc.)."""
    __tablename__ = 'Dispositivos_AV'

    id       = db.Column(db.Integer, primary_key=True)
    nombre   = db.Column(db.String(100), nullable=False)   # "Control TV", "Cable HDMI"…
    aula     = db.Column(db.String(60),  nullable=False)   # "Salón 101"
    activo   = db.Column(db.Boolean, default=True)

    prestamos = db.relationship('PrestamoAV', backref='dispositivo',
                                order_by='PrestamoAV.fecha_prestamo.desc()')

    @property
    def disponible(self):
        """True si no hay ningún préstamo activo ('prestado') en este momento."""
        return not any(p.estado == 'prestado' for p in self.prestamos)

    def __repr__(self):
        return f'<DispositivoAV {self.nombre} — {self.aula}>'


class PrestamoAV(db.Model):
    """Registro de préstamo de equipo audiovisual a un alumno."""
    __tablename__ = 'Prestamos_AV'

    ESTADOS = ['prestado', 'devuelto', 'sancionado']

    id                      = db.Column(db.Integer, primary_key=True)
    id_dispositivo          = db.Column(db.Integer, db.ForeignKey('Dispositivos_AV.id'), nullable=False)
    aula                    = db.Column(db.String(60))
    profesor                = db.Column(db.String(150))
    nombre_alumno           = db.Column(db.String(150), nullable=False)
    carrera                 = db.Column(db.String(100))
    matricula               = db.Column(db.String(30))
    telefono                = db.Column(db.String(20))
    fecha_prestamo          = db.Column(db.DateTime, default=datetime.utcnow)
    hora_devolucion_esperada= db.Column(db.DateTime)          # fecha_prestamo + 2h
    fecha_devolucion_real   = db.Column(db.DateTime)
    estado                  = db.Column(db.String(20), default='prestado')
    condicion_ok            = db.Column(db.Boolean)           # True=bien, False=sanción
    nota_sancion            = db.Column(db.Text)

    def __repr__(self):
        return f'<PrestamoAV {self.nombre_alumno} [{self.estado}]>'


class ReservaAuditorio(db.Model):
    """Reserva del Auditorio Interactivo FIT por docente o usuario externo."""
    __tablename__ = 'Reservas_Auditorio'

    TIPOS  = ['docente', 'externo']
    ESTADOS = ['reservado', 'en_uso', 'completado', 'cancelado']

    id              = db.Column(db.Integer, primary_key=True)
    tipo_usuario    = db.Column(db.String(20), nullable=False)   # docente | externo
    nombre          = db.Column(db.String(150), nullable=False)
    matricula       = db.Column(db.String(30))                   # docentes
    departamento    = db.Column(db.String(100), nullable=False)
    telefono        = db.Column(db.String(20))                   # externos
    correo          = db.Column(db.String(120))                  # externos
    nombre_evento   = db.Column(db.String(200), nullable=False)
    descripcion     = db.Column(db.Text)
    fecha_inicio    = db.Column(db.DateTime, nullable=False)
    fecha_fin       = db.Column(db.DateTime, nullable=False)
    estado          = db.Column(db.String(20), default='reservado')
    pago_verificado = db.Column(db.Boolean, default=False)       # solo externos
    notas           = db.Column(db.Text)
    fecha_registro  = db.Column(db.DateTime, default=datetime.utcnow)
    registrado_por  = db.Column(db.Integer, db.ForeignKey('Usuarios.id'))

    registrador = db.relationship('Usuario', foreign_keys=[registrado_por])

    @property
    def duracion_horas(self):
        delta = self.fecha_fin - self.fecha_inicio
        return round(delta.total_seconds() / 3600, 1)

    @property
    def es_externo(self):
        return self.tipo_usuario == 'externo'

    def __repr__(self):
        return f'<ReservaAuditorio {self.nombre_evento} [{self.estado}]>'

