"""
Utilidades de autenticación para API externa
Decoradores para validar API Keys en endpoints públicos
"""
from functools import wraps
from flask import request, jsonify
from app.models.client import Client


def require_api_key(f):
    """
    Decorador para requerir API Key válida en endpoints externos

    Uso:
        @bp.route('/api/external/endpoint')
        @require_api_key
        def endpoint():
            # request.client contendrá el objeto Client autenticado
            pass

    Headers esperados:
        X-API-Key: clip_xxxxxxxxxxxxxxxxxxxx
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Obtener API Key del header
        api_key = request.headers.get('X-API-Key')

        if not api_key:
            return jsonify({
                'success': False,
                'error': 'API Key requerida',
                'message': 'Debe incluir el header X-API-Key con su API Key'
            }), 401

        # Validar API Key
        client = Client.query.filter_by(api_key=api_key, is_active=True).first()

        if not client:
            return jsonify({
                'success': False,
                'error': 'API Key inválida o inactiva',
                'message': 'La API Key proporcionada no es válida o el cliente está inactivo'
            }), 403

        # Adjuntar cliente al request para uso posterior
        request.client = client

        return f(*args, **kwargs)

    return decorated_function


def get_client_from_api_key(api_key: str):
    """
    Obtiene un cliente válido por API Key

    Args:
        api_key: API Key del cliente

    Returns:
        Client o None si no es válida
    """
    if not api_key:
        return None

    return Client.query.filter_by(api_key=api_key, is_active=True).first()
