"""
Endpoints para recibir webhooks de WooCommerce
Versión: 2.0
"""
from flask import Blueprint, request, jsonify
import logging
import hmac
import hashlib
import base64
import json
import threading
from datetime import datetime

from app import db
from app.models.client import Client
from app.models.woocommerce_integration import WooCommerceIntegration
from app.models.product import Product
from app.models.category import Category
from app.models.image import Image

logger = logging.getLogger(__name__)

webhooks_bp = Blueprint('webhooks', __name__, url_prefix='/api/webhooks')


@webhooks_bp.route('/test', methods=['GET'])
def webhook_test():
    """Endpoint de prueba mínimo"""
    return "WEBHOOK BLUEPRINT WORKS!", 200


@webhooks_bp.route('/health', methods=['GET'])
def webhook_health():
    """Endpoint para verificar si el servidor puede recibir webhooks"""
    logger.info("✅ [WEBHOOK HEALTH] Server is reachable!")
    return jsonify({
        'status': 'healthy',
        'message': 'Webhook endpoint is reachable',
        'timestamp': datetime.utcnow().isoformat()
    }), 200


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

    logger.info(f"🔔 [WEBHOOK] ID={webhook_id}, Topic={webhook_topic}, Event={webhook_event}, Resource={webhook_resource}")

    # Validar que tenemos los headers requeridos
    if not all([webhook_id, webhook_topic, webhook_signature]):
        logger.warning("❌ [WEBHOOK] Incompleto: faltan headers requeridos")
        return jsonify({'error': 'Missing required headers'}), 400

    # Obtener body crudo
    payload_body = request.get_data()

    # Parsear JSON
    try:
        payload = request.get_json()
    except Exception as e:
        logger.error(f"❌ [WEBHOOK] Error parseando JSON: {str(e)}")
        return jsonify({'error': 'Invalid JSON'}), 400

    # Obtener store URL del payload
    store_url = payload.get('_links', {}).get('self', [{}])[0].get('href', '')
    if not store_url:
        logger.warning("⚠️ [WEBHOOK] No store URL en payload")
        return jsonify({'error': 'No store URL'}), 400

    # Buscar integración por store URL
    integration = WooCommerceIntegration.query.filter_by(store_url=store_url).first()

    if not integration:
        logger.warning(f"❌ [WEBHOOK] No hay integración para store: {store_url}")
        return jsonify({'error': 'Integration not found'}), 404

    logger.info(f"✅ [WEBHOOK] Integración encontrada: {integration.client_id}")

    # Verificar firma del webhook
    if not verify_webhook_signature(payload_body, webhook_signature, integration.webhook_secret):
        logger.warning(f"❌ [WEBHOOK] Firma inválida para webhook {webhook_id}")
        return jsonify({'error': 'Invalid signature'}), 403

    logger.info(f"✅ [WEBHOOK] Firma válida. Procesando webhook...")

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
        logger.error(f"❌ [WEBHOOK] Error procesando webhook: {str(e)}", exc_info=True)
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

    logger.info(f"🔄 [WEBHOOK] Procesando: {topic} - Producto #{product_id} ({product_name})")

    if event == 'created':
        logger.info(f"➕ [WEBHOOK] CREAR nuevo producto")
        _handle_product_created(integration, payload)

    elif event == 'updated':
        logger.info(f"🔄 [WEBHOOK] ACTUALIZAR producto existente")
        _handle_product_updated(integration, payload)

    elif event == 'deleted':
        logger.info(f"🗑️ [WEBHOOK] ELIMINAR producto")
        _handle_product_deleted(integration, payload)

    elif event == 'restored':
        logger.info(f"♻️ [WEBHOOK] RESTAURAR producto")
        _handle_product_restored(integration, payload)

    logger.info(f"✅ [WEBHOOK] Procesamiento completado: {topic}")


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
            logger.warning(f"⚠️ [WEBHOOK] Producto {ext_id} sin categoría válida")
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

        logger.info(f"✅ [WEBHOOK] Producto CREADO: {ext_id} ({product.name}) en categoría {category_id}")

        # Procesar imágenes y embeddings en background (no bloquear respuesta del webhook)
        thread = threading.Thread(
            target=_process_product_images_and_embeddings,
            args=(product.id, client.id, payload.get('images', []))
        )
        thread.daemon = True
        thread.start()

    except Exception as e:
        logger.error(f"❌ [WEBHOOK] Error creando producto: {str(e)}", exc_info=True)
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

        # Loguear cambios importantes
        old_category_id = product.category_id
        old_name = product.name
        old_price = product.price
        old_stock = product.stock

        # Actualizar campos
        _update_product_fields(product, payload)
        db.session.add(product)
        db.session.commit()

        # Loguear cambios detectados
        changes = []
        if old_name != product.name:
            changes.append(f"nombre: '{old_name}' → '{product.name}'")
        if old_category_id != product.category_id:
            changes.append(f"categoría: {old_category_id} → {product.category_id}")
        if old_price != product.price:
            changes.append(f"precio: {old_price} → {product.price}")
        if old_stock != product.stock:
            changes.append(f"stock: {old_stock} → {product.stock}")

        if changes:
            logger.info(f"✅ [WEBHOOK] Producto actualizado: {ext_id} ({product.name}). Cambios: {', '.join(changes)}")
        else:
            logger.info(f"✅ [WEBHOOK] Producto actualizado: {ext_id} ({product.name}). Sin cambios detectados")

        # Procesar imágenes y embeddings en background
        thread = threading.Thread(
            target=_process_product_images_and_embeddings,
            args=(product.id, client.id, payload.get('images', []))
        )
        thread.daemon = True
        thread.start()

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
            logger.warning(f"⚠️ [WEBHOOK] Producto {ext_id} no encontrado para deletear")
            return

        product.is_active = False
        product.sync_status = 'synced'
        product.last_sync_at = datetime.utcnow()
        db.session.add(product)
        db.session.commit()

        logger.info(f"✅ [WEBHOOK] Producto ELIMINADO: {ext_id} ({product.name})")

    except Exception as e:
        logger.error(f"❌ [WEBHOOK] Error deletando producto: {str(e)}", exc_info=True)
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
            logger.warning(f"⚠️ [WEBHOOK] Producto {ext_id} no encontrado para restaurar")
            return

        product.is_active = True
        product.sync_status = 'synced'
        product.last_sync_at = datetime.utcnow()
        db.session.add(product)
        db.session.commit()

        logger.info(f"✅ [WEBHOOK] Producto RESTAURADO: {ext_id} ({product.name})")

    except Exception as e:
        logger.error(f"❌ [WEBHOOK] Error restaurando producto: {str(e)}", exc_info=True)
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
    """
    Resolver la categoría interna desde las categorías de WooCommerce

    Si un producto está en una categoría padre Y su categoría hija,
    se asigna SOLO a la hija (más específica).
    """
    if not categories:
        return None

    # Obtener todas las categorías válidas del producto
    valid_categories = []
    for cat in categories:
        ext_id = str(cat.get('id')) if cat.get('id') is not None else None
        if not ext_id:
            continue
        existing = Category.query.filter_by(client_id=client_id, external_id=ext_id).first()
        if existing:
            valid_categories.append(existing)

    if not valid_categories:
        return None

    if len(valid_categories) == 1:
        # Solo una categoría: asignar directamente
        return valid_categories[0].id

    # Múltiples categorías: buscar relación padre-hijo
    # Preferir las categorías que NO son padres de otra categoría en la lista
    for candidate in valid_categories:
        # ¿Es esta categoría padre de alguna otra en la lista?
        is_parent_of_another = any(
            other.parent_external_id == candidate.external_id
            for other in valid_categories
            if other.id != candidate.id
        )

        if not is_parent_of_another:
            # Esta es una categoría "hoja" (no es padre de otra en la lista)
            logger.info(f"📁 Categoría seleccionada (hoja): {candidate.name} (padre: {candidate.parent_external_id})")
            return candidate.id

    # Fallback: retornar la primera si no hay relación padre-hijo clara
    logger.warning(f"⚠️ Sin relación padre-hijo clara, usando primera categoría: {valid_categories[0].name}")
    return valid_categories[0].id


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


def _process_product_images_and_embeddings(product_id: str, client_id: str, images_data: list):
    """
    Procesa imágenes y embeddings en background (no bloquea respuesta del webhook)

    Args:
        product_id: ID interno del producto
        client_id: ID del cliente
        images_data: Lista de datos de imágenes del webhook
    """
    try:
        logger.info(f"🖼️ Iniciando procesamiento de imágenes para producto {product_id}")

        # Descargar y guardar imágenes
        images_created = _sync_product_images_webhook(product_id, images_data)
        logger.info(f"✅ {images_created} imágenes procesadas para producto {product_id}")

        if images_created > 0:
            # Generar embeddings CLIP para las nuevas imágenes
            embeddings_generated = _generate_embeddings_for_product(product_id)
            logger.info(f"✅ {embeddings_generated} embeddings generados para producto {product_id}")

            # Recalcular centroide de la categoría
            _recalculate_category_centroid(product_id)
            logger.info(f"✅ Centroide recalculado para categoría del producto {product_id}")

    except Exception as e:
        logger.error(f"Error procesando imágenes/embeddings del producto {product_id}: {str(e)}", exc_info=True)


def _sync_product_images_webhook(product_id: str, images_data: list) -> int:
    """Sincronizar imágenes desde webhook (solo base64, sin Cloudinary)"""
    import io
    import hashlib
    import requests
    from PIL import Image as PILImage

    processed = 0
    try:
        product = Product.query.get(product_id)
        if not product:
            logger.warning(f"Producto {product_id} no encontrado")
            return 0

        for idx, img_data in enumerate(images_data):
            source_url = img_data.get('src')
            if not source_url:
                continue

            url_hash = hashlib.sha256(source_url.encode()).hexdigest()

            # Evitar duplicados
            existing_image = Image.query.filter_by(
                product_id=product.id,
                hash_sha256=url_hash
            ).first()

            if existing_image:
                continue

            # Descargar y convertir a base64
            base64_full, base64_thumb, mime_type, width, height, size_bytes = _download_and_convert_image_webhook(source_url)
            if not base64_thumb:
                continue

            image = Image(
                client_id=product.client_id,
                product_id=product.id,
                filename=f"wc_{product.external_id}_{idx}.{mime_type.split('/')[-1] if mime_type else 'jpg'}",
                original_filename=source_url.split('/')[-1],
                source_url=source_url,
                base64_data=base64_full,
                base64_thumb=base64_thumb,
                mime_type=mime_type,
                width=width,
                height=height,
                size_bytes=size_bytes,
                hash_sha256=url_hash,
                is_primary=(idx == 0),
                display_order=idx,
                upload_status='completed',
                is_processed=False,
            )
            db.session.add(image)
            processed += 1

        db.session.commit()
        return processed

    except Exception as e:
        logger.error(f"Error sincronizando imágenes del webhook: {str(e)}", exc_info=True)
        db.session.rollback()
        return 0


def _download_and_convert_image_webhook(url: str, thumb_size: tuple = (300, 300)) -> tuple:
    """Descargar imagen y convertir a base64"""
    import io
    import base64
    import requests
    from PIL import Image as PILImage

    try:
        response = requests.get(url, timeout=15, verify=False)
        if response.status_code != 200:
            return None, None, '', 0, 0, 0

        image_bytes = response.content
        size_bytes = len(image_bytes)

        img = PILImage.open(io.BytesIO(image_bytes))
        width, height = img.size
        mime_type = f"image/{img.format.lower()}" if img.format else "image/jpeg"

        # Convertir a RGB si es necesario
        if img.mode in ('RGBA', 'LA', 'P'):
            background = PILImage.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if 'A' in img.mode else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        base64_full = None  # No guardamos imagen completa

        # Crear thumbnail
        img_thumb = img.copy()
        img_thumb.thumbnail(thumb_size, PILImage.Resampling.LANCZOS)
        thumb_buffer = io.BytesIO()
        img_thumb.save(thumb_buffer, format='JPEG', quality=85, optimize=True)
        thumb_buffer.seek(0)
        base64_thumb = base64.b64encode(thumb_buffer.read()).decode('utf-8')

        return base64_full, base64_thumb, mime_type, width, height, size_bytes

    except Exception as e:
        logger.error(f"Error descargando imagen {url}: {str(e)}")
        return None, None, '', 0, 0, 0


def _generate_embeddings_for_product(product_id: str) -> int:
    """Generar embeddings CLIP para imágenes no procesadas del producto"""
    try:
        from app.blueprints.embeddings import get_clip_model, load_image_from_source
        import torch
        import numpy as np

        product = Product.query.get(product_id)
        if not product:
            logger.warning(f"Producto {product_id} no encontrado")
            return 0

        # Obtener imágenes sin procesar
        unprocessed = Image.query.filter_by(
            product_id=product.id,
            is_processed=False
        ).filter(Image.base64_thumb.isnot(None)).all()

        if not unprocessed:
            return 0

        clip_model, clip_processor = get_clip_model()
        generated = 0

        for image in unprocessed:
            try:
                image_bytes = base64.b64decode(image.base64_thumb)
                pil_image = load_image_from_source(image_bytes)
                inputs = clip_processor(images=pil_image, return_tensors="pt")

                if torch.cuda.is_available():
                    inputs = {k: v.cuda() for k, v in inputs.items()}

                with torch.no_grad():
                    feats = clip_model.get_image_features(**inputs)
                    feats = feats / feats.norm(dim=-1, keepdim=True)
                    embedding = feats.cpu().numpy().flatten()

                image.clip_embedding = json.dumps(embedding.tolist())
                image.is_processed = True
                image.upload_status = 'completed'
                generated += 1

            except Exception as e:
                logger.error(f"Error generando embedding para imagen {image.id}: {str(e)}")
                image.upload_status = 'failed'
                image.error_message = str(e)

            db.session.add(image)

        db.session.commit()
        return generated

    except Exception as e:
        logger.error(f"Error generando embeddings para producto {product_id}: {str(e)}", exc_info=True)
        db.session.rollback()
        return 0


def _recalculate_category_centroid(product_id: str):
    """Recalcular el centroide de la categoría después de generar embeddings"""
    try:
        import numpy as np

        product = Product.query.get(product_id)
        if not product or not product.category_id:
            return

        category = Category.query.get(product.category_id)
        if not category:
            return

        # Recolectar todos los embeddings de la categoría
        embeddings = []
        for prod in category.products:
            for image in prod.images:
                if image.is_processed and image.clip_embedding:
                    try:
                        emb = json.loads(image.clip_embedding)
                        embeddings.append(emb)
                    except Exception:
                        continue

        if embeddings:
            centroid = np.mean(np.array(embeddings), axis=0)
            category.centroid_embedding = json.dumps(centroid.tolist())
            db.session.add(category)
            db.session.commit()
            logger.info(f"✅ Centroide recalculado para categoría {category.id}")

    except Exception as e:
        logger.error(f"Error recalculando centroide para producto {product_id}: {str(e)}", exc_info=True)
        db.session.rollback()

