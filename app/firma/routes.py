"""
Rutas públicas de firma en campo (sin login requerido).

Seguridad aplicada:
  - Token UUID de 256 bits (secrets.token_urlsafe), single-use, 4h expiración
  - Token validado tanto en GET como en POST
  - Token incluido en body del form y comparado con compare_digest (CSRF propio)
  - Estado de la orden revalidado en el POST (previene race condition)
  - Las 3 firmas (técnico, supervisor, solicitante) se capturan en el dispositivo
  - Commit atómico: estado 'entregada' + invalidación del token en una sola transacción
  - Rate limit: 10 submit/hora por IP en la ruta pública
  - Cache-Control: no-store en todas las respuestas
  - Tamaño de firma_b64 validado (100 chars mínimo, 600 KB máximo)
"""
import hmac as hmac_lib
from datetime import datetime, timezone

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
    ahora  = datetime.now(timezone.utc)
    expira = orden.token_firma_expira
    if expira is not None and expira.tzinfo is None:
        expira = expira.replace(tzinfo=timezone.utc)
    if not expira or ahora > expira:
        abort(410)
    if orden.estado not in ('completada', 'no_realizada'):
        abort(410)
    return orden


def _validar_firma(valor: str | None) -> bool:
    return bool(valor) and 100 <= len(valor) <= _MAX_FIRMA


@firma_bp.route('/<token>', methods=['GET'])
def firma_movil(token):
    orden = _orden_por_token(token)
    resp = make_response(render_template('firma/firma_movil.html', orden=orden, token=token))
    return _no_cache(resp)


@firma_bp.route('/<token>', methods=['POST'])
@limiter.limit('10/hour', error_message='Demasiados intentos. Intenta más tarde.')
def firma_movil_submit(token):
    orden = _orden_por_token(token)

    body_token = request.form.get('token', '')
    if not hmac_lib.compare_digest(body_token, token):
        abort(400)

    firma_realizo   = request.form.get('firma_realizo', '').strip()
    firma_superviso = request.form.get('firma_superviso', '').strip()
    firma_solic     = request.form.get('firma_solicitante', '').strip()

    if not all(map(_validar_firma, [firma_realizo, firma_superviso, firma_solic])):
        abort(400)

    orden.firma_realizo_b64        = firma_realizo
    orden.firma_superviso_b64      = firma_superviso
    orden.firma_solicitante_b64    = firma_solic
    orden.nombre_solicitante_firma = orden.solicitante.nombre_completo
    orden.estado                   = 'entregada'
    orden.fecha_entrega            = datetime.now(timezone.utc)

    from ..utils.firma_digital import firmar_orden as generar_hmac
    secret = current_app.config.get('FIRMA_SECRET_KEY', '')
    canonical, hmac_hex = generar_hmac(orden, secret)
    orden.firma_tipo      = 'hmac_sha256'
    orden.firma_hmac      = hmac_hex
    orden.firma_canonical = canonical

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
