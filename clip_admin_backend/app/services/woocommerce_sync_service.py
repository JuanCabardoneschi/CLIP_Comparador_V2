"""Servicio de sincronización inicial para WooCommerce.
Incluye categorías, atributos, productos, imágenes y embeddings (similar a Tiendanube).
"""
import base64
import hashlib
import io
import json
import logging
from datetime import datetime, timezone
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
from app.utils.logging_config import log_system

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

    def full_sync(self, sync_options: Dict = None, is_resync: bool = False) -> Dict:
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

            log_system(f"[WOO SYNC] Inicio sync para cliente {self.client.id}")

            # Si es resync, limpiar embeddings viejos para emular "primera vez"
            if is_resync:
                Image.query.filter(
                    Image.product_id.in_(
                        db.session.query(Product.id).filter_by(client_id=self.client.id)
                    )
                ).update({'is_processed': False, 'clip_embedding': None})
                db.session.commit()
                logger.info(f"🔄 [RESYNC] Embeddings limpiados para cliente {self.client.id}")

            if sync_options.get('categories', True):
                created, updated = self.sync_categories()
                stats['categories_created'] = created
                stats['categories_updated'] = updated

            # Sincronizar atributos globales antes de productos
            if sync_options.get('attributes', True):
                stats['attributes_upserted'] += self.sync_attributes()

            if sync_options.get('products', True):
                logger.info("[WOO SYNC] Sincronizando productos...")
                created, updated, attr_upserts, images_count, embeddings_count = self.sync_products(
                    sync_images=sync_options.get('images', True)
                )
                stats['products_created'] = created
                stats['products_updated'] = updated
                stats['attributes_upserted'] += attr_upserts
                stats['images_processed'] = images_count
                stats['embeddings_generated'] = embeddings_count

            if sync_options.get('embeddings', True) and not sync_options.get('products', True):
                logger.info("[WOO SYNC] Generando embeddings (modo batch)...")
                embeddings = self.generate_embeddings(force_regenerate=False)
                stats['embeddings_generated'] = embeddings

            if sync_options.get('centroids', True) and stats.get('embeddings_generated', 0) > 0:
                logger.info("[WOO SYNC] Recalculando centroides...")
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
            logger.info(f"[WOO SYNC] Sync completada para cliente {self.client.id}")
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

        for idx, cat in enumerate(categories, 1):
            ext_id = str(cat.get('id'))
            parent_ext = str(cat.get('parent')) if cat.get('parent') else None
            name = cat.get('name') or 'Sin nombre'
            slug = cat.get('slug') or None

            log_system(f"[WOO SYNC] Categoría {idx}/{len(categories)} ext_id={ext_id}")

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
            log_system(f"[WOO SYNC] Categoría guardada ext_id={ext_id}")
        return created, updated

    # ---------------- Atributos ----------------

    def sync_attributes(self) -> int:
        """Atributos globales de WooCommerce → ProductAttributeConfig."""
        upserts = 0
        log_system("[WOO SYNC] Listando atributos")
        attributes = self.api.list_attributes()

        for idx, attr in enumerate(attributes, 1):
            key = attr.get('slug') or attr.get('name')
            label = attr.get('name') or key
            if not key:
                continue

            log_system(f"[WOO SYNC] Atributo {idx}/{len(attributes)} key={key}")

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
            log_system(f"[WOO SYNC] Atributo guardado key={key}")
        return upserts

    # ---------------- Productos ----------------

    def sync_products(self, sync_images: bool = True) -> (int, int, int, int, int):
        created = 0
        updated = 0
        attr_upserts = 0
        images_processed = 0
        embeddings_generated = 0

        if sync_images:
            logger.info(f"📥 [SYNC] Iniciando descarga de imágenes para cliente {self.client.id}")

        products = self.api.get_all_products(status='publish')
        log_system(f"[WOO SYNC] Productos recibidos: {len(products)}")
        attr_values = {}  # key -> set(values)

        for idx, prod in enumerate(products, 1):
            ext_id = str(prod.get('id'))
            if not ext_id:
                continue

            log_system(f"[WOO SYNC] Procesando producto {idx}/{len(products)} (ext_id={ext_id})")

            category_id = self._resolve_category_id(prod.get('categories', []))
            if not category_id:
                log_system(f"[WOO SYNC] Producto sin categoría válida ext_id={ext_id}")
                continue

            product = Product.query.filter_by(client_id=self.client.id, external_id=ext_id).first()
            name = prod.get('name') or 'Sin nombre'
            description = prod.get('description') or None
            sku = prod.get('sku') or None
            price = prod.get('price') or None
            permalink = prod.get('permalink') or None

            # 🆕 MANEJO CORRECTO DE STOCK ILIMITADO EN WOOCOMMERCE
            # manage_stock=false significa "stock ilimitado" (no gestionado)
            # manage_stock=true + stock_quantity=N significa "stock limitado de N unidades"
            stock_q = prod.get('stock_quantity')
            stock_status = prod.get('stock_status')
            manage_stock = prod.get('manage_stock', True)  # Por defecto True si no viene

            # Determinar stock final según manage_stock
            if stock_status == 'outofstock':
                # WooCommerce marca sin stock aunque manage_stock sea false
                final_stock = 0
            elif not manage_stock:
                # Stock ILIMITADO (no gestionado) → usar -1 como indicador
                final_stock = -1
            elif stock_q is not None:
                # Stock limitado con cantidad específica
                final_stock = int(stock_q)
            else:
                # Sin información, mantener valor anterior
                final_stock = product.stock if product else 0

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
            product.stock = final_stock  # 🆕 Usar stock calculado (ilimitado = -1)
            product.manage_stock = manage_stock  # 🆕 Guardar flag de WooCommerce
            product.external_url = permalink
            product.is_active = prod.get('status', 'publish') == 'publish'
            product.attributes = attributes if attributes else None
            product.sync_status = 'synced'
            product.last_sync_at = datetime.utcnow()

            db.session.add(product)
            db.session.commit()
            log_system(f"[WOO SYNC] Producto guardado ext_id={ext_id}")

            # Sincronizar imágenes del producto si está habilitado
            if sync_images:
                images_data = prod.get('images', []) or []
                log_system(f"[WOO SYNC] Producto {ext_id} imágenes: {len(images_data)}")
                images_count, embeddings_count = self._sync_product_images(product, images_data)
                images_processed += images_count
                embeddings_generated += embeddings_count

        # Upsert de configs de atributos según valores encontrados en productos
        for key, values in attr_values.items():
            attr_upserts += self._upsert_attribute_config(key, values)

        if sync_images and images_processed > 0:
            logger.info(f"✅ [SYNC] Descarga completada: {images_processed} imágenes procesadas")

        return created, updated, attr_upserts, images_processed, embeddings_generated

    def sync_differences(self, sync_images: bool = True, progress_callback=None) -> Dict:
        """Sincroniza solo diferencias usando date_modified de WooCommerce."""
        created = 0
        updated = 0
        trashed = 0
        hard_deleted = 0
        attr_upserts = 0
        images_processed = 0
        embeddings_generated = 0

        attr_values: Dict[str, set] = {}

        # Sync categorías y atributos primero (barato, asegura consistencia)
        categories_created, categories_updated = self.sync_categories()
        attr_upserts += self.sync_attributes()

        page = 1
        per_page = 100
        processed = 0
        total_products = None
        woo_ids = set()

        while True:
            products, total, total_pages = self.api.list_products_with_meta(
                page=page,
                per_page=per_page,
                status='any'
            )

            if total_products is None and total is not None:
                total_products = total

            if not products:
                break

            for prod in products:
                ext_id = str(prod.get('id')) if prod.get('id') is not None else None
                if not ext_id:
                    continue

                woo_ids.add(ext_id)

                product = Product.query.filter_by(
                    client_id=self.client.id,
                    external_id=ext_id
                ).first()

                woo_modified = self._parse_woo_datetime(
                    prod.get('date_modified_gmt') or prod.get('date_modified')
                )
                local_sync = product.last_sync_at if product else None

                should_update = False
                if not product:
                    should_update = True
                elif not local_sync:
                    should_update = True
                elif woo_modified and woo_modified > local_sync:
                    should_update = True

                if not should_update:
                    continue

                # Si está en papelera, soft delete
                if prod.get('status') == 'trash':
                    if product and product.is_active:
                        product.is_active = False
                        product.sync_status = 'synced'
                        product.last_sync_at = datetime.utcnow()
                        db.session.add(product)
                        trashed += 1
                    continue

                category_id = self._resolve_category_id(prod.get('categories', []))
                if not category_id:
                    log_system(f"[WOO DIFF] Producto sin categoría válida ext_id={ext_id}")
                    continue

                if not product:
                    product = Product(
                        client_id=self.client.id,
                        external_id=ext_id,
                        category_id=category_id,
                        name=prod.get('name') or 'Sin nombre',
                    )
                    db.session.add(product)
                    db.session.flush()
                    created += 1
                else:
                    updated += 1

                # Actualizar campos principales
                product.category_id = category_id
                product.name = prod.get('name') or product.name
                product.description = prod.get('description') or None
                product.sku = prod.get('sku') or None
                price = prod.get('price')
                product.price = price if price not in (None, '') else None

                stock_q = prod.get('stock_quantity')
                stock_status = prod.get('stock_status')
                manage_stock = prod.get('manage_stock', True)

                if stock_status == 'outofstock':
                    final_stock = 0
                elif not manage_stock:
                    final_stock = -1
                elif stock_q is not None:
                    final_stock = int(stock_q)
                else:
                    final_stock = product.stock

                product.stock = final_stock
                product.manage_stock = manage_stock
                product.external_url = prod.get('permalink') or None
                product.is_active = prod.get('status', 'publish') == 'publish'
                product.attributes = self._extract_attributes(prod, attr_values) or None
                product.sync_status = 'synced'
                product.last_sync_at = datetime.utcnow()

                db.session.add(product)

                if sync_images:
                    images_data = prod.get('images', []) or []
                    images_count, embeddings_count = self._sync_product_images(product, images_data)
                    images_processed += images_count
                    embeddings_generated += embeddings_count

            db.session.commit()

            processed += len(products)
            if progress_callback:
                progress_callback(processed, total_products or processed, created, updated, trashed, page, total_pages)

            if len(products) < per_page:
                break

            page += 1

        # Hard delete: productos locales que ya no existen en WooCommerce
        if woo_ids:
            missing_products = (
                Product.query
                .filter(Product.client_id == self.client.id)
                .filter(Product.external_id.isnot(None))
                .filter(~Product.external_id.in_(woo_ids))
                .all()
            )

            for product in missing_products:
                Image.query.filter_by(product_id=product.id).delete()
                db.session.delete(product)
                hard_deleted += 1

            if missing_products:
                db.session.commit()

        # Upsert de configs de atributos
        for key, values in attr_values.items():
            attr_upserts += self._upsert_attribute_config(key, values)
        db.session.commit()

        return {
            'categories_created': categories_created,
            'categories_updated': categories_updated,
            'products_created': created,
            'products_updated': updated,
            'products_trashed': trashed,
            'products_hard_deleted': hard_deleted,
            'attributes_upserted': attr_upserts,
            'images_processed': images_processed,
            'embeddings_generated': embeddings_generated,
            'total_processed': processed,
            'total_products': total_products
        }

    def sync_stock_only(self, progress_callback=None) -> Dict:
        """Re-sincroniza únicamente stock desde WooCommerce."""
        updated = 0
        missing = 0
        processed = 0
        total_products = None

        page = 1
        per_page = 100

        while True:
            products, total, total_pages = self.api.list_products_with_meta(
                page=page,
                per_page=per_page,
                status='publish'
            )

            if total_products is None and total is not None:
                total_products = total

            if not products:
                break

            for prod in products:
                ext_id = str(prod.get('id'))
                if not ext_id:
                    continue

                product = Product.query.filter_by(client_id=self.client.id, external_id=ext_id).first()
                if not product:
                    missing += 1
                    continue

                stock_q = prod.get('stock_quantity')
                stock_status = prod.get('stock_status')
                manage_stock = prod.get('manage_stock', True)

                if stock_status == 'outofstock':
                    final_stock = 0
                elif not manage_stock:
                    final_stock = -1
                elif stock_q is not None:
                    final_stock = int(stock_q)
                else:
                    final_stock = product.stock

                product.stock = final_stock
                product.manage_stock = bool(manage_stock)
                product.is_active = prod.get('status', 'publish') == 'publish'
                product.last_sync_at = datetime.utcnow()

                db.session.add(product)
                updated += 1

            db.session.commit()

            processed += len(products)
            if progress_callback:
                progress_callback(processed, total_products or processed, updated, missing, page, total_pages)

            if len(products) < per_page:
                break

            page += 1

        return {
            'updated': updated,
            'missing': missing,
            'total': processed,
            'total_products': total_products
        }

    def verify_sync_status(self) -> Dict:
        """Verifica estado de sincronización entre WooCommerce y BD local."""
        woo_products = self.api.get_all_products(status='publish')
        woo_categories = self.api.get_all_categories()

        woo_product_ids = {str(p.get('id')) for p in woo_products if p.get('id') is not None}
        woo_category_ids = {str(c.get('id')) for c in woo_categories if c.get('id') is not None}
        woo_images_total = sum(len(p.get('images') or []) for p in woo_products)

        local_products = Product.query.filter_by(client_id=self.client.id, is_active=True).all()
        local_categories = Category.query.filter_by(client_id=self.client.id, is_active=True).all()
        local_images = Image.query.filter_by(client_id=self.client.id).all()

        local_product_ids = {str(p.external_id) for p in local_products if p.external_id}
        local_category_ids = {str(c.external_id) for c in local_categories if c.external_id}

        missing_products = sorted(list(woo_product_ids - local_product_ids))
        extra_products = sorted(list(local_product_ids - woo_product_ids))
        missing_categories = sorted(list(woo_category_ids - local_category_ids))
        extra_categories = sorted(list(local_category_ids - woo_category_ids))

        products_without_images = [p for p in local_products if p.images.count() == 0]
        images_unprocessed = [img.id for img in local_images if not img.is_processed]

        woo_product_map = {
            str(p.get('id')): {
                'id': str(p.get('id')),
                'name': p.get('name') or 'Sin nombre',
                'status': p.get('status')
            }
            for p in woo_products if p.get('id') is not None
        }
        local_product_map = {
            str(p.external_id): {
                'id': str(p.external_id),
                'name': p.name,
                'is_active': p.is_active
            }
            for p in local_products if p.external_id
        }

        webhooks = self.api.list_webhooks()
        webhook_topics = [w.get('topic') for w in webhooks if isinstance(w, dict)]

        has_product_created = 'product.created' in webhook_topics

        return {
            'counts': {
                'woo_products': len(woo_product_ids),
                'woo_categories': len(woo_category_ids),
                'woo_images': woo_images_total,
                'local_products': len(local_products),
                'local_categories': len(local_categories),
                'local_images': len(local_images),
            },
            'missing': {
                'products': len(missing_products),
                'categories': len(missing_categories),
            },
            'extra': {
                'products': len(extra_products),
                'categories': len(extra_categories),
            },
            'integrity': {
                'products_without_images': len(products_without_images),
                'images_unprocessed': len(images_unprocessed),
            },
            'webhooks': {
                'topics': webhook_topics,
                'has_product_created': has_product_created,
            },
            'details': {
                'missing_product_ids': missing_products[:50],
                'extra_product_ids': extra_products[:50],
                'missing_category_ids': missing_categories[:50],
                'extra_category_ids': extra_categories[:50],
                'missing_products': [woo_product_map.get(pid) for pid in missing_products[:20] if pid in woo_product_map],
                'extra_products': [local_product_map.get(pid) for pid in extra_products[:20] if pid in local_product_map],
                'products_without_images': [
                    {'id': str(p.id), 'external_id': p.external_id, 'name': p.name}
                    for p in products_without_images[:20]
                ]
            }
        }

    def verify_products_by_ids(self, product_ids: List[int]) -> Dict:
        """Verifica en WooCommerce y BD local un conjunto de IDs externos."""
        results = []

        for pid in product_ids:
            try:
                woo_product = self.api.get_product(int(pid))
                woo_found = True
            except Exception as e:
                results.append({
                    'id': str(pid),
                    'woo_found': False,
                    'error': str(e)
                })
                continue

            local_product = Product.query.filter_by(
                client_id=self.client.id,
                external_id=str(pid)
            ).first()

            results.append({
                'id': str(pid),
                'woo_found': woo_found,
                'woo_status': woo_product.get('status'),
                'woo_name': woo_product.get('name'),
                'woo_images': len(woo_product.get('images') or []),
                'woo_categories': [c.get('id') for c in (woo_product.get('categories') or [])],
                'local_found': bool(local_product),
                'local_is_active': local_product.is_active if local_product else None,
                'local_category_id': str(local_product.category_id) if local_product else None,
                'local_images': local_product.images.count() if local_product else 0,
            })

        return {
            'items': results,
            'total': len(results)
        }

    def sync_missing_images_only(self) -> Dict:
        """Sincroniza solo imágenes faltantes (productos sin imágenes locales)."""
        from sqlalchemy import func

        woo_products = self.api.get_all_products(status='publish')
        woo_map = {
            str(p.get('id')): p
            for p in woo_products if p.get('id') is not None
        }

        products_without_images = (
            db.session.query(Product)
            .outerjoin(Image, Image.product_id == Product.id)
            .filter(Product.client_id == self.client.id)
            .group_by(Product.id)
            .having(func.count(Image.id) == 0)
            .all()
        )

        processed_products = 0
        images_added = 0

        for product in products_without_images:
            ext_id = str(product.external_id) if product.external_id else None
            if not ext_id or ext_id not in woo_map:
                continue

            images_data = woo_map[ext_id].get('images', []) or []
            if not images_data:
                continue

            images_count, _embeddings_count = self._sync_product_images(product, images_data)
            images_added += images_count
            processed_products += 1

        db.session.commit()

        return {
            'products_without_images': len(products_without_images),
            'products_processed': processed_products,
            'images_added': images_added
        }

    # ---------------- Helpers ----------------

    def _resolve_category_id(self, categories: List[Dict]):
        """
        Resolver la categoría interna desde las categorías de WooCommerce.

        Si un producto está en una categoría padre Y su categoría hija,
        se asigna SOLO a la hija (más específica/leaf).

        Args:
            categories: Lista de dicts con categorías de WooCommerce

        Returns:
            UUID de la categoría interna o None
        """
        if not categories:
            return None

        # Obtener todas las categorías válidas del producto
        valid_categories = []
        for cat in categories:
            ext_id = str(cat.get('id')) if cat.get('id') is not None else None
            if not ext_id:
                continue

            existing = Category.query.filter_by(
                client_id=self.client.id,
                external_id=ext_id
            ).first()

            if existing:
                valid_categories.append(existing)

        if not valid_categories:
            return None

        if len(valid_categories) == 1:
            # Solo una categoría: asignar directamente
            return valid_categories[0].id

        # Múltiples categorías: buscar relación padre-hijo
        # Preferir las categorías que NO son padres de otra categoría en la lista (LEAF)
        for candidate in valid_categories:
            # ¿Es esta categoría padre de alguna otra en la lista?
            is_parent_of_another = any(
                other.parent_external_id == candidate.external_id
                for other in valid_categories
                if other.id != candidate.id
            )

            if not is_parent_of_another:
                # Esta es una categoría "hoja" (no es padre de otra en la lista)
                logger.info(f"🔍 [SYNC] Producto asignado a categoría hoja: {candidate.name} (en vez de padre)")
                return candidate.id

        # Fallback: retornar la primera si no hay relación padre-hijo clara
        logger.warning(f"⚠️ [SYNC] No hay relación padre-hijo clara, usando primera categoría")
        return valid_categories[0].id

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

    def _parse_woo_datetime(self, value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None

        try:
            raw = value.replace('Z', '+00:00')
            parsed = datetime.fromisoformat(raw)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).replace(tzinfo=None)
        except (ValueError, TypeError):
            return None

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

    def _sync_product_images(self, product: Product, images_data: List[Dict]) -> Tuple[int, int]:
        processed = 0
        embeddings_generated = 0
        import time
        batch_size = 4
        batch_images = []
        batch_sources = []

        def _flush_batch():
            nonlocal embeddings_generated
            if not batch_images:
                return

            log_system(f"[WOO SYNC] Generando embeddings batch ({len(batch_images)}) para producto {product.external_id}")
            self._generate_embeddings_batch(batch_images, batch_sources)
            embeddings_generated += len(batch_images)
            batch_images.clear()
            batch_sources.clear()

        # 🔍 DEBUG: Ver qué campos trae WooCommerce en images
        if images_data and processed == 0:
            log_system(f"[WOO SYNC] DEBUG - Campos disponibles en imagen WooCommerce: {list(images_data[0].keys())}")
            import json
            log_system(f"[WOO SYNC] DEBUG - Estructura completa: {json.dumps(images_data[0], indent=2)}")

        for idx, img_data in enumerate(images_data):
            source_url = img_data.get('src')
            thumbnail_url = img_data.get('thumbnail') or None
            if not source_url:
                raise ValueError(f"Imagen sin src en producto {product.external_id}")

            # ✅ Usar thumbnail que devuelve WooCommerce (300x300)
            image_url = thumbnail_url or source_url
            log_system(f"[WOO SYNC] Imagen {idx + 1}/{len(images_data)} producto {product.external_id}")
            log_system(f"[WOO SYNC]   Original: {source_url}")
            log_system(f"[WOO SYNC]   Thumbnail API: {thumbnail_url}")
            log_system(f"[WOO SYNC]   Usando: {image_url}")

            url_hash = hashlib.sha256(source_url.encode()).hexdigest()

            existing_image = Image.query.filter_by(
                product_id=product.id,
                hash_sha256=url_hash
            ).first()

            if existing_image:
                if existing_image.is_processed and existing_image.clip_embedding:
                    continue

                if processed == 0:
                    logger.info(f"[WOO SYNC] Reprocesando imagen existente para producto {product.external_id}")

                existing_image.upload_status = 'processing'
                if existing_image.base64_thumb:
                    image_source = existing_image.base64_thumb
                elif existing_image.source_url:
                    image_source = existing_image.source_url
                else:
                    existing_image.upload_status = 'failed'
                    existing_image.error_message = 'No hay fuente de imagen disponible'
                    db.session.add(existing_image)
                    db.session.commit()
                    raise ValueError(f"No hay fuente de imagen para {existing_image.id}")

                self._generate_embedding_for_image(existing_image, image_source)
                db.session.add(existing_image)
                db.session.commit()
                log_system(f"[WOO SYNC] Imagen existente procesada {existing_image.id}")
                embeddings_generated += 1
                continue

            t_start = time.time()
            # 🚀 Descargar thumbnail 300x300 devuelto por WooCommerce
            try:
                base64_thumb, mime_type, width, height, size_bytes = self._download_thumbnail_direct(image_url)
            except Exception as e:
                log_system(
                    f"[WOO SYNC] Error descargando thumbnail {image_url}: {e}"
                )
                continue
            t_download = time.time()

            if not base64_thumb:
                log_system(
                    f"[WOO SYNC] Imagen sin thumbnail para producto {product.external_id}: {image_url}"
                )
                continue

            image = Image(
                client_id=self.client.id,
                product_id=product.id,
                filename=f"wc_{product.external_id}_{idx}.{mime_type.split('/')[-1] if mime_type else 'jpg'}",
                original_filename=source_url.split('/')[-1],
                source_url=source_url,
                base64_data=None,  # 🚀 No guardamos imagen full, solo thumbnail
                base64_thumb=base64_thumb,
                mime_type=mime_type,
                width=width,
                height=height,
                size_bytes=size_bytes,
                hash_sha256=url_hash,
                is_primary=(idx == 0),
                display_order=idx,
                upload_status='processing',
                is_processed=False,
            )
            db.session.add(image)
            processed += 1

            db.session.commit()
            log_system(f"[WOO SYNC] Imagen guardada {image.id} producto {product.external_id}")

            log_system(f"[WOO SYNC] Imagen descargada ({size_bytes} bytes) para producto {product.external_id}")

            batch_images.append(image)
            batch_sources.append(base64_thumb)

            if len(batch_images) >= batch_size:
                _flush_batch()

            if processed <= 5 or processed % 100 == 0:
                logger.info(f"[DOWNLOAD] Imagen {processed}: {t_download - t_start:.2f}s ({size_bytes} bytes)")

        # Procesar últimos pendientes del batch
        _flush_batch()

        return processed, embeddings_generated

    def _generate_embedding_for_image(self, image: Image, image_source: str) -> None:
        from app.blueprints.embeddings import generate_clip_embedding

        log_system(f"[WOO SYNC] Generando embedding para imagen {image.id}")
        embedding, _metadata = generate_clip_embedding(image_source, image)
        if embedding is None:
            image.upload_status = 'failed'
            image.error_message = "No se pudo generar embedding"
            log_system(f"[WOO SYNC] Error generando embedding para imagen {image.id}: embedding None")
            raise RuntimeError(f"Embedding None para imagen {image.id}")

        image.clip_embedding = json.dumps(embedding)
        image.is_processed = True
        image.upload_status = 'completed'
        image.error_message = None
        log_system(f"[WOO SYNC] Embedding generado para imagen {image.id}")

    def _generate_embeddings_batch(self, images: List[Image], image_sources: List[str]) -> None:
        from app.blueprints.embeddings import generate_clip_embeddings_batch

        log_system(f"[WOO SYNC] Iniciando batch de embeddings: {len(images)} imágenes")
        results = generate_clip_embeddings_batch(image_sources, images)

        for image, (embedding, metadata) in zip(images, results):
            if embedding is None:
                image.upload_status = 'failed'
                image.error_message = "No se pudo generar embedding"
                log_system(f"[WOO SYNC] Error generando embedding batch para imagen {image.id}: embedding None")
                raise RuntimeError(f"Embedding None para imagen {image.id}")

            image.clip_embedding = json.dumps(embedding)
            image.is_processed = True
            image.upload_status = 'completed'
            image.error_message = None

            if hasattr(image, 'metadata') and metadata:
                image.metadata = json.dumps(metadata)

            db.session.add(image)
            db.session.commit()
            log_system(f"[WOO SYNC] Embedding generado (batch) para imagen {image.id}")

    def _download_thumbnail_direct(self, url: str) -> Tuple[Optional[str], str, int, int, int]:
        """
        Descarga thumbnail pre-generado directamente sin resize.
        Retorna: (base64_data, mime_type, width, height, size_bytes)
        """
        import requests
        from PIL import Image as PILImage
        import io
        import base64

        try:
            response = requests.get(url, timeout=30, verify=True)
            response.raise_for_status()

            image_bytes = response.content
            size_bytes = len(image_bytes)

            # Abrir con PIL para obtener dimensiones y mime type
            img = PILImage.open(io.BytesIO(image_bytes))
            width, height = img.size

            # Determinar mime type
            format_lower = img.format.lower() if img.format else 'jpeg'
            mime_type = f"image/{format_lower}"

            # Convertir a base64
            base64_data = base64.b64encode(image_bytes).decode('utf-8')

            return base64_data, mime_type, width, height, size_bytes

        except Exception as e:
            log_system(f"[WOO SYNC] Error descargando thumbnail {url}: {str(e)}")
            return None, None, 0, 0, 0

    def _download_and_convert_image(self, url: str, thumb_size: Tuple[int, int] = (300, 300)) -> Tuple[Optional[str], Optional[str], str, int, int, int]:
        response = requests.get(url, timeout=15, verify=False)
        if response.status_code != 200:
            log_system(f"[WOO SYNC] Error descargando imagen ({response.status_code}): {url}")
            raise RuntimeError(f"Error descargando imagen {response.status_code} {url}")

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

        if not base64_thumb:
            raise RuntimeError(f"No se pudo generar thumbnail para {url}")

        return base64_full, base64_thumb, mime_type, width, height, size_bytes

    # ---------------- Embeddings y centroides ----------------

    def generate_embeddings(self, force_regenerate: bool = True) -> int:
        try:
            from app.blueprints.embeddings import get_clip_model, load_image_from_source
            import torch
            import numpy as np

            clip_model, clip_processor = get_clip_model()

            if force_regenerate:
                images_q = Image.query.filter_by(client_id=self.client.id).all()
                logger.info(f"[EMBEDDING] force_regenerate=True: {len(images_q)} imágenes totales para cliente {self.client.id}")
                for img in images_q:
                    img.clip_embedding = None
                    img.is_processed = False
                db.session.commit()
                unprocessed = images_q
            else:
                unprocessed = Image.query.filter_by(client_id=self.client.id, is_processed=False).filter(
                    Image.base64_thumb.isnot(None)
                ).all()
                logger.info(f"[EMBEDDING] force_regenerate=False: {len(unprocessed)} imágenes SIN procesar para cliente {self.client.id}")

            logger.info(f"[EMBEDDING] Iniciando generación de embeddings para {len(unprocessed)} imágenes")
            generated = 0
            import time
            for idx, image in enumerate(unprocessed):
                try:
                    iter_start = time.time()
                    if idx < 10:
                        logger.info(f"[EMBEDDING] Procesando imagen {idx+1}/{len(unprocessed)}: {image.id}")

                    t1 = time.time()
                    image_bytes = base64.b64decode(image.base64_thumb)
                    t2 = time.time()
                    pil_image = load_image_from_source(image_bytes)
                    t3 = time.time()
                    inputs = clip_processor(images=pil_image, return_tensors="pt")
                    t4 = time.time()
                    if torch.cuda.is_available():
                        inputs = {k: v.cuda() for k, v in inputs.items()}

                    t5 = time.time()
                    with torch.no_grad():
                        feats = clip_model.get_image_features(**inputs)
                        feats = feats / feats.norm(dim=-1, keepdim=True)
                        embedding = feats.cpu().numpy().flatten()
                    t6 = time.time()

                    image.clip_embedding = json.dumps(embedding.tolist())
                    image.is_processed = True
                    image.upload_status = 'completed'
                    generated += 1
                    t7 = time.time()

                    if idx < 5:
                        logger.info(f"[TIMING] b64={t2-t1:.2f}s load={t3-t2:.2f}s proc={t4-t3:.2f}s feat={t6-t5:.2f}s save={t7-t6:.2f}s total={t7-iter_start:.2f}s")

                    if generated % 100 == 0:
                        logger.info(f"[EMBEDDING] Procesadas {generated} imágenes...")
                except Exception as e:
                    logger.error(f"[EMBEDDING] Error en imagen {image.id}: {e}", exc_info=True)
                    image.upload_status = 'failed'
                    image.error_message = str(e)
                db.session.add(image)

            db.session.commit()
            logger.info(f"[EMBEDDING] ✅ Embedding generation completada: {generated} embeddings generados")
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

    def update_category_parent(self, external_category_id: str, parent_external_id: str | None) -> Dict:
        """Actualiza el padre de una categoría WooCommerce (CLIP → Woo)

        Args:
            external_category_id: ID de la categoría en WooCommerce (Category.external_id)
            parent_external_id: ID de la categoría padre en WooCommerce (Category.external_id) o None para raíz
        """
        if not external_category_id:
            raise ValueError("Se requiere external_id de la categoría para actualizar en WooCommerce")

        payload = {
            'parent': int(parent_external_id) if parent_external_id else 0
        }

        logger.info(
            f"WooCommerce: actualizando padre de categoría {external_category_id} -> "
            f"{parent_external_id if parent_external_id else 'root'}"
        )
        return self.api.update_category(int(external_category_id), payload)


def start_full_sync(client_id: str, sync_options: Dict = None, is_resync: bool = False) -> Dict:
    """
    Función auxiliar para iniciar sincronización completa de WooCommerce.
    Puede ser llamada desde un task asíncrono o endpoint de resincronización.

    Args:
        client_id: ID del cliente
        sync_options: Dict con opciones de sincronización:
            - categories: bool (sincronizar categorías)
            - attributes: bool (sincronizar atributos)
            - products: bool (sincronizar productos)
            - images: bool (sincronizar imágenes)
            - embeddings: bool (generar embeddings)
            - centroids: bool (calcular centroides)
        is_resync: bool (True si es resincronización - limpia embeddings viejos)

    Returns:
        Dict con resultado de la sincronización
    """
    try:
        service = WooCommerceSyncService(client_id)
        return service.full_sync(sync_options, is_resync=is_resync)
    except Exception as e:
        logger.error(f"Error iniciando sincronización WooCommerce para cliente {client_id}: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }
