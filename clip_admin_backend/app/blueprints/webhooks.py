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
from app.models.product import Product
from app.models.category import Category
from app.models.image import Image

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
        _handle_product_created(integration, payload)

    elif event == 'updated':
        logger.info(f"🔄 Producto actualizado: {product_name}")
        _handle_product_updated(integration, payload)

    elif event == 'deleted':
        logger.info(f"🗑️ Producto eliminado: {product_name}")
        _handle_product_deleted(integration, payload)

    elif event == 'restored':
        logger.info(f"♻️ Producto restaurado: {product_name}")
        _handle_product_restored(integration, payload)

    logger.info(f"✅ Webhook procesado: {topic} - {product_name}")


def _handle_product_created(integration: WooCommerceIntegration, payload: dict):
    """Crear nuevo producto desde webhook"""
    try:
        client = Client.query.get(integration.client_id)
        if not client:
            logger.error(f"Cliente {integration.client_id} no encontrado")
            return

        ext_id = str(payload.get('id'))
        if not ext_id:
            logger.warning("Webhook: No product ID en payload")
            return

        # Evitar duplicados
        existing = Product.query.filter_by(client_id=client.id, external_id=ext_id).first()
        if existing:
            logger.info(f"Producto {ext_id} ya existe, actualizando en su lugar")
            _handle_product_updated(integration, payload)
            return

        # Resolver categoría
        category_id = _resolve_category_id(client.id, payload.get('categories', []))
        if not category_id:
            logger.warning(f"Webhook: No hay categoría válida para producto {ext_id}")
            return

        # Crear producto
        product = Product(
            client_id=client.id,
            external_id=ext_id,
            category_id=category_id,
            name=payload.get('name') or 'Sin nombre',
        )
        db.session.add(product)
        db.session.flush()

        # Actualizar campos
        _update_product_fields(product, payload)
        db.session.add(product)
        db.session.commit()

        logger.info(f"✅ Producto creado: {ext_id} ({product.name})")

    except Exception as e:
        logger.error(f"Error creando producto desde webhook: {str(e)}", exc_info=True)
        db.session.rollback()


def _handle_product_updated(integration: WooCommerceIntegration, payload: dict):
    """Actualizar producto existente desde webhook"""
    try:
        client = Client.query.get(integration.client_id)
        if not client:
            logger.error(f"Cliente {integration.client_id} no encontrado")
            return

        ext_id = str(payload.get('id'))
        if not ext_id:
            logger.warning("Webhook: No product ID en payload")
            return

        product = Product.query.filter_by(client_id=client.id, external_id=ext_id).first()
        if not product:
            logger.warning(f"Producto {ext_id} no encontrado, creando nuevo")
            _handle_product_created(integration, payload)
            return

        # Actualizar campos
        _update_product_fields(product, payload)
        db.session.add(product)
        db.session.commit()

        logger.info(f"✅ Producto actualizado: {ext_id} ({product.name})")

    except Exception as e:
        logger.error(f"Error actualizando producto desde webhook: {str(e)}", exc_info=True)
        db.session.rollback()


def _handle_product_deleted(integration: WooCommerceIntegration, payload: dict):
    """Marcar producto como inactivo cuando se elimina en WooCommerce"""
    try:
        client = Client.query.get(integration.client_id)
        if not client:
            logger.error(f"Cliente {integration.client_id} no encontrado")
            return

        ext_id = str(payload.get('id'))
        if not ext_id:
            logger.warning("Webhook: No product ID en payload")
            return

        product = Product.query.filter_by(client_id=client.id, external_id=ext_id).first()
        if not product:
            logger.warning(f"Producto {ext_id} no encontrado para deletear")
            return

        product.is_active = False
        product.sync_status = 'synced'
        product.last_sync_at = datetime.utcnow()
        db.session.add(product)
        db.session.commit()

        logger.info(f"✅ Producto marcado como inactivo: {ext_id}")

    except Exception as e:
        logger.error(f"Error deletando producto desde webhook: {str(e)}", exc_info=True)
        db.session.rollback()


def _handle_product_restored(integration: WooCommerceIntegration, payload: dict):
    """Reactivar producto cuando se restaura en WooCommerce"""
    try:
        client = Client.query.get(integration.client_id)
        if not client:
            logger.error(f"Cliente {integration.client_id} no encontrado")
            return

        ext_id = str(payload.get('id'))
        if not ext_id:
            logger.warning("Webhook: No product ID en payload")
            return

        product = Product.query.filter_by(client_id=client.id, external_id=ext_id).first()
        if not product:
            logger.warning(f"Producto {ext_id} no encontrado para restaurar")
            return

        product.is_active = True
        product.sync_status = 'synced'
        product.last_sync_at = datetime.utcnow()
        db.session.add(product)
        db.session.commit()

        logger.info(f"✅ Producto reactivado: {ext_id}")

    except Exception as e:
        logger.error(f"Error restaurando producto desde webhook: {str(e)}", exc_info=True)
        db.session.rollback()


def _update_product_fields(product: Product, payload: dict):
    """Actualizar campos del producto desde payload de WooCommerce"""
    # Campos básicos
    product.name = payload.get('name') or product.name
    product.description = payload.get('description') or product.description
    product.sku = payload.get('sku') or product.sku
    product.external_url = payload.get('permalink') or product.external_url
    product.is_active = payload.get('status', 'publish') == 'publish'
    product.sync_status = 'synced'
    product.last_sync_at = datetime.utcnow()

    # Precio
    price = payload.get('price')
    if price not in (None, ''):
        try:
            product.price = float(price)
        except (ValueError, TypeError):
            logger.warning(f"Precio inválido para producto: {price}")

    # Stock
    stock_q = payload.get('stock_quantity')
    if stock_q is not None:
        try:
            product.stock = int(stock_q)
        except (ValueError, TypeError):
            logger.warning(f"Stock inválido para producto: {stock_q}")

    # Categoría
    categories = payload.get('categories', [])
    if categories:
        new_category_id = _resolve_category_id(product.client_id, categories)
        if new_category_id:
            product.category_id = new_category_id

    # Atributos
    attributes = _extract_attributes(payload.get('attributes', []) or [])
    if attributes:
        product.attributes = attributes


def _resolve_category_id(client_id: str, categories: list) -> str:
    """Resolver la categoría interna desde las categorías de WooCommerce"""
    for cat in categories or []:
        ext_id = str(cat.get('id')) if cat.get('id') is not None else None
        if not ext_id:
            continue
        existing = Category.query.filter_by(client_id=client_id, external_id=ext_id).first()
        if existing:
            return existing.id
    return None


def _extract_attributes(attributes_list: list) -> dict:
    """Extraer atributos del payload de WooCommerce"""
    attrs = {}
    for attr in attributes_list or []:
        key = attr.get('name') or attr.get('slug')
        if not key:
            continue
        options = attr.get('options') or []
        value = None

        if isinstance(options, list):
            if len(options) == 1:
                value = options[0]
            elif len(options) > 1:
                value = options
        else:
            value = options

        if value is not None:
            attrs[key] = value

    return attrs

