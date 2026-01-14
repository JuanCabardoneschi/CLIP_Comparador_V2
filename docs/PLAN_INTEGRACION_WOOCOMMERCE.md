# Plan de Integración WooCommerce para CLIP Comparador V2

## 📋 Análisis Comparativo: Tiendanube vs WooCommerce

### Tiendanube (Implementación Actual)
- **Arquitectura**: SaaS cerrado con OAuth 2.0
- **Autenticación**: Client ID + Client Secret → Access Token
- **API Base**: `https://api.tiendanube.com/v1`
- **Webhooks**: Registro automático vía API
- **Widget**: Inyección vía Script Tag API
- **Modelo**: Multi-tenant con `store_id` único

### WooCommerce (A Implementar)
- **Arquitectura**: Plugin open-source para WordPress
- **Autenticación**: Consumer Key + Consumer Secret (OAuth 1.0a o HTTP Basic Auth)
- **API Base**: `https://tudominio.com/wp-json/wc/v3`
- **Webhooks**: Configuración manual o vía API
- **Widget**: Plugin personalizado o código en theme
- **Modelo**: Self-hosted (cada tienda tiene su propio dominio)

---

## 🔑 Diferencias Clave

### 1. **Autenticación**
| Aspecto | Tiendanube | WooCommerce |
|---------|------------|-------------|
| Método | OAuth 2.0 centralizado | REST API con Consumer Keys |
| Flujo | 3-legged OAuth | Credenciales por tienda |
| Tokens | Access Token renovable | Consumer Key + Secret permanente |
| Seguridad | HMAC-SHA256 para webhooks | Signature OAuth 1.0a opcional |

### 2. **Instalación**
| Aspecto | Tiendanube | WooCommerce |
|---------|------------|-------------|
| Proceso | App Store → OAuth → Auto-install | Manual por tienda |
| Widget | Script API automático | Plugin o shortcode manual |
| Configuración | Centralizada en nuestra app | Por tienda individual |

### 3. **Sincronización de Datos**
| Aspecto | Tiendanube | WooCommerce |
|---------|------------|-------------|
| API Endpoint | `/store_id/products` | `/products` |
| Paginación | `page` + `per_page` | `page` + `per_page` |
| Imágenes | URLs directas | URLs en `images[].src` |
| Categorías | `/categories` | `/products/categories` |
| Webhooks | Push automático | Push con validación |

---

## 📐 Arquitectura Propuesta para WooCommerce

### Modelo de Base de Datos

```python
class WooCommerceIntegration(db.Model):
    """
    Similar a TiendanubeIntegration pero adaptado a WooCommerce
    """
    __tablename__ = 'woocommerce_integrations'

    id = db.Column(db.String(36), primary_key=True)
    client_id = db.Column(db.String(36), db.ForeignKey('clients.id'))

    # Datos de la tienda WooCommerce
    store_url = db.Column(db.String(500), nullable=False, unique=True)  # https://mitienda.com
    store_name = db.Column(db.String(255))

    # Credenciales REST API (encriptadas)
    consumer_key = db.Column(db.Text, nullable=False)
    consumer_secret = db.Column(db.Text, nullable=False)

    # Webhooks configurados
    webhook_ids = db.Column(JSONB, nullable=True)
    webhook_secret = db.Column(db.String(100))  # Para validar webhooks

    # Estado y sincronización
    is_active = db.Column(db.Boolean, default=True)
    api_version = db.Column(db.String(10), default='v3')
    installed_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_sync_at = db.Column(db.DateTime)
    sync_status = db.Column(db.String(50))

    # Relaciones
    client = db.relationship('Client', backref='woocommerce_integrations')
```

### Flujo de Instalación

```
┌─────────────────────────────────────────────────────┐
│ 1. Administrador de tienda WooCommerce              │
│    - Accede a panel admin de CLIP Comparador       │
│    - Click en "Conectar WooCommerce"                │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│ 2. Formulario de Conexión                           │
│    - URL de tienda: https://mitienda.com            │
│    - Consumer Key: ck_xxxxxxxxxxxxx                │
│    - Consumer Secret: cs_xxxxxxxxxxxxx              │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│ 3. Validación y Test de Conexión                    │
│    GET /wp-json/wc/v3/system_status                │
│    - Verifica credenciales                          │
│    - Obtiene info de tienda                         │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│ 4. Crear Cliente + Integración                      │
│    - Generar API key para widget                    │
│    - Guardar credenciales encriptadas               │
│    - Marcar integration_type='woocommerce'          │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│ 5. Registrar Webhooks (Opcional/Automático)         │
│    POST /wp-json/wc/v3/webhooks                    │
│    - product.created, product.updated, etc.         │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│ 6. Proporcionar Instrucciones de Widget             │
│    - Plugin WordPress (recomendado)                 │
│    - Shortcode manual                               │
│    - Código JavaScript para theme                   │
└─────────────────────────────────────────────────────┘
```

---

## 🛠️ Componentes a Desarrollar

### 1. **Modelo de Datos**
```
📁 clip_admin_backend/app/models/
  └── woocommerce_integration.py  ← NUEVO
```

### 2. **Blueprints (Rutas)**
```
📁 clip_admin_backend/app/blueprints/
  ├── woocommerce_setup.py       ← NUEVO: Formulario de conexión
  ├── woocommerce_webhooks.py    ← NUEVO: Receptor de webhooks
  └── woocommerce_admin.py       ← NUEVO: Panel de administración
```

### 3. **Servicios**
```
📁 clip_admin_backend/app/services/
  └── woocommerce_sync_service.py  ← NUEVO: Sincronización de datos
```

### 4. **Templates**
```
📁 clip_admin_backend/app/templates/woocommerce/
  ├── connect_form.html           ← Formulario de conexión
  ├── dashboard.html              ← Estado de integración
  └── widget_instructions.html    ← Guía de instalación del widget
```

### 5. **Plugin WordPress (Opcional)**
```
📁 woocommerce-plugin/
  ├── clip-comparador-widget.php     ← Plugin principal
  ├── assets/
  │   ├── js/widget-loader.js
  │   └── css/widget-styles.css
  └── readme.txt
```

---

## 📝 Plan de Acción Detallado

### FASE 1: Infraestructura Base (2-3 días)

#### 1.1 Modelo de Base de Datos
- [ ] Crear `woocommerce_integration.py`
- [ ] Migración de base de datos (añadir tabla)
- [ ] Actualizar modelo `Client` para soportar `integration_type='woocommerce'`
- [ ] Funciones de encriptación/desencriptación para credenciales

#### 1.2 Servicio de Conexión
- [ ] `WooCommerceAPIClient` class
  - Autenticación HTTP Basic Auth
  - Rate limiting handling
  - Error handling
- [ ] Método `test_connection()` para validar credenciales
- [ ] Método `get_store_info()` para obtener datos de la tienda

### FASE 2: Sincronización de Datos (3-4 días)

#### 2.1 WooCommerceSyncService
- [ ] `sync_categories()` - GET `/products/categories`
- [ ] `sync_products()` - GET `/products` con paginación
- [ ] `sync_product_images()` - Descargar y procesar imágenes
- [ ] `sync_stock()` - Actualizar inventario
- [ ] `sync_attributes()` - Mapear atributos de productos

#### 2.2 Procesamiento de Imágenes
- [ ] Adaptar pipeline de descarga de imágenes
- [ ] Generar embeddings CLIP para productos WooCommerce
- [ ] Calcular centroides de categorías

### FASE 3: Webhooks (2-3 días)

#### 3.1 Registro de Webhooks
- [ ] `register_webhooks()` vía API de WooCommerce
- [ ] Eventos a escuchar:
  - `product.created`
  - `product.updated`
  - `product.deleted`
  - `product.restored`

#### 3.2 Receptor de Webhooks
- [ ] Blueprint `woocommerce_webhooks.py`
- [ ] Validación de firma webhook (HMAC-SHA256)
- [ ] Procesamiento asíncrono de eventos
- [ ] Actualización incremental de productos

### FASE 4: Panel de Administración (2 días)

#### 4.1 Formulario de Conexión
- [ ] Template `connect_form.html`
- [ ] Validación de URL y credenciales
- [ ] Test de conexión en tiempo real (AJAX)

#### 4.2 Dashboard de Integración
- [ ] Estado de sincronización
- [ ] Últimas actualizaciones
- [ ] Estadísticas de productos/categorías
- [ ] Botones de acción (resincronizar, desconectar)

### FASE 5: Widget e Instrucciones (2-3 días)

#### 5.1 Documentación de Widget
- [ ] Guía de instalación paso a paso
- [ ] 3 métodos de integración:
  1. **Plugin WordPress** (recomendado)
  2. **Shortcode**: `[clip_comparador]`
  3. **Código JavaScript** en theme

#### 5.2 Plugin WordPress (Opcional pero Recomendado)
- [ ] Plugin básico de WordPress
- [ ] Settings page en WP Admin
- [ ] Auto-inyección del widget en páginas de producto
- [ ] Activación con API key

### FASE 6: Testing y QA (2 días)

- [ ] Tests unitarios para WooCommerceAPIClient
- [ ] Tests de integración para sync_service
- [ ] Validación con tienda WooCommerce de prueba
- [ ] Pruebas de webhooks end-to-end
- [ ] Validación de búsqueda visual con productos WooCommerce

---

## 🔐 Consideraciones de Seguridad

### 1. **Almacenamiento de Credenciales**
```python
# ✅ CORRECTO: Encriptar consumer key y secret
integration.set_consumer_key(ck)
integration.set_consumer_secret(cs)

# ❌ INCORRECTO: Guardar en texto plano
integration.consumer_key = ck  # NO HACER ESTO
```

### 2. **Validación de Webhooks**
```python
def verify_webhook_signature(request):
    """
    WooCommerce usa HMAC-SHA256 con webhook_secret
    Header: X-WC-Webhook-Signature
    """
    signature = request.headers.get('X-WC-Webhook-Signature')
    payload = request.get_data()
    expected = base64.b64encode(
        hmac.new(webhook_secret.encode(), payload, hashlib.sha256).digest()
    ).decode()
    return hmac.compare_digest(signature, expected)
```

### 3. **Rate Limiting**
- WooCommerce no tiene límite oficial, pero respetar buenas prácticas
- Implementar exponential backoff en caso de errores 429
- Sincronización en background tasks (Celery/RQ)

---

## 📊 Endpoints de API WooCommerce a Utilizar

### Información de Sistema
```http
GET /wp-json/wc/v3/system_status
```

### Productos
```http
GET    /wp-json/wc/v3/products              # Listar
GET    /wp-json/wc/v3/products/:id          # Obtener uno
POST   /wp-json/wc/v3/products              # Crear (no usar)
PUT    /wp-json/wc/v3/products/:id          # Actualizar stock
DELETE /wp-json/wc/v3/products/:id          # No usar
```

### Categorías
```http
GET /wp-json/wc/v3/products/categories
GET /wp-json/wc/v3/products/categories/:id
```

### Atributos
```http
GET /wp-json/wc/v3/products/attributes
GET /wp-json/wc/v3/products/:product_id/variations
```

### Webhooks
```http
POST   /wp-json/wc/v3/webhooks              # Registrar
GET    /wp-json/wc/v3/webhooks              # Listar
DELETE /wp-json/wc/v3/webhooks/:id          # Eliminar
```

---

## 🎯 Comparación de Payloads

### Producto en Tiendanube
```json
{
  "id": 123,
  "name": { "es": "Remera Básica" },
  "description": { "es": "..." },
  "handle": { "es": "remera-basica" },
  "images": [
    { "id": 456, "src": "https://..." }
  ],
  "categories": [
    { "id": 789, "name": { "es": "Ropa" } }
  ],
  "variants": [
    { "price": "1500.00", "stock": 10 }
  ]
}
```

### Producto en WooCommerce
```json
{
  "id": 123,
  "name": "Remera Básica",
  "description": "<p>...</p>",
  "slug": "remera-basica",
  "images": [
    { "id": 456, "src": "https://..." }
  ],
  "categories": [
    { "id": 789, "name": "Ropa" }
  ],
  "price": "1500",
  "stock_quantity": 10
}
```

**Diferencias principales:**
- Tiendanube: campos multi-idioma `{ "es": "..." }`
- WooCommerce: campos directos (string/number)
- Tiendanube: `variants` para stock/precio
- WooCommerce: `price` y `stock_quantity` en producto base

---

## 🚀 Ventajas de la Integración WooCommerce

1. **Mercado más grande**: WooCommerce es el 36% del mercado de e-commerce
2. **Self-hosted**: Más control para el cliente
3. **Open-source**: Documentación completa y comunidad activa
4. **Diversificación**: No depender solo de Tiendanube
5. **Modelo de negocio**: Potencial para vender como plugin premium

---

## 📈 Estimación de Tiempo Total

| Fase | Duración | Prioridad |
|------|----------|-----------|
| 1. Infraestructura Base | 2-3 días | Alta |
| 2. Sincronización | 3-4 días | Alta |
| 3. Webhooks | 2-3 días | Media |
| 4. Panel Admin | 2 días | Media |
| 5. Widget/Plugin | 2-3 días | Alta |
| 6. Testing | 2 días | Alta |
| **TOTAL** | **13-17 días** | - |

---

## 🎓 Recursos de Referencia

### Documentación Oficial
- [WooCommerce REST API Documentation](https://woocommerce.github.io/woocommerce-rest-api-docs/)
- [WooCommerce Webhooks Guide](https://woocommerce.com/document/webhooks/)
- [WordPress Plugin Handbook](https://developer.wordpress.org/plugins/)

### Ejemplos de Código
- [WooCommerce Python Client](https://github.com/woocommerce/wc-api-python)
- [WooCommerce REST API Examples](https://github.com/woocommerce/woocommerce-rest-api)

### Herramientas Útiles
- [Postman Collection WooCommerce](https://documenter.getpostman.com/view/8186696/SzYbyHXj)
- [WooCommerce API Tester Plugin](https://wordpress.org/plugins/woocommerce-api-tester/)

---

## ✅ Checklist de Inicio Rápido

Antes de comenzar la implementación:

- [ ] Crear tienda WooCommerce de prueba (Local o hosting gratuito)
- [ ] Generar Consumer Keys en WooCommerce → Settings → Advanced → REST API
- [ ] Probar endpoints manualmente con Postman/cURL
- [ ] Revisar estructura de datos de productos/categorías
- [ ] Definir mapeo de atributos Tiendanube ↔ WooCommerce
- [ ] Planificar estrategia de migración de clientes existentes (si aplica)

---

## 🤝 Próximos Pasos

1. **Validar el plan**: Revisar este documento y ajustar prioridades
2. **Setup inicial**: Crear tienda de prueba WooCommerce
3. **POC (Proof of Concept)**: Implementar conexión básica y listar productos
4. **Iteración**: Desarrollar por fases según el plan
5. **Documentación**: Mantener actualizada la guía de integración

---

**Fecha de creación**: 14 de Enero de 2026
**Última actualización**: 14 de Enero de 2026
**Estado**: 📋 Planificación
