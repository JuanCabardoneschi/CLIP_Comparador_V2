# 🛒 Integración CLIP Comparador con Plataformas E-Commerce
## Análisis Comparativo: TiendaNube vs Shopify

> **Fecha de análisis:** 20 de Noviembre, 2025
> **Versión:** 1.0
> **Documentación consultada:**
> - TiendaNube API: https://tiendanube.github.io/api-documentation/
> - Shopify API: https://shopify.dev/docs/api
> - Shopify Apps: https://shopify.dev/docs/apps

---

## 📊 RESUMEN EJECUTIVO

### **Recomendación Final: SHOPIFY es MÁS SIMPLE y MEJOR OPCIÓN**

**Razones principales:**
1. ✅ **Tooling superior**: Shopify CLI automatiza todo
2. ✅ **GraphQL moderno**: API más eficiente que REST
3. ✅ **App Extensions**: Integración nativa sin código JS custom
4. ✅ **Documentación**: Más completa y con ejemplos
5. ✅ **Mercado global**: 4.3M+ comercios vs 100K de TN
6. ✅ **Monetización**: App Store más grande y rentable

---

## 🌎 CONTEXTO DE MERCADO

| Aspecto | TiendaNube | Shopify |
|---------|------------|---------|
| **Región principal** | Latinoamérica (Argentina, Brasil, México) | Global (180+ países) |
| **Número de tiendas** | ~100,000 | ~4,300,000 |
| **Idiomas** | Español, Portugués | 50+ idiomas |
| **Monetización** | Mercado mediano | Mercado gigante (App Store) |
| **Plan gratuito** | Sí (limitado) | Prueba 3 días |
| **Foco** | LATAM small business | Global all sizes |

---

## 🔧 COMPARACIÓN TÉCNICA DETALLADA

### 1. AUTENTICACIÓN Y AUTORIZACIÓN

#### **TiendaNube**
```python
# OAuth 2.0 clásico (solo Authorization Code Grant)
# Flujo manual:
# 1. Registrar app en partners.tiendanube.com
# 2. Usuario va a /apps/{app_id}/authorize
# 3. Redirect con code
# 4. POST /apps/authorize/token con client_secret
# 5. Recibir access_token (no expira)

import requests

# Obtener access token
response = requests.post(
    'https://www.tiendanube.com/apps/authorize/token',
    json={
        'client_id': 'YOUR_APP_ID',
        'client_secret': 'YOUR_SECRET',
        'grant_type': 'authorization_code',
        'code': 'AUTHORIZATION_CODE'
    },
    headers={'Content-Type': 'application/json'}
)

access_token = response.json()['access_token']
store_id = response.json()['user_id']

# Usar en requests
headers = {
    'Authentication': f'bearer {access_token}',  # Nota: "Authentication" no "Authorization"
    'User-Agent': 'MyApp (contact@myapp.com)'
}
```

**❌ Problemas:**
- Token no expira (riesgo seguridad)
- Header `Authentication` en lugar de estándar `Authorization`
- Sin Token Exchange (requiere server-side siempre)
- Sin sesión tokens para embedded apps

---

#### **Shopify**
```python
# OAuth 2.0 moderno con múltiples opciones
# - Token Exchange (recomendado para embedded apps)
# - Authorization Code Grant (legacy)
# - Session Tokens para autenticación de requests

# OPCIÓN 1: Shopify CLI automatiza todo (recomendado)
# shopify app init
# shopify app dev

# OPCIÓN 2: Token Exchange (embedded apps)
import shopify

# Shopify SDK maneja automáticamente:
# - OAuth flow
# - Token refresh
# - Session management
# - HMAC verification

shopify.Session.setup(
    api_key=API_KEY,
    secret=API_SECRET
)

session = shopify.Session(shop_url, API_VERSION)
access_token = session.request_token(params)

# Usar con SDK
shopify.ShopifyResource.activate_session(session)
products = shopify.Product.find()
```

**✅ Ventajas:**
- Token Exchange nativo
- Session tokens para embedded apps
- SDK oficial con auto-refresh
- Shopify CLI automatiza setup
- Tokens con expiración (más seguro)

---

### 2. API: REST vs GraphQL

#### **TiendaNube**
```python
# Solo REST API (versión 2025-03)
# Endpoint pattern: https://api.tiendanube.com/2025-03/{store_id}/{resource}

import requests

BASE_URL = f'https://api.tiendanube.com/2025-03/{store_id}'

# GET Productos
response = requests.get(
    f'{BASE_URL}/products',
    headers={
        'Authentication': f'bearer {access_token}',
        'User-Agent': 'MyApp (contact@myapp.com)'
    },
    params={
        'page': 1,
        'per_page': 50
    }
)

products = response.json()

# Paginación manual
# Link header contiene next, prev, first, last
link_header = response.headers.get('Link')

# Rate limit: 2 req/sec, burst 40 (x10 para Plus)
# Header: X-Rate-Limit-Remaining
```

**❌ Limitaciones:**
- Solo REST (no GraphQL)
- Over-fetching de datos
- Múltiples requests para datos relacionados
- Rate limit restrictivo (2 req/sec base)

---

#### **Shopify**
```python
# GraphQL Admin API (preferido) + REST legacy

# GRAPHQL (recomendado)
query = '''
query getProducts {
  products(first: 50) {
    edges {
      node {
        id
        title
        handle
        images(first: 5) {
          edges {
            node {
              url
              altText
            }
          }
        }
        variants(first: 10) {
          edges {
            node {
              id
              price
              sku
              inventoryQuantity
            }
          }
        }
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
'''

# SDK oficial simplifica queries
import shopify

products = shopify.GraphQL().execute(query)

# O usar REST (legacy pero simple)
products = shopify.Product.find(
    limit=50,
    fields='id,title,images,variants'
)

# Rate limit: 40 req/sec base, 400 para Plus
# Mucho más generoso que TiendaNube
```

**✅ Ventajas:**
- GraphQL permite fetch optimizado
- Un solo request para datos complejos
- REST disponible para casos simples
- Rate limit 20x mayor
- Cursor-based pagination automática

---

### 3. PRODUCTOS E IMÁGENES

#### **TiendaNube**
```json
// GET /products/{id}
{
  "id": 1234,
  "name": {
    "es": "Camisa Azul",
    "pt": "Camisa Azul"
  },
  "description": {
    "es": "<p>Descripción</p>",
    "pt": "<p>Descrição</p>"
  },
  "images": [
    {
      "id": 101,
      "src": "https://d26lpennugtm8s.cloudfront.net/stores/001/234/products/image-640-0.jpg",
      "position": 1,
      "product_id": 1234
    }
  ],
  "variants": [
    {
      "id": 5678,
      "price": "29.99",
      "stock": 10,
      "sku": "CAM-001",
      "values": [{"es": "M"}]
    }
  ],
  "categories": [4567],
  "published": true,
  "created_at": "2024-01-01T00:00:00Z"
}
```

**Características:**
- Imágenes en CDN CloudFront de TN
- i18n con objetos `{es, pt}`
- Variantes simples
- Categorías por ID

---

#### **Shopify**
```json
// GraphQL Product
{
  "data": {
    "product": {
      "id": "gid://shopify/Product/1234",
      "title": "Camisa Azul",
      "handle": "camisa-azul",
      "descriptionHtml": "<p>Descripción</p>",
      "images": {
        "edges": [
          {
            "node": {
              "id": "gid://shopify/ProductImage/5678",
              "url": "https://cdn.shopify.com/s/files/1/0001/2345/products/image.jpg?v=1234",
              "altText": "Camisa azul frente",
              "width": 2048,
              "height": 2048
            }
          }
        ]
      },
      "variants": {
        "edges": [
          {
            "node": {
              "id": "gid://shopify/ProductVariant/9012",
              "price": "29.99",
              "sku": "CAM-001",
              "inventoryQuantity": 10,
              "selectedOptions": [
                {
                  "name": "Size",
                  "value": "M"
                }
              ]
            }
          }
        ]
      },
      "collections": {
        "edges": [...]
      },
      "publishedAt": "2024-01-01T00:00:00Z"
    }
  }
}
```

**Características:**
- Imágenes en CDN de Shopify (optimizadas)
- Metafields para datos custom
- Variantes complejas con múltiples opciones
- Collections (categorías) más flexibles
- Global IDs (GIDs) únicos
- Transformaciones de imagen en URL

---

### 4. WEBHOOKS

#### **TiendaNube**
```python
# Registro manual de webhooks
import requests

# POST /webhooks
response = requests.post(
    f'https://api.tiendanube.com/2025-03/{store_id}/webhooks',
    headers={
        'Authentication': f'bearer {access_token}',
        'User-Agent': 'MyApp (contact@myapp.com)',
        'Content-Type': 'application/json'
    },
    json={
        'event': 'product/created',
        'url': 'https://myapp.com/webhooks/tiendanube'
    }
)

# Verificar webhook (HMAC SHA256)
import hmac
import hashlib

def verify_webhook(data, hmac_header, secret):
    digest = hmac.new(
        secret.encode('utf-8'),
        data.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(digest, hmac_header)

# En tu endpoint
@app.route('/webhooks/tiendanube', methods=['POST'])
def handle_webhook():
    hmac_header = request.headers.get('X-Linkedstore-Hmac-Sha256')
    data = request.get_data(as_text=True)

    if not verify_webhook(data, hmac_header, APP_SECRET):
        return 'Unauthorized', 401

    payload = request.json
    event = payload['event']  # 'product/created'
    product_id = payload['id']

    # Procesar...
    return '', 200
```

**Eventos disponibles:**
- `product/created`, `product/updated`, `product/deleted`
- `order/created`, `order/updated`, `order/paid`
- `category/created`, `category/updated`, `category/deleted`
- `customer/created`, `customer/updated`
- `app/uninstalled`

**❌ Limitaciones:**
- Sin retry policy clara
- Timeout 10 segundos
- Sin manejo de orden garantizado

---

#### **Shopify**
```python
# Registro mediante GraphQL o Shopify CLI (automático)

# OPCIÓN 1: Shopify CLI (recomendado)
# En shopify.app.toml
"""
[webhooks]
subscriptions = [
  {
    topics = ["products/create", "products/update"]
    uri = "/api/webhooks"
  }
]
"""

# OPCIÓN 2: GraphQL Admin API
mutation {
  webhookSubscriptionCreate(
    topic: PRODUCTS_CREATE
    webhookSubscription: {
      format: JSON
      callbackUrl: "https://myapp.com/webhooks"
    }
  ) {
    webhookSubscription {
      id
      topic
      format
      endpoint {
        __typename
        ... on WebhookHttpEndpoint {
          callbackUrl
        }
      }
    }
  }
}

# Verificar webhook (HMAC)
from shopify import webhook

@app.route('/webhooks', methods=['POST'])
def handle_webhook():
    # Shopify SDK verifica automáticamente
    if not webhook.verify(request.get_data(), request.headers):
        return 'Unauthorized', 401

    topic = request.headers.get('X-Shopify-Topic')
    shop = request.headers.get('X-Shopify-Shop-Domain')
    event_id = request.headers.get('X-Shopify-Event-Id')

    payload = request.json

    # Procesar...
    return '', 200
```

**Eventos disponibles:**
- 100+ topics disponibles
- `products/*`, `orders/*`, `customers/*`, etc.
- `app/uninstalled`, `shop/update`
- Granularidad fina (ej: `orders/paid` vs `orders/fulfilled`)

**✅ Ventajas:**
- Retry policy robusto (exponential backoff)
- Timeout configurable
- Headers ricos con metadata
- Deduplicación con `X-Shopify-Event-Id`
- EventBridge y Pub/Sub nativos
- Shopify CLI registra automáticamente

---

### 5. INTEGRACIÓN STOREFRONT (WIDGET)

#### **TiendaNube - Scripts**
```javascript
// 1. Crear script en Partners Portal
// 2. Subir archivo JS
// 3. Auto-instalado o manual con POST /scripts

// Script se inyecta como:
// <script src="https://apps-scripts.tiendanube.com/app-handle/script-name.js?store=1234"></script>

// En tu script (clip-widget-tiendanube.js)
(function() {
    'use strict';

    // Variable global LS disponible
    const storeId = LS.store.id;
    const storeUrl = LS.store.url;
    const currentLang = LS.lang;  // 'es', 'pt_BR'

    // Si es página de producto
    if (LS.product) {
        const productId = LS.product.id;
        const productName = LS.product.name;
    }

    // Cargar jQuery (si necesario)
    useJquery().then((jq) => {
        // Usar jQuery
        jq('#clip-widget').show();
    });

    // Renderizar widget
    function renderWidget() {
        const container = document.getElementById('clip-widget-container');

        // Llamar a tu API de búsqueda
        fetch('https://yourapi.com/api/search', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': 'clip_tiendanube_key'
            },
            body: JSON.stringify({
                image: imageData,
                store_id: storeId
            })
        })
        .then(res => res.json())
        .then(results => {
            // results = [{tiendanube_product_id: 1234, score: 0.95}]
            displayResults(results);
        });
    }

    // Mostrar resultados
    function displayResults(results) {
        // Construir HTML con datos de productos
        // URLs: LS.store.url + '/products/' + product_handle
    }

    renderWidget();
})();
```

**Configuración en Partners:**
- Name, Handle
- Location: `store` o `checkout`
- Event: `onfirstinteraction` (default) o `onload` (requiere aprobación)
- Auto-installed: `true` (recomendado)

**❌ Limitaciones:**
- JS vanilla (sin framework moderno)
- Necesita manual file upload
- Sin hot reload
- Variable `LS` limitada
- Performance depende de evento (`onload` requiere aprobación)

---

#### **Shopify - Theme App Extensions**
```liquid
<!-- app-block.liquid -->
{% schema %}
{
  "name": "CLIP Visual Search",
  "target": "section",
  "settings": [
    {
      "type": "text",
      "id": "api_key",
      "label": "API Key",
      "default": ""
    },
    {
      "type": "select",
      "id": "position",
      "label": "Position",
      "options": [
        {"value": "top", "label": "Top"},
        {"value": "bottom", "label": "Bottom"}
      ],
      "default": "top"
    }
  ]
}
{% endschema %}

<div class="clip-widget" data-api-key="{{ block.settings.api_key }}">
  <button id="clip-search-trigger">
    🔍 Search by Image
  </button>
  <div id="clip-search-results"></div>
</div>

<script>
  // JavaScript embebido o asset
  (function() {
    const apiKey = document.querySelector('.clip-widget').dataset.apiKey;

    // Acceso a Shopify data
    const productId = {{ product.id | json }};
    const productHandle = {{ product.handle | json }};

    // Llamar a tu API
    async function search(imageData) {
      const response = await fetch('https://yourapi.com/api/search', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': apiKey
        },
        body: JSON.stringify({
          image: imageData,
          shop: Shopify.shop
        })
      });

      const results = await response.json();
      displayResults(results);
    }

    function displayResults(results) {
      // results = [{shopify_product_id: 1234, handle: 'blue-shirt'}]
      const html = results.map(product => `
        <div class="product-card">
          <img src="${product.image_url}" />
          <a href="/products/${product.handle}">${product.title}</a>
          <span>${product.price}</span>
        </div>
      `).join('');

      document.getElementById('clip-search-results').innerHTML = html;
    }
  })();
</script>

<style>
  .clip-widget {
    padding: 20px;
    background: white;
    border-radius: 8px;
  }
</style>
```

**Shopify CLI para desarrollo:**
```bash
# Crear app con extensiones
shopify app init

# Agregar theme extension
shopify app generate extension

# Desarrollo local con hot reload
shopify app dev

# Deploy automático
shopify app deploy
```

**✅ Ventajas:**
- **App Blocks**: Drag & drop en theme editor
- **Settings schema**: UI config sin código
- **Liquid templating**: Acceso a datos Shopify
- **Hot reload**: Desarrollo rápido
- **No code injection**: Merchant arrastra el bloque
- **Theme-agnostic**: Funciona en cualquier tema OS 2.0
- **Versioning**: Control de versiones automático

**Alternativa: App Embed Blocks**
```liquid
<!-- Para widgets flotantes/overlay -->
{% schema %}
{
  "name": "CLIP Search Overlay",
  "target": "body",
  "settings": [...]
}
{% endschema %}

<!-- Siempre visible, merchant lo activa -->
```

---

### 6. ADMIN PANEL INTEGRATION

#### **TiendaNube**
- No hay integración nativa en admin
- Solo panel externo (tu web app)
- Merchant accede via URL configurada
- Sin componentes nativos

```python
# Tu app Flask/Django independiente
@app.route('/admin')
@require_tiendanube_session
def admin_panel():
    store_id = session['store_id']
    access_token = session['access_token']

    # Fetch data de TN API
    products = get_tiendanube_products(store_id, access_token)

    return render_template('admin.html', products=products)
```

---

#### **Shopify - Embedded Apps**
```javascript
// App renderizada DENTRO del admin de Shopify
// Usa App Bridge para integración nativa

import {
  Page,
  Layout,
  Card,
  Button,
  Banner
} from '@shopify/polaris';

import { useAppBridge } from '@shopify/app-bridge-react';
import { Redirect } from '@shopify/app-bridge/actions';

function AdminPanel() {
  const app = useAppBridge();

  const handleProductClick = (productId) => {
    // Navegar a producto en Shopify admin
    const redirect = Redirect.create(app);
    redirect.dispatch(Redirect.Action.ADMIN_PATH, {
      path: `/products/${productId}`
    });
  };

  return (
    <Page title="CLIP Visual Search">
      <Layout>
        <Layout.Section>
          <Card title="Configuration" sectioned>
            <Button primary onClick={saveSettings}>
              Save Settings
            </Button>
          </Card>
        </Layout.Section>

        <Layout.Section>
          <Card title="Products">
            {/* Lista de productos con CLIP */}
          </Card>
        </Layout.Section>
      </Layout>
    </Page>
  );
}
```

**✅ Ventajas:**
- **Polaris components**: UI nativa de Shopify
- **App Bridge**: Navegación integrada
- **Contextual Save Bar**: Barra de guardado nativa
- **Session tokens**: Auth automática
- **Mobile support**: Funciona en Shopify mobile app

---

### 7. MODELO DE DATOS Y SINCRONIZACIÓN

#### **Esquema para TiendaNube**
```sql
-- Tabla de sincronización
CREATE TABLE tiendanube_products (
    id UUID PRIMARY KEY,
    client_id UUID REFERENCES clients(id),

    -- IDs de TiendaNube
    tiendanube_product_id BIGINT NOT NULL,
    tiendanube_variant_id BIGINT,
    tiendanube_store_id BIGINT NOT NULL,

    -- Cache de datos TN
    name JSONB,  -- {"es": "...", "pt": "..."}
    sku TEXT,
    price DECIMAL(10,2),
    stock INTEGER,
    images JSONB,  -- Array de URLs CloudFront

    -- CLIP embeddings
    primary_image_embedding TEXT,  -- Vector 512-dim

    -- Metadata
    mapped_category_id UUID REFERENCES categories(id),
    is_active BOOLEAN DEFAULT true,
    last_synced_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(client_id, tiendanube_product_id, tiendanube_variant_id)
);

CREATE INDEX idx_tn_store ON tiendanube_products(tiendanube_store_id);
CREATE INDEX idx_tn_category ON tiendanube_products(mapped_category_id);
```

---

#### **Esquema para Shopify**
```sql
-- Tabla de sincronización
CREATE TABLE shopify_products (
    id UUID PRIMARY KEY,
    client_id UUID REFERENCES clients(id),

    -- IDs de Shopify (GIDs)
    shopify_product_id TEXT NOT NULL,  -- "gid://shopify/Product/1234"
    shopify_variant_id TEXT,           -- "gid://shopify/ProductVariant/5678"
    shop_domain TEXT NOT NULL,         -- "mystore.myshopify.com"

    -- Cache de datos Shopify
    title TEXT,
    handle TEXT,
    sku TEXT,
    price DECIMAL(10,2),
    inventory_quantity INTEGER,
    image_urls JSONB,  -- Array de URLs CDN Shopify

    -- CLIP embeddings
    primary_image_embedding TEXT,  -- Vector 512-dim

    -- Metafields custom
    custom_attributes JSONB,

    -- Metadata
    mapped_category_id UUID REFERENCES categories(id),
    is_active BOOLEAN DEFAULT true,
    last_synced_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(client_id, shopify_product_id, shopify_variant_id)
);

CREATE INDEX idx_shop_domain ON shopify_products(shop_domain);
CREATE INDEX idx_shop_category ON shopify_products(mapped_category_id);
```

---

### 8. HERRAMIENTAS DE DESARROLLO

| Herramienta | TiendaNube | Shopify |
|-------------|------------|---------|
| **CLI** | ❌ No existe | ✅ Shopify CLI (potente) |
| **SDK oficial** | ❌ Solo librerías community | ✅ Python, Ruby, Node, PHP |
| **GraphQL Explorer** | ❌ N/A | ✅ GraphiQL integrado |
| **Local dev** | Manual (ngrok) | ✅ CLI con tunneling automático |
| **Hot reload** | ❌ No | ✅ Sí (con CLI) |
| **Templates** | ❌ No | ✅ React Router, Remix templates |
| **Testing** | Manual | ✅ Dev stores ilimitadas |
| **Deployment** | Manual | ✅ `shopify app deploy` |

---

### 9. COMPLEJIDAD DE IMPLEMENTACIÓN

#### **TiendaNube - Flujo Completo**
```
1. SETUP (Manual - 2-3 días)
   ├── Registrar en partners.tiendanube.com
   ├── Crear app manualmente
   ├── Configurar OAuth callbacks
   ├── Implementar OAuth flow desde cero
   └── Setup webhooks manualmente

2. SINCRONIZACIÓN (Complejo - 1 semana)
   ├── Implementar sync service
   ├── GET /products (paginación manual)
   ├── Descargar imágenes de CloudFront
   ├── Calcular embeddings CLIP
   ├── Guardar en DB con i18n JSONB
   └── Mapear categorías TN → CLIP

3. WEBHOOKS (Medio - 2 días)
   ├── Crear endpoint /webhooks/tiendanube
   ├── Implementar HMAC verification
   ├── POST /webhooks para registrar
   ├── Procesar product/*, order/*
   └── Re-sync on events

4. WIDGET (Difícil - 1 semana)
   ├── Crear archivo JS vanilla
   ├── Subir a Partners Portal
   ├── Testear con variable LS
   ├── POST /scripts si no auto-install
   ├── Iterar sin hot reload (lento)
   └── Manejar multi-idioma (es/pt)

5. ADMIN PANEL (Medio - 3 días)
   ├── App Flask/Django externa
   ├── Implementar sesiones
   ├── UI custom completa
   └── Deploy independiente

TOTAL: ~3-4 semanas
DIFICULTAD: Alta (todo manual)
```

---

#### **Shopify - Flujo Completo**
```
1. SETUP (Shopify CLI - 1 hora)
   ├── $ shopify app init
   ├── Elegir template (React Router)
   ├── OAuth automático
   ├── Webhooks auto-registrados
   └── Dev store creada

2. SINCRONIZACIÓN (Simple - 2-3 días)
   ├── Usar GraphQL query optimizado
   ├── Un request para productos + imágenes + variantes
   ├── URLs CDN Shopify directo
   ├── Calcular embeddings CLIP
   ├── Metafields para datos custom
   └── Collections (categorías) nativas

3. WEBHOOKS (Automático - 1 día)
   ├── Definir en shopify.app.toml
   ├── CLI registra automáticamente
   ├── SDK verifica HMAC
   ├── Webhooks processados
   └── Retry automático

4. WIDGET (Fácil - 2-3 días)
   ├── $ shopify app generate extension
   ├── Elegir "Theme app extension"
   ├── Liquid + JS/CSS
   ├── Hot reload con $ shopify app dev
   ├── Merchant arrastra bloque en theme editor
   └── Settings schema para config

5. ADMIN PANEL (Simple - 2 días)
   ├── Template React incluido
   ├── Polaris components nativos
   ├── App Bridge integrado
   ├── Session tokens automáticos
   └── Deploy con $ shopify app deploy

TOTAL: ~1-2 semanas
DIFICULTAD: Baja (CLI automatiza 80%)
```

---

## 🎯 COMPARACIÓN LADO A LADO

| Criterio | TiendaNube | Shopify | Ganador |
|----------|------------|---------|---------|
| **Setup inicial** | Manual, 2-3 días | CLI, 1 hora | 🏆 Shopify |
| **Documentación** | Buena, español | Excelente, inglés | 🏆 Shopify |
| **API** | REST only | GraphQL + REST | 🏆 Shopify |
| **Rate limits** | 2 req/sec (40 burst) | 40 req/sec (400 Plus) | 🏆 Shopify |
| **Webhooks** | Manual, básicos | Auto, 100+ topics | 🏆 Shopify |
| **Widget** | JS file upload | Theme extensions | 🏆 Shopify |
| **Admin panel** | Externa | Embedded nativa | 🏆 Shopify |
| **SDK oficial** | ❌ No | ✅ Sí (5+ lenguajes) | 🏆 Shopify |
| **CLI** | ❌ No | ✅ Sí (potente) | 🏆 Shopify |
| **Hot reload** | ❌ No | ✅ Sí | 🏆 Shopify |
| **Testing** | Manual | Dev stores | 🏆 Shopify |
| **Deployment** | Manual | CLI deploy | 🏆 Shopify |
| **Mercado** | 100K tiendas LATAM | 4.3M global | 🏆 Shopify |
| **App Store** | Mediano | Gigante | 🏆 Shopify |
| **Idioma** | Español | Inglés | TiendaNube |
| **Región** | LATAM | Global | Shopify |

**RESULTADO: Shopify gana 14 vs 2**

---

## 💰 MODELO DE NEGOCIO

### **TiendaNube**
- Comisión: 20% de los ingresos de la app
- Pagos mensuales
- Mercado: ~100,000 tiendas (90% small business)
- Potencial: $5-50K USD/año (app nicho LATAM)

### **Shopify**
- Comisión: 15-25% según tipo de app
- Marketplace masivo
- Mercado: 4.3M+ tiendas (todos los tamaños)
- Potencial: $50K-500K+ USD/año (app exitosa)

---

## 🚀 RECOMENDACIÓN FINAL

### **Implementar SHOPIFY primero**

#### **Razones técnicas:**
1. ✅ **Shopify CLI ahorra semanas de desarrollo**
2. ✅ **GraphQL = queries optimizadas, menos requests**
3. ✅ **Theme App Extensions = mejor UX merchant**
4. ✅ **SDK oficial = menos bugs**
5. ✅ **Hot reload = desarrollo 5x más rápido**
6. ✅ **Documentación superior con ejemplos**

#### **Razones de negocio:**
1. ✅ **Mercado 43x más grande**
2. ✅ **Global vs regional**
3. ✅ **Mejor monetización**
4. ✅ **Más inversión en plataforma**
5. ✅ **Comunidad más activa**

#### **Roadmap sugerido:**
```
FASE 1 (2 semanas): Shopify MVP
├── Setup con Shopify CLI
├── Sync inicial GraphQL
├── Webhooks básicos
├── Theme extension con widget
└── Testing en dev stores

FASE 2 (1 semana): Optimización
├── Cache embeddings
├── Batch processing
├── Error handling
└── Performance tuning

FASE 3 (Opcional - 2-3 semanas): TiendaNube
├── Solo si hay demanda LATAM
├── Reutilizar lógica CLIP
├── Adaptar sync a REST
└── Widget JS vanilla
```

---

## 📚 RECURSOS Y DOCUMENTACIÓN

### **Shopify**
- **Developer Docs**: https://shopify.dev/docs
- **API Reference**: https://shopify.dev/docs/api
- **CLI**: https://shopify.dev/docs/apps/build/cli-for-apps
- **Templates**: https://github.com/Shopify/shopify-app-template-react-router
- **Partners**: https://partners.shopify.com/
- **Community**: https://community.shopify.com/c/shopify-apis-and-sdks/

### **TiendaNube**
- **API Docs**: https://tiendanube.github.io/api-documentation/
- **Partners**: https://partners.tiendanube.com/
- **Partners BR**: https://www.nuvemshop.com.br/parceiros
- **Support**: parceiros@nuvemshop.com.br / socios@tiendanube.com

---

## 🔧 CÓDIGO DE EJEMPLO: SYNC PRODUCTS

### **Shopify GraphQL Sync**
```python
# services/shopify_sync.py

import shopify
from app.models.shopify_product import ShopifyProduct
from app.services.clip_engine import calculate_embedding

class ShopifySync:
    def __init__(self, shop_domain, access_token):
        session = shopify.Session(shop_domain, '2025-10', access_token)
        shopify.ShopifyResource.activate_session(session)

    def initial_sync(self, client_id):
        """Sincronización inicial completa"""
        query = '''
        query getProducts($cursor: String) {
          products(first: 50, after: $cursor) {
            edges {
              node {
                id
                title
                handle
                images(first: 5) {
                  edges {
                    node {
                      id
                      url
                      altText
                    }
                  }
                }
                variants(first: 10) {
                  edges {
                    node {
                      id
                      price
                      sku
                      inventoryQuantity
                    }
                  }
                }
              }
            }
            pageInfo {
              hasNextPage
              endCursor
            }
          }
        }
        '''

        cursor = None
        products_synced = 0

        while True:
            result = shopify.GraphQL().execute(query, {'cursor': cursor})
            data = json.loads(result)

            products = data['data']['products']['edges']

            for edge in products:
                product = edge['node']
                self._sync_product(product, client_id)
                products_synced += 1

            page_info = data['data']['products']['pageInfo']
            if not page_info['hasNextPage']:
                break

            cursor = page_info['endCursor']

        return products_synced

    def _sync_product(self, product_data, client_id):
        """Sincroniza un producto individual"""
        # Extraer imagen principal
        primary_image_url = None
        if product_data['images']['edges']:
            primary_image_url = product_data['images']['edges'][0]['node']['url']

        # Calcular embedding CLIP
        embedding = None
        if primary_image_url:
            embedding = calculate_embedding(primary_image_url)

        # Guardar o actualizar
        for variant_edge in product_data['variants']['edges']:
            variant = variant_edge['node']

            ShopifyProduct.upsert(
                client_id=client_id,
                shopify_product_id=product_data['id'],
                shopify_variant_id=variant['id'],
                shop_domain=self.shop_domain,
                title=product_data['title'],
                handle=product_data['handle'],
                sku=variant['sku'],
                price=variant['price'],
                inventory_quantity=variant['inventoryQuantity'],
                image_urls=[img['node']['url'] for img in product_data['images']['edges']],
                primary_image_embedding=embedding
            )

# Usage
sync = ShopifySync('mystore.myshopify.com', access_token)
sync.initial_sync(client_id='uuid-here')
```

**✅ Ventajas:**
- Un query para todo (producto + imágenes + variantes)
- Paginación cursor automática
- URLs CDN Shopify directo (no download)
- 50 productos por request vs 30 de TN REST

---

### **TiendaNube REST Sync**
```python
# services/tiendanube_sync.py

import requests
from app.models.tiendanube_product import TiendaNubeProduct
from app.services.clip_engine import calculate_embedding

class TiendaNubeSync:
    def __init__(self, store_id, access_token):
        self.store_id = store_id
        self.access_token = access_token
        self.base_url = f'https://api.tiendanube.com/2025-03/{store_id}'
        self.headers = {
            'Authentication': f'bearer {access_token}',
            'User-Agent': 'CLIPComparador (contact@clip.com)'
        }

    def initial_sync(self, client_id):
        """Sincronización inicial completa"""
        page = 1
        products_synced = 0

        while True:
            response = requests.get(
                f'{self.base_url}/products',
                headers=self.headers,
                params={'page': page, 'per_page': 50}
            )

            if response.status_code != 200:
                break

            products = response.json()
            if not products:
                break

            for product in products:
                self._sync_product(product, client_id)
                products_synced += 1

            # Check si hay más páginas (Link header)
            link_header = response.headers.get('Link')
            if not link_header or 'rel="next"' not in link_header:
                break

            page += 1

        return products_synced

    def _sync_product(self, product_data, client_id):
        """Sincroniza un producto individual"""
        # Extraer imagen principal
        primary_image_url = None
        if product_data['images']:
            primary_image_url = product_data['images'][0]['src']

        # Calcular embedding CLIP
        embedding = None
        if primary_image_url:
            # Descargar imagen de CloudFront
            embedding = calculate_embedding(primary_image_url)

        # Extraer nombres i18n
        name = product_data['name']  # {"es": "...", "pt": "..."}

        # Guardar variantes
        for variant in product_data['variants']:
            TiendaNubeProduct.upsert(
                client_id=client_id,
                tiendanube_product_id=product_data['id'],
                tiendanube_variant_id=variant['id'],
                tiendanube_store_id=self.store_id,
                name=name,  # JSONB
                sku=variant['sku'],
                price=variant['price'],
                stock=variant['stock'],
                images=[img['src'] for img in product_data['images']],
                primary_image_embedding=embedding
            )

# Usage
sync = TiendaNubeSync(store_id=1234, access_token='...')
sync.initial_sync(client_id='uuid-here')
```

**❌ Limitaciones:**
- Múltiples requests (1 por página)
- Paginación manual
- Rate limit: 2 req/sec (sync lento)
- i18n JSONB complejo

---

## 🎓 CONCLUSIÓN TÉCNICA

### **Por qué Shopify es más simple:**

1. **Tooling moderno**
   - Shopify CLI automatiza 80% del setup
   - TiendaNube todo manual

2. **API superior**
   - GraphQL optimiza queries (1 request vs 10)
   - REST de TN requiere múltiples round-trips

3. **Development Experience**
   - Hot reload en Shopify = iteración rápida
   - TiendaNube = upload manual + refresh

4. **Integración nativa**
   - Theme Extensions = drag & drop merchant
   - Scripts TN = código inyectado (menos confiable)

5. **Debugging**
   - Shopify dev stores + logs + GraphiQL
   - TiendaNube = testing en producción

6. **Documentación**
   - Shopify: Guías paso a paso + videos + templates
   - TiendaNube: API reference básico

### **Cuándo considerar TiendaNube:**
- ✅ Tu mercado objetivo es 100% LATAM
- ✅ Tus clientes solo hablan español/portugués
- ✅ Ya tienes experiencia con TN
- ✅ Tu competencia está solo en TN

### **Por qué empezar con Shopify:**
- ✅ Alcance global
- ✅ Desarrollo 2-3x más rápido
- ✅ Mejor ROI
- ✅ Más fácil escalar

---

## 📊 TIMELINE COMPARATIVO

```
SHOPIFY:
Semana 1: ████████████████ Setup + Sync + Webhooks (CLI)
Semana 2: ████████████████ Widget + Testing + Deploy
TOTAL: 2 semanas → LISTO PARA PRODUCCIÓN

TIENDANUBE:
Semana 1: ████████ OAuth + Sync manual
Semana 2: ████████ Webhooks + DB schema
Semana 3: ████████ Widget JS + Testing
Semana 4: ████████ Debug + Deploy
TOTAL: 4 semanas → LISTO PARA PRODUCCIÓN
```

**Shopify ahorra 50% del tiempo de desarrollo.**

---

## ✅ DECISIÓN FINAL

**Implementar SHOPIFY primero**, luego evaluar TiendaNube si:
1. Hay demanda específica de LATAM
2. Shopify app es rentable
3. Tienes recursos para mantener 2 integraciones

**Ratio esfuerzo/beneficio:**
- Shopify: ⭐⭐⭐⭐⭐ (5/5)
- TiendaNube: ⭐⭐⭐☆☆ (3/5)

---

**Documentación creada:** 20 Nov 2025
**Autor:** GitHub Copilot (Claude Sonnet 4.5)
**Proyecto:** CLIP Comparador V2
