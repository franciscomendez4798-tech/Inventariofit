"""
Genera la Orden de Servicio de Mantenimiento (R-AP-33-05-01) en PDF.

Estrategia:
  1. Usa el PDF oficial original como base (página 1 únicamente).
  2. Crea una capa ReportLab con los valores de la orden.
  3. Mezcla ambas capas con pypdf → PDF final con el formato intacto.

El layout, encabezado y estructura del documento NO se modifican.
Solo se insertan los datos del solicitante y, al finalizar el servicio,
las firmas y datos de ejecución.
"""
import base64
import io
import os

from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas as rl_canvas

_PDF_TEMPLATE = os.path.join(os.path.dirname(__file__), 'template_base.pdf')

PAGE_W = 612.0
PAGE_H = 792.0


def _rl_y(pdf_top: float, font_size: float = 10) -> float:
    """Convierte Y de pdfplumber (desde arriba) a Y de ReportLab (desde abajo)."""
    return PAGE_H - pdf_top - font_size * 0.85


# ── Campos de texto de solicitud ──────────────────────────────────────────
_CAMPOS = {
    'nombre':       (206.0, 159.8),
    'departamento': (196.0, 173.7),
    'descripcion':  (90.0,  368.6),
}

_FECHA_SOL_CENTER_X = 480.0   # centrada entre x=438 y x=522
_FECHA_SOL_Y_TOP    = 132.2

# ── Checkboxes tipo de mantenimiento ──────────────────────────────────────
_CB_TIPO = {
    'preventivo': (108.0, 216.0),
    'correctivo': (108.0, 230.9),
}

# ── Checkboxes tipo de servicio ───────────────────────────────────────────
_CB_SERVICIO = {
    'plomeria':     (126.0, 286.8),
    'computo':      (126.0, 300.7),
    'electricidad': (126.0, 314.4),
    'otro':         (126.0, 328.3),
    'pintura':      (281.8, 286.8),
    'jardineria':   (281.8, 300.7),
    'limpieza':     (281.8, 314.4),
    'ac':           (419.5, 286.8),
    'vehiculos':    (419.5, 300.7),
}
_OTRO_X, _OTRO_Y = 230.0, 327.3

# ── Sección de ejecución (caja inferior) ──────────────────────────────────
# "Fecha de ejecución del servicio:" termina en x=264; valor centrado 264–381
_FECHA_EJ_CENTER_X = 323.0
_FECHA_EJ_Y_TOP    = 448.3

# "Si" ocupa x=226.8–236.8 | "No" ocupa x=246.1–260.8
_SI_X  = 226.0   # inicio de "Si"
_NO_X  = 246.0   # inicio de "No"
_SINO_Y_TOP = 462.2

# Motivo (primera línea de guiones en y=489.8), empieza en x=110
_MOTIVO_X     = 110.0
_MOTIVO_Y_TOP = 489.8

# ── Firmas ────────────────────────────────────────────────────────────────
# Cada firma se centra horizontalmente sobre su bloque y se posiciona
# con el borde INFERIOR de la imagen justo encima de "Nombre y Firma"
_FIRMAS = {
    # (center_x,  y_top_bottom_of_image)  — y_top = pdfplumber top del label
    'realizo':    (192.6, 557.0),   # "Nombre y Firma" Realizó en y_top=569
    'superviso':  (425.1, 555.0),   # "Nombre y Firma" Supervisó en y_top=567
    'solicitante':(306.9, 624.0),   # "Nombre y Firma" Conformidad en y_top=636
}
_MAX_FIRMA_W = 110.0   # ancho máximo de la imagen de firma (pts)
_MAX_FIRMA_H =  40.0   # alto máximo


# ── Helpers ────────────────────────────────────────────────────────────────

def _draw_wrapped(c, text, x, y, max_width, font_name, font_size, line_height=14.0):
    if not text:
        return
    words = text.split()
    line  = ''
    for word in words:
        test = f'{line} {word}'.strip()
        if c.stringWidth(test, font_name, font_size) <= max_width:
            line = test
        else:
            c.drawString(x, y, line)
            y   -= line_height
            line = word
    if line:
        c.drawString(x, y, line)


def _draw_firma(c, firma_b64: str, center_x: float, bottom_y_pdfplumber: float):
    """Dibuja la imagen de firma centrada en center_x con borde inferior en bottom_y."""
    if not firma_b64:
        return
    try:
        raw = base64.b64decode(firma_b64.split(',')[-1])
        img_buf = io.BytesIO(raw)

        # Obtener dimensiones originales con PIL
        from PIL import Image as PILImage
        pil = PILImage.open(io.BytesIO(raw))
        orig_w, orig_h = pil.size

        # Escalar manteniendo aspecto dentro de los límites
        scale = min(_MAX_FIRMA_W / orig_w, _MAX_FIRMA_H / orig_h, 1.0)
        draw_w = orig_w * scale
        draw_h = orig_h * scale

        # Posición: centrada horizontalmente, borde inferior en bottom_y_pdfplumber
        rl_bottom = PAGE_H - bottom_y_pdfplumber
        x = center_x - draw_w / 2

        img_buf.seek(0)
        c.drawImage(
            rl_canvas.ImageReader(img_buf),
            x, rl_bottom,
            width=draw_w, height=draw_h,
            mask='auto',
        )
    except Exception:
        pass   # si falla la firma, continúa sin ella


# ── Construcción de la capa de datos ──────────────────────────────────────

def _draw_overlay(orden) -> io.BytesIO:
    servicios = set(orden.get_servicios()) if callable(
        getattr(orden, 'get_servicios', None)) else set()

    buf = io.BytesIO()
    c   = rl_canvas.Canvas(buf, pagesize=letter)

    fn  = 'Helvetica'
    fnb = 'Helvetica-Bold'
    fs  = 10

    # ── 1. FECHA DE SOLICITUD ────────────────────────────────────────────
    fecha_sol = (orden.fecha_solicitud.strftime('%d / %m / %Y')
                 if orden.fecha_solicitud else '')
    c.setFont(fnb, fs)
    c.drawCentredString(_FECHA_SOL_CENTER_X, _rl_y(_FECHA_SOL_Y_TOP, fs), fecha_sol)

    # ── 2. NOMBRE Y DEPARTAMENTO ─────────────────────────────────────────
    nombre = orden.solicitante.nombre_completo if orden.solicitante else ''
    depto  = orden.departamento.nombre         if orden.departamento else ''
    for campo, valor in [('nombre', nombre), ('departamento', depto)]:
        x, top = _CAMPOS[campo]
        c.drawString(x, _rl_y(top, fs), valor)

    # ── 3. DESCRIPCIÓN ───────────────────────────────────────────────────
    c.setFont(fn, fs)
    x_d, top_d = _CAMPOS['descripcion']
    _draw_wrapped(c, orden.descripcion or '', x_d, _rl_y(top_d, fs),
                  max_width=432.0, font_name=fn, font_size=fs)

    # ── 4. TIPO DE MANTENIMIENTO ─────────────────────────────────────────
    tipo = (orden.tipo_mantenimiento or '').lower()
    c.setFont(fnb, fs + 1)
    for key, (x, top) in _CB_TIPO.items():
        if tipo == key:
            c.drawString(x, _rl_y(top, fs), 'X')

    # ── 5. TIPO DE SERVICIO ──────────────────────────────────────────────
    for key, (x, top) in _CB_SERVICIO.items():
        if key in servicios:
            c.drawString(x, _rl_y(top, fs), 'X')

    if 'otro' in servicios and orden.otro_servicio:
        c.setFont(fn, fs)
        c.drawString(_OTRO_X, _rl_y(_OTRO_Y, fs), orden.otro_servicio)

    # ── 6. SECCIÓN DE EJECUCIÓN (solo si el servicio ya fue completado) ──
    estado = getattr(orden, 'estado', '') or ''
    if estado in ('completada', 'entregada'):

        # 6a. Fecha de ejecución
        fecha_ej = ''
        if getattr(orden, 'fecha_ejecucion', None):
            fecha_ej = orden.fecha_ejecucion.strftime('%d / %m / %Y')
        c.setFont(fnb, fs)
        c.drawCentredString(_FECHA_EJ_CENTER_X, _rl_y(_FECHA_EJ_Y_TOP, fs), fecha_ej)

        # 6b. Sí / No
        realizado = getattr(orden, 'servicio_realizado', True)
        realizado = True if realizado is None else realizado   # default: Sí
        c.setFont(fnb, fs + 2)
        if realizado:
            c.drawString(_SI_X, _rl_y(_SINO_Y_TOP, fs), 'X')
        else:
            c.drawString(_NO_X, _rl_y(_SINO_Y_TOP, fs), 'X')

        # 6c. Motivo (solo si no se realizó)
        motivo = getattr(orden, 'motivo_no_realizado', None) or ''
        if motivo and not realizado:
            c.setFont(fn, fs)
            _draw_wrapped(c, motivo, _MOTIVO_X, _rl_y(_MOTIVO_Y_TOP, fs),
                          max_width=400.0, font_name=fn, font_size=fs)

        # 6d. Firmas
        firma_realizo    = getattr(orden, 'firma_realizo_b64',    None)
        firma_superviso  = getattr(orden, 'firma_superviso_b64',  None)
        firma_solicitante= getattr(orden, 'firma_solicitante_b64',None)

        _draw_firma(c, firma_realizo,     *_FIRMAS['realizo'])
        _draw_firma(c, firma_superviso,   *_FIRMAS['superviso'])
        _draw_firma(c, firma_solicitante, *_FIRMAS['solicitante'])

    c.save()
    buf.seek(0)
    return buf


# ── Función principal ──────────────────────────────────────────────────────

def generar_pdf_orden(orden) -> io.BytesIO:
    """Página 1 del template oficial + overlay con los datos de la orden."""
    reader = PdfReader(_PDF_TEMPLATE)
    page1  = reader.pages[0]

    overlay_pdf  = PdfReader(_draw_overlay(orden))
    page1.merge_page(overlay_pdf.pages[0])

    writer = PdfWriter()
    writer.add_page(page1)

    out = io.BytesIO()
    writer.write(out)
    out.seek(0)
    return out


def guardar_pdf_orden(orden, directorio: str) -> str:
    os.makedirs(directorio, exist_ok=True)
    nombre = f'OSM_{orden.folio}_{orden.fecha_solicitud.strftime("%Y%m%d")}.pdf'
    ruta   = os.path.join(directorio, nombre)
    buf    = generar_pdf_orden(orden)
    with open(ruta, 'wb') as f:
        f.write(buf.read())
    return ruta
