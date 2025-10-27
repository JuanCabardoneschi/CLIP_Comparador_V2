# Análisis Completo: Sistema de Analytics de Tienda

**Fecha**: 24 de Octubre, 2025
**Objetivo**: Analizar la implementación del sistema de Analytics de Tienda para clientes/comerciantes
**Alcance**: Métricas de negocio, tracking de búsquedas, conversiones y comportamiento de usuarios

---

## 📊 Estado Actual del Sistema

### ✅ Componentes Existentes

#### 1. **Modelo de Datos** (`SearchLog`)
**Ubicación**: `app/models/search_log.py`

**Estado**: ✅ Modelo creado pero **NO UTILIZADO**

**Esquema actual**:
```python
class SearchLog(db.Model):
    id                  # UUID
    client_id          # FK a clients
    query_type         # 'text' | 'image'
    query_data         # JSON con datos de consulta
    results_count      # Cantidad de resultados
    response_time      # Tiempo de respuesta (segundos)
    created_at         # Timestamp de búsqueda
```

**Limitaciones identificadas**:
- ❌ No captura datos de imagen (hash, embedding)
- ❌ No almacena resultados devueltos (IDs de productos)
- ❌ No tiene tracking de clicks en resultados
- ❌ No tiene tracking de conversiones
- ❌ No almacena categoría detectada
- ❌ No almacena color detectado
- ❌ No guarda métricas de confianza/similitud
- ❌ Campo `query_text` no existe (pero se referencia en analytics.py)
- ❌ Campo `search_type` no existe (pero se referencia en analytics.py)
- ❌ Campo `response_time_ms` no existe (solo `response_time` en segundos)

#### 2. **Blueprint de Analytics** (`analytics.py`)
**Ubicación**: `app/blueprints/analytics.py`

**Estado**: ✅ Código existe pero con **BUGS** y sin templates

**Rutas implementadas**:
- `GET /analytics/` - Dashboard general ✅
- `GET /analytics/clients` - Analytics por cliente ✅
- `GET /analytics/searches` - Analytics de búsquedas ❌ (usa campos inexistentes)
- `GET /analytics/performance` - Métricas de rendimiento ❌ (usa campos inexistentes)
- `GET /analytics/client/<client_id>` - Detalle de cliente ✅
- `GET /analytics/api/stats/overview` - API stats generales ✅
- `GET /analytics/api/stats/searches-by-day` - API búsquedas/día ✅
- `GET /analytics/api/stats/client/<client_id>` - API stats de cliente ✅

**Problemas críticos**:
```python
# En analytics.py línea 79 - Campo inexistente
top_queries = db.session.query(
    SearchLog.query_text,  # ❌ Este campo NO EXISTE en el modelo
    func.count(SearchLog.id).label("count")
)

# En analytics.py línea 89 - Campo inexistente
search_types = db.session.query(
    SearchLog.search_type,  # ❌ Este campo NO EXISTE en el modelo
    func.count(SearchLog.id).label("count")
)

# En analytics.py línea 111 - Campo inexistente
avg_response_time = db.session.query(
    func.avg(SearchLog.response_time_ms)  # ❌ Debería ser response_time
).scalar() or 0
```

#### 3. **Templates**
**Ubicación**: `app/templates/analytics/`

**Estado**: ❌ **DIRECTORIO VACÍO** - No hay templates

**Templates requeridos (no existen)**:
- `analytics/index.html`
- `analytics/clients.html`
- `analytics/searches.html`
- `analytics/performance.html`
- `analytics/client_detail.html`

#### 4. **Integración en API de Búsqueda**
**Ubicación**: `app/blueprints/api.py` - `/api/search`

**Estado**: ❌ **NO HAY TRACKING**

**Código actual**: Endpoint `/api/search` NO guarda logs en `SearchLog`

#### 5. **Widget Tracking**
**Ubicación**: `app/static/js/clip-widget-embed.js`

**Estado**: ❌ **NO HAY TRACKING**

**Código actual**: Widget NO envía eventos de:
- Click en producto
- Conversión (visita a tienda)
- Tiempo en resultados
- Interacciones con modal de imágenes

#### 6. **Menú de Navegación**
**Ubicación**: `app/templates/layouts/base.html` línea 213

**Estado**: ⚠️ **ENLACE PLACEHOLDER**

```html
<a class="nav-link" href="#"
   onclick="alert('Analytics de Mi Tienda - En desarrollo')">
    <i class="bi bi-bar-chart me-2"></i>
    Analytics de Tienda
</a>
```

---

## 🎯 Objetivos del Sistema de Analytics de Tienda

### Objetivos de Negocio
1. **Visibilidad de uso**: Clientes/comerciantes ven cuántas búsquedas reciben
2. **Optimización de catálogo**: Identificar productos más buscados vs. menos buscados
3. **Métricas de conversión**: Medir efectividad de búsqueda → click → venta
4. **Calidad de resultados**: Detectar búsquedas sin clicks (resultados irrelevantes)
5. **Patrones de uso**: Horarios pico, categorías populares, tendencias

### Diferenciación vs. Analytics Administrativo

| Aspecto | Analytics Admin (actual) | Analytics de Tienda (propuesto) |
|---------|-------------------------|--------------------------------|
| **Usuario** | Super Admin | Cliente/Comerciante |
| **Alcance** | Todos los clientes | Solo su tienda |
| **Datos** | Métricas técnicas | Métricas de negocio |
| **Objetivo** | Operaciones/sistemas | Ventas/optimización |
| **Ejemplos** | "Cliente X tiene 500 productos" | "Mis camisas rojas se buscan 3x más que las azules" |

---

## 🗄️ Rediseño del Modelo de Datos

### Tabla `search_logs` (MEJORADA)

**Necesidad**: Capturar información completa de cada búsqueda para analytics

```sql
CREATE TABLE search_logs (
    -- Identificación
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,

    -- Datos de búsqueda
    query_type VARCHAR(20) NOT NULL,  -- 'image' | 'text' | 'hybrid'
    image_hash VARCHAR(64),           -- Hash MD5 de imagen (para deduplicación)
    image_size_bytes INTEGER,         -- Tamaño de imagen subida

    -- Detección automática
    detected_category_id UUID REFERENCES categories(id),
    category_confidence FLOAT,        -- Confianza de detección (0.0-1.0)
    detected_color VARCHAR(50),       -- Color dominante detectado
    color_confidence FLOAT,           -- Confianza de color

    -- Resultados
    results_count INTEGER DEFAULT 0,
    result_product_ids JSON,          -- Array de UUIDs: ["uuid1", "uuid2", ...]
    top_similarity_score FLOAT,       -- Similitud del resultado #1
    avg_similarity_score FLOAT,       -- Promedio de similitudes

    -- Rendimiento
    response_time_ms INTEGER,         -- Tiempo total de respuesta (ms)
    embedding_time_ms INTEGER,        -- Tiempo generación embedding
    search_time_ms INTEGER,           -- Tiempo búsqueda en DB

    -- Interacciones (actualizables)
    clicked_product_id UUID,          -- Producto clickeado (NULL si no hay click)
    clicked_at TIMESTAMP,             -- Momento del click
    time_to_click_ms INTEGER,         -- Tiempo desde búsqueda hasta click
    converted BOOLEAN DEFAULT FALSE,  -- Si visitó la tienda externa
    converted_at TIMESTAMP,           -- Momento de conversión

    -- Contexto técnico
    user_agent TEXT,                  -- Navegador/dispositivo
    ip_address VARCHAR(45),           -- IP (para geolocalización opcional)
    referer_url TEXT,                 -- URL desde donde buscó

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Índices para performance
    INDEX idx_search_logs_client_created (client_id, created_at DESC),
    INDEX idx_search_logs_category (detected_category_id),
    INDEX idx_search_logs_clicked (clicked_product_id),
    INDEX idx_search_logs_converted (client_id, converted, created_at)
);
```

**Razones del diseño**:
- `image_hash`: Detectar imágenes repetidas (ej: usuario busca 2 veces lo mismo)
- `result_product_ids`: Saber QUÉ productos se mostraron (para A/B testing)
- `clicked_product_id`: **Métrica clave** - ¿el resultado fue relevante?
- `converted`: **Métrica de negocio** - ¿la búsqueda generó venta potencial?
- `time_to_click_ms`: Detectar si usuarios dudan (baja confianza en resultados)
- Campos separados de tiempo: Identificar cuellos de botella (embedding vs. DB)

---

## 📡 Flujo de Tracking Completo

### 1. **Tracking de Búsqueda** (Backend)

**Ubicación**: `app/blueprints/api.py` - endpoint `/api/search`

**Momento**: Al finalizar procesamiento de búsqueda

**Implementación propuesta**:
```python
@bp.route("/search", methods=["POST"])
def visual_search():
    start_time = time.time()

    # ... código actual de búsqueda ...

    # Al final, antes de return:
    try:
        log_entry = SearchLog(
            client_id=client.id,
            query_type='image',
            image_hash=hashlib.md5(image_data).hexdigest(),
            image_size_bytes=len(image_data),
            detected_category_id=detected_category.id if detected_category else None,
            category_confidence=category_confidence,
            detected_color=detected_color_name,
            color_confidence=color_confidence,
            results_count=len(results),
            result_product_ids=json.dumps([r['id'] for r in results]),
            top_similarity_score=results[0]['similarity'] if results else None,
            avg_similarity_score=sum(r['similarity'] for r in results) / len(results) if results else None,
            response_time_ms=int((time.time() - start_time) * 1000),
            embedding_time_ms=embedding_time,
            search_time_ms=search_time,
            user_agent=request.headers.get('User-Agent'),
            ip_address=request.remote_addr,
            referer_url=request.headers.get('Referer')
        )
        db.session.add(log_entry)
        db.session.commit()

        # Retornar search_id en respuesta para tracking posterior
        return jsonify({
            "success": True,
            "search_id": log_entry.id,  # ← Nuevo campo
            "results": results,
            # ... resto de respuesta
        })
    except Exception as e:
        print(f"⚠️ Error logging search: {e}")
        # No fallar la búsqueda si falla el logging
```

**Impacto**: +10-20ms por búsqueda (inserción en BD)

---

### 2. **Tracking de Clicks** (Frontend → Backend)

**Flujo completo**:
```
Usuario hace click en producto
    ↓
Widget JS envía evento a backend
    ↓
Backend actualiza search_log con clicked_product_id
    ↓
Analytics registran CTR (click-through rate)
```

#### Frontend (Widget)

**Ubicación**: `app/static/js/clip-widget-embed.js`

**Modificación propuesta**:
```javascript
// Variable global para guardar search_id
let currentSearchId = null;

// En displayResults(), después de mostrar productos:
function displayResults(items, searchId) {
    currentSearchId = searchId;  // Guardar ID de búsqueda

    // ... código actual de renderizado ...

    // Agregar event listener a cada producto
    document.querySelectorAll('.clip-widget-result-item').forEach((item, index) => {
        item.addEventListener('click', () => {
            trackProductClick(items[index].id, index);
        });
    });
}

// Nueva función de tracking
async function trackProductClick(productId, position) {
    if (!currentSearchId) return;

    try {
        await fetch(`${config.serverUrl}/api/search/track-click`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': config.apiKey
            },
            body: JSON.stringify({
                search_id: currentSearchId,
                product_id: productId,
                position: position  // 0=primer resultado, 1=segundo, etc.
            })
        });
    } catch (e) {
        console.warn('Error tracking click:', e);
        // No interrumpir UX si falla tracking
    }
}
```

#### Backend (Nuevo endpoint)

**Ubicación**: `app/blueprints/api.py`

**Nuevo endpoint**:
```python
@bp.route("/search/track-click", methods=["POST"])
@require_api_key
def track_click():
    """Registrar click en resultado de búsqueda"""
    data = request.get_json()

    search_id = data.get('search_id')
    product_id = data.get('product_id')
    position = data.get('position', 0)

    if not search_id or not product_id:
        return jsonify({"error": "Missing required fields"}), 400

    # Actualizar log de búsqueda
    search_log = SearchLog.query.get(search_id)
    if not search_log:
        return jsonify({"error": "Search not found"}), 404

    # Verificar que el producto estaba en los resultados
    result_ids = json.loads(search_log.result_product_ids)
    if product_id not in result_ids:
        return jsonify({"error": "Product not in results"}), 400

    # Actualizar campos de click
    search_log.clicked_product_id = product_id
    search_log.clicked_at = datetime.utcnow()
    search_log.time_to_click_ms = int((datetime.utcnow() - search_log.created_at).total_seconds() * 1000)
    search_log.click_position = position  # Agregar campo a modelo

    db.session.commit()

    return jsonify({"success": True})
```

**Campos adicionales al modelo**:
- `click_position INTEGER` - Posición del resultado clickeado (0-indexed)

---

### 3. **Tracking de Conversión** (Frontend → Backend)

**Definición de "Conversión"**: Usuario visitó la tienda externa (click en botón "Ver producto")

**Flujo**:
```
Usuario click en "Ver producto" (enlace externo)
    ↓
Widget JS envía evento de conversión
    ↓
Backend marca converted=true
    ↓
Analytics calculan conversion rate
```

#### Frontend

```javascript
// En displayResults(), al generar botón "Ver producto":
const productLink = document.createElement('a');
productLink.href = item.url_producto;
productLink.target = '_blank';
productLink.className = 'clip-widget-result-link';
productLink.textContent = 'Ver producto';

// Tracking de conversión al hacer click
productLink.addEventListener('click', () => {
    trackConversion(item.id);
});

async function trackConversion(productId) {
    if (!currentSearchId) return;

    try {
        await fetch(`${config.serverUrl}/api/search/track-conversion`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': config.apiKey
            },
            body: JSON.stringify({
                search_id: currentSearchId,
                product_id: productId
            })
        });
    } catch (e) {
        console.warn('Error tracking conversion:', e);
    }
}
```

#### Backend

```python
@bp.route("/search/track-conversion", methods=["POST"])
@require_api_key
def track_conversion():
    """Registrar conversión (visita a tienda)"""
    data = request.get_json()

    search_id = data.get('search_id')
    product_id = data.get('product_id')

    if not search_id:
        return jsonify({"error": "Missing search_id"}), 400

    search_log = SearchLog.query.get(search_id)
    if not search_log:
        return jsonify({"error": "Search not found"}), 404

    # Marcar como convertido
    search_log.converted = True
    search_log.converted_at = datetime.utcnow()
    search_log.converted_product_id = product_id  # Nuevo campo

    db.session.commit()

    return jsonify({"success": True})
```

---

## 📊 Dashboard de Analytics de Tienda

### Vista 1: Overview (Dashboard Principal)

**Ruta**: `/store-analytics/`

**Métricas principales** (último mes):
```
┌─────────────────────────────────────────────────┐
│  📊 RESUMEN DE MI TIENDA - Octubre 2025        │
├─────────────────────────────────────────────────┤
│                                                 │
│  🔍 Total Búsquedas:        1,247              │
│  👆 Total Clicks:             523 (41.9% CTR)  │
│  🛒 Conversiones:             187 (35.8% CR)   │
│  ⏱️  Tiempo promedio:        342ms             │
│                                                 │
│  📈 vs. Mes Anterior:         +23% ↗️           │
│                                                 │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│  📈 BÚSQUEDAS POR DÍA (últimos 30 días)        │
│                                                 │
│  [Gráfico de línea: búsquedas/día]            │
│  - Identificar picos de tráfico                │
│  - Comparar con mes anterior                   │
│                                                 │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│  🔥 TOP 5 PRODUCTOS MÁS BUSCADOS               │
│                                                 │
│  1. Camisa Rey León    87 búsquedas (67% CTR)  │
│  2. Remera Verde       64 búsquedas (52% CTR)  │
│  3. Pantalón Negro     51 búsquedas (71% CTR)  │
│  4. Zapatos Deportivos 43 búsquedas (39% CTR)  │
│  5. Vestido Floral     38 búsquedas (82% CTR)  │
│                                                 │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│  📁 CATEGORÍAS MÁS BUSCADAS                    │
│                                                 │
│  CAMISAS     45% ████████████░░░░               │
│  PANTALONES  28% ███████░░░░░░░░                │
│  CALZADO     18% █████░░░░░░░░░░                │
│  ACCESORIOS   9% ██░░░░░░░░░░░░░                │
│                                                 │
└─────────────────────────────────────────────────┘
```

**Queries necesarias**:
```python
# Total búsquedas último mes
total_searches = SearchLog.query.filter(
    SearchLog.client_id == current_client.id,
    SearchLog.created_at >= datetime.now() - timedelta(days=30)
).count()

# CTR (Click-Through Rate)
clicks = SearchLog.query.filter(
    SearchLog.client_id == current_client.id,
    SearchLog.clicked_product_id.isnot(None),
    SearchLog.created_at >= datetime.now() - timedelta(days=30)
).count()
ctr = (clicks / total_searches * 100) if total_searches > 0 else 0

# Conversion Rate
conversions = SearchLog.query.filter(
    SearchLog.client_id == current_client.id,
    SearchLog.converted == True,
    SearchLog.created_at >= datetime.now() - timedelta(days=30)
).count()
conversion_rate = (conversions / clicks * 100) if clicks > 0 else 0

# Productos más clickeados
top_products = db.session.query(
    Product.name,
    func.count(SearchLog.id).label('search_count'),
    func.count(SearchLog.clicked_product_id).label('click_count')
).join(
    SearchLog, SearchLog.clicked_product_id == Product.id
).filter(
    SearchLog.client_id == current_client.id,
    SearchLog.created_at >= datetime.now() - timedelta(days=30)
).group_by(
    Product.id, Product.name
).order_by(desc('click_count')).limit(5).all()

# Categorías más buscadas
top_categories = db.session.query(
    Category.name,
    func.count(SearchLog.id).label('count'),
    func.round(func.count(SearchLog.id) * 100.0 / total_searches, 1).label('percentage')
).join(
    SearchLog, SearchLog.detected_category_id == Category.id
).filter(
    SearchLog.client_id == current_client.id,
    SearchLog.created_at >= datetime.now() - timedelta(days=30)
).group_by(
    Category.id, Category.name
).order_by(desc('count')).all()
```

---

### Vista 2: Análisis de Productos

**Ruta**: `/store-analytics/products`

**Objetivo**: Identificar productos "estrella" vs. productos que no generan interés

```
┌─────────────────────────────────────────────────────────────────┐
│  🎯 RENDIMIENTO POR PRODUCTO                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Filtros: [Categoría ▼] [Ordenar: Más buscados ▼] [🔍 Buscar] │
│                                                                 │
│  ┌──────────────────┬──────────┬────────┬──────────┬─────────┐ │
│  │ Producto         │ Búsquedas│ Clicks │ CTR      │ Ventas  │ │
│  ├──────────────────┼──────────┼────────┼──────────┼─────────┤ │
│  │ 🔥 Camisa León   │   87     │   58   │  66.7% ✅│   12    │ │
│  │ ⭐ Remera Verde  │   64     │   33   │  51.6%   │    8    │ │
│  │ ⚠️  Pantalón XL  │   12     │    1   │   8.3% ❌│    0    │ │
│  │ 💤 Zapatos Boot  │    2     │    0   │   0.0% ❌│    0    │ │
│  └──────────────────┴──────────┴────────┴──────────┴─────────┘ │
│                                                                 │
│  Indicadores:                                                   │
│  🔥 Alto rendimiento (CTR > 50%)                               │
│  ⭐ Rendimiento normal (CTR 30-50%)                            │
│  ⚠️  Bajo rendimiento (CTR 10-30%)                             │
│  💤 Sin interés (CTR < 10%) - Considerar revisar catálogo     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Valor de negocio**:
- Detectar productos "zombies" (en catálogo pero nadie los busca)
- Identificar productos con alta demanda para priorizar stock
- Productos con búsquedas pero bajo CTR → mejorar imágenes/descripciones

---

### Vista 3: Tendencias y Patrones

**Ruta**: `/store-analytics/trends`

```
┌─────────────────────────────────────────────────────────────────┐
│  📅 ANÁLISIS POR DÍA DE LA SEMANA                              │
│                                                                 │
│  Lun ██████████████░░░░  67 búsquedas                          │
│  Mar █████████████████░░  89 búsquedas (pico)                  │
│  Mié ████████████░░░░░░  58 búsquedas                          │
│  Jue ███████████████████  98 búsquedas (pico)                  │
│  Vie ██████████████████░  91 búsquedas                          │
│  Sáb ███████████████████  95 búsquedas                          │
│  Dom ████████░░░░░░░░░░  43 búsquedas                          │
│                                                                 │
│  💡 Insight: Mayor tráfico Jue-Sáb. Considerar promociones.   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  🕐 ANÁLISIS POR HORA DEL DÍA                                  │
│                                                                 │
│  [Gráfico de calor: horas vs. búsquedas]                      │
│                                                                 │
│  Horarios pico identificados:                                  │
│  • 10:00-12:00 hs  (23% del tráfico)                          │
│  • 15:00-17:00 hs  (31% del tráfico)                          │
│  • 20:00-22:00 hs  (28% del tráfico)                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  🎨 COLORES MÁS BUSCADOS                                       │
│                                                                 │
│  Negro    ████████████████░░  187 búsquedas (35%)              │
│  Blanco   ███████████░░░░░░░  123 búsquedas (23%)              │
│  Azul     ██████████░░░░░░░░  109 búsquedas (20%)              │
│  Rojo     ██████░░░░░░░░░░░░   67 búsquedas (12%)              │
│  Verde    ████░░░░░░░░░░░░░░   45 búsquedas  (8%)              │
│  Otros    ██░░░░░░░░░░░░░░░░   12 búsquedas  (2%)              │
│                                                                 │
│  💡 Insight: Expandir stock de productos negros y blancos.     │
└─────────────────────────────────────────────────────────────────┘
```

---

### Vista 4: Búsquedas Sin Resultado (Oportunidades)

**Ruta**: `/store-analytics/missed-opportunities`

```
┌─────────────────────────────────────────────────────────────────┐
│  ⚠️  BÚSQUEDAS CON PROBLEMAS (última semana)                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  📊 Resumen:                                                    │
│  • Total búsquedas:              342                           │
│  • Sin resultados:                 23  (6.7%)                  │
│  • Con resultados pero sin clicks: 89  (26.0%) ⚠️              │
│  • Categoría no detectada:         12  (3.5%)                  │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  🔍 BÚSQUEDAS SIN CLICKS (baja relevancia)                     │
│                                                                 │
│  Imagen buscada    │ Categoría    │ Resultados │ Acción        │
│  ───────────────────┼──────────────┼────────────┼───────────────│
│  [Img Zapato Rojo] │ CALZADO      │ 3 prod     │ 📷 Revisar    │
│  [Img Camisa XL]   │ CAMISAS      │ 3 prod     │ 📷 Revisar    │
│  [Img Vestido]     │ No detectada │ 0 prod     │ ➕ Agregar    │
│                                                                 │
│  💡 Acciones sugeridas:                                        │
│  • Revisar imágenes de productos mostrados                     │
│  • Agregar productos similares a los buscados                  │
│  • Mejorar embeddings de productos con bajo CTR                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Query para detectar búsquedas sin clicks**:
```python
missed_searches = SearchLog.query.filter(
    SearchLog.client_id == current_client.id,
    SearchLog.clicked_product_id.is_(None),
    SearchLog.results_count > 0,  # Hubo resultados pero no clickearon
    SearchLog.created_at >= datetime.now() - timedelta(days=7)
).order_by(desc(SearchLog.created_at)).limit(20).all()
```

**Valor de negocio**:
- **Detectar gaps en catálogo**: Usuarios buscan productos que no tienes
- **Identificar resultados irrelevantes**: Sistema devuelve productos pero no son lo que buscan
- **Oportunidades de expansión**: "Se buscan zapatos rojos 23 veces, pero no los vendemos"

---

## 🎨 Wireframes de UI

### Dashboard Principal (Mobile-First)

```
┌─────────────────────────────────┐
│ 📊 Analytics de Mi Tienda      │
│ [Rango: Último mes ▼]          │
├─────────────────────────────────┤
│                                 │
│ ┌─────────────┬─────────────┐  │
│ │ 🔍 BÚSQUEDAS│ 👆 CLICKS   │  │
│ │    1,247    │     523     │  │
│ │   +23% ↗️    │   42% CTR   │  │
│ └─────────────┴─────────────┘  │
│                                 │
│ ┌─────────────┬─────────────┐  │
│ │ 🛒 VENTAS   │ ⏱️  TIEMPO   │  │
│ │     187     │    342ms    │  │
│ │   36% CR    │   -15% ↘️    │  │
│ └─────────────┴─────────────┘  │
│                                 │
│ ┌───────────────────────────┐  │
│ │ 📈 Búsquedas (últimos 7d)│  │
│ │                           │  │
│ │     *                     │  │
│ │    **    *                │  │
│ │   *  *  * *   *           │  │
│ │  *    **   * * *          │  │
│ │ L M M J V S D             │  │
│ └───────────────────────────┘  │
│                                 │
│ ┌───────────────────────────┐  │
│ │ 🔥 Top Productos          │  │
│ ├───────────────────────────┤  │
│ │ 1. Camisa León            │  │
│ │    87 búsquedas | 67% CTR │  │
│ │ ──────────────────────── │  │
│ │ 2. Remera Verde           │  │
│ │    64 búsquedas | 52% CTR │  │
│ │ ──────────────────────── │  │
│ │ 3. Pantalón Negro         │  │
│ │    51 búsquedas | 71% CTR │  │
│ └───────────────────────────┘  │
│                                 │
│ [Ver más detalles →]           │
│                                 │
└─────────────────────────────────┘
```

---

## 🛠️ Arquitectura Técnica

### Stack Tecnológico

**Backend**:
- Flask blueprints para rutas
- SQLAlchemy para queries
- PostgreSQL para almacenamiento
- JSON para datos flexibles (result_product_ids, etc.)

**Frontend**:
- Bootstrap 5 (ya en uso)
- Chart.js para gráficos
- JavaScript vanilla para tracking
- AJAX para actualización de datos sin refresh

**Librerías adicionales**:
```python
# requirements.txt
# (ya existen)
Flask==3.x
SQLAlchemy==2.x
psycopg2-binary==2.x

# (agregar)
pandas==2.x          # Para análisis de datos avanzados (opcional)
```

---

## 📦 Plan de Implementación

### Fase 1: Fundación (1 semana)
**Objetivo**: Tracking básico funcionando

**Tareas**:
1. ✅ **Migración de BD**
   - Crear script de migración Alembic
   - Agregar nuevos campos a `search_logs`
   - Índices para performance

2. ✅ **Tracking de búsquedas**
   - Modificar `/api/search` para guardar logs
   - Incluir `search_id` en respuesta
   - Testing: verificar que se guardan logs

3. ✅ **Endpoints de tracking**
   - `/api/search/track-click`
   - `/api/search/track-conversion`
   - Validaciones y seguridad

4. ✅ **Widget tracking**
   - Modificar `clip-widget-embed.js`
   - Event listeners en productos
   - Envío de eventos a backend
   - Testing: verificar eventos se reciben

**Entregable**: Sistema de tracking completo funcionando (sin UI)

**Validación**:
```sql
-- Verificar que se guardan búsquedas
SELECT COUNT(*) FROM search_logs WHERE created_at > NOW() - INTERVAL '1 day';

-- Verificar que se registran clicks
SELECT COUNT(*) FROM search_logs
WHERE clicked_product_id IS NOT NULL
AND created_at > NOW() - INTERVAL '1 day';
```

---

### Fase 2: Dashboard Básico (1 semana)
**Objetivo**: UI funcional con métricas principales

**Tareas**:
1. ✅ **Blueprint de store_analytics**
   - Crear `app/blueprints/store_analytics.py`
   - Decorador `@login_required` + filtro por cliente
   - Rutas básicas

2. ✅ **Template base**
   - Crear `app/templates/store_analytics/base.html`
   - Navegación entre secciones
   - Responsive con Bootstrap 5

3. ✅ **Vista Overview**
   - Template `store_analytics/overview.html`
   - KPIs principales (búsquedas, clicks, conversiones)
   - Gráfico de búsquedas/día (Chart.js)

4. ✅ **Actualizar menú**
   - Cambiar link placeholder en `base.html`
   - Enlazar a `/store-analytics/`

**Entregable**: Dashboard básico accesible desde menú

---

### Fase 3: Análisis Avanzado (1 semana)
**Objetivo**: Insights accionables para clientes

**Tareas**:
1. ✅ **Vista de Productos**
   - Top productos más buscados
   - Productos con bajo CTR
   - Filtros por categoría

2. ✅ **Vista de Tendencias**
   - Análisis por día de semana
   - Análisis por hora
   - Colores más buscados

3. ✅ **Vista de Oportunidades**
   - Búsquedas sin clicks
   - Categorías no detectadas
   - Sugerencias accionables

**Entregable**: Suite completa de analytics

---

### Fase 4: Optimizaciones (Opcional)
**Objetivo**: Performance y features avanzadas

**Tareas**:
1. ⏳ **Caching**
   - Redis para métricas frecuentes
   - TTL de 5-15 minutos

2. ⏳ **Exports**
   - Exportar a CSV/Excel
   - Reportes programados por email

3. ⏳ **Alertas**
   - Notificar si CTR cae < 30%
   - Alertar si búsquedas sin resultados > 10%

4. ⏳ **Comparaciones**
   - Comparar mes actual vs. anterior
   - Benchmark vs. promedio de industria

---

## 📊 Métricas de Éxito

### KPIs del Sistema de Analytics

1. **Adopción por clientes**
   - Objetivo: >80% de clientes visitan analytics al menos 1x/semana
   - Métrica: `analytics_visits / active_clients`

2. **Utilidad percibida**
   - Objetivo: Clientes identifican al menos 1 acción a tomar
   - Métrica: Encuesta post-uso + feedback

3. **Performance**
   - Objetivo: Dashboard carga en <2 segundos
   - Métrica: Response time del endpoint

4. **Impacto en negocio del cliente**
   - Objetivo: Clientes optimizan catálogo basándose en datos
   - Métrica: Cambios en productos después de usar analytics

---

## ⚠️ Riesgos y Mitigaciones

### Riesgo 1: Overhead en Performance
**Problema**: Guardar log en cada búsqueda puede ralentizar API

**Mitigación**:
- Logging asíncrono (background task)
- Índices apropiados en BD
- Monitoring de tiempos de respuesta

### Riesgo 2: Privacidad de Datos
**Problema**: IPs y user agents son datos sensibles

**Mitigación**:
- Anonimizar IPs (guardar solo primeros 3 octetos)
- Política de retención (borrar logs > 90 días)
- GDPR compliance si aplica

### Riesgo 3: Volumen de Datos
**Problema**: 1000 búsquedas/día = 365K registros/año

**Mitigación**:
- Agregación mensual (guardar solo totales después de 90 días)
- Particionamiento de tablas por fecha
- Archiving a storage más barato (S3, etc.)

### Riesgo 4: Complejidad de Queries
**Problema**: Queries de analytics pueden ser lentas

**Mitigación**:
- Índices compuestos estratégicos
- Vistas materializadas para métricas frecuentes
- Caching en Redis

---

## 💰 Estimación de Esfuerzo

| Fase | Tareas | Complejidad | Tiempo Estimado |
|------|--------|-------------|-----------------|
| **Fase 1: Fundación** | Migración BD + Tracking backend + Widget JS | Alta | 1 semana (40h) |
| **Fase 2: Dashboard Básico** | Blueprint + Templates + Overview | Media | 1 semana (40h) |
| **Fase 3: Análisis Avanzado** | Vistas adicionales + Queries complejas | Media | 1 semana (40h) |
| **Fase 4: Optimizaciones** | Caching + Exports + Alertas | Baja | 3-5 días (24h) |
| **Testing & QA** | Tests unitarios + E2E + Fixes | Media | 2-3 días (16h) |

**Total estimado**: 3-4 semanas (160 horas)

**Desglose por rol**:
- Backend (Python/Flask): 60h
- Frontend (Templates/JS): 50h
- BD/Queries: 30h
- Testing/QA: 20h

---

## 🎯 Criterios de Aceptación

### Funcionales
- ✅ Sistema registra 100% de búsquedas realizadas
- ✅ Clicks se asocian correctamente a búsquedas
- ✅ Conversiones se registran cuando usuario visita tienda
- ✅ Dashboard muestra métricas en tiempo real (<5 min delay)
- ✅ Cliente solo ve datos de su tienda (aislamiento multi-tenant)
- ✅ Filtros por rango de fechas funcionan correctamente
- ✅ Top productos se calculan correctamente
- ✅ Búsquedas sin clicks se identifican correctamente

### No Funcionales
- ✅ Tracking no afecta performance de búsqueda (+<20ms)
- ✅ Dashboard carga en <2 segundos
- ✅ Sistema soporta 10K búsquedas/día sin degradación
- ✅ Responsive en mobile/tablet/desktop
- ✅ Compatible con navegadores modernos (Chrome, Firefox, Safari)

### Seguridad
- ✅ Solo clientes autenticados acceden a analytics
- ✅ Cliente solo ve sus propios datos (no de otros)
- ✅ Datos sensibles (IPs) anonimizados
- ✅ Tracking endpoints validan API key

---

## 📚 Recursos Técnicos

### Modelos a Modificar/Crear

1. **`search_logs` (MODIFICAR)**
   - Archivo: `app/models/search_log.py`
   - Cambios: +15 campos nuevos

2. **`store_analytics` Blueprint (CREAR)**
   - Archivo: `app/blueprints/store_analytics.py`
   - Rutas: 6-8 endpoints

3. **Widget JS (MODIFICAR)**
   - Archivo: `app/static/js/clip-widget-embed.js`
   - Cambios: +50 líneas tracking

### Templates a Crear

1. `app/templates/store_analytics/base.html`
2. `app/templates/store_analytics/overview.html`
3. `app/templates/store_analytics/products.html`
4. `app/templates/store_analytics/trends.html`
5. `app/templates/store_analytics/opportunities.html`

### Queries SQL Complejas

**1. CTR por categoría**:
```sql
SELECT
    c.name AS category,
    COUNT(sl.id) AS total_searches,
    COUNT(sl.clicked_product_id) AS total_clicks,
    ROUND(COUNT(sl.clicked_product_id) * 100.0 / COUNT(sl.id), 2) AS ctr
FROM search_logs sl
JOIN categories c ON sl.detected_category_id = c.id
WHERE sl.client_id = :client_id
  AND sl.created_at >= :start_date
GROUP BY c.id, c.name
ORDER BY total_searches DESC;
```

**2. Productos estrella vs. zombies**:
```sql
WITH product_stats AS (
    SELECT
        p.id,
        p.name,
        COUNT(DISTINCT sl.id) AS appearances,
        COUNT(sl.clicked_product_id) AS clicks,
        COUNT(CASE WHEN sl.converted THEN 1 END) AS conversions
    FROM products p
    LEFT JOIN search_logs sl ON sl.result_product_ids::jsonb ? p.id::text
    WHERE p.client_id = :client_id (via category)
      AND sl.created_at >= :start_date
    GROUP BY p.id, p.name
)
SELECT
    *,
    CASE
        WHEN clicks * 100.0 / NULLIF(appearances, 0) > 50 THEN '🔥 Estrella'
        WHEN clicks * 100.0 / NULLIF(appearances, 0) BETWEEN 30 AND 50 THEN '⭐ Normal'
        WHEN clicks * 100.0 / NULLIF(appearances, 0) BETWEEN 10 AND 30 THEN '⚠️ Bajo'
        ELSE '💤 Zombie'
    END AS performance
FROM product_stats
ORDER BY appearances DESC;
```

**3. Tendencias por hora**:
```sql
SELECT
    EXTRACT(HOUR FROM created_at) AS hour,
    EXTRACT(DOW FROM created_at) AS day_of_week,
    COUNT(*) AS search_count
FROM search_logs
WHERE client_id = :client_id
  AND created_at >= NOW() - INTERVAL '30 days'
GROUP BY hour, day_of_week
ORDER BY hour, day_of_week;
```

---

## 🔗 Integración con Sistemas Existentes

### 1. Analytics Admin (existente)
- **Relación**: Analytics Admin muestra métricas globales; Store Analytics muestra por cliente
- **Compartición**: Pueden compartir queries base (refactorizar en `app/services/analytics_service.py`)
- **Diferenciación**: Admin = técnico/operativo; Store = negocio/ventas

### 2. SearchOptimizer
- **Relación**: Analytics puede mostrar impacto de ajustes de optimizer
- **Ejemplo**: "Después de aumentar peso visual, CTR subió 15%"
- **Feature futura**: A/B testing automático de configs

### 3. Inventory System
- **Relación**: Correlacionar búsquedas con stock
- **Ejemplo**: "Producto más buscado está sin stock → reabastece"
- **Feature futura**: Alertas de stock bajo en productos demandados

---

## 🚀 Roadmap Futuro

### V1 (MVP - 3 semanas)
- ✅ Tracking de búsquedas/clicks/conversiones
- ✅ Dashboard básico con KPIs
- ✅ Top productos y categorías
- ✅ Búsquedas sin clicks

### V2 (Análisis Avanzado - 2 semanas)
- ⏳ Tendencias temporales (día/hora)
- ⏳ Análisis de colores
- ⏳ Exports CSV/Excel
- ⏳ Comparaciones período anterior

### V3 (Inteligencia - 4 semanas)
- ⏳ Detección automática de gaps en catálogo
- ⏳ Sugerencias de productos a agregar
- ⏳ Predicción de demanda
- ⏳ A/B testing de configs de búsqueda

### V4 (Integración - 3 semanas)
- ⏳ Webhooks para eventos (búsqueda, conversión)
- ⏳ API REST para analytics externos
- ⏳ Integración con Google Analytics
- ⏳ Dashboards embebibles en sitio del cliente

---

## 📝 Conclusión

El sistema de **Analytics de Tienda** es una pieza clave para:

1. **Empoderar a clientes**: Datos accionables para optimizar catálogo
2. **Diferenciación competitiva**: Pocas plataformas de búsqueda visual ofrecen analytics profundos
3. **Retroalimentación del sistema**: Métricas de calidad (CTR) para mejorar algoritmo
4. **Monetización futura**: Analytics premium como feature de pago

**Estado actual**:
- ⚠️ Infraestructura parcial (modelo SearchLog sin uso, analytics.py con bugs, sin UI)

**Siguiente paso recomendado**:
- 🎯 **Implementar Fase 1** (Fundación) para empezar a capturar datos
- Incluso sin UI, los datos acumulados serán valiosos para análisis posterior
- **Estimación**: 1 semana de desarrollo

**ROI esperado**:
- Clientes toman decisiones basadas en datos → mejoran conversión
- Mejores conversiones → clientes felices → retención → MRR estable
- Datos de calidad → entrenar mejor algoritmo → mejores resultados → círculo virtuoso

---

**Archivos relacionados**:
- `app/models/search_log.py` (modelo a mejorar)
- `app/blueprints/analytics.py` (código con bugs a arreglar)
- `app/blueprints/api.py` (agregar tracking)
- `app/static/js/clip-widget-embed.js` (agregar eventos)
- `BACKLOG_MEJORAS.md` línea 484 (item #4 - SearchLog para Analytics)
