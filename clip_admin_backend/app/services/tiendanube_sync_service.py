"""
Servicio de sincronización con Tiendanube
Pipeline completo: Categorías → Productos → Imágenes Base64 → Embeddings → Centroides
"""
import requests
import logging
import base64
import hashlib
import io
from PIL import Image as PILImage
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import json
import time

from app import db
from sqlalchemy.orm.attributes import flag_modified
from app.models.client import Client
from app.models.tiendanube_integration import TiendanubeIntegration
from app.models.category import Category
from app.models.product import Product
from app.models.image import Image
from app.models.product_attribute_config import ProductAttributeConfig
from app.models.embedding import Embedding
from app.services.alternative_terms_generator import generate_alternative_terms
from app.services.alternative_terms_generator import (
    FASHION_VOCABULARY_ES,
    FASHION_CATEGORY_GROUPS,
)

logger = logging.getLogger(__name__)

TIENDANUBE_API_BASE = 'https://api.tiendanube.com/v1'
MAX_RETRIES = 3
RETRY_DELAY = 2  # segundos

class TiendanubeSyncService:
    """Servicio para sincronización inicial e incremental con Tiendanube"""

    def __init__(self, integration_or_client_id):
        """
        Inicializa el servicio de sincronización.

        Args:
            integration_or_client_id: Puede ser un objeto TiendanubeIntegration o un client_id (str)
        """
        if isinstance(integration_or_client_id, str):
            # Es un client_id
            self.client = Client.query.get(integration_or_client_id)
            if not self.client:
                raise ValueError(f"Cliente {integration_or_client_id} no encontrado")

            self.integration = TiendanubeIntegration.query.filter_by(
                client_id=integration_or_client_id, is_active=True
            ).first()

            if not self.integration:
                raise ValueError(f"No hay integración activa para cliente {integration_or_client_id}")
        else:
            # Es un objeto TiendanubeIntegration
            self.integration = integration_or_client_id
            self.client = Client.query.get(self.integration.client_id)
            if not self.client:
                raise ValueError(f"Cliente {self.integration.client_id} no encontrado")

        self.store_id = self.integration.store_id
        self.access_token = self.integration.get_access_token()
        self.headers = {
            'Authentication': f'bearer {self.access_token}',
            'User-Agent': 'CLIP Comparador V2 (info@clipcomparador.com)',
            'Content-Type': 'application/json'
        }

        # Stats de sincronización
        self.stats = {
            'categories_created': 0,
            'categories_updated': 0,
            'products_created': 0,
            'products_updated': 0,
            'images_processed': 0,
            'errors': []
        }

    def full_sync(self, sync_options: Dict = None) -> Dict:
        """
        Sincronización completa o selectiva según sync_options.

        Args:
            sync_options: Dict con flags de qué sincronizar. Si es None, sincroniza todo.
        """
        try:
            # Opciones por defecto: sincronizar todo
            if sync_options is None:
                sync_options = {
                    'categories': True,
                    'products': True,
                    'images': True,
                    'stock': True,
                    'attributes': True,
                    'embeddings': True
                }

            logger.info(f"Iniciando sincronización para store_id={self.store_id}")
            logger.info(f"Opciones: {sync_options}")
            self.integration.sync_status = 'in_progress'
            self.integration.sync_error = None
            db.session.commit()

            start_time = time.time()
            steps_completed = []

            # 1. Sincronizar categorías
            if sync_options.get('categories', True):
                logger.info("Paso 1: Sincronizando categorías...")
                self.sync_categories()
                steps_completed.append('categories')

                # Heurística: inferir industria por categorías iniciales sólo si aún es genérica
                try:
                    self._maybe_assign_industry_from_categories()
                except Exception as _e:
                    logger.warning(f"No se pudo inferir industria por categorías: {_e}")

            # 2. Sincronizar productos (con imágenes si está habilitado)
            if sync_options.get('products', True) or sync_options.get('attributes', False):
                logger.info("Paso 2: Sincronizando productos...")
                # Si solo queremos atributos, podemos optimizar para no re-descargar imágenes
                sync_images = sync_options.get('images', True)
                self.sync_products(sync_images=sync_images, update_attributes_only=sync_options.get('attributes', False) and not sync_options.get('products', False))
                steps_completed.append('products')

            # 3. Generar embeddings CLIP (si no existen)
            if sync_options.get('embeddings', True):
                logger.info("Paso 3: Generando embeddings CLIP (regenerando todos)...")
                self.generate_embeddings(force_regenerate=True)  # Siempre regenerar TODO cuando se solicita desde UI
                steps_completed.append('embeddings')

            # 4. Calcular centroides de categorías
            if sync_options.get('embeddings', True):  # Solo si generamos embeddings
                logger.info("Paso 4: Calculando centroides de categorías...")
                self.calculate_category_centroids()
                steps_completed.append('centroids')

            # 5. Regenerar embeddings de TEXTO a 512D
            if sync_options.get('embeddings', True):
                logger.info("Paso 5: Regenerando embeddings de TEXTO a 512D...")
                try:
                    self._regenerate_text_embeddings_clip512()
                    steps_completed.append('text_embeddings')
                except Exception as e:
                    logger.warning(f"Aviso: Error regenerando embeddings de texto: {e}")

            duration = time.time() - start_time

            # Actualizar estado de integración
            self.integration.sync_status = 'completed'
            self.integration.last_sync_at = datetime.utcnow()
            db.session.commit()

            logger.info(f"Sincronización completa exitosa en {duration:.2f}s")

            return {
                'success': True,
                'duration_seconds': duration,
                'stats': self.stats
            }

        except Exception as e:
            logger.error(f"Error en sincronización completa: {str(e)}", exc_info=True)
            self.integration.sync_status = 'error'
            self.integration.sync_error = str(e)
            db.session.commit()

            return {
                'success': False,
                'error': str(e),
                'stats': self.stats
            }

    def sync_categories(self):
        """Sincroniza categorías desde Tiendanube"""
        try:
            page = 1
            per_page = 50

            while True:
                url = f'{TIENDANUBE_API_BASE}/{self.store_id}/categories'
                params = {'page': page, 'per_page': per_page}

                response = self._api_request('GET', url, params=params)
                if not response:
                    break

                categories = response.json()
                if not categories:
                    break

                for cat_data in categories:
                    self._sync_category(cat_data)

                if len(categories) < per_page:
                    break

                page += 1
                time.sleep(0.5)  # Rate limiting

        except Exception as e:
            logger.error(f"Error sincronizando categorías: {str(e)}")
            self.stats['errors'].append(f"Categorías: {str(e)}")

    def _sync_category(self, cat_data: Dict):
        """Sincroniza una categoría individual"""
        try:
            external_id = str(cat_data['id'])

            # Buscar categoría existente
            category = Category.query.filter_by(
                client_id=self.client.id,
                external_id=external_id
            ).first()

            name = cat_data.get('name', {}).get('es', f'Categoría {external_id}')
            description = cat_data.get('description', {}).get('es', '')

            if category:
                # Actualizar existente - NO tocar campos propietarios (name_en, clip_prompt, etc)
                category.name = name
                category.description = description
                category.last_sync_at = datetime.utcnow()
                category.sync_status = 'synced'
                self.stats['categories_updated'] += 1
            else:
                # Crear nueva - auto-generar campos propietarios
                client_industry = self.client.industry if hasattr(self.client, 'industry') else 'general'

                # Auto-traducir nombre a inglés
                name_en = Category.auto_translate_to_english(name, client_industry)

                # Auto-generar CLIP prompt
                clip_prompt = Category.generate_clip_prompt(name_en)

                # Auto-generar alternative_terms
                alternative_terms = None
                try:
                    alternative_terms = generate_alternative_terms(name)
                    if alternative_terms:
                        logger.info(f"✨ Alternative terms generados: '{name}' → '{alternative_terms}'")
                except Exception as e:
                    logger.warning(f"No se pudieron generar alternative_terms para '{name}': {e}")

                logger.info(f"✨ Auto-generando campos CLIP: '{name}' → name_en='{name_en}', clip_prompt='{clip_prompt}'")

                category = Category(
                    client_id=self.client.id,
                    name=name,
                    name_en=name_en,
                    description=description,
                    clip_prompt=clip_prompt,
                    alternative_terms=alternative_terms,
                    external_id=external_id,
                    last_sync_at=datetime.utcnow(),
                    sync_status='synced'
                )
                db.session.add(category)
                self.stats['categories_created'] += 1

            db.session.commit()

        except Exception as e:
            logger.error(f"Error sincronizando categoría {cat_data.get('id')}: {str(e)}")
            self.stats['errors'].append(f"Categoría {cat_data.get('id')}: {str(e)}")

    # ------------------------------------------------------------
    # Heurística de rubro por categorías iniciales (moda/fashion)
    # ------------------------------------------------------------
    def _maybe_assign_industry_from_categories(self) -> None:
        """Si el cliente aún no tiene una industria específica, infiere 'fashion'
        cuando las categorías sincronizadas coinciden con vocabulario de moda.

        Criterio simple: si al menos 3 categorías contienen términos del
        vocabulario/grupos de moda, asignar 'fashion'.
        """
        try:
            current = (self.client.industry or '').lower().strip()
            specific_industries = {"fashion", "electronics", "automotive", "home"}
            if current in specific_industries:
                return  # Ya está específica, no tocar

            # Cargar categorías actuales del cliente
            categories = Category.query.filter_by(client_id=self.client.id).all()
            if not categories:
                return

            vocab_set = set(FASHION_VOCABULARY_ES)
            # Incluir términos de grupos (tops/bottoms/swimwear)
            for terms in FASHION_CATEGORY_GROUPS.values():
                vocab_set.update(terms)

            matches = 0
            for c in categories:
                name = (c.name or '').lower()
                if not name:
                    continue
                # Coincidencia por substring para soportar multi-palabra (p.ej. "traje de baño")
                if any(term in name for term in vocab_set):
                    matches += 1

            if matches >= 3:
                logger.info(f"🎯 Industria inferida como 'fashion' por categorías (matches={matches})")
                self.client.industry = 'fashion'
                # Marcar fuente de inferencia en integration_config
                if not self.client.integration_config:
                    self.client.integration_config = {}
                self.client.integration_config['industry_inferred'] = 'fashion_from_categories'
                flag_modified(self.client, 'integration_config')
                db.session.commit()

                # 🆕 Inicializar perfil de búsqueda para 'fashion' (carga en caché)
                from app.services.search_profiles_service import SearchProfilesService
                try:
                    profile = SearchProfilesService.get_profile(self.client.id, 'fashion', force_reload=True)
                    logger.info(f"✅ Perfil de búsqueda 'fashion' inicializado para {self.client.slug}")
                except Exception as e:
                    logger.warning(f"⚠️ Error inicializando perfil de búsqueda: {e}")
        except Exception as e:
            logger.warning(f"Heurística de industria falló: {e}")

    def _auto_create_attribute_configs(self, variant_attributes: Dict, attribute_names: Dict = None):
        """Auto-crea configuraciones de atributos basadas en variantes

        Args:
            variant_attributes: Dict con estructura {0: set(['Rojo', 'Azul']), 1: set(['S', 'M', 'L'])}
            attribute_names: Dict con nombres reales de Tiendanube {0: 'Color', 1: 'Talle'}
        """
        # Fallback a nombres genéricos si no se proporcionan
        fallback_names = {
            0: 'Color',
            1: 'Talla',
            2: 'Material',
            3: 'Estilo'
        }

        for idx, values_set in variant_attributes.items():
            # Usar nombre de Tiendanube si está disponible, sino fallback
            if attribute_names and idx in attribute_names:
                attr_label = attribute_names[idx]
            else:
                attr_label = fallback_names.get(idx, f'Atributo {idx + 1}')

            # Convertir el label a formato snake_case para usar como key
            # Ejemplo: "Color" -> "color", "Talla especial" -> "talla_especial"
            attr_key = attr_label.lower().strip().replace(' ', '_').replace('-', '_')
            # Remover caracteres especiales
            attr_key = ''.join(c for c in attr_key if c.isalnum() or c == '_')

            values = sorted(list(values_set))

            # Verificar si ya existe
            existing = ProductAttributeConfig.query.filter_by(
                client_id=self.client.id,
                key=attr_key
            ).first()

            if not existing:
                config = ProductAttributeConfig(
                    client_id=self.client.id,
                    key=attr_key,
                    label=attr_label,
                    type='list',
                    required=False,
                    options={
                        'multiple': False,
                        'values': values
                    },
                    field_order=idx,
                    expose_in_search=True
                )
                db.session.add(config)
                logger.info(f"✨ Auto-creado atributo '{attr_label}' con valores: {values}")
            else:
                # Actualizar opciones si hay nuevos valores
                current_values = set(existing.options.get('values', []) if existing.options else [])
                new_values = set(values)

                if new_values - current_values:
                    existing.options = {
                        'multiple': False,
                        'values': sorted(list(current_values | new_values))
                    }
                    logger.info(f"📝 Actualizado atributo '{attr_label}' con nuevos valores")

        db.session.commit()

    def _get_best_price(self, variants: List[Dict]) -> Optional[float]:
        """Obtiene el mejor precio: promocional si existe, sino el precio regular

        Prioridad:
        1. Precio promocional más bajo
        2. Precio regular más bajo
        """
        if not variants:
            return None

        promo_prices = []
        regular_prices = []

        for variant in variants:
            promo = variant.get('promotional_price')
            regular = variant.get('price')

            if promo:
                try:
                    promo_prices.append(float(promo))
                except (ValueError, TypeError):
                    pass

            if regular:
                try:
                    regular_prices.append(float(regular))
                except (ValueError, TypeError):
                    pass

        # Devolver el menor precio promocional, o el menor regular
        if promo_prices:
            return min(promo_prices)
        elif regular_prices:
            return min(regular_prices)

        return None

    def _extract_product_attributes(self, variants: List[Dict], attribute_names: Dict = None) -> Dict:
        """Extrae los valores de atributos del primer variante (producto simple) o agrega todos

        Args:
            variants: Lista de variantes del producto
            attribute_names: Dict con nombres reales de Tiendanube {0: 'Color', 1: 'Talle'}
        """
        if not variants:
            return {}

        # Fallback a nombres genéricos
        fallback_names = {
            0: 'Color',
            1: 'Talla',
            2: 'Material',
            3: 'Estilo'
        }

        # Tomar valores del primer variante como representativos
        first_variant = variants[0]
        values = first_variant.get('values', [])

        attributes = {}
        for idx, value_obj in enumerate(values):
            # Determinar el nombre del atributo
            if attribute_names and idx in attribute_names:
                attr_label = attribute_names[idx]
            else:
                attr_label = fallback_names.get(idx, f'Atributo {idx + 1}')

            # Convertir a snake_case para usar como key (igual que en _auto_create_attribute_configs)
            attr_key = attr_label.lower().strip().replace(' ', '_').replace('-', '_')
            attr_key = ''.join(c for c in attr_key if c.isalnum() or c == '_')

            if isinstance(value_obj, dict):
                val = value_obj.get('es', value_obj.get('pt', ''))
            else:
                val = str(value_obj)

            if val:
                attributes[attr_key] = val

        return attributes

    def sync_products(self, sync_images: bool = True, update_attributes_only: bool = False):
        """Sincroniza productos con sus imágenes desde Tiendanube

        Args:
            sync_images: Si True, sincroniza imágenes. Si False, solo metadatos.
            update_attributes_only: Si True, solo actualiza atributos dinámicos sin tocar otros campos.
        """
        try:
            logger.info("🔍 Paso 1: Recolectando productos y analizando variantes...")

            # Paso 1: Recolectar todos los productos para análisis
            all_products = []
            page = 1
            per_page = 50

            while True:
                url = f'{TIENDANUBE_API_BASE}/{self.store_id}/products'
                params = {'page': page, 'per_page': per_page}

                response = self._api_request('GET', url, params=params)
                if not response:
                    break

                products = response.json()
                if not products:
                    break

                all_products.extend(products)

                if len(products) < per_page:
                    break

                page += 1
                time.sleep(0.5)  # Rate limiting

            if not all_products:
                logger.warning("No se obtuvieron productos de Tiendanube")
                return

            logger.info(f"📦 Encontrados {len(all_products)} productos")

            # Paso 2: Analizar variantes para detectar atributos y extraer nombres desde products.attributes
            logger.info("🔎 Paso 2: Detectando atributos desde variantes...")
            all_variant_attributes = {}
            attribute_names_from_tiendanube = {}

            for prod_data in all_products:
                # Extraer nombres de atributos desde product.attributes
                product_attributes = prod_data.get('attributes', [])
                for idx, attr_name_obj in enumerate(product_attributes):
                    if idx not in attribute_names_from_tiendanube:
                        if isinstance(attr_name_obj, dict):
                            name = attr_name_obj.get('es', attr_name_obj.get('pt', f'Atributo {idx + 1}'))
                        else:
                            name = str(attr_name_obj)
                        attribute_names_from_tiendanube[idx] = name
                        logger.info(f"📌 Detectado nombre de atributo {idx}: '{name}'")

                # Extraer valores de variantes
                variants = prod_data.get('variants', [])
                if not variants:
                    continue

                for variant in variants:
                    values = variant.get('values', [])
                    for idx, value_obj in enumerate(values):
                        if idx not in all_variant_attributes:
                            all_variant_attributes[idx] = set()

                        if isinstance(value_obj, dict):
                            val = value_obj.get('es', value_obj.get('pt', ''))
                        else:
                            val = str(value_obj)

                        if val:
                            all_variant_attributes[idx].add(val)

            # Paso 3: Auto-crear configuraciones de atributos con nombres reales
            if all_variant_attributes:
                logger.info(f"✨ Detectados {len(all_variant_attributes)} tipos de atributos")
                self._auto_create_attribute_configs(all_variant_attributes, attribute_names_from_tiendanube)

            # Paso 4: Sincronizar productos
            logger.info(f"💾 Paso 3: Sincronizando {len(all_products)} productos...")
            for prod_data in all_products:
                self._sync_product(prod_data, attribute_names_from_tiendanube, sync_images=sync_images, update_attributes_only=update_attributes_only)

        except Exception as e:
            logger.error(f"Error sincronizando productos: {str(e)}")
            self.stats['errors'].append(f"Productos: {str(e)}")

    def _normalize_and_sync_attribute_values(self, product_attributes: Dict) -> Dict:
        """
        Normaliza valores de atributos y agrega nuevos valores a la configuración de atributos.

        Para cada atributo de tipo 'list' que viene del producto:
        1. Normaliza el valor (mayúscula primera letra)
        2. Si el valor no está en product_attribute_config.options.values, lo agrega

        Args:
            product_attributes: Dict con atributos del producto {key: valor}

        Returns:
            Dict normalizado con los mismos atributos
        """
        if not product_attributes:
            return product_attributes

        try:
            normalized = {}

            for key, value in product_attributes.items():
                if not value:
                    normalized[key] = value
                    continue

                # Obtener configuración del atributo
                config = ProductAttributeConfig.query.filter_by(
                    client_id=self.client.id,
                    key=key
                ).first()

                if not config:
                    # Sin configuración, devolver valor sin cambios
                    normalized[key] = value
                    continue

                # Si es tipo lista, normalizar y agregar si no existe
                if config.type == 'list':
                    # Normalizar valor: capitalizar la primera letra
                    if isinstance(value, str):
                        normalized_value = value.strip().capitalize()
                    elif isinstance(value, list):
                        # Si es lista, normalizar cada elemento
                        normalized_value = [
                            v.strip().capitalize() if isinstance(v, str) else v
                            for v in value
                        ]
                    else:
                        normalized_value = value

                    # Obtener opciones actuales
                    options = config.options or {}
                    values_list = options.get('values', [])

                    # Valores a procesar (puede ser string o lista)
                    values_to_check = normalized_value if isinstance(normalized_value, list) else [normalized_value]

                    # Agregar valores faltantes
                    added_any = False
                    for val in values_to_check:
                        if val and val not in values_list:
                            values_list.append(val)
                            added_any = True
                            logger.info(f"➕ Agregado valor '{val}' a atributo '{key}' para cliente {self.client.id}")

                    # Actualizar configuración si se agregaron valores
                    if added_any:
                        options['values'] = sorted(values_list)
                        config.options = options
                        flag_modified(config, 'options')  # Marcar JSONB como modificado
                        db.session.commit()
                        logger.info(f"💾 Guardados valores actualizados para '{key}': {options['values']}")

                    normalized[key] = normalized_value
                else:
                    # Para otros tipos, devolver sin cambios
                    normalized[key] = value

            return normalized

        except Exception as e:
            logger.error(f"Error normalizando atributos: {str(e)}")
            # En caso de error, devolver los atributos originales
            return product_attributes

    def _sync_product(self, prod_data: Dict, attribute_names: Dict = None, sync_images: bool = True, update_attributes_only: bool = False):
        """Sincroniza un producto individual con sus imágenes

        Args:
            prod_data: Datos del producto desde Tiendanube
            attribute_names: Dict con nombres reales de atributos {0: 'Color', 1: 'Talle'}
            sync_images: Si True, sincroniza imágenes
            update_attributes_only: Si True, solo actualiza attributes sin tocar otros campos
        """
        try:
            external_id = str(prod_data['id'])

            # Mapear categoría
            category = self._map_category(prod_data.get('categories'))
            if not category:
                logger.warning(f"Producto {external_id} sin categoría válida, usando 'Sin categoría'")
                category = self._get_or_create_default_category()

            # Buscar producto existente
            product = Product.query.filter_by(
                client_id=self.client.id,
                external_id=external_id
            ).first()

            name = prod_data.get('name', {}).get('es', f'Producto {external_id}')
            description = prod_data.get('description', {}).get('es', '')
            brand = prod_data.get('brand', '')
            sku = prod_data.get('sku', '')

            # Obtener variantes
            variants = prod_data.get('variants', [])

            # Precio: usar promocional si existe, sino regular
            price = self._get_best_price(variants)

            # Stock: sumar todas las variantes (manejar None como 0)
            stock = sum(v.get('stock') or 0 for v in variants)

            # Extraer atributos desde variantes con nombres reales
            product_attributes = self._extract_product_attributes(variants, attribute_names)

            # Normalizar atributos y agregar nuevos valores a la configuración
            product_attributes = self._normalize_and_sync_attribute_values(product_attributes)

            # Construir external_url correctamente
            handle_data = prod_data.get('handle', {})
            if isinstance(handle_data, dict):
                # handle es un dict multiidioma: {'es': 'remera-roja', 'pt': 'camisa-vermelha'}
                handle = handle_data.get('es', handle_data.get('pt', str(external_id)))
            else:
                handle = str(handle_data) if handle_data else str(external_id)

            external_url = f"https://{self.integration.store_domain}/productos/{handle}"

            if product:
                # Actualizar existente
                if update_attributes_only:
                    # Solo actualizar atributos dinámicos
                    logger.info(f"📝 Actualizando solo atributos de '{name}'")
                    product.attributes = product_attributes if product_attributes else None
                    product.last_sync_at = datetime.utcnow()
                else:
                    # Actualización completa
                    product.name = name
                    product.description = description
                    product.brand = brand
                    product.sku = sku
                    product.price = price
                    product.stock = stock
                    product.category_id = category.id
                    product.external_url = external_url
                    product.attributes = product_attributes if product_attributes else None
                    product.last_sync_at = datetime.utcnow()
                    product.sync_status = 'synced'
                self.stats['products_updated'] += 1
            else:
                # Crear nuevo
                product = Product(
                    client_id=self.client.id,
                    category_id=category.id,
                    name=name,
                    description=description,
                    brand=brand,
                    sku=sku,
                    price=price,
                    stock=stock,
                    attributes=product_attributes if product_attributes else None,
                    external_id=external_id,
                    external_url=external_url,
                    last_sync_at=datetime.utcnow(),
                    sync_status='synced'
                )
                db.session.add(product)
                db.session.flush()  # Obtener product.id
                self.stats['products_created'] += 1

            db.session.commit()

            # Sincronizar imágenes solo si está habilitado
            if sync_images:
                images = prod_data.get('images', [])
                if images:
                    self._sync_product_images(product, images)

            # Devolver el producto sincronizado para consumidores (webhooks)
            return product

        except Exception as e:
            logger.error(f"Error sincronizando producto {prod_data.get('id')}: {str(e)}")
            self.stats['errors'].append(f"Producto {prod_data.get('id')}: {str(e)}")
            db.session.rollback()
            return None

    def _sync_product_images(self, product: Product, images_data: List[Dict]):
        """Sincroniza imágenes de un producto con pipeline Base64"""
        try:
            for idx, img_data in enumerate(images_data):
                source_url = img_data.get('src')
                if not source_url:
                    continue

                # Calcular hash de la URL para detectar cambios
                url_hash = hashlib.sha256(source_url.encode()).hexdigest()

                # Buscar imagen existente por hash
                existing_image = Image.query.filter_by(
                    product_id=product.id,
                    hash_sha256=url_hash
                ).first()

                if existing_image:
                    # Imagen ya existe y no cambió
                    continue

                # Descargar y convertir a Base64
                base64_full, base64_thumb, mime_type, width, height, size_bytes = self._download_and_convert_image(source_url)

                if not base64_thumb:
                    logger.warning(f"No se pudo procesar imagen {source_url}")
                    continue

                # Crear nueva imagen
                image = Image(
                    client_id=self.client.id,
                    product_id=product.id,
                    filename=f"tn_{product.external_id}_{idx}.{mime_type.split('/')[-1]}",
                    original_filename=source_url.split('/')[-1],
                    source_url=source_url,
                    base64_data=base64_full,  # Opcional: puede ser None para ahorrar espacio
                    base64_thumb=base64_thumb,
                    mime_type=mime_type,
                    width=width,
                    height=height,
                    size_bytes=size_bytes,
                    hash_sha256=url_hash,
                    is_primary=(idx == 0),
                    display_order=idx,
                    upload_status='completed',
                    is_processed=False  # Se generará embedding después
                )
                db.session.add(image)
                db.session.commit()

                self.stats['images_processed'] += 1

        except Exception as e:
            logger.error(f"Error sincronizando imágenes del producto {product.id}: {str(e)}")
            self.stats['errors'].append(f"Imágenes producto {product.id}: {str(e)}")

    def _download_and_convert_image(self, url: str, thumb_size: Tuple[int, int] = (300, 300)) -> Tuple[Optional[str], Optional[str], str, int, int, int]:
        """
        Descarga imagen y la convierte a Base64 (full y thumbnail).
        Retorna: (base64_full, base64_thumb, mime_type, width, height, size_bytes)
        """
        try:
            response = requests.get(url, timeout=15, verify=False)
            if response.status_code != 200:
                return None, None, '', 0, 0, 0

            image_bytes = response.content
            size_bytes = len(image_bytes)

            # Abrir con PIL
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

            # Base64 full (opcional, puede ser None para ahorrar espacio)
            # base64_full = base64.b64encode(image_bytes).decode('utf-8')
            base64_full = None  # Por defecto no guardamos full, solo thumbnail

            # Generar thumbnail
            img_thumb = img.copy()
            img_thumb.thumbnail(thumb_size, PILImage.Resampling.LANCZOS)

            thumb_buffer = io.BytesIO()
            img_thumb.save(thumb_buffer, format='JPEG', quality=85, optimize=True)
            thumb_buffer.seek(0)
            base64_thumb = base64.b64encode(thumb_buffer.read()).decode('utf-8')

            return base64_full, base64_thumb, mime_type, width, height, size_bytes

        except Exception as e:
            logger.error(f"Error descargando/convirtiendo imagen {url}: {str(e)}")
            return None, None, '', 0, 0, 0

    def generate_embeddings(self, force_regenerate: bool = True):
        """
        Genera embeddings CLIP para imágenes.

        Args:
            force_regenerate: Si True, regenera TODOS los embeddings (borra antiguos).
                             Si False, solo genera para imágenes sin procesar (is_processed=False).
        """
        try:
            # Importar funciones de embeddings
            from app.blueprints.embeddings import get_clip_model, load_image_from_source
            import torch
            import numpy as np

            # Cargar modelo CLIP
            clip_model, clip_processor = get_clip_model()

            # Si force_regenerate=True, resetear TODOS los embeddings del cliente
            if force_regenerate:
                logger.info(f"🔄 REGENERANDO: Borrando todos los embeddings previos del cliente {self.client.id}...")
                all_images = Image.query.filter_by(client_id=self.client.id).all()
                for img in all_images:
                    img.clip_embedding = None
                    img.is_processed = False
                db.session.commit()
                logger.info(f"   ✅ {len(all_images)} imágenes marcadas para regenerar")
                unprocessed_images = all_images
            else:
                # Solo obtener imágenes sin procesar
                unprocessed_images = Image.query.filter_by(
                    client_id=self.client.id,
                    is_processed=False
                ).filter(
                    Image.base64_thumb.isnot(None)
                ).all()

            logger.info(f"Generando embeddings para {len(unprocessed_images)} imágenes...")

            for image in unprocessed_images:
                try:
                    # Decodificar Base64 a bytes
                    image_bytes = base64.b64decode(image.base64_thumb)

                    # Cargar imagen
                    pil_image = load_image_from_source(image_bytes)

                    # Procesar con CLIP
                    inputs = clip_processor(images=pil_image, return_tensors="pt")

                    # Mover a GPU si está disponible
                    if torch.cuda.is_available():
                        inputs = {k: v.cuda() for k, v in inputs.items()}

                    # Generar embedding
                    with torch.no_grad():
                        image_features = clip_model.get_image_features(**inputs)
                        # Normalizar
                        image_features = image_features / image_features.norm(dim=-1, keepdim=True)
                        embedding = image_features.cpu().numpy().flatten()

                    # Serializar y guardar
                    image.clip_embedding = json.dumps(embedding.tolist())
                    image.is_processed = True
                    image.upload_status = 'completed'
                    db.session.commit()

                except Exception as e:
                    logger.error(f"Error generando embedding para imagen {image.id}: {str(e)}")
                    image.upload_status = 'failed'
                    image.error_message = str(e)
                    db.session.commit()

            logger.info(f"Embeddings generados exitosamente")

        except Exception as e:
            logger.error(f"Error en generate_embeddings: {str(e)}")
            self.stats['errors'].append(f"Embeddings: {str(e)}")

    def calculate_category_centroids(self):
        """Calcula centroides CLIP para cada categoría"""
        try:
            import numpy as np

            # Obtener categorías del cliente
            categories = Category.query.filter_by(client_id=self.client.id).all()

            for category in categories:
                try:
                    # Obtener productos de la categoría con embeddings
                    products = Product.query.filter_by(
                        client_id=self.client.id,
                        category_id=category.id,
                        is_active=True
                    ).all()

                    embeddings = []
                    for product in products:
                        for image in product.images:
                            if image.is_processed and image.clip_embedding:
                                try:
                                    emb = json.loads(image.clip_embedding)
                                    embeddings.append(emb)
                                except Exception:
                                    continue

                    if embeddings:
                        # Calcular centroide (media)
                        embeddings_array = np.array(embeddings)
                        centroid = np.mean(embeddings_array, axis=0)

                        # Guardar centroide
                        category.centroid_embedding = json.dumps(centroid.tolist())
                        db.session.commit()

                        logger.info(f"Centroide calculado para categoría {category.name}: {len(embeddings)} embeddings")

                except Exception as e:
                    logger.error(f"Error calculando centroide para categoría {category.id}: {str(e)}")

        except Exception as e:
            logger.error(f"Error en calculate_category_centroids: {str(e)}")
            self.stats['errors'].append(f"Centroides: {str(e)}")

    def _map_category(self, categories_data: List[Dict]) -> Optional[Category]:
        """Mapea categoría de Tiendanube a categoría local"""
        if not categories_data:
            return None

        # Tomar primera categoría
        cat_data = categories_data[0]
        external_id = str(cat_data['id'])

        # Buscar categoría local por external_id
        category = Category.query.filter_by(
            client_id=self.client.id,
            external_id=external_id
        ).first()

        return category

    def _get_or_create_default_category(self) -> Category:
        """Obtiene o crea categoría 'Sin categoría'"""
        category = Category.query.filter_by(
            client_id=self.client.id,
            name='Sin categoría'
        ).first()

        if not category:
            category = Category(
                client_id=self.client.id,
                name='Sin categoría',
                description='Productos sin categoría asignada'
            )
            db.session.add(category)
            db.session.commit()

        return category

    def _api_request(self, method: str, url: str, **kwargs):
        """Realiza petición a la API de Tiendanube con reintentos"""
        for attempt in range(MAX_RETRIES):
            try:
                response = requests.request(
                    method, url,
                    headers=self.headers,
                    timeout=30,
                    verify=False,
                    **kwargs
                )

                if response.status_code == 429:  # Rate limit
                    logger.warning(f"Rate limit alcanzado, esperando {RETRY_DELAY}s...")
                    time.sleep(RETRY_DELAY)
                    continue

                if response.status_code >= 400:
                    logger.error(f"Error API {response.status_code}: {response.text}")
                    return None

                return response

            except Exception as e:
                logger.error(f"Error en petición API (intento {attempt + 1}/{MAX_RETRIES}): {str(e)}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
                else:
                    return None

        return None


    def _sync_single_product(self, product_id: str) -> Optional[Product]:
        """
        Sincroniza un único producto desde Tiendanube (para webhooks).

        Args:
            product_id: ID externo del producto en Tiendanube

        Returns:
            Product object o None si falla
        """
        try:
            # Obtener producto desde API
            url = f'{TIENDANUBE_API_BASE}/{self.store_id}/products/{product_id}'
            response = self._api_request('GET', url)

            if not response:
                logger.error(f"No se pudo obtener producto {product_id} desde Tiendanube")
                return None

            prod_data = response.json()

            # Extraer nombres de atributos desde product.attributes
            attribute_names_from_tiendanube = {}
            product_attributes = prod_data.get('attributes', [])
            for idx, attr_name_obj in enumerate(product_attributes):
                if isinstance(attr_name_obj, dict):
                    name = attr_name_obj.get('es', attr_name_obj.get('pt', f'Atributo {idx + 1}'))
                else:
                    name = str(attr_name_obj)
                attribute_names_from_tiendanube[idx] = name

            # Sincronizar usando método existente
            product = self._sync_product(prod_data, attribute_names_from_tiendanube)

            # Generar embeddings si hay imágenes nuevas
            if product:
                images = Image.query.filter_by(
                    product_id=product.id,
                    is_processed=False
                ).all()

                if images:
                    # Importar funciones de embeddings
                    from app.blueprints.embeddings import get_clip_model, load_image_from_source
                    import torch
                    import numpy as np

                    # Cargar modelo CLIP
                    clip_model, clip_processor = get_clip_model()

                    for image in images:
                        try:
                            if image.base64_thumb:
                                # Decodificar Base64 a bytes
                                image_bytes = base64.b64decode(image.base64_thumb)

                                # Cargar imagen
                                pil_image = load_image_from_source(image_bytes)

                                # Procesar con CLIP
                                inputs = clip_processor(images=pil_image, return_tensors="pt")

                                # Mover a GPU si está disponible
                                if torch.cuda.is_available():
                                    inputs = {k: v.cuda() for k, v in inputs.items()}

                                # Generar embedding
                                with torch.no_grad():
                                    image_features = clip_model.get_image_features(**inputs)
                                    # Normalizar
                                    image_features = image_features / image_features.norm(dim=-1, keepdim=True)
                                    embedding = image_features.cpu().numpy().flatten()

                                # Serializar y guardar
                                image.clip_embedding = json.dumps(embedding.tolist())
                                image.is_processed = True
                                image.upload_status = 'completed'

                        except Exception as e:
                            logger.error(f"Error generando embedding para imagen {image.id}: {str(e)}")
                            image.upload_status = 'failed'
                            image.error_message = str(e)

                    db.session.commit()

                # Actualizar centroide de categoría
                if product.category_id:
                    category = Category.query.get(product.category_id)
                    if category:
                        self._calculate_single_category_centroid(category)

            return product

        except Exception as e:
            logger.error(f"Error sincronizando producto individual {product_id}: {str(e)}", exc_info=True)
            return None

    def _sync_single_category(self, category_id: str) -> Optional[Category]:
        """
        Sincroniza una única categoría desde Tiendanube (para webhooks).

        Args:
            category_id: ID externo de la categoría en Tiendanube

        Returns:
            Category object o None si falla
        """
        try:
            # Obtener categoría desde API
            url = f'{TIENDANUBE_API_BASE}/{self.store_id}/categories/{category_id}'
            response = self._api_request('GET', url)

            if not response:
                logger.error(f"No se pudo obtener categoría {category_id} desde Tiendanube")
                return None

            cat_data = response.json()

            # Sincronizar usando método existente
            self._sync_category(cat_data)

            # Buscar categoría recién sincronizada
            category = Category.query.filter_by(
                client_id=self.client.id,
                external_id=category_id
            ).first()

            return category

        except Exception as e:
            logger.error(f"Error sincronizando categoría individual {category_id}: {str(e)}", exc_info=True)
            return None

    def _calculate_single_category_centroid(self, category: Category):
        """
        Calcula centroide para una única categoría.

        Args:
            category: Objeto Category
        """
        try:
            import numpy as np

            # Obtener embeddings de productos en esta categoría
            products = Product.query.filter_by(
                client_id=self.client.id,
                category_id=category.id,
                is_active=True
            ).all()

            embeddings = []
            for product in products:
                images = Image.query.filter_by(
                    product_id=product.id,
                    is_processed=True
                ).all()

                for image in images:
                    if image.clip_embedding:
                        try:
                            emb = json.loads(image.clip_embedding)
                            embeddings.append(emb)
                        except Exception:
                            continue

            if embeddings:
                # Calcular centroide (media)
                embeddings_array = np.array(embeddings)
                centroid = np.mean(embeddings_array, axis=0)

                # Guardar centroide
                category.centroid_embedding = json.dumps(centroid.tolist())
                db.session.commit()

                logger.info(f"Centroide actualizado para categoría {category.name}: {len(embeddings)} embeddings")

        except Exception as e:
            logger.error(f"Error calculando centroide para categoría {category.id}: {str(e)}")


    def _regenerate_text_embeddings_clip512(self):
        """Regenera embeddings de texto (vocab:X, color:X) a 512D usando CLIP."""
        try:
            from app.blueprints.embeddings import get_clip_model
            import torch
            import numpy as np

            logger.info(f"🔄 Regenerando embeddings de TEXTO a 512D para cliente {self.client.id}...")

            # Cargar modelo CLIP
            clip_model, clip_processor = get_clip_model()

            # Obtener todos los embeddings de texto del cliente
            old_embeddings = Embedding.query.filter_by(client_id=self.client.id).all()
            if not old_embeddings:
                logger.info("   Sin embeddings de texto para regenerar")
                return

            count_updated = 0
            for emb in old_embeddings:
                try:
                    # Extraer texto del key
                    parts = emb.key.split(':')
                    text_value = ':'.join(parts[1:]) if len(parts) >= 2 else emb.key

                    # Prompt contextual según tipo
                    if emb.type == 'color':
                        prompt = f"A product that is {text_value}"
                    elif emb.type == 'vocabulary':
                        prompt = f"A {text_value} product"
                    else:
                        prompt = text_value

                    # Procesar con CLIP
                    inputs = clip_processor(text=[prompt], return_tensors="pt")
                    if torch.cuda.is_available():
                        inputs = {k: v.cuda() for k, v in inputs.items()}

                    with torch.no_grad():
                        text_features = clip_model.get_text_features(**inputs)
                        text_features = text_features / text_features.norm(dim=-1, keepdim=True)
                        embedding_vec = text_features.cpu().numpy().flatten()

                    # Guardar embedding 512D
                    emb.embedding = json.dumps(embedding_vec.tolist())
                    emb.updated_at = datetime.utcnow()
                    db.session.commit()
                    count_updated += 1

                except Exception as e:
                    logger.warning(f"   ⚠️ Error en {emb.key}: {e}")

            logger.info(f"   ✅ {count_updated} embeddings de texto regenerados a 512D")

        except Exception as e:
            logger.error(f"Error regenerando embeddings de texto: {str(e)}")
            self.stats['errors'].append(f"Embeddings texto: {str(e)}")


def start_full_sync(client_id: str, sync_options: Dict = None) -> Dict:
    """
    Función auxiliar para iniciar sincronización completa o selectiva.
    Puede ser llamada desde un task asíncrono o endpoint.

    Args:
        client_id: ID del cliente
        sync_options: Dict con opciones de sincronización:
            - products: bool (sincronizar productos)
            - categories: bool (sincronizar categorías)
            - images: bool (sincronizar imágenes)
            - stock: bool (actualizar stock)
            - attributes: bool (sincronizar atributos dinámicos)
            - embeddings: bool (generar embeddings)
    """
    try:
        service = TiendanubeSyncService(client_id)
        return service.full_sync(sync_options)
    except Exception as e:
        logger.error(f"Error iniciando sincronización para cliente {client_id}: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }
