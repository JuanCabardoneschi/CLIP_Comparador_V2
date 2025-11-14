"""
Blueprint para la página de búsqueda del widget
Ruta pública para clientes que acceden desde el botón del widget
"""
from flask import Blueprint, render_template, request, redirect, url_for
from app.models import Client
from app import db

widget_search_bp = Blueprint('widget_search', __name__, url_prefix='/widget')

@widget_search_bp.route('/search')
def search_page():
    """
    Página de búsqueda del widget
    Query params:
    - api_key: API key del cliente (requerido)
    - return_url: URL para volver (opcional)
    """
    api_key = request.args.get('api_key')
    return_url = request.args.get('return_url', '')

    # Validar API key
    if not api_key:
        return render_template('widget/error.html',
                             error='API key requerida',
                             message='No se proporcionó una API key válida'), 400

    # Verificar que la API key existe buscando en clientes
    client = Client.query.filter_by(api_key=api_key, is_active=True).first()
    if not client:
        return render_template('widget/error.html',
                             error='API key inválida',
                             message='La API key proporcionada no es válida'), 403

    # Renderizar página de búsqueda
    return render_template('widget/search.html',
                         api_key=api_key,
                         client_name=client.name,
                         return_url=return_url)
