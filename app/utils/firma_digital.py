"""
Firma digital HMAC-SHA256 para Órdenes de Servicio.

Garantiza que:
- La firma está vinculada al folio específico de la orden
- Cualquier modificación de nombres o imágenes PNG invalida la firma
- Nuevos departamentos y usuarios se benefician automáticamente
- Las órdenes legado (png_legacy) no se alteran

Uso:
    canonical, hmac_hex = firmar_orden(orden, secret_key)
    valida = verificar_firma(orden, secret_key)
"""
import hashlib
import hmac as hmac_lib


def _sha256_b64(data: str | None) -> str:
    """Hash SHA-256 de un string base64 (imagen PNG). Retorna 'vacio' si no hay datos."""
    if not data:
        return 'vacio'
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


def _canonical_string(orden) -> str:
    """
    Construye la cadena canónica que se firmará.
    Cualquier cambio en estos campos invalida la firma.
    """
    fecha = orden.fecha_entrega.isoformat() if orden.fecha_entrega else 'sin_fecha'
    return '|'.join([
        orden.folio,
        fecha,
        orden.nombre_realizo or 'sin_realizo',
        orden.nombre_superviso or 'sin_superviso',
        orden.nombre_solicitante_firma or 'sin_solicitante',
        _sha256_b64(orden.firma_realizo_b64),
        _sha256_b64(orden.firma_superviso_b64),
        _sha256_b64(orden.firma_solicitante_b64),
    ])


def firmar_orden(orden, secret_key: str) -> tuple[str, str]:
    """
    Genera la firma HMAC-SHA256 para una orden de servicio.

    Retorna:
        (canonical_string, hmac_hex)
    """
    canonical = _canonical_string(orden)
    mac = hmac_lib.new(
        secret_key.encode('utf-8'),
        canonical.encode('utf-8'),
        hashlib.sha256
    )
    return canonical, mac.hexdigest()


def verificar_firma(orden, secret_key: str) -> bool:
    """
    Verifica que la firma almacenada en la orden sea válida.

    Retorna True si la firma es correcta, False si fue alterada o es legado.
    """
    if orden.firma_tipo != 'hmac_sha256':
        return False
    if not orden.firma_hmac:
        return False

    canonical, expected = firmar_orden(orden, secret_key)

    # Comparación segura contra timing attacks
    return hmac_lib.compare_digest(expected, orden.firma_hmac)
