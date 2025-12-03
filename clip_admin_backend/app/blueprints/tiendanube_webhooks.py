"""
Tiendanube Webhooks Receiver Blueprint
=======================================
Procesa webhooks de Tiendanube con verificación HMAC.

Events:
- product/created, product/updated, product/deleted
- category/created, category/updated, category/deleted
- app/suspended, app/uninstalled

Security:
- HMAC-SHA256 verification using X-Linked-Nube-Info-Id + request body + CLIENT_SECRET
"""
import hashlib
import hmac
import json
import logging
from flask import Blueprint, request, jsonify, current_app
from app import db
from app.models.tiendanube_integration import TiendanubeIntegration
from app.models.product import Product
from app.models.category import Category
from app.models.image import Image
from app.services.tiendanube_sync_service import TiendanubeSyncService
from datetime import datetime

logger = logging.getLogger(__name__)

tiendanube_webhooks_bp = Blueprint('tiendanube_webhooks', __name__, url_prefix='/api/webhooks/tiendanube')


def verify_hmac(store_id: str, request_body: bytes) -> bool:
    """
    Verifica firma HMAC del webhook según documentación Tiendanube.

    HMAC = SHA256(store_id + request_body + CLIENT_SECRET)

    Args:
        store_id: ID de tienda desde X-Linked-Nube-Info-Id
        request_body: Body raw del request

    Returns:
        True si la firma es válida
    """
    try:
        client_secret = current_app.config.get('TIENDANUBE_CLIENT_SECRET', '')
        if not client_secret:
            logger.error("TIENDANUBE_CLIENT_SECRET no configurado")
            return False

        # Construir mensaje: store_id + body + secret
        message = store_id + request_body.decode('utf-8') + client_secret

        # Calcular HMAC-SHA256
        expected_signature = hmac.new(
            client_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        # Obtener firma del header
        received_signature = request.headers.get('X-Linkedstore-Webhook-Signature', '')

        # Comparación segura
        return hmac.compare_digest(expected_signature, received_signature)

    except Exception as e:
        logger.error(f"Error verificando HMAC: {str(e)}")
        return False


def get_integration_by_store_id(store_id: str) -> TiendanubeIntegration:
    """Busca integración activa por store_id."""
    integration = TiendanubeIntegration.query.filter_by(
        store_id=store_id,
        is_active=True
    ).first()

    if not integration:
        logger.warning(f"Integración no encontrada o inactiva para store_id={store_id}")

    return integration


@tiendanube_webhooks_bp.route('/product', methods=['POST'])
def webhook_product():
    """
    Webhook: product/created, product/updated, product/deleted

    Payload example:
    {
        "event": "product/created",
        "store_id": "123456",
        "id": "789" (product_id)
    }
    """
    try:
        # Obtener payload primero
        payload = request.get_json()

        # Obtener store_id del header o del payload (fallback)
        store_id = request.headers.get('X-Linked-Nube-Info-Id', '')
        if not store_id:
            store_id = str(payload.get('store_id', ''))
            if not store_id:
                logger.warning("Webhook sin X-Linked-Nube-Info-Id header ni store_id en payload")
                return jsonify({"error": "Missing store_id"}), 400
            logger.info(f"📋 store_id obtenido del payload: {store_id}")

        # Verificar HMAC
        if not verify_hmac(store_id, request.data):
            logger.warning(f"HMAC inválido para store_id={store_id}")
            return jsonify({"error": "Invalid signature"}), 401

        event = payload.get('event', '')
        product_id = str(payload.get('id', ''))

        logger.info(f"Webhook recibido: {event} para product_id={product_id}, store_id={store_id}")

        # Buscar integración
        integration = get_integration_by_store_id(store_id)
        if not integration:
            return jsonify({"error": "Integration not found"}), 404

        # Inicializar servicio de sync
        sync_service = TiendanubeSyncService(integration)

        # Procesar según evento
        if event == 'product/created' or event == 'product/updated':
            # Sincronizar producto específico
            product = sync_service._sync_single_product(product_id)
            if product:
                logger.info(f"Producto {event.split('/')[1]}: {product.name} (id={product.id})")
                return jsonify({
                    "status": "success",
                    "event": event,
                    "product_id": str(product.id)
                }), 200
            else:
                logger.error(f"Error sincronizando producto {product_id}")
                return jsonify({"error": "Sync failed"}), 500

        elif event == 'product/deleted':
            # Marcar producto como inactivo
            product = Product.query.filter_by(
                client_id=integration.client_id,
                external_id=product_id
            ).first()

            if product:
                product.is_active = False
                product.sync_status = 'deleted'
                product.last_sync_at = datetime.utcnow()
                db.session.commit()
                logger.info(f"Producto eliminado: {product.name} (external_id={product_id})")
                return jsonify({"status": "deleted"}), 200
            else:
                logger.warning(f"Producto {product_id} no encontrado para eliminar")
                return jsonify({"status": "not_found"}), 404

        else:
            logger.warning(f"Evento desconocido: {event}")
            return jsonify({"error": "Unknown event"}), 400

    except Exception as e:
        logger.error(f"Error procesando webhook de producto: {str(e)}", exc_info=True)
        return jsonify({"error": "Internal error"}), 500


@tiendanube_webhooks_bp.route('/category', methods=['POST'])
def webhook_category():
    """
    Webhook: category/created, category/updated, category/deleted

    Payload example:
    {
        "event": "category/created",
        "store_id": "123456",
        "id": "789" (category_id)
    }
    """
    try:
        # Obtener payload primero
        payload = request.get_json()

        # Obtener store_id del header o del payload (fallback)
        store_id = request.headers.get('X-Linked-Nube-Info-Id', '')
        if not store_id:
            store_id = str(payload.get('store_id', ''))
            if not store_id:
                logger.warning("Webhook sin X-Linked-Nube-Info-Id header ni store_id en payload")
                return jsonify({"error": "Missing store_id"}), 400
            logger.info(f"📋 store_id obtenido del payload: {store_id}")

        # Verificar HMAC
        if not verify_hmac(store_id, request.data):
            logger.warning(f"HMAC inválido para store_id={store_id}")
            return jsonify({"error": "Invalid signature"}), 401

        event = payload.get('event', '')
        category_id = str(payload.get('id', ''))

        logger.info(f"Webhook recibido: {event} para category_id={category_id}, store_id={store_id}")

        # Buscar integración
        integration = get_integration_by_store_id(store_id)
        if not integration:
            return jsonify({"error": "Integration not found"}), 404

        # Inicializar servicio de sync
        sync_service = TiendanubeSyncService(integration)

        # Procesar según evento
        if event == 'category/created' or event == 'category/updated':
            # Sincronizar categoría específica
            category = sync_service._sync_single_category(category_id)
            if category:
                logger.info(f"Categoría {event.split('/')[1]}: {category.name} (id={category.id})")
                return jsonify({
                    "status": "success",
                    "event": event,
                    "category_id": str(category.id)
                }), 200
            else:
                logger.error(f"Error sincronizando categoría {category_id}")
                return jsonify({"error": "Sync failed"}), 500

        elif event == 'category/deleted':
            # Marcar categoría como inactiva
            category = Category.query.filter_by(
                client_id=integration.client_id,
                external_id=category_id
            ).first()

            if category:
                category.is_active = False
                category.sync_status = 'deleted'
                category.last_sync_at = datetime.utcnow()
                db.session.commit()
                logger.info(f"Categoría eliminada: {category.name} (external_id={category_id})")
                return jsonify({"status": "deleted"}), 200
            else:
                logger.warning(f"Categoría {category_id} no encontrada para eliminar")
                return jsonify({"status": "not_found"}), 404

        else:
            logger.warning(f"Evento desconocido: {event}")
            return jsonify({"error": "Unknown event"}), 400

    except Exception as e:
        logger.error(f"Error procesando webhook de categoría: {str(e)}", exc_info=True)
        return jsonify({"error": "Internal error"}), 500


@tiendanube_webhooks_bp.route('/app', methods=['POST'])
def webhook_app():
    """
    Webhook: app/suspended, app/uninstalled

    Payload example:
    {
        "event": "app/suspended",
        "store_id": "123456"
    }
    """
    try:
        # Obtener payload primero
        payload = request.get_json()

        # Obtener store_id del header o del payload (fallback)
        store_id = request.headers.get('X-Linked-Nube-Info-Id', '')
        if not store_id:
            store_id = str(payload.get('store_id', ''))
            if not store_id:
                logger.warning("Webhook sin X-Linked-Nube-Info-Id header ni store_id en payload")
                return jsonify({"error": "Missing store_id"}), 400
            logger.info(f"📋 store_id obtenido del payload: {store_id}")

        # Verificar HMAC
        if not verify_hmac(store_id, request.data):
            logger.warning(f"HMAC inválido para store_id={store_id}")
            return jsonify({"error": "Invalid signature"}), 401

        event = payload.get('event', '')

        logger.info(f"Webhook recibido: {event} para store_id={store_id}")

        # Buscar integración
        integration = get_integration_by_store_id(store_id)
        if not integration:
            return jsonify({"error": "Integration not found"}), 404

        # Procesar según evento
        if event == 'app/suspended':
            integration.is_active = False
            integration.integration_status = 'suspended'
            db.session.commit()
            logger.info(f"Integración suspendida: store_id={store_id}")
            return jsonify({"status": "suspended"}), 200

        elif event == 'app/uninstalled':
            # Desactivar integración y datos asociados
            integration.is_active = False
            integration.integration_status = 'uninstalled'

            # Desactivar cliente (no eliminar, por política GDPR)
            client = integration.client
            client.is_active = False

            db.session.commit()
            logger.info(f"Integración desinstalada: store_id={store_id}, client_id={integration.client_id}")
            return jsonify({"status": "uninstalled"}), 200

        elif event == 'store/redact':
            # GDPR: Solicitud de eliminación de datos de la tienda
            integration.is_active = False
            integration.integration_status = 'redacted'

            # Desactivar cliente y marcar para revisión GDPR
            client = integration.client
            client.is_active = False

            db.session.commit()
            logger.warning(f"🔒 GDPR: Solicitud de eliminación de datos - store_id={store_id}, client_id={integration.client_id}")
            return jsonify({"status": "redacted", "message": "Data marked for deletion"}), 200

        else:
            logger.warning(f"Evento desconocido: {event}")
            return jsonify({"error": "Unknown event"}), 400

    except Exception as e:
        logger.error(f"Error procesando webhook de app: {str(e)}", exc_info=True)
        return jsonify({"error": "Internal error"}), 500


@tiendanube_webhooks_bp.route('/gdpr', methods=['POST'])
def webhook_gdpr():
    """
    Webhook GDPR: Solicitudes de datos o eliminación

    Payload example:
    {
        "event": "customer/data_request" | "customer/redact",
        "store_id": "123456",
        "customer_id": "789"
    }

    Nota: Implementación básica. Puede requerir proceso manual según GDPR.
    """
    try:
        # Obtener store_id del header
        store_id = request.headers.get('X-Linked-Nube-Info-Id', '')
        if not store_id:
            logger.warning("Webhook GDPR sin X-Linked-Nube-Info-Id header")
            return jsonify({"error": "Missing store_id"}), 400

        # Verificar HMAC
        if not verify_hmac(store_id, request.data):
            logger.warning(f"HMAC inválido para GDPR webhook, store_id={store_id}")
            return jsonify({"error": "Invalid signature"}), 401

        # Obtener payload
        payload = request.get_json()
        event = payload.get('event', '')
        customer_id = payload.get('customer_id', '')

        logger.warning(f"GDPR Webhook recibido: {event} para customer_id={customer_id}, store_id={store_id}")

        # Registrar en logs para procesamiento manual
        # En producción, esto debería crear un ticket o notificación
        logger.warning(f"⚠️ ACCIÓN GDPR REQUERIDA: {event} - store_id={store_id}, customer_id={customer_id}")

        return jsonify({
            "status": "acknowledged",
            "message": "GDPR request logged for processing"
        }), 200

    except Exception as e:
        logger.error(f"Error procesando webhook GDPR: {str(e)}", exc_info=True)
        return jsonify({"error": "Internal error"}), 500


@tiendanube_webhooks_bp.route('/health', methods=['GET'])
def health():
    """Health check endpoint for webhook receiver."""
    return jsonify({"status": "ok", "service": "tiendanube_webhooks"}), 200
