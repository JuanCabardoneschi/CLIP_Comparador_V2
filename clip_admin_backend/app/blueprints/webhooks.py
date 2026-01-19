"""
Endpoints para recibir webhooks de WooCommerce
"""
from flask import Blueprint, request, jsonify
import logging
import hmac
import hashlib
import base64
import json
from datetime import datetime

from app import db
from app.models.client import Client
from app.models.woocommerce_integration import WooCommerceIntegration

logger = logging.getLogger(__name__)

webhooks_bp = Blueprint('webhooks', __name__, url_prefix='/api/webhooks')


def verify_webhook_signature(payload_body: bytes, signature: str, secret: str) -> bool:
    """
    Verifica la firma HMAC-SHA256 del webhook de WooCommerce
    
    Args:
        payload_body: Body crudo del request (bytes)
        signature: Valor de X-WC-Webhook-Signature (base64)
        secret: Secret del webhook
    
    Returns:
        True si la firma es válida
    """
    try:
        # Calcular HMAC-SHA256
        expected_signature = base64.b64encode(
            hmac.new(
                secret.encode(),
                payload_body,
                hashlib.sha256
            ).digest()
        ).decode()
        
        # Comparar (timing-safe)
        return hmac.compare_digest(expected_signature, signature)
    except Exception as e:
        logger.error(f"Error verificando firma webhook: {str(e)}")
        return False


@webhooks_bp.route('/woocommerce', methods=['POST'])
def handle_woocommerce_webhook():
    """
    Endpoint que recibe los webhooks de WooCommerce
    
    Headers esperados:
    - X-WC-Webhook-ID: ID del webhook
    - X-WC-Webhook-Topic: Tema del evento (product.created, product.updated, etc)
    - X-WC-Webhook-Resource: Recurso (product)
    - X-WC-Webhook-Event: Evento (created, updated, deleted, restored)
    - X-WC-Webhook-Signature: Firma HMAC-SHA256 (base64)
    
    Body:
    - JSON con los datos del producto
    """
    
    # Obtener headers
    webhook_id = request.headers.get('X-WC-Webhook-ID')
    webhook_topic = request.headers.get('X-WC-Webhook-Topic')
    webhook_resource = request.headers.get('X-WC-Webhook-Resource')
    webhook_event = request.headers.get('X-WC-Webhook-Event')
    webhook_signature = request.headers.get('X-WC-Webhook-Signature')
    
    logger.info(f"🔔 Webhook recibido: ID={webhook_id}, Topic={webhook_topic}, Event={webhook_event}")
    
    # Validar que tenemos los headers requeridos
    if not all([webhook_id, webhook_topic, webhook_signature]):
        logger.warning("❌ Webhook incompleto: faltan headers requeridos")
        return jsonify({'error': 'Missing required headers'}), 400
    
    # Obtener body crudo
    payload_body = request.get_data()
    
    # Parsear JSON
    try:
        payload = request.get_json()
    except Exception as e:
        logger.error(f"❌ Error parseando JSON: {str(e)}")
        return jsonify({'error': 'Invalid JSON'}), 400
    
    # Obtener store URL del payload
    store_url = payload.get('_links', {}).get('self', [{}])[0].get('href', '')
    if not store_url:
        logger.warning("⚠️ No store URL en webhook")
        return jsonify({'error': 'No store URL'}), 400
    
    # Buscar integración por store URL
    integration = WooCommerceIntegration.query.filter_by(store_url=store_url).first()
    
    if not integration:
        logger.warning(f"❌ No hay integración para store: {store_url}")
        return jsonify({'error': 'Integration not found'}), 404
    
    # Verificar firma del webhook
    if not verify_webhook_signature(payload_body, webhook_signature, integration.webhook_secret):
        logger.warning(f"❌ Firma inválida para webhook {webhook_id}")
        return jsonify({'error': 'Invalid signature'}), 403
    
    logger.info(f"✅ Firma válida. Procesando webhook...")
    
    # Encolar el procesamiento del webhook (por ahora lo hacemos sincronizadamente)
    try:
        _process_webhook(integration, webhook_topic, webhook_event, payload)
        
        return jsonify({
            'success': True,
            'webhook_id': webhook_id,
            'topic': webhook_topic,
            'message': 'Webhook processed successfully'
        }), 200
    
    except Exception as e:
        logger.error(f"❌ Error procesando webhook: {str(e)}")
        return jsonify({'error': str(e)}), 500


def _process_webhook(integration: WooCommerceIntegration, topic: str, event: str, payload: dict):
    """
    Procesa el webhook según el tipo de evento
    
    Args:
        integration: Integración WooCommerce
        topic: Tema del evento (product.created, product.updated, etc)
        event: Evento (created, updated, deleted, restored)
        payload: Datos del evento
    """
    
    product_id = payload.get('id')
    product_name = payload.get('name', 'Unknown')
    
    logger.info(f"🔄 Procesando {topic}: producto {product_id} ({product_name})")
    
    if event == 'created':
        logger.info(f"➕ Nuevo producto: {product_name}")
        # TODO: Implementar lógica de sincronización incremental para nuevos productos
    
    elif event == 'updated':
        logger.info(f"🔄 Producto actualizado: {product_name}")
        # TODO: Implementar lógica de sincronización incremental para cambios
    
    elif event == 'deleted':
        logger.info(f"🗑️ Producto eliminado: {product_name}")
        # TODO: Implementar lógica para marcar producto como inactivo
    
    elif event == 'restored':
        logger.info(f"♻️ Producto restaurado: {product_name}")
        # TODO: Implementar lógica para reactivar producto
    
    # Por ahora solo loguear
    logger.info(f"📝 Webhook procesado: {topic} - {product_name}")

