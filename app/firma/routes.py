"""
Rutas públicas de firma en campo (sin login requerido).

Seguridad aplicada:
  - Token UUID de 256 bits (secrets.token_urlsafe), single-use, 4h expiración
  - Token validado tanto en GET como en POST
  - Token incluido en body del form y comparado con compare_digest (CSRF propio)
  - Estado de la orden revalidado en el POST (previene race condition)
  - Firma pre-cargada del supervisor capturada al generar el token
  - Commit atómico: estado 'entregada' + invalidación del token en una sola transacción
  - Rate limit: 10 submit/hora por IP en la ruta pública
  - Cache-Control: no-store en todas las respuestas
  - Tamaño de firma_b64 validado (100 chars mínimo, 600 KB máximo)
"""
import hmac as hmac_lib
import os
from datetime import datetime

from flask import abort, current_app, make_response, render_template, request

from . import firma_bp
from ..extensions import db, limiter
from ..models import OrdenServicio

_MAX_FIRMA = 600_000   # ~450 KB en base64


def _no_cache(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    return response


def _orden_por_token(token: str) -> OrdenServicio:
    """Busca y valida la orden. Aborta con 404 si no existe o 410 si expiró/cerrada."""
    orden = OrdenServicio.query.filter_by(token_firma=token).first()
    if not orden:
        abort(404)
    ahora = datetime.utcnow()
    if not orden.token_firma_expira or ahora > orden.token_firma_expira:
        abort(410)  # Gone — expirado
    if orden.estado not in ('completada', 'no_realizada'):
        abort(410)  # Orden ya cerrada
    return orden


@firma_bp.route('/<token>', methods=['GET'])
def firma_movil(token):
    orden = _orden_por_token(token)
    resp = make_response(render_template('firma/firma_movil.html', orden=orden, token=token))
    return _no_cache(resp)


@firma_bp.route('/<token>', methods=['POST'])
@limiter.limit('10/hour', error_message='Demasiados intentos. Intenta más tarde.')
def firma_movil_submit(token):
    # 1. Revalidar token en URL
    orden = _orden_por_token(token)

    # 2. Token en body == token en URL (protección CSRF propia para ruta pública)
    body_token = request.form.get('token', '')
    if not hmac_lib.compare_digest(body_token, token):
        abort(400)

    # 3. Validar que el supervisor ya tiene firma pre-cargada (se cargó al generar el token)
    if not orden.firma_superviso_b64:
        abort(409)

    # 4. Validar firmas recibidas
    firma_realizo = request.form.get('firma_realizo', '').strip()
    firma_solic   = request.form.get('firma_solicitante', '').strip()

    if not firma_realizo or not (100 <= len(firma_realizo) <= _MAX_FIRMA):
        abort(400)
    if not firma_solic or not (100 <= len(firma_solic) <= _MAX_FIRMA):
        abort(400)

    # 5. Aplicar firmas
    orden.firma_realizo_b64        = firma_realizo
    orden.firma_solicitante_b64    = firma_solic
    orden.nombre_solicitante_firma = orden.solicitante.nombre_completo
    orden.estado                   = 'entregada'
    orden.fecha_entrega            = datetime.utcnow()

    # 6. HMAC-SHA256 de integridad (vincula folio + fecha + nombres + hashes de firmas)
    from ..utils.firma_digital import firmar_orden as generar_hmac
    secret = current_app.config.get('FIRMA_SECRET_KEY', '')
    canonical, hmac_hex = generar_hmac(orden, secret)
    orden.firma_tipo      = 'hmac_sha256'
    orden.firma_hmac      = hmac_hex
    orden.firma_canonical = canonical

    # 7. Generar PDF
    try:
        from ..utils.orden_servicio_pdf import guardar_pdf_orden
        directorio = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'static', 'uploads', 'ordenes_servicio'
        )
        ruta_abs = guardar_pdf_orden(orden, directorio)
        ruta_rel = os.path.relpath(ruta_abs, os.path.dirname(os.path.dirname(__file__)))
        orden.archivo_docx_path = ruta_rel
    except Exception:
        pass  # La orden se cierra igual; el PDF puede regenerarse manualmente

    # 8. Invalidar token — mismo commit que el cambio de estado (atómico)
    orden.token_firma        = None
    orden.token_firma_expira = None

    db.session.commit()

    resp = make_response(render_template('firma/ok.html'))
    return _no_cache(resp)


# ── Manejadores de error propios para esta sección ────────────────────────────

@firma_bp.app_errorhandler(410)
def gone(e):
    resp = make_response(render_template('firma/expirado.html'), 410)
    return _no_cache(resp)
