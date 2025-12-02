# Arquitectura Unificada - Standalone + Tiendanube

## 📊 Decisiones de Arquitectura

### 1. ✅ Sistema Unificado (NO versiones separadas)

**Razón**: Un solo codebase, un deployment, mantenimiento centralizado, fácil agregar nuevas integraciones.

### 2. ✅ Tiendanube como Fuente de Verdad (Source of Truth)

**Razón**: Flujo unidireccional previene conflictos, simplifica UX, reduce bugs de sincronización.

---

## 🏗️ Modelo de Datos Extendido

### Extensión de la tabla `clients`

```sql
-- Agregar campos de integración
ALTER TABLE clients ADD COLUMN integration_type VARCHAR(50) DEFAULT 'standalone';
-- Valores: 'standalone', 'tiendanube', 'shopify', 'woocommerce'

ALTER TABLE clients ADD COLUMN integration_config JSONB DEFAULT '{}';
-- Estructura para Tiendanube:
-- {
--   "store_id": "7019043",
--   "store_name": "Test Clip",
--   "store_domain": "test-clip-1.mitiendanube.com",
--   "access_token_encrypted": "xxx",  // Encriptado con AES-256
--   "scopes": ["read_products", "write_scripts"],
--   "script_id": 12345,
--   "installed_at": "2025-12-02T10:30:00Z",
--   "last_sync_at": "2025-12-02T15:45:00Z"
-- }

ALTER TABLE clients ADD COLUMN is_read_only BOOLEAN DEFAULT FALSE;
-- TRUE para integraciones (Tiendanube), FALSE para standalone

ALTER TABLE clients ADD COLUMN plan VARCHAR(50) DEFAULT 'starter';
-- 'starter', 'professional', 'business', 'enterprise'

ALTER TABLE clients ADD COLUMN search_limit INTEGER DEFAULT 500;
-- Límite de búsquedas por mes según plan

-- Índices para performance
CREATE INDEX idx_clients_integration_type ON clients(integration_type);
CREATE INDEX idx_clients_read_only ON clients(is_read_only);
```

### Extensión de la tabla `products`

```sql
-- Agregar referencias a sistemas externos
ALTER TABLE products ADD COLUMN external_id VARCHAR(100);
-- Para Tiendanube: el product_id
-- Para Shopify: el product_id
-- NULL para standalone

ALTER TABLE products ADD COLUMN external_variant_id VARCHAR(100);
-- ID de la variante en el sistema externo

ALTER TABLE products ADD COLUMN external_url TEXT;
-- URL del producto en la tienda externa

ALTER TABLE products ADD COLUMN last_sync_at TIMESTAMP;
-- Última sincronización desde sistema externo

ALTER TABLE products ADD COLUMN sync_status VARCHAR(50) DEFAULT 'synced';
-- 'synced', 'pending', 'error', 'deleted_external'

-- Índices
CREATE INDEX idx_products_external_id ON products(external_id);
CREATE INDEX idx_products_sync_status ON products(sync_status);
```

### Extensión de la tabla `categories`

```sql
ALTER TABLE categories ADD COLUMN external_id VARCHAR(100);
ALTER TABLE categories ADD COLUMN last_sync_at TIMESTAMP;
ALTER TABLE categories ADD COLUMN sync_status VARCHAR(50) DEFAULT 'synced';

CREATE INDEX idx_categories_external_id ON categories(external_id);
```

### Nueva tabla: `sync_logs`

```sql
CREATE TABLE sync_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id VARCHAR(36) NOT NULL REFERENCES clients(id),
    sync_type VARCHAR(50) NOT NULL,  -- 'full', 'incremental', 'webhook'
    entity_type VARCHAR(50),  -- 'product', 'category', 'image'
    entity_id VARCHAR(100),  -- external_id
    action VARCHAR(50),  -- 'create', 'update', 'delete'
    status VARCHAR(50) NOT NULL,  -- 'success', 'error', 'skipped'
    error_message TEXT,
    metadata JSONB,  -- Datos adicionales del sync
    duration_ms INTEGER,  -- Tiempo que tomó la operación
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_sync_logs_client ON sync_logs(client_id);
CREATE INDEX idx_sync_logs_created_at ON sync_logs(created_at);
CREATE INDEX idx_sync_logs_status ON sync_logs(status);
```

---

## 🔒 Control de Permisos por Tipo de Integración

### Clase de permisos en el modelo Client

```python
# clip_admin_backend/app/models/client.py

class Client(db.Model):
    # ... campos existentes ...

    integration_type = db.Column(db.String(50), default='standalone')
    integration_config = db.Column(db.JSON, default={})
    is_read_only = db.Column(db.Boolean, default=False)
    plan = db.Column(db.String(50), default='starter')
    search_limit = db.Column(db.Integer, default=500)

    @property
    def can_create_products(self):
        """Puede crear productos desde nuestro panel"""
        return self.integration_type == 'standalone'

    @property
    def can_edit_products(self):
        """Puede editar productos desde nuestro panel"""
        return self.integration_type == 'standalone'

    @property
    def can_delete_products(self):
        """Puede eliminar productos desde nuestro panel"""
        return self.integration_type == 'standalone'

    @property
    def can_create_categories(self):
        """Puede crear categorías desde nuestro panel"""
        return self.integration_type == 'standalone'

    @property
    def can_edit_categories(self):
        """Puede editar categorías desde nuestro panel"""
        return self.integration_type == 'standalone'

    @property
    def can_delete_categories(self):
        """Puede eliminar categorías desde nuestro panel"""
        return self.integration_type == 'standalone'

    @property
    def can_manage_clip_settings(self):
        """Puede gestionar configuración CLIP (prompts, umbrales, etc)"""
        return True  # Todos pueden

    @property
    def can_regenerate_embeddings(self):
        """Puede regenerar embeddings manualmente"""
        return True  # Todos pueden

    @property
    def can_view_analytics(self):
        """Puede ver analytics de búsquedas"""
        return True  # Todos pueden

    @property
    def is_tiendanube(self):
        """Es una integración de Tiendanube"""
        return self.integration_type == 'tiendanube'

    @property
    def tiendanube_store_id(self):
        """Obtener store_id de Tiendanube si aplica"""
        if self.is_tiendanube:
            return self.integration_config.get('store_id')
        return None

    @property
    def tiendanube_access_token(self):
        """Obtener access token desencriptado de Tiendanube"""
        if self.is_tiendanube:
            encrypted = self.integration_config.get('access_token_encrypted')
            if encrypted:
                from app.utils.encryption import decrypt_token
                return decrypt_token(encrypted)
        return None
```

---

## 🎨 UI Adaptativa según Tipo de Cliente

### Template Jinja2 con permisos

```html
<!-- clip_admin_backend/app/templates/products/list.html -->

{% extends "base.html" %}

{% block content %}
<div class="container">
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h2>
            Productos
            {% if client.is_tiendanube %}
                <span class="badge bg-info">Sincronizado con Tiendanube</span>
            {% endif %}
        </h2>

        {% if client.can_create_products %}
            <a href="{{ url_for('products.create') }}" class="btn btn-primary">
                <i class="bi bi-plus-circle"></i> Nuevo Producto
            </a>
        {% else %}
            <div class="alert alert-info mb-0">
                <i class="bi bi-info-circle"></i>
                Los productos se gestionan en
                <a href="https://{{ client.integration_config.store_domain }}/admin/products"
                   target="_blank">
                    Tiendanube <i class="bi bi-box-arrow-up-right"></i>
                </a>
            </div>
        {% endif %}
    </div>

    <!-- Filtros y búsqueda -->
    <div class="card mb-4">
        <div class="card-body">
            <!-- ... filtros ... -->

            {% if client.is_tiendanube %}
                <button class="btn btn-outline-primary" onclick="syncFromTiendanube()">
                    <i class="bi bi-arrow-repeat"></i> Sincronizar ahora
                </button>
                <small class="text-muted ms-2">
                    Última sync: {{ client.integration_config.last_sync_at|default('Nunca')|format_datetime }}
                </small>
            {% endif %}
        </div>
    </div>

    <!-- Tabla de productos -->
    <div class="table-responsive">
        <table class="table table-hover">
            <thead>
                <tr>
                    <th>Imagen</th>
                    <th>Nombre</th>
                    <th>SKU</th>
                    <th>Categoría</th>
                    <th>Precio</th>
                    <th>Stock</th>
                    <th>Estado</th>
                    {% if client.is_tiendanube %}
                        <th>Sync Status</th>
                    {% endif %}
                    <th>Acciones</th>
                </tr>
            </thead>
            <tbody>
                {% for product in products %}
                <tr>
                    <td>
                        {% if product.primary_image %}
                            <img src="{{ product.primary_image.thumbnail_url }}"
                                 alt="{{ product.name }}"
                                 class="product-thumbnail">
                        {% endif %}
                    </td>
                    <td>
                        {{ product.name }}
                        {% if product.external_url %}
                            <a href="{{ product.external_url }}" target="_blank"
                               class="text-muted ms-1" title="Ver en Tiendanube">
                                <i class="bi bi-box-arrow-up-right"></i>
                            </a>
                        {% endif %}
                    </td>
                    <td>{{ product.sku }}</td>
                    <td>{{ product.category.name if product.category else '-' }}</td>
                    <td>${{ product.price|format_price }}</td>
                    <td>{{ product.stock }}</td>
                    <td>
                        <span class="badge bg-{{ 'success' if product.is_active else 'secondary' }}">
                            {{ 'Activo' if product.is_active else 'Inactivo' }}
                        </span>
                    </td>
                    {% if client.is_tiendanube %}
                        <td>
                            {% if product.sync_status == 'synced' %}
                                <i class="bi bi-check-circle text-success"></i>
                            {% elif product.sync_status == 'pending' %}
                                <i class="bi bi-clock text-warning"></i>
                            {% elif product.sync_status == 'error' %}
                                <i class="bi bi-exclamation-circle text-danger"></i>
                            {% endif %}
                        </td>
                    {% endif %}
                    <td>
                        <a href="{{ url_for('products.view', id=product.id) }}"
                           class="btn btn-sm btn-outline-primary">
                            Ver
                        </a>

                        {% if client.can_edit_products %}
                            <a href="{{ url_for('products.edit', id=product.id) }}"
                               class="btn btn-sm btn-outline-secondary">
                                Editar
                            </a>
                        {% else %}
                            <!-- Mostrar botón deshabilitado con tooltip -->
                            <button class="btn btn-sm btn-outline-secondary"
                                    disabled
                                    data-bs-toggle="tooltip"
                                    title="Editar en Tiendanube">
                                Editar
                            </button>
                        {% endif %}

                        {% if client.can_delete_products %}
                            <button class="btn btn-sm btn-outline-danger"
                                    onclick="deleteProduct('{{ product.id }}')">
                                Eliminar
                            </button>
                        {% endif %}

                        <!-- Acciones siempre disponibles -->
                        <button class="btn btn-sm btn-outline-info"
                                onclick="regenerateEmbeddings('{{ product.id }}')">
                            <i class="bi bi-arrow-repeat"></i> Regenerar Embeddings
                        </button>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>
{% endblock %}

{% block scripts %}
<script>
function syncFromTiendanube() {
    if (!confirm('¿Sincronizar productos desde Tiendanube? Esto puede tomar varios minutos.')) {
        return;
    }

    fetch('/api/sync/tiendanube/full', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'}
    })
    .then(res => res.json())
    .then(data => {
        if (data.status === 'started') {
            showSyncProgress(data.job_id);
        }
    });
}

function showSyncProgress(jobId) {
    // Implementar WebSocket o polling para mostrar progreso
    // Similar a lo que hicimos en migrate_eve_to_tiendanube.py
}

function regenerateEmbeddings(productId) {
    if (!confirm('¿Regenerar embeddings para este producto?')) return;

    fetch(`/api/products/${productId}/regenerate-embeddings`, {
        method: 'POST'
    })
    .then(res => res.json())
    .then(data => {
        alert(data.message);
        location.reload();
    });
}
</script>
{% endblock %}
```

---

## 🔄 Flujo de Sincronización

### Diagrama de Flujo Unidireccional

```
TIENDANUBE                          CLIP BACKEND
────────────                        ────────────

1. Merchant crea producto
   │
   │ webhook: product/created
   ├──────────────────────────────> 2. Recibir webhook
   │                                    ├─ Verificar HMAC
   │                                    ├─ Validar client activo
   │                                    ├─ Queue job en background
   │                                    └─ Responder 200 OK
   │
   │                                 3. Job procesa en background:
   │                                    ├─ GET /products/{id} desde Tiendanube
   │                                    ├─ Crear product en nuestra DB
   │                                    ├─ Descargar imágenes
   │                                    ├─ Upload a Cloudinary
   │                                    ├─ Generar embeddings CLIP
   │                                    ├─ Actualizar centroide de categoría
   │                                    └─ Log de sincronización
   │
   │                                 4. Producto disponible para búsqueda

IMPORTANTE: No hay flujo inverso (CLIP → Tiendanube)
            Nuestro sistema es READ-ONLY desde webhooks
```

### Código del webhook handler

```python
# clip_admin_backend/app/blueprints/webhooks_tiendanube.py

from flask import Blueprint, request, jsonify
from app.models import Client, Product, Category, Image
from app.services.tiendanube_sync import TiendanubeSync
from app.utils.encryption import verify_hmac
from app.utils.queue import queue_job
import logging

bp = Blueprint('webhooks_tiendanube', __name__, url_prefix='/webhooks/tiendanube')
logger = logging.getLogger(__name__)

@bp.route('/', methods=['POST'])
def handle_webhook():
    """
    Endpoint principal para recibir webhooks de Tiendanube

    Payload esperado:
    {
        "store_id": "123456",
        "event": "product/created",
        "id": 789  // ID del recurso afectado
    }
    """

    # 1. Verificar firma HMAC
    if not verify_hmac(request):
        logger.warning(f"Invalid HMAC signature from {request.remote_addr}")
        return jsonify({'error': 'Invalid signature'}), 401

    payload = request.json
    store_id = payload.get('store_id')
    event = payload.get('event')
    resource_id = payload.get('id')

    logger.info(f"Received webhook: {event} for store {store_id}, resource {resource_id}")

    # 2. Obtener client por store_id
    client = Client.query.filter_by(
        integration_type='tiendanube'
    ).filter(
        Client.integration_config['store_id'].astext == str(store_id)
    ).first()

    if not client:
        logger.error(f"Client not found for store_id {store_id}")
        return jsonify({'error': 'Client not found'}), 404

    if not client.is_active:
        logger.warning(f"Client {client.id} is inactive, ignoring webhook")
        return jsonify({'status': 'ignored', 'reason': 'client_inactive'}), 200

    # 3. Encolar job en background (responder rápido a Tiendanube)
    job_id = queue_job('process_tiendanube_webhook', {
        'client_id': client.id,
        'event': event,
        'resource_id': resource_id,
        'payload': payload
    })

    logger.info(f"Queued webhook job {job_id} for client {client.id}")

    return jsonify({'status': 'queued', 'job_id': job_id}), 200


# Handlers específicos por tipo de evento (ejecutados en background)

def process_product_created(client, resource_id, payload):
    """Handler para product/created"""
    sync_service = TiendanubeSync(client)

    try:
        # 1. Obtener detalles del producto desde Tiendanube API
        product_data = sync_service.get_product(resource_id)

        # 2. Crear producto en nuestra DB
        product = sync_service.create_product_from_data(product_data)

        # 3. Descargar y procesar imágenes
        sync_service.sync_product_images(product, product_data['images'])

        # 4. Generar embeddings
        sync_service.generate_product_embeddings(product)

        # 5. Recalcular centroide de categoría
        if product.category_id:
            sync_service.recalculate_category_centroid(product.category_id)

        # 6. Log de éxito
        sync_service.log_sync('product', resource_id, 'create', 'success')

        logger.info(f"Product {resource_id} created successfully for client {client.id}")
        return {'status': 'success', 'product_id': product.id}

    except Exception as e:
        logger.error(f"Error creating product {resource_id}: {str(e)}")
        sync_service.log_sync('product', resource_id, 'create', 'error', str(e))
        raise


def process_product_updated(client, resource_id, payload):
    """Handler para product/updated"""
    sync_service = TiendanubeSync(client)

    try:
        # 1. Buscar producto existente por external_id
        product = Product.query.filter_by(
            client_id=client.id,
            external_id=str(resource_id)
        ).first()

        if not product:
            logger.warning(f"Product {resource_id} not found, creating new")
            return process_product_created(client, resource_id, payload)

        # 2. Obtener datos actualizados desde Tiendanube
        product_data = sync_service.get_product(resource_id)

        # 3. Actualizar campos básicos (NO editables desde nuestro panel)
        sync_service.update_product_from_data(product, product_data)

        # 4. Verificar si cambiaron las imágenes
        if sync_service.images_changed(product, product_data['images']):
            # Re-descargar imágenes y regenerar embeddings
            sync_service.sync_product_images(product, product_data['images'], replace=True)
            sync_service.generate_product_embeddings(product)

            # Recalcular centroide
            if product.category_id:
                sync_service.recalculate_category_centroid(product.category_id)

        sync_service.log_sync('product', resource_id, 'update', 'success')

        logger.info(f"Product {resource_id} updated successfully")
        return {'status': 'success', 'product_id': product.id}

    except Exception as e:
        logger.error(f"Error updating product {resource_id}: {str(e)}")
        sync_service.log_sync('product', resource_id, 'update', 'error', str(e))
        raise


def process_product_deleted(client, resource_id, payload):
    """Handler para product/deleted"""
    try:
        product = Product.query.filter_by(
            client_id=client.id,
            external_id=str(resource_id)
        ).first()

        if product:
            # Soft delete
            product.is_active = False
            product.sync_status = 'deleted_external'
            product.updated_at = datetime.utcnow()
            db.session.commit()

            # Recalcular centroide
            if product.category_id:
                sync_service = TiendanubeSync(client)
                sync_service.recalculate_category_centroid(product.category_id)

            logger.info(f"Product {resource_id} soft-deleted")

        return {'status': 'success'}

    except Exception as e:
        logger.error(f"Error deleting product {resource_id}: {str(e)}")
        raise
```

---

## 🚫 Prevención de Ediciones en Clientes Tiendanube

### Decorador para proteger endpoints

```python
# clip_admin_backend/app/utils/decorators.py

from functools import wraps
from flask import abort, flash, redirect, url_for
from flask_login import current_user

def standalone_only(f):
    """
    Decorador que solo permite acceso a clientes standalone.
    Previene que clientes de Tiendanube creen/editen/eliminen productos/categorías.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        client = current_user.client

        if client.integration_type != 'standalone':
            flash('Esta acción no está disponible para integraciones externas. '
                  'Gestiona tus productos desde Tiendanube.', 'warning')
            return redirect(url_for('products.list'))

        return f(*args, **kwargs)
    return decorated_function


def can_edit_products(f):
    """Decorador que verifica permiso de edición de productos"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        client = current_user.client

        if not client.can_edit_products:
            abort(403)

        return f(*args, **kwargs)
    return decorated_function
```

### Uso en blueprints

```python
# clip_admin_backend/app/blueprints/products.py

from app.utils.decorators import standalone_only, can_edit_products

@bp.route('/create', methods=['GET', 'POST'])
@login_required
@standalone_only  # Solo clientes standalone
def create():
    """Crear nuevo producto (solo standalone)"""
    # ... código de creación ...
    pass


@bp.route('/<product_id>/edit', methods=['GET', 'POST'])
@login_required
@can_edit_products  # Verifica permisos
def edit(product_id):
    """Editar producto existente"""
    # ... código de edición ...
    pass


@bp.route('/<product_id>/delete', methods=['POST'])
@login_required
@standalone_only
def delete(product_id):
    """Eliminar producto (solo standalone)"""
    # ... código de eliminación ...
    pass


@bp.route('/<product_id>/regenerate-embeddings', methods=['POST'])
@login_required
# NO tiene restricción - todos pueden regenerar embeddings
def regenerate_embeddings(product_id):
    """Regenerar embeddings CLIP para un producto"""
    # ... código de regeneración ...
    pass
```

---

## 📊 Dashboard Diferenciado

### Métricas según tipo de integración

```python
# clip_admin_backend/app/blueprints/dashboard.py

@bp.route('/')
@login_required
def index():
    client = current_user.client

    # Métricas comunes para todos
    stats = {
        'total_products': Product.query.filter_by(
            client_id=client.id,
            is_active=True
        ).count(),
        'total_categories': Category.query.filter_by(
            client_id=client.id
        ).count(),
        'total_searches': get_search_count(client.id),
        'embeddings_generated': get_embeddings_count(client.id),
    }

    # Métricas específicas para Tiendanube
    if client.is_tiendanube:
        stats['sync_status'] = get_sync_status(client.id)
        stats['last_sync'] = client.integration_config.get('last_sync_at')
        stats['products_pending_sync'] = Product.query.filter_by(
            client_id=client.id,
            sync_status='pending'
        ).count()
        stats['sync_errors'] = get_recent_sync_errors(client.id)

    return render_template('dashboard.html',
                         client=client,
                         stats=stats)
```

---

## ✅ Resumen de Decisiones

### ✅ Sistema Unificado
- **1 codebase** para standalone + Tiendanube + futuras integraciones
- **1 deployment** en Railway
- **1 base de datos** con campos adicionales
- Más fácil de mantener y escalar

### ✅ Flujo Unidireccional
- **Tiendanube → CLIP Backend** (vía webhooks)
- **NO** CLIP Backend → Tiendanube
- Cliente gestiona productos en Tiendanube
- Nuestro panel es **read-only** para datos de productos/categorías
- Nuestro panel **SÍ permite** gestionar configuración CLIP

### ✅ Permisos Granulares
```python
Standalone:
  ✅ Crear/Editar/Eliminar productos
  ✅ Crear/Editar/Eliminar categorías
  ✅ Gestionar configuración CLIP
  ✅ Ver analytics

Tiendanube:
  ❌ Crear/Editar/Eliminar productos (solo desde Tiendanube)
  ❌ Crear/Editar/Eliminar categorías (solo desde Tiendanube)
  ✅ Gestionar configuración CLIP
  ✅ Regenerar embeddings
  ✅ Ver analytics
  ✅ Sincronización manual
```

### ✅ UX Clara
- Badge visible "Sincronizado con Tiendanube"
- Botones deshabilitados con tooltips explicativos
- Link directo a admin de Tiendanube para ediciones
- Botón de "Sincronizar ahora" manual

---

## 🎯 Próximo Paso: Implementación

Con esta arquitectura definida, podemos proceder a:

1. **Crear migración de base de datos** con nuevos campos
2. **Extender modelo Client** con propiedades de permisos
3. **Crear servicio TiendanubeSync** para sincronización
4. **Implementar webhooks handler** con seguridad HMAC
5. **Adaptar templates** para mostrar/ocultar según permisos
6. **Agregar decoradores** de protección en blueprints

¿Procedemos con la implementación de la Fase 1 (OAuth + infraestructura base)?
