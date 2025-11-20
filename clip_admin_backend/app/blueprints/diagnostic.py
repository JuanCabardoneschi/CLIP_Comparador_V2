"""
DEPRECADO: Módulo de diagnóstico eliminado.

Este módulo ha sido deprecado el 19 de noviembre de 2025.
Ya no proporciona funcionalidad alguna.

Todas las rutas devuelven HTTP 410 Gone.
"""

from flask import Blueprint, jsonify

diagnostic_bp = Blueprint('diagnostic', __name__, url_prefix='/diagnostic')


@diagnostic_bp.route('/', defaults={'path': ''})
@diagnostic_bp.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def deprecated_endpoint(path):
    """
    Devuelve HTTP 410 Gone para todas las rutas del módulo diagnostic.
    
    Este endpoint fue deprecado el 19 de noviembre de 2025.
    Utiliza los endpoints principales de búsqueda en su lugar:
    - /api/search/text
    - /api/search/gpt4v-unified
    """
    return jsonify({
        'error': 'Gone',
        'message': 'Este endpoint ha sido eliminado permanentemente.',
        'deprecated_date': '2025-11-19',
        'alternatives': [
            '/api/search/text',
            '/api/search/gpt4v-unified'
        ]
    }), 410
