# Plan de Desarrollo - Plugin Tiendanube CLIP Comparador V2

## 📋 Resumen Ejecutivo

**Objetivo**: Desarrollar un plugin oficial de Tiendanube que permita a cualquier tienda existente integrar nuestro sistema de búsqueda visual por CLIP de forma automática, sin configuración manual.

**Flujo Ideal del Cliente**:
1. Cliente con tienda Tiendanube busca "CLIP Visual Search" en App Store
2. Instala el plugin desde su admin panel
3. Plugin automáticamente:
   - Crea cuenta en nuestro sistema
   - Importa categorías y productos completos
   - Genera embeddings CLIP para todas las imágenes
   - Calcula centroides de categorías
   - Configura webhooks para sincronización en tiempo real
   - Inyecta widget en la tienda
4. Cliente puede gestionar todo desde panel embebido en Tiendanube

---

## 🏗️ Arquitectura del Sistema

### Componentes Principales

```
┌─────────────────────────────────────────────────────────────┐
│                    TIENDANUBE APP STORE                     │
│                  (Plugin CLIP Search)                       │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      │ OAuth 2.0 Installation Flow
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              CLIP BACKEND (Railway)                         │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  OAuth Callback Handler                              │  │
│  │  - Recibe código de autorización                     │  │
│  │  - Obtiene access_token + store_id                   │  │
│  │  - Crea client en nuestra DB                         │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Initial Sync Service                                │  │
│  │  - GET /categories (paginated)                       │  │
│  │  - GET /products (paginated, con imágenes)           │  │
│  │  - Descarga imágenes a Cloudinary                    │  │
│  │  - Genera embeddings CLIP (batch)                    │  │
│  │  - Calcula centroides de categorías                  │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Webhook Handler                                     │  │
│  │  - product/created → crear producto + embeddings     │  │
│  │  - product/updated → actualizar + regenerar          │  │
│  │  - product/deleted → eliminar de nuestro sistema     │  │
│  │  - category/created → crear categoría                │  │
│  │  - category/updated → actualizar                     │  │
│  │  - category/deleted → eliminar                       │  │
│  │  - app/uninstalled → limpiar datos (GDPR)            │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Plugin Admin Panel (Iframe embebido)                │  │
│  │  - Dashboard de sincronización                       │  │
│  │  - Gestión de categorías CLIP                        │  │
│  │  - Configuración de umbrales                         │  │
│  │  - Preview del widget                                │  │
│  │  - Analytics de búsquedas                            │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                      │
                      │ Webhooks (HTTPS POST)
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    TIENDANUBE STORE                         │
│  - Recibe eventos de nuestro sistema                        │
│  - Widget inyectado automáticamente via Script resource     │
└─────────────────────────────────────────────────────────────┘
```

---

## 📝 Requisitos y Configuración Tiendanube

### 1. Registro como Partner
- **URL**: https://www.tiendanube.com/partners
- Registrarse en programa de partners
- Crear app desde panel de partners

### 2. Configuración de la App

#### URLs Requeridas (todas HTTPS):
```
Callback URL (OAuth):
  https://clipcomparadorv2-production.up.railway.app/tiendanube/oauth/callback

App URL (Panel principal):
  https://clipcomparadorv2-production.up.railway.app/tiendanube/admin

Preferences URL (Configuración):
  https://clipcomparadorv2-production.up.railway.app/tiendanube/preferences

Privacy Policy URL:
  https://clipcomparadorv2-production.up.railway.app/privacy

Support URL:
  https://clipcomparadorv2-production.up.railway.app/support

Support Email:
  soporte@clipcomparador.com

Webhook Store Redact:
  https://clipcomparadorv2-production.up.railway.app/webhooks/tiendanube/store-redact

Webhook Customer Redact:
  https://clipcomparadorv2-production.up.railway.app/webhooks/tiendanube/customer-redact

Webhook Customers Data Request:
  https://clipcomparadorv2-production.up.railway.app/webhooks/tiendanube/data-request
```

#### Scopes Necesarios:
```
read_products       - Leer productos para sincronización inicial
write_products      - Actualizar productos con metadatos CLIP
read_content        - Leer páginas para contexto
write_scripts       - Inyectar widget automáticamente
```

### 3. OAuth Flow

```
1. User clicks "Install App" en Tiendanube
   → https://www.tiendanube.com/apps/{app_id}/authorize?state={csrf_token}

2. User acepta permisos (scopes)

3. Tiendanube redirige a callback URL:
   → https://.../oauth/callback?code={auth_code}&state={csrf_token}

4. Nuestro backend hace POST:
   URL: https://www.tiendanube.com/apps/authorize/token
   Body: {
     "client_id": "{app_id}",
     "client_secret": "{app_secret}",
     "grant_type": "authorization_code",
     "code": "{auth_code}"
   }

5. Recibimos:
   {
     "access_token": "xxx",
     "token_type": "bearer",
     "scope": "read_products,write_products...",
     "user_id": "store_id"  // Este es el store_id!
   }

6. Guardamos en DB:
   - access_token (encriptado)
   - store_id
   - scopes
   - Creamos client en nuestra tabla clients
   - Generamos api_key interno
```

---

## 🔄 Sincronización Inicial (Post-Instalación)

### Proceso Automático en Background

```python
def initial_sync_tiendanube_store(store_id: str, access_token: str):
    """
    Se ejecuta en background job (Celery/RQ) después de OAuth
    """

    # 1. Obtener información de la tienda
    store_info = get_store_info(store_id, access_token)
    # GET https://api.tiendanube.com/2025-03/{store_id}/store

    # 2. Crear client en nuestra DB
    client = create_clip_client(
        name=store_info['name'],
        email=store_info['email'],
        domain=store_info['main_domain'],
        tiendanube_store_id=store_id,
        tiendanube_access_token=encrypt(access_token),
        api_key=generate_api_key(),
        plan='starter',  # Plan inicial
        is_active=True
    )

    # 3. Sincronizar categorías
    categories = sync_categories(store_id, access_token, client.id)
    # GET https://api.tiendanube.com/2025-03/{store_id}/categories
    # Paginar con ?page=1&per_page=200
    # Crear en nuestra tabla categories con mapping tiendanube_category_id

    # 4. Sincronizar productos (HEAVY)
    products = sync_products_batch(store_id, access_token, client.id, categories)
    # GET https://api.tiendanube.com/2025-03/{store_id}/products
    # Por cada producto:
    #   - Crear registro en products con tiendanube_product_id
    #   - Descargar imágenes desde product.images[].src
    #   - Subir a Cloudinary con folder={client.id}/products/
    #   - Crear registros en images con cloudinary_url

    # 5. Generar embeddings (HEAVY)
    generate_embeddings_for_client(client.id)
    # Procesar todas las imágenes en batch
    # Usar CLIP model para generar embeddings
    # Actualizar images.clip_embedding

    # 6. Calcular centroides de categorías
    calculate_category_centroids(client.id)
    # Por cada categoría:
    #   - Obtener todos los embeddings de productos en esa categoría
    #   - Calcular promedio (centroide)
    #   - Guardar en categories.centroid_embedding

    # 7. Registrar webhooks en Tiendanube
    register_tiendanube_webhooks(store_id, access_token)
    # POST https://api.tiendanube.com/2025-03/{store_id}/webhooks
    # Eventos:
    #   - product/created, product/updated, product/deleted
    #   - category/created, category/updated, category/deleted
    #   - app/uninstalled

    # 8. Inyectar widget automáticamente
    inject_widget_script(store_id, access_token, client.api_key)
    # POST https://api.tiendanube.com/2025-03/{store_id}/scripts
    # Body: {
    #   "event": "onload",
    #   "where": "store",
    #   "src": "https://.../clip-widget-embed-v5.js?api_key={api_key}"
    # }

    # 9. Notificar al cliente por email
    send_installation_complete_email(store_info['email'], client.id)

    return {
        'status': 'completed',
        'categories_synced': len(categories),
        'products_synced': len(products),
        'embeddings_generated': count_embeddings(client.id)
    }
```

### Consideraciones de Performance

**Rate Limiting Tiendanube**:
- Bucket size: 40 requests
- Rate: 2 requests/second
- Planes superiores: 10x (20 req/s)

**Estrategia**:
- Procesar en chunks de 40 productos
- Sleep de 0.5s entre requests
- Usar API pagination: `?page=X&per_page=200`
- Sincronización inicial puede tomar 15-30 min para tienda grande
- Mostrar progress bar en tiempo real (WebSocket/SSE)

---

## 🔗 Sistema de Webhooks Bidireccional

### Webhooks de Tiendanube → CLIP Backend

**Endpoint**: `POST /webhooks/tiendanube`

**Eventos a Manejar**:

```python
WEBHOOK_HANDLERS = {
    'product/created': handle_product_created,
    'product/updated': handle_product_updated,
    'product/deleted': handle_product_deleted,
    'category/created': handle_category_created,
    'category/updated': handle_category_updated,
    'category/deleted': handle_category_deleted,
    'app/uninstalled': handle_app_uninstalled,
    'app/suspended': handle_app_suspended,
    'app/resumed': handle_app_resumed,
}

def handle_product_created(payload):
    """
    Payload: {
        'store_id': 123,
        'event': 'product/created',
        'id': 456  # product_id
    }
    """
    store_id = payload['store_id']
    product_id = payload['id']

    # 1. Obtener client por store_id
    client = get_client_by_tiendanube_store_id(store_id)

    # 2. Obtener detalles del producto desde Tiendanube
    product_data = get_tiendanube_product(store_id, product_id, client.tiendanube_access_token)
    # GET https://api.tiendanube.com/2025-03/{store_id}/products/{product_id}

    # 3. Crear producto en nuestra DB
    product = create_product_from_tiendanube(client.id, product_data)

    # 4. Descargar y procesar imágenes
    for image_url in product_data['images']:
        # Descargar imagen
        image_bytes = download_image(image_url['src'])

        # Subir a Cloudinary
        cloudinary_result = upload_to_cloudinary(
            image_bytes,
            folder=f"{client.id}/products/{product.id}"
        )

        # Crear registro de imagen
        image = create_image(
            product_id=product.id,
            cloudinary_url=cloudinary_result['secure_url'],
            cloudinary_public_id=cloudinary_result['public_id'],
            is_primary=(image_url['position'] == 1)
        )

        # Generar embedding CLIP
        embedding = generate_clip_embedding(image_bytes)
        update_image_embedding(image.id, embedding)

    # 5. Recalcular centroide de la categoría
    if product.category_id:
        recalculate_category_centroid(product.category_id)

    return {'status': 'ok', 'product_id': product.id}

def handle_product_updated(payload):
    """Actualizar producto existente y regenerar embeddings si cambió imagen"""
    # Similar a created pero con update
    pass

def handle_product_deleted(payload):
    """Soft delete del producto en nuestra DB"""
    product = get_product_by_tiendanube_id(payload['id'], payload['store_id'])
    product.is_active = False
    product.deleted_at = datetime.utcnow()
    db.session.commit()

    # Recalcular centroide de categoría
    if product.category_id:
        recalculate_category_centroid(product.category_id)

def handle_app_uninstalled(payload):
    """GDPR: Marcar client como desinstalado"""
    client = get_client_by_tiendanube_store_id(payload['store_id'])
    client.is_active = False
    client.uninstalled_at = datetime.utcnow()
    db.session.commit()

    # Programar eliminación de datos después de 48 horas (GDPR)
    schedule_data_deletion(client.id, delay_hours=48)
```

**Seguridad - Verificar HMAC**:
```python
import hmac
import hashlib

def verify_webhook_signature(request):
    """Verificar que el webhook viene realmente de Tiendanube"""
    received_hmac = request.headers.get('X-Linkedstore-Hmac-Sha256')
    app_secret = os.getenv('TIENDANUBE_APP_SECRET')

    calculated_hmac = hmac.new(
        app_secret.encode('utf-8'),
        request.data,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(received_hmac, calculated_hmac)

@app.route('/webhooks/tiendanube', methods=['POST'])
def tiendanube_webhook():
    # Verificar firma HMAC
    if not verify_webhook_signature(request):
        return jsonify({'error': 'Invalid signature'}), 401

    payload = request.json
    event = payload.get('event')

    # Responder rápidamente (Tiendanube espera 2XX en <10s)
    queue_webhook_job(event, payload)

    return jsonify({'status': 'queued'}), 200
```

---

## 🎨 Panel de Administración Embebido

### Interfaz en Tiendanube Admin

Tiendanube permite embeber iframe en el panel de admin. Crear página:

**URL**: `/tiendanube/admin?store_id={store_id}&token={temp_token}`

**Secciones**:

1. **Dashboard Principal**
   - Estado de sincronización
   - Productos indexados vs total en Tiendanube
   - Embeddings generados
   - Últimas búsquedas (top 10)
   - Analytics: búsquedas/día, productos más buscados

2. **Gestión de Categorías CLIP**
   - Lista de categorías sincronizadas
   - Editar CLIP prompts personalizados
   - Ajustar visual features
   - Recalcular centroides manualmente
   - Preview de categoría (mostrar productos similares)

3. **Configuración Avanzada**
   - Umbrales de confianza:
     - category_confidence_threshold (default: 0.7)
     - product_similarity_threshold (default: 0.6)
   - Activar/desactivar categorías específicas
   - Configurar número de resultados (default: 10)

4. **Widget Configuration**
   - Preview del widget en tiempo real
   - Personalización de colores (CSS variables)
   - Posición del botón
   - Textos personalizados
   - Test del widget (abrir modal de prueba)

5. **Analytics Avanzado**
   - Gráfico de búsquedas por día
   - Productos con más impresiones
   - Tasa de conversión (búsqueda → click)
   - Exportar datos a CSV

6. **Sincronización Manual**
   - Botón "Re-sincronizar Todo"
   - Botón "Regenerar Embeddings"
   - Botón "Recalcular Centroides"
   - Log de sincronización (últimas 50 operaciones)

### Autenticación del Panel

```python
@app.route('/tiendanube/admin')
def tiendanube_admin_panel():
    """
    Tiendanube envía:
    - store_id en URL
    - puede enviar token temporal o esperamos validar sesión
    """
    store_id = request.args.get('store_id')

    # Validar que store_id corresponde a client activo
    client = get_client_by_tiendanube_store_id(store_id)
    if not client or not client.is_active:
        return render_template('error.html', message='Store not found')

    # Generar token JWT temporal para la sesión del iframe
    token = generate_jwt(client.id, expires_in=3600)

    return render_template('tiendanube_admin.html',
                         client=client,
                         token=token,
                         analytics=get_client_analytics(client.id))
```

---

## 🔧 Widget Injection Automático

### Script Resource en Tiendanube

Al instalar el plugin, crear automáticamente un Script:

```python
def inject_widget_script(store_id: str, access_token: str, api_key: str):
    """
    POST https://api.tiendanube.com/2025-03/{store_id}/scripts
    """

    script_data = {
        "event": "onload",
        "where": "store",  # Cargar en todas las páginas de la tienda
        "src": f"https://clipcomparadorv2-production.up.railway.app/static/clip-widget-embed-v5.js?api_key={api_key}"
    }

    response = requests.post(
        f"https://api.tiendanube.com/2025-03/{store_id}/scripts",
        headers={
            'Authentication': f'bearer {access_token}',
            'Content-Type': 'application/json',
            'User-Agent': 'CLIP Visual Search (soporte@clipcomparador.com)'
        },
        json=script_data
    )

    if response.status_code == 201:
        script_id = response.json()['id']
        # Guardar script_id en nuestra DB para poder eliminarlo después
        save_tiendanube_script_id(store_id, script_id)
        return script_id
    else:
        raise Exception(f"Failed to inject script: {response.text}")
```

### Widget JavaScript (v5 - Auto-config)

```javascript
// clip-widget-embed-v5.js
(function() {
    // Detectar si ya fue cargado
    if (window.CLIP_WIDGET_LOADED) return;
    window.CLIP_WIDGET_LOADED = true;

    // Extraer api_key del src del script
    const scriptTag = document.currentScript ||
                      Array.from(document.scripts).find(s => s.src.includes('clip-widget-embed-v5.js'));
    const apiKey = new URLSearchParams(new URL(scriptTag.src).search).get('api_key');

    if (!apiKey) {
        console.error('[CLIP Widget] No API key found');
        return;
    }

    // Inyectar botón flotante
    const button = document.createElement('button');
    button.id = 'clip-search-button';
    button.innerHTML = `
        <svg><!-- Icono de búsqueda --></svg>
        <span>Buscar por imagen</span>
    `;
    button.onclick = function() {
        openClipOverlay(apiKey);
    };
    document.body.appendChild(button);

    // Función para abrir overlay
    function openClipOverlay(apiKey) {
        // Crear overlay similar a actual pero con auto-config
        const overlay = document.createElement('div');
        overlay.id = 'clip-search-overlay';
        overlay.innerHTML = `
            <iframe
                src="https://clipcomparadorv2-production.up.railway.app/search?api_key=${apiKey}&embedded=true"
                frameborder="0"
                allowfullscreen
            ></iframe>
        `;
        document.body.appendChild(overlay);

        // Event listener para cerrar
        overlay.onclick = function(e) {
            if (e.target === overlay) {
                closeClipOverlay();
            }
        };
    }

    function closeClipOverlay() {
        const overlay = document.getElementById('clip-search-overlay');
        if (overlay) overlay.remove();
    }

    // Listener para mensajes desde iframe
    window.addEventListener('message', function(event) {
        if (event.data.type === 'CLIP_CLOSE') {
            closeClipOverlay();
        } else if (event.data.type === 'CLIP_PRODUCT_CLICK') {
            // Redirigir a producto en Tiendanube
            const productUrl = event.data.url;
            window.location.href = productUrl;
        }
    });

    console.log('[CLIP Widget] Initialized successfully');
})();
```

---

## 📊 Modelos de Base de Datos (Extensiones)

### Nueva Tabla: `tiendanube_integrations`

```sql
CREATE TABLE tiendanube_integrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    store_id VARCHAR(50) NOT NULL UNIQUE,  -- Tiendanube store_id
    access_token TEXT NOT NULL,  -- Encriptado
    store_name VARCHAR(255),
    store_email VARCHAR(255),
    store_domain VARCHAR(255),
    scopes TEXT[],  -- Array de scopes autorizados
    script_id INTEGER,  -- ID del script inyectado
    is_active BOOLEAN DEFAULT TRUE,
    installed_at TIMESTAMP DEFAULT NOW(),
    uninstalled_at TIMESTAMP,
    last_sync_at TIMESTAMP,
    sync_status VARCHAR(50),  -- 'pending', 'in_progress', 'completed', 'error'
    sync_error TEXT,
    webhook_ids JSONB,  -- {"product_created": 123, "product_updated": 456, ...}
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_tiendanube_store_id ON tiendanube_integrations(store_id);
CREATE INDEX idx_tiendanube_client_id ON tiendanube_integrations(client_id);
```

### Extensión Tabla `products`

```sql
ALTER TABLE products ADD COLUMN tiendanube_product_id VARCHAR(50);
ALTER TABLE products ADD COLUMN tiendanube_variant_id VARCHAR(50);
ALTER TABLE products ADD COLUMN tiendanube_last_sync TIMESTAMP;

CREATE INDEX idx_products_tiendanube_id ON products(tiendanube_product_id);
```

### Extensión Tabla `categories`

```sql
ALTER TABLE categories ADD COLUMN tiendanube_category_id VARCHAR(50);
ALTER TABLE categories ADD COLUMN tiendanube_last_sync TIMESTAMP;

CREATE INDEX idx_categories_tiendanube_id ON categories(tiendanube_category_id);
```

---

## 🚀 Fases de Implementación

### **Fase 1: Infraestructura Base** (1 semana)
- [ ] Registrar app en Tiendanube Partner Portal
- [ ] Configurar URLs y scopes
- [ ] Crear endpoints OAuth:
  - `GET /tiendanube/oauth/authorize` (redirect to Tiendanube)
  - `GET /tiendanube/oauth/callback` (receive code, exchange for token)
- [ ] Crear modelos DB: `tiendanube_integrations`
- [ ] Sistema de encriptación para access_tokens
- [ ] Blueprint: `tiendanube_integration.py`

**Entregables**:
- OAuth flow funcional
- Poder instalar app y guardar credenciales

---

### **Fase 2: Sincronización Inicial** (2 semanas)
- [ ] Servicio de sincronización de categorías
  - GET /categories con paginación
  - Mapeo a nuestro schema
  - Manejo de idiomas múltiples
- [ ] Servicio de sincronización de productos
  - GET /products con paginación
  - Descarga de imágenes
  - Upload a Cloudinary
- [ ] Generación de embeddings en batch
  - Optimizar para procesar miles de imágenes
  - Progress tracking (Redis/DB)
- [ ] Cálculo de centroides
- [ ] Background jobs con Celery/RQ
- [ ] UI de progreso en tiempo real (WebSocket/SSE)

**Entregables**:
- Script que sincroniza tienda completa
- Dashboard mostrando progreso

---

### **Fase 3: Sistema de Webhooks** (1.5 semanas)
- [ ] Endpoint POST `/webhooks/tiendanube`
- [ ] Verificación de firma HMAC
- [ ] Handlers para cada evento:
  - product/created, updated, deleted
  - category/created, updated, deleted
  - app/uninstalled, suspended, resumed
- [ ] Registro automático de webhooks al instalar
- [ ] Sistema de reintentos para webhooks fallidos
- [ ] Logs de webhooks recibidos

**Entregables**:
- Webhooks funcionando en ambas direcciones
- Sincronización en tiempo real

---

### **Fase 4: Widget Auto-Injection** (1 semana)
- [ ] Crear clip-widget-embed-v5.js
  - Auto-configuración con api_key en URL
  - Botón flotante responsive
  - Overlay modal
  - Comunicación con iframe (postMessage)
- [ ] Endpoint POST /scripts en Tiendanube al instalar
- [ ] Personalización de estilos (CSS variables)
- [ ] Testing en diferentes themes de Tiendanube

**Entregables**:
- Widget se inyecta automáticamente
- Funciona en cualquier tema de Tiendanube

---

### **Fase 5: Panel de Administración** (2 semanas)
- [ ] Frontend con React/Vue embebible en iframe
- [ ] Dashboard principal con métricas
- [ ] Gestión de categorías CLIP
- [ ] Configuración de umbrales
- [ ] Analytics avanzado con gráficos
- [ ] Sincronización manual
- [ ] Preview del widget
- [ ] Sistema de autenticación JWT para iframe

**Entregables**:
- Panel completo en iframe de Tiendanube
- CRUD de configuraciones

---

### **Fase 6: Testing y Optimización** (1 semana)
- [ ] Testing con tienda real de producción
- [ ] Optimización de rate limiting
- [ ] Manejo de errores robusto
- [ ] Logging completo
- [ ] Documentación técnica
- [ ] Guía de usuario
- [ ] Video tutorial

**Entregables**:
- Sistema estable en producción
- Documentación completa

---

### **Fase 7: Publicación en App Store** (1 semana)
- [ ] Completar metadata de la app:
  - Logo y screenshots
  - Descripción en español e inglés
  - Categoría: "Marketing y ventas"
  - Pricing (Freemium o suscripción)
- [ ] Cumplir requisitos de GDPR/LGPD
  - Webhooks de redact implementados
  - Privacy policy publicada
  - Terms of service
- [ ] Revisión por equipo de Tiendanube
- [ ] Publicación oficial

**Entregables**:
- App publicada en App Store
- Disponible para instalación pública

---

## 📈 Modelo de Negocio

### Planes Propuestos

**Starter** (Gratis - 14 días trial)
- Hasta 100 productos
- 500 búsquedas/mes
- Widget básico
- Soporte por email

**Professional** ($29/mes)
- Hasta 1,000 productos
- 5,000 búsquedas/mes
- Widget personalizable
- Analytics básico
- Soporte prioritario

**Business** ($99/mes)
- Productos ilimitados
- Búsquedas ilimitadas
- Widget totalmente personalizable
- Analytics avanzado
- API access
- Soporte 24/7

**Enterprise** (Custom)
- Todo de Business
- Servidor dedicado
- Modelo CLIP fine-tuned
- Integración personalizada
- SLA garantizado

### Implementación de Billing

Tiendanube permite cobros recurrentes:
```python
# POST https://api.tiendanube.com/2025-03/{store_id}/subscriptions
{
    "plan_id": "clip_professional",
    "amount": 29.00,
    "currency": "USD",
    "frequency": "monthly"
}
```

---

## 🔐 Consideraciones de Seguridad

1. **Encriptación de Tokens**
   - `access_token` encriptado en DB (AES-256)
   - No exponer en logs

2. **HMAC Verification**
   - Verificar firma en todos los webhooks
   - Usar `hmac.compare_digest()` para evitar timing attacks

3. **Rate Limiting**
   - Respetar límites de Tiendanube (2 req/s)
   - Implementar exponential backoff

4. **GDPR/LGPD Compliance**
   - Eliminar datos 48 horas después de uninstall
   - Webhooks de store_redact y customer_redact
   - Data export functionality

5. **CORS**
   - Configurar correctamente para iframe embedding
   - `X-Frame-Options: ALLOW-FROM https://admin.tiendanube.com`

---

## 📚 Recursos y Referencias

### Documentación Oficial
- Tiendanube API: https://tiendanube.github.io/api-documentation/
- OAuth Flow: https://tiendanube.github.io/api-documentation/authentication
- Webhooks: https://tiendanube.github.io/api-documentation/resources/webhook
- Scripts: https://tiendanube.github.io/api-documentation/resources/script

### Contactos
- Soporte BR: parceiros@nuvemshop.com.br
- Soporte AR/MX: socios@tiendanube.com
- Partner Portal: https://www.tiendanube.com/partners

### Testing
- RequestCatcher (webhooks): https://requestcatcher.com/
- Postman Collection: Crear colección con todos los endpoints

---

## ✅ Checklist de Launch

### Pre-Launch
- [ ] OAuth flow testeado completamente
- [ ] Sincronización inicial probada con 1000+ productos
- [ ] Webhooks recibiendo eventos correctamente
- [ ] Widget renderiza en 3+ themes diferentes
- [ ] Panel de admin accesible desde Tiendanube
- [ ] Analytics funcionando correctamente
- [ ] Rate limiting respetado (no 429 errors)
- [ ] Logs implementados (Sentry/Logtail)
- [ ] Backups automáticos configurados
- [ ] Monitoring con alerts (Railway/New Relic)

### Legal/Compliance
- [ ] Privacy Policy publicada
- [ ] Terms of Service publicados
- [ ] GDPR webhooks implementados
- [ ] Data retention policy definida (48h post-uninstall)
- [ ] Cookie consent (si aplica)

### Marketing
- [ ] Landing page del plugin
- [ ] Video demo (2-3 min)
- [ ] Screenshots profesionales (5+)
- [ ] Descripción optimizada (ES/PT)
- [ ] Casos de uso documentados
- [ ] Plan de pricing definido
- [ ] FAQ preparado

### Post-Launch
- [ ] Monitorear primeras instalaciones
- [ ] Responder feedback rápidamente
- [ ] Iterar basado en métricas
- [ ] Escalar infraestructura según demanda

---

## 🎯 Métricas de Éxito

### KPIs Técnicos
- Tiempo de sincronización inicial < 20 min (tienda 1000 productos)
- Uptime > 99.5%
- Latencia API < 500ms p95
- Error rate < 0.1%

### KPIs de Negocio
- Instalaciones/mes: 10+ (primer mes), 50+ (6 meses)
- Conversion rate (install → paid): >20%
- Churn rate: <5%/mes
- NPS > 50

### KPIs de Usuario
- Búsquedas por instalación/mes: >100
- Tiempo promedio de búsqueda: <10s
- Click-through rate: >30%
- Retorno al plugin: >3x/mes

---

## 🚨 Riesgos y Mitigación

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Rate limiting agresivo | Media | Alto | Implementar queue system, exponential backoff |
| Tienda con 10k+ productos | Media | Alto | Sincronización incremental, chunk processing |
| Cambios en API de Tiendanube | Baja | Alto | Monitorear deprecations, versioning |
| Fallo en generación de embeddings | Media | Alto | Retry logic, fallback a búsqueda de texto |
| Costos de Cloudinary elevados | Alta | Medio | Optimizar imágenes, usar transformaciones eficientes |
| Rechazo en App Store review | Media | Alto | Seguir guidelines estrictamente, pre-review |

---

**Próximos Pasos Inmediatos**:

1. ✅ Completar análisis (este documento)
2. ⏳ Registrar cuenta de partner en Tiendanube
3. ⏳ Crear app en partners panel
4. ⏳ Implementar Fase 1 (OAuth)
5. ⏳ Testing inicial con tienda demo

**Estimación Total**: 9-10 semanas para MVP completo publicado en App Store

---

## 🗃️ Requisitos de Base de Datos (Actualizado)

### Tablas y columnas nuevas/extendidas

1) `clients` (extensiones)
- `integration_type` VARCHAR(50) DEFAULT 'standalone'  // 'standalone' | 'tiendanube'
- `integration_config` JSONB DEFAULT '{}'              // metadatos de integración (store_id, domain, scopes, etc.)
- `is_read_only` BOOLEAN DEFAULT FALSE                 // TRUE para Tiendanube
- `plan` VARCHAR(50) DEFAULT 'starter'
- `search_limit` INTEGER DEFAULT 500

2) `tiendanube_integrations` (nueva)
- `id` UUID PK
- `client_id` UUID FK → `clients(id)`
- `store_id` VARCHAR(50) UNIQUE
- `access_token` TEXT (encriptado)
- `store_name` VARCHAR(255)
- `store_email` VARCHAR(255)
- `store_domain` VARCHAR(255)
- `scopes` TEXT[]
- `script_id` INTEGER (opcional; puede no existir si el plan del merchant no permite scripts)
- `is_active` BOOLEAN DEFAULT TRUE
- `installed_at`, `uninstalled_at`, `last_sync_at`
- `sync_status` VARCHAR(50)  // 'pending', 'in_progress', 'completed', 'error'
- `sync_error` TEXT
- `webhook_ids` JSONB       // {"product_created": 123, ...}
- Índices: `store_id`, `client_id`

3) `products` (extensiones)
- `external_id` VARCHAR(100)          // product_id de Tiendanube
- `external_variant_id` VARCHAR(100)  // variant_id (si aplica)
- `external_url` TEXT                 // URL pública del producto en la tienda
- `last_sync_at` TIMESTAMP
- `sync_status` VARCHAR(50) DEFAULT 'synced'
- Índices: `external_id`, `sync_status`

4) `categories` (extensiones)
- `external_id` VARCHAR(100)          // category_id de Tiendanube
- `last_sync_at` TIMESTAMP
- `sync_status` VARCHAR(50) DEFAULT 'synced'
- Índices: `external_id`

5) `images` (extensiones para estrategia Base64)
- `base64_data` TEXT                  // imagen completa en Base64 (opcional según política)
- `base64_thumb` TEXT                 // thumbnail Base64 optimizado (recomendado para UI)
- `mime_type` VARCHAR(50)             // 'image/jpeg', 'image/png', 'image/webp', etc.
- `width` INT, `height` INT
- `size_bytes` INT
- `hash_sha256` VARCHAR(128)          // fingerprint del contenido para detectar cambios
- `source_url` TEXT                   // `product.images[].src` de Tiendanube
- `source_updated_at` TIMESTAMP
- `clip_embedding` TEXT               // vector serializado
- `is_primary` BOOLEAN, `display_order` INT

6) `sync_logs` (nueva)
- `id` UUID PK
- `client_id` UUID FK → `clients(id)`
- `sync_type` VARCHAR(50)     // 'full', 'incremental', 'webhook'
- `entity_type` VARCHAR(50)   // 'product', 'category', 'image'
- `entity_id` VARCHAR(100)    // external_id
- `action` VARCHAR(50)        // 'create', 'update', 'delete'
- `status` VARCHAR(50)        // 'success', 'error', 'skipped'
- `error_message` TEXT
- `metadata` JSONB
- `duration_ms` INTEGER
- `created_at` TIMESTAMP DEFAULT NOW()
- Índices: `client_id`, `created_at`, `status`

Notas clave:
- PostgreSQL es obligatorio; no usar SQLite.
- `access_token` debe almacenarse encriptado (AES-256) y nunca en logs.
- La política por defecto usa thumbnails Base64 para UI; la imagen full puede ser opcional.

---

## 👤 Registración del Cliente (Instalación OAuth)

Política: cada instalación crea un **nuevo cliente** en nuestro sistema, independiente de cualquier cliente existente (por ejemplo, `eve-store`). El cliente `eve-store` se mantiene intacto; solo se usa como referencia histórica.

### Flujo

1) Instalación (OAuth Authorization Code)
- Merchant acepta permisos → redirección a `callback` con `code`
- POST `https://www.tiendanube.com/apps/authorize/token` con `client_id`, `client_secret`, `grant_type=authorization_code`, `code`
- Recibimos `{ access_token, token_type, scope, user_id (store_id) }`

2) Creación del cliente
- Crear registro en `clients` con:
  - `name`, `email`, `domain` obtenidos vía `GET /store`
  - `integration_type='tiendanube'`
  - `is_read_only=True`
  - `api_key` generado
- Crear registro en `tiendanube_integrations` con:
  - `store_id`, `access_token` (encriptado), `scopes`, `store_name`, `store_domain`
  - `installed_at=NOW()`, `sync_status='pending'`

3) Registro de Webhooks
- Crear webhooks para: `product/created|updated|deleted`, `category/created|updated|deleted`, `app/uninstalled`
- Guardar IDs en `webhook_ids`

4) Detección de compatibilidad de Scripts
- Intentar `POST /scripts` solo si el plan soporta `write_scripts`
- Si falla/plan limitado: ofrecer **fallback** de enlace de menú configurado desde el panel

5) Notificación y onboarding
- Página de bienvenida + email con enlace al panel y estado de sync

Resultado: cliente creado (nuevo), `eve-store` no se toca.

---

## 🔄 Política de Desinstalación y Reinstalación

Estados y Webhooks:
- `app/uninstalled`: marcar cliente inactivo, pausar sync, eliminar webhooks.
- `store/redact` (hasta 48h): eliminar definitivamente datos del store (GDPR/LGPD).

Reinstalación:
- Si reinstala **antes de 48h** y NO llegó `store/redact`: reusar embeddings y thumbnails Base64, correr **sync incremental** (categorías/productos actualizados) y registrar webhooks de nuevo.
- Si reinstala **después de `store/redact`** o vencida la ventana: **sync full** (categorías, productos, imágenes → Base64, embeddings, centroides).
- En todos los casos: generar y almacenar **nuevo** `access_token` y validar scopes.

UX del Panel:
- Mostrar estado “App desinstalada” y, si procede, opción de reinstalar con incremental.
- Si hubo `store/redact`, indicar que se requiere reindexación completa.
- Botón “Forzar sincronización completa” para correcciones manuales.

---

## 📦 Imágenes Base64 y Webhooks

Estrategia sin Cloudinary:
- Ingesta: descargar `product.images[].src` → convertir a Base64 (full opcional, thumbnail recomendado) → guardar en `images.*` con `hash_sha256`.
- Embeddings: generar directamente desde bytes (buffer) ya descargados.
- Visualización: el widget y el admin usan `base64_thumb` por defecto para rapidez; la imagen full Base64 es opcional.

Webhooks:
- `product/created`: crear producto, descargar imágenes, generar thumbnails y embeddings, actualizar centroides.
- `product/updated`: comparar `hash_sha256`; si cambia, reingestar imagen, regenerar embeddings y thumbnail, recalcular centroides.
- `product/deleted`: marcar producto inactivo y recalcular centroides.

Fallback Scripts:
- Si el plan del merchant no admite `write_scripts`, se ofrece un **enlace de menú** al widget: `https://.../tiendanube/widget?api_key=...`.

---
