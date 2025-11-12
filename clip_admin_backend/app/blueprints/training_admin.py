"""Blueprint Admin para entrenamiento visual (Iteración 1 y 2).
"""
from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user
from app.models.category import Category
from app.models.client import Client
from app.models.product import Product
from app.models.image import Image
from flask import current_app
from io import BytesIO
from app.services.training_service import (
    log_training_event,
    recompute_variants,
    list_variants,
    upsert_variant
)
import tempfile
import os

bp = Blueprint('training_admin', __name__, url_prefix='/admin/training')


def _require_category(category_id: str, client_id: str):
    cat = Category.query.filter_by(id=category_id, client_id=client_id).first()
    if not cat:
        return None, jsonify({'success': False, 'error': 'category_not_found'}), 404
    return cat, None, None


@bp.route('/', methods=['GET'])
@login_required
def index():
    """Panel de entrenamiento visual"""
    # Si es superadmin, cargar todos los clientes; si no, solo su cliente
    if current_user.role == 'SUPER_ADMIN':
        clients = Client.query.filter_by(is_active=True).all()
    else:
        clients = []

    return render_template('training/index.html', clients=clients)


@bp.route('/event', methods=['POST'])
@login_required
def create_event():
    data = request.get_json(force=True, silent=True) or {}
    client_id = data.get('client_id') or current_user.client_id
    category_id = data.get('category_id')
    query_image_ref = data.get('query_image_ref')
    topk_results = data.get('topk_results', [])
    positives = data.get('positives', [])
    negatives = data.get('negatives', [])
    variant_key = data.get('variant_key')

    if not category_id:
        return jsonify({'success': False, 'error': 'missing_category_id'}), 400

    # Verificar acceso a categoría
    _, err_resp, status = _require_category(category_id, client_id)
    if err_resp:
        return err_resp, status

    ev = log_training_event(
        client_id=client_id,
        category_id=category_id,
        query_image_ref=query_image_ref,
        topk_results=topk_results,
        positives=positives,
        negatives=negatives,
        variant_key=variant_key
    )

    # Automaticamente recomputar centroides si hay variant_key
    if variant_key:
        try:
            recompute_result = recompute_variants(client_id, category_id)
            print(f"✅ Auto-recompute después de entrenamiento: {recompute_result}")
        except Exception as e:
            print(f"⚠️ Error en auto-recompute: {e}")
            # No fallar el entrenamiento si falla el recompute

    return jsonify({'success': True, 'event': ev.to_dict()})


@bp.route('/recompute', methods=['POST'])
@login_required
def recompute():
    data = request.get_json(force=True, silent=True) or {}
    client_id = data.get('client_id') or current_user.client_id
    category_id = data.get('category_id')
    if not category_id:
        return jsonify({'success': False, 'error': 'missing_category_id'}), 400
    _, err_resp, status = _require_category(category_id, client_id)
    if err_resp:
        return err_resp, status
    result = recompute_variants(client_id, category_id)
    return jsonify(result)


@bp.route('/variants', methods=['GET'])
@login_required
def variants():
    client_id = request.args.get('client_id') or current_user.client_id
    category_id = request.args.get('category_id')
    if not category_id:
        return jsonify([])
    _, err_resp, status = _require_category(category_id, client_id)
    if err_resp:
        return jsonify([])
    data = list_variants(client_id, category_id)
    return jsonify(data)


@bp.route('/variant', methods=['POST'])
@login_required
def variant_upsert():
    data = request.get_json(force=True, silent=True) or {}
    client_id = data.get('client_id') or current_user.client_id
    category_id = data.get('category_id')
    variant_key = data.get('variant_key')
    name = data.get('name') or variant_key
    active = data.get('active', True)
    prompts = data.get('prompts')
    if not category_id or not variant_key:
        return jsonify({'success': False, 'error': 'missing_params'}), 400
    _, err_resp, status = _require_category(category_id, client_id)
    if err_resp:
        return err_resp, status
    variant = upsert_variant(client_id, category_id, variant_key, name, active, prompts)
    return jsonify({'success': True, 'variant': variant})


@bp.route('/search', methods=['POST'])
@login_required
def admin_search():
    """
    Endpoint de búsqueda interna para admins (usa sesión en lugar de API key).
    Proxy simplificado al visual search del cliente logueado.
    """
    try:
        # Obtener client_id del usuario logueado o del form (superadmin)
        client_id = request.form.get('client_id') or str(current_user.client_id)

        # Verificar que el usuario tenga acceso
        if current_user.role != 'SUPER_ADMIN' and str(current_user.client_id) != client_id:
            return jsonify({'error': 'Acceso denegado'}), 403

        # Obtener cliente
        from app.models.client import Client
        client = Client.query.get(client_id)
        if not client:
            return jsonify({'error': 'Cliente no encontrado'}), 404

        # Obtener API key del cliente para usar el endpoint existente
        api_key = client.api_key

        # Verificar imagen
        if 'image' not in request.files:
            return jsonify({'error': 'Imagen requerida'}), 400

        image_file = request.files['image']
        if image_file.filename == '':
            return jsonify({'error': 'No se seleccionó archivo'}), 400

        # Preparar datos para reenviar al endpoint unificado /api/search
        img_bytes = image_file.read()
        image_file.stream.seek(0)

        form_data = {
            'limit': request.form.get('top_k', '20'),
            'threshold': request.form.get('threshold', '0.1'),
            # Pasar hints si el endpoint los soporta
            'category_id': request.form.get('category_id') or '',
            # Flag para permitir más resultados en panel de entrenamiento (sin el cap del widget)
            'admin_training': '1'
        }

        # Reenviar "force_category" si viene marcado desde el frontend
        force_category_flag = request.form.get('force_category')
        if force_category_flag is not None:
            form_data['force_category'] = force_category_flag

        # Reenviar "mode" si viene (opcional, por ahora usamos single como default)
        if request.form.get('mode'):
            form_data['mode'] = request.form.get('mode')

        # Construir request de prueba con multipart/form-data y header X-API-Key
        with current_app.test_request_context(
            '/api/search',
            method='POST',
            data={
                **form_data,
                'image': (BytesIO(img_bytes), image_file.filename or 'upload.jpg')
            },
            headers={'X-API-Key': api_key},
            content_type='multipart/form-data'
        ):
            from app.blueprints.api import visual_search
            return visual_search()

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
