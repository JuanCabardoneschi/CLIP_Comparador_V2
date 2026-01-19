"""Servicio de sincronización inicial para WooCommerce.
Incluye categorías, atributos, productos, imágenes y embeddings (similar a Tiendanube).
"""
import base64
import hashlib
import io
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import requests
from PIL import Image as PILImage

from app import db
from app.models.client import Client
from app.models.category import Category
from app.models.image import Image
from app.models.product import Product
from app.models.product_attribute_config import ProductAttributeConfig
from app.models.woocommerce_integration import WooCommerceIntegration
from app.services.woocommerce_api_client import WooCommerceAPIClient

logger = logging.getLogger(__name__)


class WooCommerceSyncService:
    """Sincronización básica: categorías, atributos y productos."""

    def __init__(self, integration_or_client_id):
        if isinstance(integration_or_client_id, str):
            self.client = Client.query.get(integration_or_client_id)
            if not self.client:
                raise ValueError(f"Cliente {integration_or_client_id} no encontrado")
            self.integration = WooCommerceIntegration.query.filter_by(
                client_id=self.client.id, is_active=True
            ).first()
            if not self.integration:
                raise ValueError(f"No hay integración WooCommerce activa para cliente {self.client.id}")
        else:
            self.integration = integration_or_client_id
            self.client = Client.query.get(self.integration.client_id)
            if not self.client:
                raise ValueError(f"Cliente {self.integration.client_id} no encontrado")

        self.api = WooCommerceAPIClient(
            store_url=self.integration.store_url,
            consumer_key=self.integration.get_consumer_key(),
            consumer_secret=self.integration.get_consumer_secret(),
            api_version=self.integration.api_version,
            verify_ssl=self.integration.use_ssl,
        )

    # ---------------- Public API ----------------

    def full_sync(self, sync_options: Dict = None) -> Dict:
        if sync_options is None:
            sync_options = {
                'categories': True,
                'attributes': True,
                'products': True,
                'images': True,
                'embeddings': True,
                'centroids': True,
            }

        stats = {
            'categories_created': 0,
            'categories_updated': 0,
            'products_created': 0,
            'products_updated': 0,
            'attributes_upserted': 0,
            'images_processed': 0,
            'embeddings_generated': 0,
            'centroids_computed': 0,
        }

        try:
            self.integration.sync_status = 'in_progress'
            self.integration.sync_error = None
            db.session.commit()

            if sync_options.get('categories', True):
                created, updated = self.sync_categories()
                stats['categories_created'] = created
                stats['categories_updated'] = updated

            # Sincronizar atributos globales antes de productos
            if sync_options.get('attributes', True):
                stats['attributes_upserted'] += self.sync_attributes()

            if sync_options.get('products', True):
                created, updated, attr_upserts, images_count = self.sync_products(
                    sync_images=sync_options.get('images', True)
                )
                stats['products_created'] = created
                stats['products_updated'] = updated
                stats['attributes_upserted'] += attr_upserts
                stats['images_processed'] = images_count

            if sync_options.get('embeddings', True):
                embeddings = self.generate_embeddings(force_regenerate=True)
                stats['embeddings_generated'] = embeddings

            if sync_options.get('centroids', True) and stats.get('embeddings_generated', 0) > 0:
                centroids = self.calculate_category_centroids()
                stats['centroids_computed'] = centroids

            # Registrar webhooks automáticamente cuando la sincronización termina exitosamente
            import os
            delivery_url = os.environ.get('WEBHOOK_DELIVERY_URL', 'https://clip-comparador-v2.railway.app')
            webhook_result = self.register_webhooks(delivery_url)
            stats['webhooks_registered'] = webhook_result.get('success', False)
            if webhook_result.get('success'):
                stats['webhook_ids'] = webhook_result.get('webhook_ids', [])

            self.integration.sync_status = 'completed'
            self.integration.last_sync_at = datetime.utcnow()
            db.session.commit()
            return stats
        except Exception as e:
            logger.exception("Error en sincronización WooCommerce")
            db.session.rollback()
            self.integration.sync_status = 'error'
            self.integration.sync_error = str(e)
            db.session.commit()
            raise

    # ---------------- Categorías ----------------

    def sync_categories(self) -> (int, int):
        created = 0
        updated = 0
        categories = self.api.get_all_categories()

        for cat in categories:
            ext_id = str(cat.get('id'))
            parent_ext = str(cat.get('parent')) if cat.get('parent') else None
            name = cat.get('name') or 'Sin nombre'
            slug = cat.get('slug') or None

            existing = Category.query.filter_by(client_id=self.client.id, external_id=ext_id).first()

            if not existing:
                category = Category(
                    client_id=self.client.id,
                    external_id=ext_id,
                    parent_external_id=parent_ext,
                    name=name,
                    name_en=name,
                    slug=slug,
                    description=cat.get('description'),
                    is_active=True,
                    sync_status='synced',
                    last_sync_at=datetime.utcnow(),
                )
                db.session.add(category)
                created += 1
            else:
                existing.name = name
                existing.name_en = name
                existing.slug = slug or existing.slug
                existing.description = cat.get('description')
                existing.parent_external_id = parent_ext
                existing.is_active = True
                existing.sync_status = 'synced'
                existing.last_sync_at = datetime.utcnow()
                updated += 1

        db.session.commit()
        return created, updated

    # ---------------- Atributos ----------------

    def sync_attributes(self) -> int:
        """Atributos globales de WooCommerce → ProductAttributeConfig."""
        upserts = 0
        try:
            attributes = self.api.list_attributes()
        except Exception:
            attributes = []

        for attr in attributes:
            key = attr.get('slug') or attr.get('name')
            label = attr.get('name') or key
            if not key:
                continue

            config = ProductAttributeConfig.query.filter_by(client_id=self.client.id, key=key).first()
            if not config:
                config = ProductAttributeConfig(
                    client_id=self.client.id,
                    key=key,
                    label=label,
                    type='list',
                    required=False,
                    options=None,
                    expose_in_search=True,
                )
                db.session.add(config)
            else:
                config.label = label
            upserts += 1

        db.session.commit()
        return upserts

    # ---------------- Productos ----------------

    def sync_products(self, sync_images: bool = True) -> (int, int, int, int):
        created = 0
        updated = 0
        attr_upserts = 0
        images_processed = 0

        products = self.api.get_all_products(status='publish')
        attr_values = {}  # key -> set(values)

        for prod in products:
            ext_id = str(prod.get('id'))
            if not ext_id:
                continue

            category_id = self._resolve_category_id(prod.get('categories', []))
            if not category_id:
                # Sin categoría válida, omitir
                continue

            product = Product.query.filter_by(client_id=self.client.id, external_id=ext_id).first()
            name = prod.get('name') or 'Sin nombre'
            description = prod.get('description') or None
            sku = prod.get('sku') or None
            price = prod.get('price') or None
            permalink = prod.get('permalink') or None
            stock_q = prod.get('stock_quantity')

            attributes = self._extract_attributes(prod, attr_values)

            if not product:
                product = Product(
                    client_id=self.client.id,
                    external_id=ext_id,
                    category_id=category_id,
                    name=name,
                )
                db.session.add(product)
                db.session.flush()  # asegurar product.id para imágenes
                created += 1
            else:
                updated += 1

            product.category_id = category_id
            product.name = name
            product.description = description
            product.sku = sku
            product.price = price if price not in (None, '') else None
            product.stock = int(stock_q) if stock_q is not None else product.stock
            product.external_url = permalink
            product.is_active = prod.get('status', 'publish') == 'publish'
            product.attributes = attributes if attributes else None
            product.sync_status = 'synced'
            product.last_sync_at = datetime.utcnow()

            db.session.add(product)

            # Sincronizar imágenes del producto si está habilitado
            if sync_images:
                images_data = prod.get('images', []) or []
                images_processed += self._sync_product_images(product, images_data)

        db.session.commit()

        # Upsert de configs de atributos según valores encontrados en productos
        for key, values in attr_values.items():
            attr_upserts += self._upsert_attribute_config(key, values)

        db.session.commit()
        return created, updated, attr_upserts, images_processed

    # ---------------- Helpers ----------------

    def _resolve_category_id(self, categories: List[Dict]):
        for cat in categories or []:
            ext_id = str(cat.get('id')) if cat.get('id') is not None else None
            if not ext_id:
                continue
            existing = Category.query.filter_by(client_id=self.client.id, external_id=ext_id).first()
            if existing:
                return existing.id
        return None

    def _extract_attributes(self, prod: Dict, attr_values: Dict[str, set]) -> Dict:
        attrs = {}
        for attr in prod.get('attributes', []) or []:
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

            if value is None:
                continue

            attrs[key] = value

            if key not in attr_values:
                attr_values[key] = set()

            if isinstance(options, list):
                attr_values[key].update([str(o) for o in options])
            elif options:
                attr_values[key].add(str(options))

        return attrs

    def _upsert_attribute_config(self, key: str, values: set) -> int:
        config = ProductAttributeConfig.query.filter_by(client_id=self.client.id, key=key).first()
        options_dict = None
        attr_type = 'text'

        if values:
            attr_type = 'list'
            options_dict = {'multiple': True, 'values': sorted(list(values))}

        if not config:
            config = ProductAttributeConfig(
                client_id=self.client.id,
                key=key,
                label=key,
                type=attr_type,
                options=options_dict,
                required=False,
                expose_in_search=True,
            )
            db.session.add(config)
            return 1

        # Actualizar existente
        config.type = attr_type
        config.options = options_dict
        db.session.add(config)
        return 1

    # ---------------- Imágenes ----------------

    def _sync_product_images(self, product: Product, images_data: List[Dict]) -> int:
        processed = 0
        for idx, img_data in enumerate(images_data):
            source_url = img_data.get('src')
            if not source_url:
                continue

            url_hash = hashlib.sha256(source_url.encode()).hexdigest()

            existing_image = Image.query.filter_by(
                product_id=product.id,
                hash_sha256=url_hash
            ).first()

            if existing_image:
                continue

            base64_full, base64_thumb, mime_type, width, height, size_bytes = self._download_and_convert_image(source_url)
            if not base64_thumb:
                continue

            image = Image(
                client_id=self.client.id,
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

        return processed

    def _download_and_convert_image(self, url: str, thumb_size: Tuple[int, int] = (300, 300)) -> Tuple[Optional[str], Optional[str], str, int, int, int]:
        try:
            response = requests.get(url, timeout=15, verify=False)
            if response.status_code != 200:
                return None, None, '', 0, 0, 0

            image_bytes = response.content
            size_bytes = len(image_bytes)

            img = PILImage.open(io.BytesIO(image_bytes))
            width, height = img.size
            mime_type = f"image/{img.format.lower()}" if img.format else "image/jpeg"

            if img.mode in ('RGBA', 'LA', 'P'):
                background = PILImage.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if 'A' in img.mode else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')

            base64_full = None  # no almacenamos imagen completa

            img_thumb = img.copy()
            img_thumb.thumbnail(thumb_size, PILImage.Resampling.LANCZOS)
            thumb_buffer = io.BytesIO()
            img_thumb.save(thumb_buffer, format='JPEG', quality=85, optimize=True)
            thumb_buffer.seek(0)
            base64_thumb = base64.b64encode(thumb_buffer.read()).decode('utf-8')

            return base64_full, base64_thumb, mime_type, width, height, size_bytes
        except Exception:
            return None, None, '', 0, 0, 0

    # ---------------- Embeddings y centroides ----------------

    def generate_embeddings(self, force_regenerate: bool = True) -> int:
        try:
            from app.blueprints.embeddings import get_clip_model, load_image_from_source
            import torch
            import numpy as np

            clip_model, clip_processor = get_clip_model()

            if force_regenerate:
                images_q = Image.query.filter_by(client_id=self.client.id).all()
                for img in images_q:
                    img.clip_embedding = None
                    img.is_processed = False
                db.session.commit()
                unprocessed = images_q
            else:
                unprocessed = Image.query.filter_by(client_id=self.client.id, is_processed=False).filter(
                    Image.base64_thumb.isnot(None)
                ).all()

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
                    image.upload_status = 'failed'
                    image.error_message = str(e)
                db.session.add(image)

            db.session.commit()
            return generated
        except Exception as e:
            logger.error(f"Error generando embeddings WooCommerce: {e}")
            db.session.rollback()
            return 0

    def calculate_category_centroids(self) -> int:
        try:
            import numpy as np

            categories = Category.query.filter_by(client_id=self.client.id).all()
            computed = 0

            for category in categories:
                embeddings = []
                for product in category.products:
                    for image in product.images:
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
                    computed += 1

            db.session.commit()
            return computed
        except Exception as e:
            logger.error(f"Error calculando centroides WooCommerce: {e}")
            db.session.rollback()
            return 0

    # ---- Webhooks ----

    def register_webhooks(self, delivery_url: str) -> Dict:
        """Registra los webhooks en WooCommerce para mantener sincronización en tiempo real

        Args:
            delivery_url: URL base del servidor (ej: https://clip-comparador-v2.railway.app)

        Returns:
            Dict con webhook_ids registrados
        """
        import secrets
        import json

        webhook_topics = [
            'product.created',
            'product.updated',
            'product.deleted',
            'product.restored',
        ]

        try:
            # Generar secret para firmar webhooks (HMAC)
            webhook_secret = secrets.token_urlsafe(32)

            webhook_ids = []
            webhook_endpoint = f"{delivery_url}/api/webhooks/woocommerce"

            for topic in webhook_topics:
                webhook_name = f"CLIP - {topic}"

                result = self.api.create_webhook(
                    name=webhook_name,
                    topic=topic,
                    delivery_url=webhook_endpoint,
                    secret=webhook_secret,
                    status='active'
                )

                if 'id' in result:
                    webhook_ids.append(result['id'])
                    logger.info(f"Webhook registrado: {webhook_name} (ID: {result['id']})")

            # Guardar webhook_secret y webhook_ids en la integración
            self.integration.webhook_secret = webhook_secret
            self.integration.webhook_ids = json.dumps(webhook_ids)  # Guardamos como JSON
            db.session.commit()

            logger.info(f"Webhooks registrados exitosamente para {self.client.name}. Total: {len(webhook_ids)}")

            return {
                'success': True,
                'webhook_ids': webhook_ids,
                'secret_hash': hashlib.sha256(webhook_secret.encode()).hexdigest()[:16],  # No guardar el secret completo en logs
            }

        except Exception as e:
            logger.error(f"Error registrando webhooks para {self.client.name}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
            }

    # ---------------- Actualizaciones desde CLIP → WooCommerce ----------------

    def update_product_category(self, external_product_id: str, external_category_id: str) -> Dict:
        """Actualiza la categoría de un producto WooCommerce (CLIP → Woo)

        Args:
            external_product_id: ID del producto en WooCommerce (Product.external_id)
            external_category_id: ID de la categoría en WooCommerce (Category.external_id)
        """
        if not external_product_id or not external_category_id:
            raise ValueError("Se requieren external_id de producto y categoría para actualizar en WooCommerce")

        payload = {
            'categories': [
                {'id': int(external_category_id)}
            ]
        }

        logger.info(f"WooCommerce: actualizando categoría de producto {external_product_id} -> {external_category_id}")
        return self.api.update_product(int(external_product_id), payload)
