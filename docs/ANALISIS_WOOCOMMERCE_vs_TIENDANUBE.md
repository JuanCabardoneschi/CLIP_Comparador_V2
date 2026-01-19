# Análisis Comparativo: TiendaNube vs WooCommerce - Sincronización de Productos

## 📊 Hallazgos del Análisis de Credenciales WooCommerce

### Credenciales Validadas ✅
- **Store**: https://goodyshop.com.ar
- **API Version**: WooCommerce REST v3
- **Auth Method**: HTTP Basic Auth (Consumer Key + Secret)
- **Status**: TODAS las credenciales y endpoints verificados exitosamente

---

## 🏗️ ARQUITECTURA DE SINCRONIZACIÓN DE CLIENTES

### Flujo Actual en TiendaNube (Ya Implementado)
```
1. Admin conecta tienda → OAuth 2.0 redirect → Autorización en TiendaNube
2. Sistema crea cliente CLIP + integración TiendaNube
3. Background job: TiendanubeSyncService.sync_products()
   ├── GET /store_id/products (todas)
   ├── GET /store_id/products/{id}/images
   ├── Descargar imágenes → Cloudinary
   ├── Almacenar en tabla 'products' y 'images'
   ├── generate_embeddings() → CLIP embeddings
   └── calculate_category_centroids()
4. Webhooks: cambios en TiendaNube → CLIP automáticamente
```

### Flujo Propuesto para WooCommerce (A Implementar)
```
1. Admin proporciona credenciales manualmente (no OAuth)
   - Store URL: https://mitienda.com
   - Consumer Key: ck_xxxxx
   - Consumer Secret: cs_xxxxx

2. Sistema valida credenciales (POST /create del cliente)
   - GET /wp-json/wc/v3/system_status
   - Crea cliente CLIP + integración WooCommerce

3. Background job: WooCommerceSyncService.sync_products()
   ├── sync_categories()
   │  └── GET /wp-json/wc/v3/products/categories → tabla 'categories'
   ├── sync_products()
   │  ├── GET /wp-json/wc/v3/products (paginated, max 100/page)
   │  └── Almacenar en tabla 'products'
   ├── sync_product_images()
   │  ├── Para CADA producto:
   │  │  └── GET /wp-json/wc/v3/products/{id}
   │  │     └── Procesar images array
   │  └── [DECISIÓN: VER ABAJO]
   ├── generate_embeddings()
   └── calculate_category_centroids()

4. Webhooks: configurar en WooCommerce para cambios incremental
```

---

## 🖼️ ESTRATEGIA DE IMÁGENES: Comparativa

### ✅ TiendaNube - Actual (REMOTE URL SIN STORAGE DUPLICADO)

**Estructura en Respuesta API:**
```json
"images": [
  {
    "id": 456,
    "src": "https://d26lpennugtm8s.cloudfront.net/stores/001/234/products/image.jpg",
    "position": 1
  }
]
```

**Características:**
- Imágenes en CDN de TiendaNube (CloudFront)
- URLs públicas, directamente accesibles sin auth
- **No se descargan localmente para almacenamiento**
- Se usan para:
  1. Generar embeddings CLIP en tiempo de ingestión
  2. Thumbnail display en el widget/admin
- Ventaja: **Cero duplicación de datos** - TiendaNube gestiona el almacenamiento

**Implementación en Código:**
```python
# En TiendanubeSyncService._sync_product_images()
for img_data in images_data:
    source_url = img_data.get('src')  # URL pública

    # Descargar SOLO para procesar (temporal)
    base64_full, base64_thumb, ... = self._download_and_convert_image(source_url)

    # Guardar en DB:
    image = Image(
        source_url=source_url,           # GUARDAR URL
        base64_thumb=base64_thumb,       # GUARDAR thumb en base64 (para display rápido)
        # NO subir a Cloudinary
    )

# Para embeddings: usar base64_thumb directo (ya en DB)
# Para widget: usar image.display_url que devuelve source_url de TiendaNube
```

---

### 🤔 WooCommerce - Propuestas

**Estructura en Respuesta API (VERIFICADA):**
```json
"images": [
  {
    "id": 7901,
    "src": "https://goodyshop.com.ar/wp-content/uploads/2025/10/imagen.jpg",
    "name": "Nombre",
    "alt": "",
    "thumbnail": "https://goodyshop.com.ar/wp-content/uploads/2025/10/imagen-300x300.jpg"
  }
]
```

**URLs son PÚBLICAMENTE ACCESIBLES:**
- HTTP 200 en todos los tests realizados
- Content-Type: image/jpeg
- No requieren autenticación
- Hosted en servidor self-hosted del cliente

---

## 🎯 OPCIONES DE IMPLEMENTACIÓN PARA WOOCOMMERCE

### **OPCIÓN A: SEGUIR MODELO TIENDANUBE (RECOMENDADO)** ✅

**Estrategia:** Usar URLs públicas de WooCommerce sin descargar ni duplicar

```python
# En WooCommerceSyncService._sync_product_images()
for img_data in product_images:
    source_url = img_data['src']  # https://goodyshop.com.ar/wp-content/uploads/...

    # Descargar SOLO temporalmente para procesamiento
    base64_thumb = self._download_and_convert_image(source_url, thumb_only=True)

    # Guardar en DB
    image = Image(
        client_id=client.id,
        product_id=product.id,
        source_url=source_url,         # GUARDAR URL ORIGINAL
        base64_thumb=base64_thumb,     # GUARDAR THUMBNAIL EN BASE64
        hash_sha256=hash(source_url),
        is_processed=False  # Marcar para embeddings
    )
    db.session.add(image)

# Luego en generate_embeddings():
# - Usar base64_thumb (ya en DB, sin I/O externo)
# - Generar embedding CLIP
# - Guardar en image.clip_embedding

# En Widget/Admin para mostrar imagen:
# - Usar image.display_url (devuelve source_url de WooCommerce directamente)
# - O usar base64_thumb si se necesita sin conexión al servidor del cliente
```

**Ventajas:**
- ✅ CERO duplicación de almacenamiento en Railway
- ✅ Mismo patrón que TiendaNube (código reutilizable)
- ✅ Cliente mantiene control de sus imágenes
- ✅ No consumimos cuota de Cloudinary
- ✅ Rendimiento: imágenes caché en thumbnail base64

**Desventajas:**
- ⚠️ Depende de disponibilidad del servidor del cliente
- ⚠️ Si cliente offline, no puedo regenerar embeddings
- ⚠️ URLs pueden cambiar si cliente mueve imágenes

**Fallback:**
- Guardar base64_full (completa) en BD si disponibilidad es crítica

---

### **OPCIÓN B: DESCARGAR A CLOUDINARY (ALTERNATIVA)**

```python
# Descargar y subir a Cloudinary
image_bytes = download_image(source_url)
cloudinary_result = cloudinary.uploader.upload(
    image_bytes,
    folder=f"clients/{client.id}",
    public_id=f"wc_{product.id}_{idx}"
)

image = Image(
    source_url=source_url,            # GUARDAR URL ORIGINAL (backup)
    cloudinary_url=cloudinary_result['secure_url'],
    cloudinary_public_id=cloudinary_result['public_id']
)
```

**Ventajas:**
- ✅ Independencia de servidor del cliente
- ✅ Imágenes optimizadas por Cloudinary
- ✅ URL permanente

**Desventajas:**
- ❌ Costo de almacenamiento en Cloudinary
- ❌ Duplicación de datos (almacenamos copia)
- ❌ Distinto a TiendaNube (más mantenimiento)
- ❌ Rate limiting de Cloudinary

---

## 📋 SINCRONIZACIÓN DE CATEGORÍAS

### Estructura de Categorías WooCommerce (VERIFICADA)

```json
{
  "id": 91,
  "name": "Delantales",
  "slug": "delantales",
  "parent": 0,
  "description": "...",
  "count": 52
}
```

### Implementación Propuesta

```python
# En WooCommerceSyncService.sync_categories()

# GET /wp-json/wc/v3/products/categories
response = self.wc_api.list_categories()

for cat_data in response:
    category = Category.query.filter_by(
        client_id=self.client.id,
        external_id=cat_data['id']
    ).first()

    if not category:
        category = Category(
            client_id=self.client.id,
            external_id=cat_data['id'],  # ID en WooCommerce
            name=cat_data['name'],
            slug=cat_data['slug'],
            parent_external_id=cat_data.get('parent', 0)
        )
    else:
        # Actualizar
        category.name = cat_data['name']

    db.session.add(category)

db.session.commit()
```

---

## 🏷️ SINCRONIZACIÓN DE ATRIBUTOS

### Hallazgos en goodyshop.com.ar

**Estado:** La tienda WooCommerce NO tiene atributos definidos
- Total de atributos globales: 0
- Productos individuales: sin atributos asignados
- Tipo de productos: "simple" (sin variantes)

### Implementación General para WooCommerce

```python
# En WooCommerceSyncService.sync_attributes()

# 1. Obtener atributos globales del sistema
response = self.wc_api.get_attributes()

attribute_mapping = {}
for attr in response:
    # Crear o actualizar configuración
    config = ProductAttributeConfig.query.filter_by(
        client_id=self.client.id,
        key=attr['slug']
    ).first()

    if not config:
        config = ProductAttributeConfig(
            client_id=self.client.id,
            key=attr['slug'],
            label=attr['name'],
            type='list',
            options=attr.get('terms', []),  # Valores predefinidos
            field_order=attr['id']
        )

    db.session.add(config)
    attribute_mapping[attr['id']] = attr['slug']

# 2. Para productos variable: obtener variantes
for product in products_variable:
    response = self.wc_api._make_request(
        'GET',
        f'/products/{product.external_id}/variations'
    )

    for variation in response:
        # Extraer atributos de la variante
        for attr_name, attr_value in variation.get('attributes', {}).items():
            # Mapear a nuestro sistema
            pass
```

---

## 🔄 FLUJO COMPLETO PROPUESTO

### 1. **Cliente crea integración WooCommerce** (Evento: POST /clients/create)

```python
# En clip_admin_backend/app/blueprints/clients.py
# Route: POST /create
# Cliente elige: integration_type = 'woocommerce'
# Form fields: store_url, consumer_key, consumer_secret

# Validación:
WooCommerceAPIClient(store_url, ck, cs).test_connection()

# Guardar:
integration = WooCommerceIntegration(
    client_id=client.id,
    store_url=store_url,
    consumer_key_encrypted=encrypt(ck),
    consumer_secret_encrypted=encrypt(cs),
    is_active=True
)
db.session.add(integration)
db.session.commit()

# Encolar job asincrónico
queue_sync_job(client.id, 'woocommerce_full_sync')
```

### 2. **Background Job: WooCommerceSyncService** (Asincrónico)

```python
# En clip_admin_backend/app/services/woocommerce_sync_service.py

class WooCommerceSyncService:
    def __init__(self, client):
        self.client = client
        self.integration = WooCommerceIntegration.query.filter_by(
            client_id=client.id, is_active=True
        ).first()
        self.wc_api = WooCommerceAPIClient(
            self.integration.store_url,
            self.integration.get_consumer_key(),
            self.integration.get_consumer_secret()
        )

    def full_sync(self):
        """Sincronización inicial completa."""
        logger.info(f"Iniciando sync para cliente {self.client.id}")

        try:
            # 1. Sincronizar categorías
            self.sync_categories()
            logger.info("✅ Categorías sincronizadas")

            # 2. Sincronizar productos
            self.sync_products()
            logger.info("✅ Productos sincronizados")

            # 3. Procesar imágenes
            self.sync_product_images()
            logger.info("✅ Imágenes procesadas")

            # 4. Generar embeddings
            self.generate_embeddings()
            logger.info("✅ Embeddings generados")

            # 5. Calcular centroides de categorías
            self.calculate_category_centroids()
            logger.info("✅ Centroides calculados")

            # Marcar como completado
            self.integration.sync_status = 'completed'
            self.integration.last_sync_at = datetime.utcnow()
            db.session.commit()

        except Exception as e:
            logger.error(f"❌ Error en sync: {str(e)}")
            self.integration.sync_status = 'error'
            self.integration.sync_error = str(e)
            db.session.commit()
            raise

    def sync_categories(self):
        """Sincronizar categorías de WooCommerce."""
        # Implementación similar a TiendaNube
        pass

    def sync_products(self):
        """Sincronizar productos."""
        # Paginación max 100 por página
        pass

    def sync_product_images(self):
        """Procesar imágenes - OPCIÓN A (Remote URLs)."""
        # Usar source_url de WooCommerce
        # Descargar solo para base64_thumb
        pass

    def generate_embeddings(self):
        """Generar embeddings CLIP."""
        # Mismo código que TiendaNube
        pass

    def calculate_category_centroids(self):
        """Calcular centroides."""
        # Mismo código que TiendaNube
        pass
```

### 3. **Webhooks (Sincronización Incremental)**

```python
# En /wp-json/wc/v3/webhooks
POST /wp-json/wc/v3/webhooks
{
    "name": "CLIP - Producto Creado",
    "topic": "product.created",
    "delivery_url": "https://clip-comparadorv2-production.up.railway.app/api/webhooks/woocommerce/product_created",
    "active": true
}

# En app/blueprints/webhooks.py
@bp.route('/woocommerce/product_created', methods=['POST'])
def woocommerce_product_created():
    """Webhook cuando se crea producto en WooCommerce."""
    payload = request.get_json()

    # Validar webhook (opcional pero recomendado)
    signature = request.headers.get('X-WC-Webhook-Signature')
    # ... validación ...

    # Obtener datos
    wc_product_id = payload['id']
    store_url = payload['_links']['self'][0]['href'].split('/wp-json/')[0]

    # Encontrar integración
    integration = WooCommerceIntegration.query.filter_by(
        store_url=store_url
    ).first()

    if integration:
        # Encolar job: descargar producto específico
        queue_sync_job(integration.client_id, 'woocommerce_sync_product', wc_product_id)
```

---

## 📊 TABLA COMPARATIVA FINAL

| Aspecto | TiendaNube | WooCommerce |
|---------|-----------|------------|
| **Autenticación** | OAuth 2.0 (centralizado) | HTTP Basic Auth (manual) |
| **Instalación** | App Store → Auto-config | Manual form → Usuario proporciona keys |
| **Imágenes** | CDN público (CloudFront) | Servidor del cliente (WordPress host) |
| **Acceso a URLs** | Públicas, sin auth | Públicas, sin auth |
| **Estrategia Propuesta** | REMOTE URLS (sin Cloudinary) | REMOTE URLS (sin Cloudinary) |
| **Categorías** | Sí, GET /categories | Sí, GET /products/categories |
| **Atributos** | Sí, en variantes | Condicional (este cliente no tiene) |
| **Webhooks** | Automáticos | Manuales o API |
| **Stock** | En variantes | stock_quantity en producto |
| **Paginación** | `page`/`per_page` | `page`/`per_page` (max 100) |
| **Almacenamiento** | Min (solo base64_thumb) | Min (mismo que TiendaNube) |
| **Duplicación** | NO | NO (si usamos OPCIÓN A) |

---

## 🎯 RECOMENDACIÓN FINAL

### **Implementar WooCommerce con OPCIÓN A (Remote URLs)**

Razones:
1. ✅ **Parity con TiendaNube** - Código casi idéntico
2. ✅ **Zero storage waste** - No duplicamos imágenes
3. ✅ **Cost effective** - Sin gasto en Cloudinary
4. ✅ **Escalable** - Same pattern para otros e-commerce (Shopify, etc.)
5. ✅ **Simple** - Menos complejidad de código

---

## 📝 Próximos Pasos Inmediatos

1. **Crear `WooCommerceAPIClient` method** para obtener categorías/atributos
   - ✅ Ya existe (listar productos, categorías)

2. **Crear `WooCommerceSyncService` class**
   - Copiar estructura de `TiendanubeSyncService`
   - Adaptar endpoints

3. **Crear `WooCommerceIntegration` model**
   - ✅ Ya existe en Railway DB

4. **Integrar en flujo de cliente creation**
   - ✅ Formulario ya existe

5. **Registrar webhooks automáticamente** (opcional en v1)

6. **Tests end-to-end** con goodyshop.com.ar

---

**Documento generado:** Análisis de API WooCommerce con credenciales verificadas en https://goodyshop.com.ar

