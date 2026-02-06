"""
Cliente de API para WooCommerce REST API v3
Maneja autenticación, rate limiting y errores
"""
import requests
import logging
from typing import Dict, List, Optional, Any
from requests.auth import HTTPBasicAuth
import time

logger = logging.getLogger(__name__)

class WooCommerceAPIError(Exception):
    """Excepción personalizada para errores de API de WooCommerce"""
    pass

class WooCommerceAPIClient:
    """
    Cliente para interactuar con WooCommerce REST API v3

    Documentación: https://woocommerce.github.io/woocommerce-rest-api-docs/
    """

    def __init__(self, store_url: str, consumer_key: str, consumer_secret: str,
                 api_version: str = 'v3', verify_ssl: bool = True):
        """
        Inicializa el cliente de API de WooCommerce.

        Args:
            store_url: URL base de la tienda (ej: https://mitienda.com)
            consumer_key: Consumer Key generado en WooCommerce
            consumer_secret: Consumer Secret generado en WooCommerce
            api_version: Versión de API (v3 por defecto)
            verify_ssl: Verificar certificados SSL (True en producción)
        """
        self.store_url = store_url.rstrip('/')
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.api_version = api_version
        self.verify_ssl = verify_ssl

        # Base URL de la API
        self.base_url = f"{self.store_url}/wp-json/wc/{self.api_version}"

        # Autenticación HTTP Basic Auth
        self.auth = HTTPBasicAuth(self.consumer_key, self.consumer_secret)

        # Headers
        self.headers = {
            'User-Agent': 'CLIP Comparador V2 (info@clipcomparador.com)',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }

        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 0.2  # 200ms entre requests (máx 5 req/sec)

    def _wait_for_rate_limit(self):
        """Implementa rate limiting básico"""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time

        if time_since_last_request < self.min_request_interval:
            time.sleep(self.min_request_interval - time_since_last_request)

        self.last_request_time = time.time()

    def _make_request(self, method: str, endpoint: str, params: Dict = None,
                     data: Dict = None, max_retries: int = 3) -> Dict:
        """
        Realiza una petición HTTP a la API de WooCommerce.

        Args:
            method: GET, POST, PUT, DELETE
            endpoint: Endpoint sin base URL (ej: '/products')
            params: Query parameters
            data: Body data para POST/PUT
            max_retries: Número de reintentos en caso de error

        Returns:
            Response JSON

        Raises:
            WooCommerceAPIError: Si la petición falla después de reintentos
        """
        self._wait_for_rate_limit()

        url = f"{self.base_url}{endpoint}"

        for attempt in range(max_retries):
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    auth=self.auth,
                    headers=self.headers,
                    params=params,
                    json=data,
                    verify=self.verify_ssl,
                    timeout=30
                )

                # Log de request
                logger.debug(f"WooCommerce API: {method} {endpoint} → {response.status_code}")

                # Manejar errores HTTP
                if response.status_code >= 400:
                    error_data = response.json() if response.content else {}
                    error_msg = error_data.get('message', f'HTTP {response.status_code}')

                    # Errores específicos
                    if response.status_code == 401:
                        raise WooCommerceAPIError(f"Autenticación fallida: {error_msg}")
                    elif response.status_code == 404:
                        raise WooCommerceAPIError(f"Recurso no encontrado: {endpoint}")
                    elif response.status_code == 429:
                        # Rate limit exceeded - esperar y reintentar
                        wait_time = 2 ** attempt  # Exponential backoff
                        logger.warning(f"Rate limit exceeded, esperando {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                    else:
                        raise WooCommerceAPIError(f"Error {response.status_code}: {error_msg}")

                # Parsear respuesta
                return response.json() if response.content else {}

            except requests.exceptions.Timeout:
                logger.warning(f"Timeout en intento {attempt + 1}/{max_retries}")
                if attempt == max_retries - 1:
                    raise WooCommerceAPIError("Request timeout después de varios intentos")
                time.sleep(1)

            except requests.exceptions.ConnectionError as e:
                logger.error(f"Error de conexión: {str(e)}")
                if attempt == max_retries - 1:
                    raise WooCommerceAPIError(f"No se pudo conectar a {self.store_url}")
                time.sleep(2)

            except Exception as e:
                logger.error(f"Error inesperado: {str(e)}")
                raise WooCommerceAPIError(f"Error inesperado: {str(e)}")

    # ==================== SYSTEM STATUS ====================

    def get_system_status(self) -> Dict:
        """
        Obtiene información del sistema WooCommerce.
        Útil para validar conexión y obtener metadatos.

        Returns:
            Dict con info del sistema (WC version, WP version, etc.)
        """
        return self._make_request('GET', '/system_status')

    def test_connection(self) -> bool:
        """
        Prueba la conexión con WooCommerce.

        Returns:
            True si la conexión es exitosa
        """
        try:
            self.get_system_status()
            return True
        except Exception as e:
            logger.error(f"Test de conexión fallido: {str(e)}")
            return False

    # ==================== PRODUCTS ====================

    def list_products(self, page: int = 1, per_page: int = 100, **filters) -> List[Dict]:
        """
        Lista productos con paginación.

        Args:
            page: Número de página
            per_page: Productos por página (max 100)
            **filters: Filtros adicionales (status, category, etc.)

        Returns:
            Lista de productos
        """
        params = {
            'page': page,
            'per_page': min(per_page, 100),  # Max 100
            **filters
        }
        response = self._make_request('GET', '/products', params=params)
        if isinstance(response, dict):
            if isinstance(response.get('data'), list):
                return response.get('data', [])
            if isinstance(response.get('products'), list):
                return response.get('products', [])
            return []
        return response if isinstance(response, list) else []

    def get_product(self, product_id: int) -> Dict:
        """Obtiene un producto por ID"""
        return self._make_request('GET', f'/products/{product_id}')

    def update_product(self, product_id: int, data: Dict) -> Dict:
        """Actualiza un producto (ej: stock, precio)"""
        return self._make_request('PUT', f'/products/{product_id}', data=data)

    # ==================== CATEGORIES ====================

    def list_categories(self, page: int = 1, per_page: int = 100) -> List[Dict]:
        """Lista categorías de productos"""
        params = {'page': page, 'per_page': min(per_page, 100)}
        return self._make_request('GET', '/products/categories', params=params)

    def get_category(self, category_id: int) -> Dict:
        """Obtiene una categoría por ID"""
        return self._make_request('GET', f'/products/categories/{category_id}')

    def update_category(self, category_id: int, data: Dict) -> Dict:
        """Actualiza una categoría (ej: parent)"""
        return self._make_request('PUT', f'/products/categories/{category_id}', data=data)

    # ==================== WEBHOOKS ====================

    def list_webhooks(self) -> List[Dict]:
        """Lista webhooks registrados"""
        return self._make_request('GET', '/webhooks')

    def create_webhook(self, topic: str, delivery_url: str, secret: str = None) -> Dict:
        """
        Crea un webhook.

        Args:
            topic: Evento (ej: 'product.created', 'product.updated')
            delivery_url: URL donde enviar el webhook
            secret: Secret para validar HMAC (opcional)

        Returns:
            Webhook creado
        """
        data = {
            'name': f'CLIP Comparador - {topic}',
            'topic': topic,
            'delivery_url': delivery_url,
            'status': 'active'
        }

        if secret:
            data['secret'] = secret

        return self._make_request('POST', '/webhooks', data=data)

    def delete_webhook(self, webhook_id: int) -> Dict:
        """Elimina un webhook"""
        return self._make_request('DELETE', f'/webhooks/{webhook_id}', params={'force': True})

    # ==================== STOCK ====================

    def update_stock(self, product_id: int, quantity: int, manage_stock: bool = True) -> Dict:
        """
        Actualiza stock de un producto.

        Args:
            product_id: ID del producto
            quantity: Nueva cantidad
            manage_stock: Si debe gestionar stock
        """
        data = {
            'stock_quantity': quantity,
            'manage_stock': manage_stock
        }
        return self.update_product(product_id, data)

    # ==================== ATTRIBUTES ====================

    def list_attributes(self) -> List[Dict]:
        """Lista atributos globales de productos"""
        return self._make_request('GET', '/products/attributes')

    def list_attribute_terms(self, attribute_id: int, page: int = 1, per_page: int = 100) -> List[Dict]:
        """Lista términos de un atributo global"""
        params = {'page': page, 'per_page': min(per_page, 100)}
        return self._make_request('GET', f'/products/attributes/{attribute_id}/terms', params=params)

    # ==================== HELPERS ====================

    def get_all_products(self, status: str = 'publish', **filters) -> List[Dict]:
        """
        Obtiene TODOS los productos con paginación automática.

        Args:
            status: Estado de productos ('publish', 'draft', 'any')
            **filters: Filtros adicionales

        Returns:
            Lista completa de productos
        """
        all_products = []
        page = 1
        per_page = 100

        while True:
            logger.info(f"Obteniendo productos - página {page}")
            products = self.list_products(page=page, per_page=per_page, status=status, **filters)

            if not isinstance(products, list):
                logger.error(f"Respuesta inesperada de WooCommerce (products): {type(products)}")
                break

            if not products:
                break

            all_products.extend(products)

            # Si recibimos menos de per_page, es la última página
            if len(products) < per_page:
                break

            page += 1

        logger.info(f"Total productos obtenidos: {len(all_products)}")
        return all_products

    def get_all_categories(self) -> List[Dict]:
        """Obtiene TODAS las categorías con paginación automática"""
        all_categories = []
        page = 1
        per_page = 100

        while True:
            categories = self.list_categories(page=page, per_page=per_page)

            if not categories:
                break

            all_categories.extend(categories)

            if len(categories) < per_page:
                break

            page += 1

        return all_categories
    # ---- Webhooks ----

    def create_webhook(self, name: str, topic: str, delivery_url: str, secret: str, status: str = 'active') -> Dict:
        """Crea un webhook en WooCommerce

        Args:
            name: Nombre del webhook (ej: 'CLIP - product.updated')
            topic: Topic del webhook (ej: 'product.updated')
            delivery_url: URL donde WooCommerce enviará los eventos
            secret: Secret para firmar el webhook (HMAC-SHA256)
            status: Estado del webhook ('active' o 'inactive')

        Returns:
            Respuesta de WooCommerce con el webhook creado (incluye 'id')
        """
        endpoint = "/webhooks"
        payload = {
            'name': name,
            'topic': topic,
            'delivery_url': delivery_url,
            'secret': secret,
            'status': status,
        }

        response = self._make_request('POST', endpoint, data=payload)
        logger.info(f"Webhook creado: {name} (topic: {topic})")
        return response

    def list_webhooks(self) -> List[Dict]:
        """Lista todos los webhooks de la tienda"""
        endpoint = "/webhooks"
        response = self._make_request('GET', endpoint)

        if isinstance(response, dict) and 'data' in response:
            return response.get('data', [])
        return response if isinstance(response, list) else []

    def delete_webhook(self, webhook_id: int) -> bool:
        """Elimina un webhook de WooCommerce

        Args:
            webhook_id: ID del webhook a eliminar

        Returns:
            True si se eliminó exitosamente
        """
        endpoint = f"/webhooks/{webhook_id}"
        self._make_request('DELETE', endpoint)
        logger.info(f"Webhook {webhook_id} eliminado")
        return True
