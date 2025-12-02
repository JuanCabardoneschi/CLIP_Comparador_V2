# Integración TiendaNube - Arquitectura y Diseño

## 📋 Resumen Ejecutivo

Este documento describe la arquitectura de integración entre CLIP Comparador V2 y TiendaNube/Nuvemshop mediante webhooks y API REST, manteniendo nuestra estructura actual y agregando una capa de sincronización bidireccional.

## 🎯 Objetivos

1. **Mantener operatoria actual**: Clientes no-TiendaNube siguen funcionando igual
2. **Sincronización unidireccional TiendaNube → CLIP**: Webhooks para recibir productos/stock/imágenes en tiempo real
3. **Capa de abstracción**: Mapeo entre estructuras de TiendaNube y CLIP
4. **CLIP como consumidor**: TiendaNube es la fuente de verdad para productos, stock, categorías e imágenes
5. **Búsqueda visual CLIP**: Productos de TiendaNube disponibles automáticamente para búsqueda con nuestro motor CLIP

## 🏗️ Arquitectura General

```
                    ┌─────────────────────────────────────┐
                    │      TiendaNube (Fuente única)      │
                    │  - Gestión de productos             │
                    │  - Control de stock                 │
                    │  - Imágenes                         │
                    │  - Categorías                       │
                    │  - Órdenes                          │
                    └─────────────────────────────────────┘
                                    │
                                    │ Webhooks (PUSH)
                                    │ + OAuth API (PULL inicial)
                                    ↓
┌─────────────────────────────────────────────────────────────────┐
│                         CLIP Comparador V2                       │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │         Clientes Tradicionales (Sin cambios)               │ │
│  │  - Carga manual de productos en Admin Panel               │ │
│  │  - Gestión completa desde CLIP                            │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │      NUEVA CAPA: TiendaNube Sync (Solo lectura)           │ │
│  │  ┌──────────────────────────────────────────────────────┐  │ │
│  │  │  Webhook Receiver (Flask Blueprint)                  │  │ │
│  │  │  ✓ product/created  → Crea producto en CLIP         │  │ │
│  │  │  ✓ product/updated  → Actualiza datos + stock       │  │ │
│  │  │  ✓ product/deleted  → Desactiva en CLIP             │  │ │
│  │  │  ✓ order/paid       → Reduce stock (opcional)       │  │ │
│  │  │  ✓ HMAC SHA256 verification                         │  │ │
│  │  └──────────────────────────────────────────────────────┘  │ │
│  │  ┌──────────────────────────────────────────────────────┐  │ │
│  │  │  TiendaNube API Client (Solo lectura)               │  │ │
│  │  │  ✓ GET /products     → Sync inicial de catálogo     │  │ │
│  │  │  ✓ GET /products/:id → Datos completos del producto │  │ │
│  │  │  ✓ GET /categories   → Importar categorías          │  │ │
│  │  │  ✗ POST/PUT/PATCH    → NO se modifica TiendaNube    │  │ │
│  │  └──────────────────────────────────────────────────────┘  │ │
│  │  ┌──────────────────────────────────────────────────────┐  │ │
│  │  │  Data Importer Service (Solo TN → CLIP)             │  │ │
│  │  │  ✓ TiendaNube Product → CLIP Product                │  │ │
│  │  │  ✓ TiendaNube Variants → CLIP Products (1:1 o 1:N)  │  │ │
│  │  │  ✓ Descargar imágenes → Cloudinary                  │  │ │
│  │  │  ✓ Generar embeddings CLIP automáticamente          │  │ │
│  │  │  ✓ Category mapping automático                      │  │ │
│  │  └──────────────────────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │         API de Búsqueda Visual (Modo lectura)              │ │
│  │  - Widget embebible para TiendaNube                       │ │
│  │  - Búsqueda por imagen en catálogo sincronizado           │ │
│  │  - Resultados filtrados por disponibilidad de stock       │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘

    IMPORTANTE: CLIP es READ-ONLY desde TiendaNube
    No hay sincronización CLIP → TiendaNube
```

## 📊 Modelo de Datos Extendido

### Nueva tabla: `tiendanube_integrations`

```sql
CREATE TABLE tiendanube_integrations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id UUID REFERENCES clients(id) NOT NULL,

    -- OAuth credentials
    store_id VARCHAR(50) NOT NULL,  -- TiendaNube store_id
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    token_expires_at TIMESTAMP,

    -- App info
    app_id VARCHAR(100),
    app_secret VARCHAR(255),

    -- Store info
    store_name VARCHAR(255),
    store_url VARCHAR(500),
    store_language VARCHAR(10) DEFAULT 'es',

    -- Sync settings (solo TN → CLIP)
    auto_import_products BOOLEAN DEFAULT TRUE,
    auto_update_stock BOOLEAN DEFAULT TRUE,
    sync_on_order_paid BOOLEAN DEFAULT FALSE,  -- Reducir stock al recibir order/paid

    -- Mapping configuration
    category_mapping JSONB,  -- {"tiendanube_cat_id": "clip_category_id"}
    attribute_mapping JSONB, -- Mapeo de atributos TN → CLIP

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    last_sync_at TIMESTAMP,
    sync_status VARCHAR(50),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_tn_client ON tiendanube_integrations(client_id);
CREATE INDEX idx_tn_store ON tiendanube_integrations(store_id);
```

### Nueva tabla: `tiendanube_product_mapping`

```sql
CREATE TABLE tiendanube_product_mapping (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    integration_id UUID REFERENCES tiendanube_integrations(id) NOT NULL,

    -- TiendaNube IDs
    tiendanube_product_id VARCHAR(50) NOT NULL,
    tiendanube_variant_id VARCHAR(50),

    -- CLIP IDs
    clip_product_id UUID REFERENCES products(id) NOT NULL,

    -- Metadata
    last_synced_at TIMESTAMP,
    is_managed_by_tiendanube BOOLEAN DEFAULT TRUE,  -- Siempre true para productos TN

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(integration_id, tiendanube_product_id, tiendanube_variant_id)
);

CREATE INDEX idx_tn_mapping_product ON tiendanube_product_mapping(tiendanube_product_id);
CREATE INDEX idx_tn_mapping_clip ON tiendanube_product_mapping(clip_product_id);
```

### Nueva tabla: `tiendanube_webhooks_log`

```sql
CREATE TABLE tiendanube_webhooks_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    integration_id UUID REFERENCES tiendanube_integrations(id),

    -- Webhook data
    event_type VARCHAR(100) NOT NULL,  -- 'product/created', 'order/paid', etc.
    store_id VARCHAR(50) NOT NULL,
    resource_id VARCHAR(50),  -- product_id, order_id, etc.

    -- Processing
    payload JSONB NOT NULL,
    processed BOOLEAN DEFAULT FALSE,
    processed_at TIMESTAMP,
    processing_error TEXT,

    -- Security
    hmac_signature VARCHAR(255),
    is_verified BOOLEAN,

    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_tn_webhooks_event ON tiendanube_webhooks_log(event_type);
CREATE INDEX idx_tn_webhooks_processed ON tiendanube_webhooks_log(processed);
```

## 🔌 API Endpoints - Integración TiendaNube

### 1. OAuth Flow y Configuración

#### `GET /api/tiendanube/auth/start`
Inicia el flujo OAuth para conectar una tienda TiendaNube.

**Parámetros:**
- `client_id`: UUID del cliente en CLIP

**Respuesta:**
```json
{
  "authorization_url": "https://www.tiendanube.com/apps/authorize/...",
  "state": "random_state_token"
}
```

#### `GET /api/tiendanube/auth/callback`
Callback OAuth que recibe el access_token de TiendaNube.

**Parámetros Query:**
- `code`: Authorization code
- `state`: State token para validación

**Respuesta:**
```json
{
  "success": true,
  "store_id": "123456",
  "store_name": "Mi Tienda",
  "integration_id": "uuid"
}
```

#### `POST /api/tiendanube/integrations/{integration_id}/disconnect`
Desconecta una integración TiendaNube.

#### `GET /api/tiendanube/integrations`
Lista todas las integraciones del cliente.

### 2. Webhooks Receiver (Solo entrada TN → CLIP)

#### `POST /api/tiendanube/webhooks/receiver`
Endpoint público que recibe webhooks de TiendaNube.

**Headers requeridos:**
- `X-Linkedstore-Hmac-Sha256`: Firma HMAC para verificación

**Payload ejemplo (product/created):**
```json
{
  "store_id": 123456,
  "event": "product/created",
  "id": 1948209
}
```

**Eventos soportados (todos son SOLO LECTURA):**
- `product/created` → Importar producto nuevo a CLIP
- `product/updated` → Actualizar datos + stock en CLIP
- `product/deleted` → Marcar como inactivo en CLIP (no eliminar)
- `order/paid` → Reducir stock si `sync_on_order_paid=true`
- `order/cancelled` → Restaurar stock
- `category/created` → Importar categoría nueva
- `category/updated` → Actualizar categoría
- `category/deleted` → Marcar categoría como inactiva

### 3. Importación Manual (Solo TN → CLIP)

#### `POST /api/tiendanube/import/full-catalog`
Importa todo el catálogo de productos desde TiendaNube.

**Body:**
```json
{
  "integration_id": "uuid",
  "import_images": true,
  "generate_embeddings": true,
  "overwrite_existing": false
}
```

**Respuesta:**
```json
{
  "success": true,
  "products_imported": 150,
  "products_updated": 23,
  "products_skipped": 5,
  "images_downloaded": 450,
  "embeddings_queued": 450,
  "categories_imported": 12,
  "errors": []
}
```

#### `POST /api/tiendanube/import/product/{tiendanube_product_id}`
Importa o actualiza un producto específico desde TiendaNube.

**Body:**
```json
{
  "integration_id": "uuid",
  "force_update": true
}
```

#### `GET /api/tiendanube/preview/product/{tiendanube_product_id}`
Vista previa de cómo se importará un producto (sin guardarlo).

**Respuesta:**
```json
{
  "tiendanube_data": { "name": "...", "variants": [...] },
  "clip_mapping": {
    "product_name": "Remera Roja M",
    "sku": "REM-M",
    "price": 2500.00,
    "stock": 10,
    "attributes": {"talla": "M", "color": "Rojo"},
    "category": "Remeras",
    "images": ["url1", "url2"]
  }
}
```

## 🔄 Flujos de Sincronización

### Flujo 1: Producto Nuevo en TiendaNube

```
1. Usuario crea producto en TiendaNube admin
   ↓
2. TiendaNube envía webhook: product/created
   ↓
3. CLIP recibe webhook → Valida HMAC
   ↓
4. Extrae store_id y product_id del payload
   ↓
5. Busca integration_id correspondiente
   ↓
6. Llama GET /products/{id} en TiendaNube API
   ↓
7. Mapea datos TiendaNube → CLIP:
   - name → product.name
   - description → product.attributes['descripcion']
   - variants → product.attributes (talla, color, etc.)
   - categories → busca/crea categoría en CLIP
   - images → descarga a Cloudinary
   ↓
8. Crea registro en products table
   ↓
9. Crea mapping en tiendanube_product_mapping
   ↓
10. Encola generación de embeddings CLIP
    ↓
11. Producto disponible para búsqueda visual
```

### Flujo 2: Stock Actualizado en TiendaNube

```
1. Comerciante actualiza stock en TiendaNube admin
   ↓
2. TiendaNube envía webhook: product/updated
   ↓
3. CLIP recibe webhook → Valida HMAC
   ↓
4. Llama GET /products/{id} para obtener datos actuales
   ↓
5. Actualiza stock en tabla products de CLIP
   ↓
6. Registra en log de sincronización
   ↓
7. Widget de búsqueda muestra stock actualizado
```

**IMPORTANTE:** Los productos gestionados por TiendaNube tienen el campo
`is_managed_by_tiendanube=true` y NO se pueden editar desde el admin de CLIP
(stock, precio, nombre, imágenes son READ-ONLY en CLIP).

### Flujo 3: Orden Pagada en TiendaNube

```
1. Cliente paga orden en TiendaNube
   ↓
2. TiendaNube envía webhook: order/paid
   ↓
3. CLIP recibe webhook
   ↓
4. Si sync_on_order_paid=false:
   - Solo loggea la orden
   - El stock ya se actualizó via product/updated
   ↓
5. Si sync_on_order_paid=true:
   - Extrae line_items de la orden
   - Por cada item:
     * Busca product_mapping
     * Reduce stock en CLIP
     * Registra venta en analytics (opcional)
   ↓
6. Responde 200 OK a TiendaNube

Nota: Normalmente sync_on_order_paid=false porque TiendaNube
ya reduce el stock automáticamente y envía product/updated.
```

## 🔐 Seguridad

### 1. Verificación HMAC
Todos los webhooks deben verificarse con HMAC SHA256:

```python
import hmac
import hashlib

def verify_tiendanube_webhook(payload: str, hmac_header: str, app_secret: str) -> bool:
    """Verifica la autenticidad de un webhook de TiendaNube."""
    expected_hmac = hmac.new(
        app_secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected_hmac, hmac_header)
```

### 2. OAuth 2.0 Flow

1. Registrar app en TiendaNube Partners
2. Obtener `app_id` y `app_secret`
3. Implementar flujo OAuth estándar
4. Almacenar tokens encriptados en BD

### 3. Rate Limiting

TiendaNube limita a **2 req/sec** con burst de 40:
- Implementar queue con Celery para importación inicial masiva
- Respetar headers: `x-rate-limit-remaining`, `x-rate-limit-reset`
- Retry con exponential backoff en 429 errors
- Los webhooks NO cuentan para rate limit (son push, no pull)

## 🗂️ Estructura de Archivos Nueva

```
clip_admin_backend/
├── app/
│   ├── blueprints/
│   │   ├── tiendanube/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py          # OAuth flow
│   │   │   ├── webhooks.py      # Webhook receiver
│   │   │   ├── sync.py          # Manual sync endpoints
│   │   │   └── admin.py         # Admin UI routes
│   ├── models/
│   │   ├── tiendanube_integration.py
│   │   ├── tiendanube_product_mapping.py
│   │   └── tiendanube_webhook_log.py
│   ├── services/
│   │   ├── tiendanube/
│   │   │   ├── __init__.py
│   │   │   ├── api_client.py        # TiendaNube API wrapper (solo GET)
│   │   │   ├── data_importer.py     # TN → CLIP data import
│   │   │   ├── webhook_processor.py # Procesar webhooks recibidos
│   │   │   ├── image_downloader.py  # Descargar imágenes → Cloudinary
│   │   │   └── oauth_manager.py     # OAuth 2.0 flow
│   └── templates/
│       └── tiendanube/
│           ├── integration_setup.html
│           ├── integration_status.html
│           └── sync_dashboard.html

shared/
└── tiendanube_config.py     # Configuración centralizada

migrations/
└── add_tiendanube_tables.py
```

## 📝 Mapeo de Datos: TiendaNube ↔ CLIP

### Producto Base

| TiendaNube | CLIP | Notas |
|------------|------|-------|
| `id` | Mapping table | No mapeo directo |
| `name.es` | `products.name` | Idioma principal |
| `description.es` | `attributes['descripcion']` | Como atributo dinámico |
| `handle.es` | Generar slug | Para URL amigable |
| `published` | `is_active` | Directo |
| `brand` | `attributes['marca']` | Si existe |
| `tags` | `attributes['tags']` | Separados por coma |
| `seo_title` | Ignorar | No usado en CLIP |
| `seo_description` | Ignorar | No usado en CLIP |

### Variantes → Atributos Dinámicos

TiendaNube usa `variants` con `attributes` y `values`:

```json
{
  "attributes": [{"es": "Talla"}, {"es": "Color"}],
  "variants": [
    {
      "id": 101,
      "values": [{"es": "M"}, {"es": "Rojo"}],
      "price": "2500.00",
      "stock": 10,
      "sku": "PROD-M-ROJO"
    }
  ]
}
```

**Mapeo a CLIP:**
1. Crear `product_attribute_config` para "talla" y "color" si no existen
2. Por cada variant:
   - Crear un producto CLIP separado (variant → product)
   - O: Usar JSONB `attributes` con array de variantes
   - Opción recomendada: **1 variant = 1 CLIP product** para mejor búsqueda

### Categorías

| TiendaNube | CLIP |
|------------|------|
| `categories[].id` | Mapping en `integration.category_mapping` |
| `categories[].name.es` | `categories.name` |
| `categories[].description.es` | `categories.description` |

**Estrategia:**
- Crear categorías CLIP automáticamente si no existen
- Admin puede reasignar manualmente
- Guardar mapping en JSONB para futuras sincronizaciones

### Imágenes

| TiendaNube | CLIP |
|------------|------|
| `images[].src` | Descargar y subir a Cloudinary |
| `images[].position` | `images.display_order` |
| Primer imagen | `is_primary=true` |

**Proceso:**
1. Descargar imagen desde URL de TiendaNube
2. Subir a Cloudinary con tag `tiendanube:{store_id}`
3. Crear registro en `images` table
4. Generar embedding CLIP en background

### Stock e Inventario

| TiendaNube | CLIP |
|------------|------|
| `variant.stock_management` | Siempre true en CLIP |
| `variant.stock` | `products.stock` (READ-ONLY) |
| `variant.price` | `products.price` (READ-ONLY) |
| `variant.sku` | `products.sku` (READ-ONLY) |

**Sincronización UNIDIRECCIONAL (TN → CLIP):**
- TN → CLIP: Via webhooks `product/updated` automáticamente
- CLIP Admin: Stock/precio de productos TN es READ-ONLY (se muestra pero no se puede editar)
- Widget: Usa stock sincronizado desde TN para mostrar disponibilidad

## 🎨 Interfaz de Usuario - Admin Panel

### 1. Página: Integraciones TiendaNube

**Ruta:** `/tiendanube/integrations`

**Contenido:**
- Card por cada integración activa
- Botón "Conectar Nueva Tienda"
- Estado de sincronización (última sync, errores)
- Botones de acción:
  - Sincronizar Ahora
  - Configurar Mapeos
  - Ver Logs
  - Desconectar

### 2. Modal: Configuración de Importación

**Contenido:**
- **Categorías:** Dropdown para mapear categorías TN → CLIP
- **Atributos:** Mapeo de attributes TN → product_attribute_config
- **Opciones de Importación:**
  - ☑ Auto-importar productos nuevos (via webhooks)
  - ☑ Auto-actualizar stock cuando cambie en TN
  - ☑ Reducir stock al recibir órdenes pagadas
  - ☑ Generar embeddings automáticamente
- **Webhooks registrados:** Lista de webhooks activos en TiendaNube
- **Advertencia:** "Los productos de TiendaNube no pueden editarse desde CLIP"

### 3. Dashboard de Sincronización

**Ruta:** `/tiendanube/sync-dashboard`

**Métricas:**
- Productos sincronizados: 450 / 500
- Última sincronización: Hace 2 horas
- Errores pendientes: 3
- Webhooks recibidos (últimas 24h): 127

**Tabla de Productos:**
| Producto CLIP | SKU | TiendaNube ID | Estado | Última Importación | Editable |
|---------------|-----|---------------|--------|-------------------|----------|
| Remera Roja M | REM-M | 12345 | ✅ Activo | 10 min | 🔒 No (TN) |
| Jean Azul 32 | JEAN-32 | 12346 | ✅ Activo | 15 min | 🔒 No (TN) |
| Zapatillas Runner | - | - | ✅ Activo | Manual | ✏️ Sí (CLIP) |

## 🛠️ Implementación por Fases

### Fase 1: Infraestructura Base (Semana 1)
- [ ] Crear tablas de BD
- [ ] Implementar modelos SQLAlchemy
- [ ] Blueprint básico `/api/tiendanube`
- [ ] OAuth flow completo
- [ ] Almacenamiento seguro de tokens

### Fase 2: Webhooks y Sincronización Básica (Semana 2)
- [ ] Endpoint webhook receiver
- [ ] Verificación HMAC
- [ ] Procesamiento de `product/created`, `product/updated`
- [ ] Data mapper: TiendaNube → CLIP
- [ ] Descarga y subida de imágenes
- [ ] Tests unitarios

### Fase 3: Sistema de Importación Continua (Semana 3)
- [ ] Procesamiento de webhooks en background (Celery)
- [ ] Rate limiting para importación masiva
- [ ] Webhook `order/paid` → reducir stock (opcional)
- [ ] Sistema de cola para embeddings
- [ ] Logs y auditoría completa
- [ ] Manejo de productos desactivados en TN

### Fase 4: UI de Administración (Semana 4)
- [ ] Página de integraciones
- [ ] Modal de configuración de importación
- [ ] Dashboard de sincronización
- [ ] Vista READ-ONLY para productos TiendaNube
- [ ] Badge "Gestionado por TiendaNube" en UI
- [ ] Sistema de notificaciones de errores
- [ ] Documentación para usuarios

### Fase 5: Testing y Optimización (Semana 5)
- [ ] Tests de integración
- [ ] Tests end-to-end con tienda de prueba
- [ ] Optimización de embeddings batch
- [ ] Monitoreo y alertas
- [ ] Documentación técnica completa

## ⚠️ Consideraciones Importantes

### Límites de TiendaNube
- **Rate limit:** 2 req/sec, burst 40 (planes altos x10)
- **Webhook retry:** 18 intentos en 48 horas
- **Timeout webhooks:** 10 segundos
- **Max productos:** 100,000 por tienda
- **Max imágenes por producto:** 250
- **Max variantes por producto:** 1,000

### Manejo de Errores
1. **Webhook falla:** Guardar payload, reintentar después
2. **API TN falla:** Exponential backoff, max 5 reintentos
3. **Imagen no descarga:** Marcar producto, continuar con otros
4. **Embedding falla:** Retry en background, no bloquear sync

### Performance
- Procesar webhooks asíncronamente (Celery)
- Batch de embeddings: Max 50 imágenes por job
- Sync inicial: Paginación de 100 productos
- Cache de tokens OAuth en Redis

### Casos Edge
- **Producto duplicado:** Verificar por SKU antes de crear, actualizar si existe
- **Categoría no mapeada:** Crear automáticamente con mismo nombre de TN
- **Imagen sin URL válida:** Skip imagen, loggear advertencia, continuar
- **Stock negativo en TN:** Ajustar a 0 en CLIP
- **Producto eliminado en TN:** Marcar `is_active=false` en CLIP (no eliminar registro)
- **Intentar editar producto TN desde CLIP:** Bloquear con mensaje "Producto gestionado por TiendaNube"
- **Integración desconectada:** Mantener productos pero mostrar warning en UI

## 🔗 Referencias

- **TiendaNube API Docs:** https://tiendanube.github.io/api-documentation/
- **OAuth 2.0:** https://oauth.net/2/
- **Webhooks Best Practices:** https://webhooks.fyi/
- **HMAC Verification:** https://en.wikipedia.org/wiki/HMAC

## 📞 Soporte

Para dudas sobre la integración:
- TiendaNube BR: parceiros@nuvemshop.com.br
- TiendaNube AR/MX: socios@tiendanube.com

---

## 🎓 Reglas de Negocio Importantes

### 1. Separación de Productos
```
┌─────────────────────────────────────────────────────────────┐
│                     Base de Datos CLIP                       │
├─────────────────────────────────────────────────────────────┤
│  Productos Tradicionales (is_managed_by_tiendanube=false)   │
│  - Editables desde CLIP Admin                               │
│  - Gestión completa de stock, precio, imágenes             │
│  - Sin restricciones                                        │
├─────────────────────────────────────────────────────────────┤
│  Productos TiendaNube (is_managed_by_tiendanube=true)      │
│  - READ-ONLY en CLIP Admin                                  │
│  - Badge "🔒 Gestionado por TiendaNube"                    │
│  - Solo se actualizan via webhooks                         │
│  - Intentar editar → Error con link a TiendaNube           │
└─────────────────────────────────────────────────────────────┘
```

### 2. Flujo de Usuario Típico

**Setup inicial:**
1. Cliente CLIP conecta su TiendaNube (OAuth)
2. Sistema importa catálogo completo (puede tomar tiempo)
3. Descarga imágenes a Cloudinary
4. Genera embeddings CLIP en background
5. Productos disponibles para búsqueda visual

**Operación diaria:**
1. Cliente gestiona todo desde TiendaNube (su admin normal)
2. Cambios → Webhooks → CLIP se actualiza automáticamente
3. Widget de búsqueda visual siempre tiene datos actualizados
4. Cliente CLIP ve productos en dashboard (solo lectura)

### 3. Ventajas de este Enfoque

✅ **Simplicidad:** No hay conflictos de sincronización bidireccional
✅ **Fuente única de verdad:** TiendaNube es la fuente, CLIP es consumidor
✅ **Sin errores de desincronización:** Webhooks garantizan actualización inmediata
✅ **Menos API calls:** Solo lecturas iniciales, el resto via webhooks push
✅ **UX clara:** Usuario sabe que TiendaNube es donde gestiona productos

---

**Próximos pasos:** Comenzar con Fase 1 - Crear tablas de BD y estructura básica del blueprint.
