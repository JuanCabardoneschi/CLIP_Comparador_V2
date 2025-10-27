# BACKLOG DE MEJORAS Y PENDIENTES
**Fecha de Creación**: 22 Octubre 2025
**Última Actualización**: 27 Octubre 2025

---

## ✅ COMPLETADO - Octubre 2025

### ⚡ Optimización de Costos Railway (27 Oct 2025)
**Estado**: ✅ COMPLETADO (Fase 1)
**Complejidad**: Media
**Impacto**: Crítico (reducción ~60% costos mensuales)

**Problema Identificado**:
- RAM usage constante >1GB en Railway (CLIP precargado 24/7)
- Costos mensuales: $50+ USD/mes (excede Hobby Plan de $5/mes)
- Flask development server sin optimizar

**Implementado (Fase 1 - Quick Wins)**:

1. **Lazy Loading de CLIP** (`app/blueprints/embeddings.py`):
   - ✅ Modelo carga solo cuando se necesita (no al inicio)
   - ✅ Auto-cleanup después de 5 min sin uso (configurable)
   - ✅ Thread en background monitorea idle time
   - ✅ Libera ~500-600MB RAM cuando está idle
   - ✅ Lazy imports de torch/transformers/numpy

2. **Gunicorn para Producción** (`Procfile`, `requirements.txt`):
   - ✅ Reemplazado `python app.py` por Gunicorn
   - ✅ 2 workers + 2 threads (optimizado Railway)
   - ✅ Timeout 120s para búsquedas pesadas
   - ✅ Logs a stdout/stderr

3. **Variables de Entorno** (`.env.example`):
   - ✅ `CLIP_PRELOAD=false` - Deshabilita precarga
   - ✅ `CLIP_IDLE_TIMEOUT=300` - Tiempo antes de liberar (5 min default)

**Reducción Esperada**:
- RAM idle: 1000MB → 400-500MB (~60% reducción)
- Costos: $50/mes → ~$15-20/mes (~70% ahorro)
- RAM activo (búsquedas): Sin cambios (sigue usando CLIP cuando se necesita)

**Archivos Modificados**:
- `clip_admin_backend/app/blueprints/embeddings.py` (lazy loading + auto-cleanup)
- `Procfile` (Gunicorn config)
- `requirements.txt` (gunicorn==21.2.0)
- `.env.example` (CLIP_PRELOAD, CLIP_IDLE_TIMEOUT)

**Documentación**:
- ✅ [docs/RAILWAY_COST_OPTIMIZATION.md](docs/RAILWAY_COST_OPTIMIZATION.md) - Plan completo 3 fases

**Próximos Pasos (Opcional - Fases 2 y 3)**:
- [ ] Cache embeddings en Redis (Fase 2)
- [ ] Cuantización modelo CLIP int8 (Fase 2)
- [ ] Arquitectura serverless CLIP worker (Fase 3)

---

### 📦 Sistema de Gestión de Inventario (24 Oct 2025)
**Estado**: ✅ COMPLETADO
**Complejidad**: Media
**Impacto**: Alto (permite integraciones ecommerce/POS)

**Implementado**:

1. **API Externa de Inventario** (`app/blueprints/external_inventory.py`):
   - ✅ POST `/api/external/inventory/reduce-stock` - Reducir stock post-venta
   - ✅ GET `/api/external/inventory/check-stock` - Consultar disponibilidad
   - ✅ POST `/api/external/inventory/bulk-check-stock` - Consultas masivas
   - ✅ Autenticación con API Key vía header `X-API-Key`
   - ✅ Validación de stock (no permite negativos)
   - ✅ Lookup flexible (product_id o sku)
   - ✅ Transacciones atómicas con rollback

2. **Panel de Administración de Stock** (`app/blueprints/inventory.py`):
   - ✅ Dashboard con estadísticas (total, sin stock, bajo stock, disponible)
   - ✅ Filtros por categoría, búsqueda, nivel de stock
   - ✅ Ajuste inline con botones +/-
   - ✅ Establecer stock absoluto manualmente
   - ✅ Indicadores visuales color-coded (rojo/amarillo/verde)
   - ✅ Updates en tiempo real con AJAX

3. **Sistema de Autenticación** (`app/utils/api_auth.py`):
   - ✅ Decorador `@require_api_key` reutilizable
   - ✅ Validación contra modelo Client existente
   - ✅ Respuestas HTTP estandarizadas (401/403)

4. **Documentación**:
   - ✅ [docs/API_INVENTARIO_EXTERNA.md](docs/API_INVENTARIO_EXTERNA.md) - Guía completa de API
   - ✅ Ejemplos en JavaScript, Python, cURL
   - ✅ Actualizado [docs/TOOLS_REFERENCE.md](docs/TOOLS_REFERENCE.md)
   - ✅ Actualizado [.github/copilot-instructions.md](.github/copilot-instructions.md)

**Archivos Creados/Modificados**:
- `clip_admin_backend/app/utils/api_auth.py` (nuevo)
- `clip_admin_backend/app/blueprints/inventory.py` (nuevo)
- `clip_admin_backend/app/blueprints/external_inventory.py` (nuevo)
- `clip_admin_backend/app/templates/inventory/index.html` (nuevo)
- `clip_admin_backend/app.py` (modificado - blueprints registrados)
- `clip_admin_backend/app/templates/layouts/base.html` (modificado - menú)

**Pendiente**:
- [ ] Testing de endpoints en Railway
- [ ] Agregar historial de cambios de stock (audit log)
- [ ] Notificaciones cuando stock crítico (<5 unidades)

---

## 🏗️ ARQUITECTURA Y REFACTORIZACIÓN

### 📊 Análisis y Modularización de app.py
**Estado**: ✅ ANÁLISIS COMPLETO - Pendiente implementación
**Complejidad**: Media-Alta
**Impacto**: Alto (mantenibilidad, testabilidad, escalabilidad)
**Prioridad**: Alta
**Fecha agregada**: 24 Octubre 2025

**Problema Actual**:
- `app.py` monolítico con 408 líneas
- Función `create_app` con 203 líneas (viola responsabilidad única)
- Código repetitivo en registro de blueprints (123 líneas)
- Logging excesivo en producción (impacto en rendimiento)
- 3 elementos de código muerto detectados

**Análisis Completo**:
- 📄 Ver: [docs/APP_PY_ANALYSIS.md](docs/APP_PY_ANALYSIS.md)
- 13 funciones inventariadas
- 100% de funciones en uso (excepto código muerto)
- Propuesta de refactorización en 5 fases
- Reducción estimada: 408 líneas → ~250 líneas en 5 archivos

**Hallazgos Críticos**:
1. ⚠️ Código muerto:
   - `datetime_format` filter (no usado en templates)
   - `currency_format` filter (no usado en templates)
   - `uploaded_file` route (directorio no existe, sistema usa Cloudinary)

2. 🔴 Logging excesivo en `before_request`:
   - Imprime headers, cookies, sesiones completas
   - Impacto en rendimiento en Railway
   - Exposición de datos sensibles en logs

3. 🟡 Código repetitivo:
   - 15 bloques try/except idénticos para blueprints
   - Simplificable a loop de ~30 líneas

**Propuesta de Refactorización**:
```
ANTES: app.py (408 líneas)

DESPUÉS:
├── app.py (50 líneas - solo entry point)
├── app/__init__.py (60 líneas - factory limpia)
└── app/core/
    ├── extensions.py (50 líneas - init de extensiones)
    ├── blueprints.py (40 líneas - registro simplificado)
    ├── handlers.py (50 líneas - hooks + error handlers)
    └── filters.py (10 líneas - template filters, OPCIONAL)
```

**Plan de Implementación** (5 Fases):
- [ ] **Fase 1**: Crear módulo `app/core/extensions.py` (ahorro: ~60 líneas)
- [ ] **Fase 2**: Crear módulo `app/core/blueprints.py` (ahorro: ~120 líneas)
- [ ] **Fase 3**: Crear módulo `app/core/handlers.py` (ahorro: ~65 líneas)
- [ ] **Fase 4**: Refactorizar `create_app` en `app/__init__.py`
- [ ] **Fase 5**: Limpiar código muerto (eliminar 3 elementos)

**Acciones Inmediatas** (antes de siguiente deploy):
- [ ] Arreglar logging en producción (`print` → `app.logger.debug`)
- [ ] Eliminar código muerto (filtros sin uso + ruta obsoleta)

**Beneficios**:
- ✅ 87% reducción en archivo principal
- ✅ Funciones testeables individualmente
- ✅ Mejor organización y mantenibilidad
- ✅ Logging controlado por nivel
- ✅ Elimina duplicación de código

**Estimación**: 1 semana (5 fases + testing)
**Siguiente paso**: Implementar Fase 1 (extensiones)

---

### Unificar Sistema de Identificación de Clientes
**Estado**: 💡 Pendiente
**Complejidad**: Media
**Impacto**: Medio (simplificación del código, mejor mantenibilidad)
**Prioridad**: Media
**Fecha agregada**: 24 Octubre 2025

**Problema Actual**:
Actualmente tenemos 3 formas de referenciar a un cliente en la BD:
- `id` (UUID): Identificador único técnico
- `slug` (string): Usado para rutas de Cloudinary y organización de archivos
- `name` (string): Nombre visible para usuarios

**Análisis**:
- **id**: Necesario (PK, relaciones FK, inmutable)
- **slug**: Usado en rutas de Cloudinary (`clip_v2/{slug}/products/...`), identificador técnico legible
- **name**: Solo UI/presentación, puede cambiar sin consecuencias técnicas

**Propuesta de Mejora**:
Reducir de 3 a 2 identificadores:

**Opción 1 - Mantener ID + NAME (eliminar slug)**:
- ❌ Requiere migración masiva de Cloudinary
- ❌ URLs de imágenes se vuelven menos legibles (UUIDs)
- ⚠️ Alto riesgo de rotura

**Opción 2 - Mantener ID + SLUG (name como computed/virtual)**:
- ✅ Slug sigue siendo inmutable (no rompe Cloudinary)
- ✅ Name se deriva del slug (`demo_fashion_store` → "Demo Fashion Store")
- ✅ UI puede formatear slug para mostrar
- ⚠️ Requiere actualizar vistas/templates que usan `client.name`

**Opción 3 - Mantener ID + NAME (slug derivado)**:
- ✅ Name es editable (UX friendly)
- ✅ Slug se auto-genera en save: `slugify(name)` con cache
- ⚠️ Requiere validación de unicidad del slug generado
- ⚠️ Migración one-time: renombrar carpetas Cloudinary

**Recomendación**: Opción 2 (ID + SLUG)
- Menor riesgo
- Slug es inmutable por diseño (similar a username)
- Name se calcula: `slug.replace('_', ' ').title()`

**Tareas**:
- [ ] Análisis de impacto en templates y vistas
- [ ] Decision final: ¿Mantener qué dos campos?
- [ ] Migration script si se elimina name
- [ ] Actualizar validaciones y formularios
- [ ] Testing exhaustivo

**Referencias**:
- Cloudinary Manager: `clip_admin_backend/app/services/cloudinary_manager.py`
- Client Model: `clip_admin_backend/app/models/client.py`
- Usos de client.name en templates: ~20 archivos

---

## 🔥 URGENTE - FASE 5 (Sistema en Producción)

### 1. Detección Multi-Producto con CLIP (Zero-Shot Multi-Categoría)
**Estado**: 💡 Diseñado, listo para implementar
**Complejidad**: Media
**Impacto**: Alto (expande casos de uso: outfits completos, room decor, etc.)
**Prioridad**: MÁXIMA para mañana
**Fecha agregada**: 23 Octubre 2025
**Estimación**: 3-4 días

**Problema Actual**:
- Sistema actual procesa imagen completa → 1 categoría → 3 productos similares
- Si usuario sube foto de outfit (camisa + pantalón + zapatos), solo matchea el elemento dominante
- Se pierden oportunidades de venta cruzada
- Competidores ya tienen esta funcionalidad

**Solución Diseñada - CLIP Multi-Categoría Iterativa**:

**Pipeline**:
```
1. Detectar categorías presentes (CLIP zero-shot classification)
   Input: Imagen + categorías del catálogo del cliente
   Output: ['CAMISAS', 'PANTALONES', 'CALZADO'] con confidencias

2. Para cada categoría detectada (threshold > 25%):
   - Generar embedding CLIP (UNA SOLA VEZ, reutilizar)
   - Buscar productos similares en esa categoría
   - Aplicar SearchOptimizer por categoría

3. Retornar resultados agrupados por categoría
```

**Casos de Uso**:
- **1 categoría detectada** → Comportamiento actual (backward compatible)
- **2+ categorías detectadas** → Modo multi-producto (nuevas ventas)
- **0 categorías > threshold** → Búsqueda sin restricción (fallback)

**Ventajas**:
- ✅ Sin modelos adicionales (solo CLIP que ya tienes)
- ✅ Zero-shot (adaptable a cualquier catálogo)
- ✅ Latencia baja (2 CLIP calls: 1 detección + 1 embedding)
- ✅ Backward compatible (si 1 categoría → funciona como siempre)
- ✅ Configurable por cliente (threshold, max categorías)
- ✅ Railway Hobby Plan compatible (sin GPU extra)

**Implementación**:

**Fase 1 - Backend (1-2 días)**:
```python
# Función nueva 1: Detectar categorías presentes
def detect_present_categories(image_data, client_id, threshold=0.25):
    """
    Usa CLIP para detectar qué categorías del catálogo están en la imagen
    Returns: [{'name': 'CAMISAS', 'confidence': 0.45}, ...]
    """
    # CLIP zero-shot classification con prompts dinámicos

# Función nueva 2: Búsqueda multi-categoría
def multi_category_search(image_data, client_id):
    """
    Pipeline completo:
    - Detectar categorías
    - Buscar en cada una
    - Agrupar resultados
    """

# Modificar endpoint /api/search:
# - Feature flag: multi_category_enabled (default: True)
# - Response con mode: 'single' | 'multi_product'
```

**Fase 2 - Widget UI (1 día)**:
```javascript
// Detectar modo multi-producto
if (response.mode === 'multi_product') {
  // Mostrar tabs por categoría
  // Grid de productos por tab
} else {
  // UI actual (single)
}
```

**Fase 3 - Admin Config (1 día)**:
```python
# Agregar a modelo Client:
multi_category_enabled = Column(Boolean, default=True)
multi_category_threshold = Column(Float, default=0.25)
max_categories_per_search = Column(Integer, default=3)

# UI Admin:
# - ☑️ Habilitar detección multi-categoría
# - Threshold confianza: [slider 0.20 - 0.50]
# - Máximo categorías: [1-5]
```

**Response Format**:
```json
{
  "mode": "multi_product",
  "detected_categories": 3,
  "results": {
    "CAMISAS": {
      "confidence": 0.45,
      "products": [
        {"name": "Camisa Blanca", "similarity": 0.89},
        ...
      ]
    },
    "PANTALONES": {
      "confidence": 0.38,
      "products": [...]
    },
    "CALZADO": {
      "confidence": 0.28,
      "products": [...]
    }
  }
}
```

**Performance Estimado**:
- 1 categoría: ~300ms (como ahora)
- 2 categorías: ~350ms (+50ms DB)
- 3 categorías: ~400ms (+100ms DB)
- Sin overhead de CLIP adicional (embedding se reutiliza)

**Testing**:
- Imagen outfit completo (camisa + pantalón + zapatos)
- Imagen producto único (backward compatibility)
- Imagen sin productos del catálogo (fallback)
- A/B testing threshold 0.20 vs 0.25 vs 0.30

**Métricas de Éxito**:
- > 30% usuarios usan multi-producto
- +25% conversión en búsquedas multi-producto
- < 5% falsos positivos (categorías incorrectas)

**Archivos a Crear/Modificar**:
- Nuevo: `app/blueprints/multi_category_detection.py`
- Modificar: `app/blueprints/api.py` (integrar multi-categoría)
- Modificar: `app/models/client.py` (campos config)
- Modificar: `clip_admin_backend/app/static/js/clip-widget-embed.js` (UI tabs)
- Nuevo: `tests/test_multi_category.py`

**Dependencias**:
- CLIP ya integrado ✅
- SearchOptimizer funcionando ✅
- Widget responsive ✅

**Riesgos**:
- ⚠️ Threshold muy bajo → falsos positivos (ej: detectar "zapatos" en reflejo)
- ⚠️ Threshold muy alto → perder categorías válidas
- Mitigación: Threshold configurable + A/B testing

**Siguiente Paso**: Implementar Fase 1 (backend) mañana 24 Oct 2025

---

### 2. Admin Panel de Atributos
**Estado**: ⏳ Pendiente
**Complejidad**: Media
**Impacto**: Alto (actualmente se editan a mano en BD)
**Fecha agregada**: 23 Octubre 2025

**Problema**:
- Los atributos (color, marca, talla, etc.) se crean desde el formulario de productos
- `expose_in_search` queda en `false` por defecto → atributos NO aparecen en API
- No hay forma de gestionar atributos centralizadamente
- Cambiar `expose_in_search` requiere UPDATE manual en BD

**Solución Necesaria**:
1. **Blueprint `/attributes/`** con vistas:
   - `GET /attributes/` → Lista todos los atributos del cliente
   - `GET /attributes/create` → Formulario crear atributo
   - `POST /attributes/create` → Guardar nuevo atributo
   - `GET /attributes/edit/<key>` → Formulario editar
   - `POST /attributes/edit/<key>` → Guardar cambios
   - `POST /attributes/delete/<key>` → Eliminar atributo

2. **Formulario debe incluir**:
   - Key (identificador único)
   - Label (nombre visible)
   - Type (text, select, list, url, etc.)
   - ☑️ **Expose in Search** (default: `True`) ← CRÍTICO
   - Description (opcional)
   - Options (para select/list)

3. **Cambiar default en modelo**:
   ```python
   # En ProductAttributeConfig
   expose_in_search = Column(Boolean, default=True, nullable=False)  # Cambiar a True
   ```

4. **Migración para datos existentes**:
   ```sql
   UPDATE product_attribute_config
   SET expose_in_search = true
   WHERE key IN ('color', 'marca', 'talla', 'material');
   ```

**Archivos a crear/modificar**:
- Nuevo: `app/blueprints/attributes.py`
- Nuevo: `app/templates/attributes/index.html`
- Nuevo: `app/templates/attributes/form.html`
- Modificar: `app/models/product_attribute_config.py` (default=True)
- Migración: `migrations/versions/xxx_set_expose_default_true.py`

**Estimación**: 2-3 días

---

## 🎯 PRIORIDAD ALTA

### 1. Sistema de Aprendizaje Adaptativo por Cliente
**Estado**: 💡 Propuesto
**Complejidad**: Alta
**Impacto**: Crítico para calidad de resultados

**Problema Identificado**:
- Sistema actual prioriza similitud visual/compositiva sobre contenido semántico
- Ejemplo: Imagen de león matchea mejor con remera verde (sin león) que con remera del Rey León
- Cada cliente/tienda necesita ponderaciones diferentes según su catálogo

**Solución Propuesta - Opción 1 (MVP Rápido)**:
- Tabla `client_search_config` con 2 pesos configurables:
  - `semantic_weight`: Peso del contenido semántico (0.0-1.0)
  - `visual_weight`: Peso de composición visual (0.0-1.0)
- Interface en admin con sliders para ajustar manualmente
- Modificar función de similitud para usar pesos ponderados
- Valores default: semantic=0.6, visual=0.4

**Solución Propuesta - Opción 2 (Sistema Completo)**:
- Embeddings descomponibles: semantic, visual, color, style
- Sistema de feedback implícito (clicks, conversiones) y explícito (thumbs up/down)
- Algoritmo de optimización automática que ajusta pesos basándose en feedback
- A/B testing framework
- Dashboard de métricas de calidad

**Archivos a Modificar**:
- Nuevo: `app/models/client_search_config.py`
- Modificar: `app/blueprints/api.py` (función de similitud)
- Modificar: `app/blueprints/embeddings.py` (generación de embeddings múltiples)
- Nuevo: `app/blueprints/search_optimization.py` (admin interface)
- Nuevo tabla DB: `client_search_weights`
- Opcional: `search_feedback_log` para tracking

**Estimación**: 2-4 semanas (MVP) / 6-8 semanas (completo)

### 2. Validación Zero‑Shot Dinámica contra Catálogo (CLIP sin hardcode)
**Estado**: 💡 Propuesto (Alta prioridad)
**Complejidad**: Media
**Impacto**: Alto (reduce falsos positivos como "pantalón" en tienda que vende "remeras")

**Idea**:
- Usar CLIP en modo open‑vocabulary (zero‑shot) para describir la imagen sin forzar categorías.
- Generar términos dinámicos del catálogo del cliente: nombres/aliases de categorías, nombres de productos, tags y keywords de descripciones.
- Construir prompts a partir de esos términos y validar si la imagen matchea algún término del catálogo por encima de un umbral configurable por cliente.

**Contrato mínimo**:
- Input: imagen subida por el widget; client_id.
- Proceso: `get_client_searchable_terms(client) → prompts → similitud CLIP`.
- Output: `matches_catalog: bool`, `best_term`, `similarity`.
- Umbral: `catalog_match_threshold` en tabla/config del cliente.

**Criterios de aceptación**:
- Si la imagen no corresponde al catálogo, el endpoint devuelve 400 con error `content_not_in_catalog` y lista de familias que sí comercializa.
- Si corresponde, continúa el flujo normal (detección de categoría + ranking de productos).
- Sin hardcode de categorías globales; todo surge del catálogo del cliente.

**Dependencias**:
- Posible cache de embeddings de términos por cliente (Redis, TTL 24h).

**Estimación**: 1 semana (incluye prueba A/B en 1 cliente)

---

### 3. Búsqueda Híbrida Texto + Imagen (hints en la búsqueda)
**Estado**: 💡 Propuesto (Alta prioridad)
**Complejidad**: Media
**Impacto**: Alto (permite guiar la intención: "con león", "sin estampado", "color verde")

**Idea**:
- El widget permite un campo de texto opcional (hints) junto a la imagen.
- Se genera un embedding híbrido combinando `image_embedding` + `text_embedding` de CLIP con pesos configurables por cliente.

**Contrato**:
- Input: `image`, `query_text` (opcional), `client_id`.
- Proceso: `hybrid = α*image + (1-α)*text` (α configurable, ej. 0.7).
- Output: ranking de productos usando el embedding híbrido.

**Criterios de aceptación**:
- Si `query_text` está vacío, comportamiento actual (solo imagen).
- Con `query_text`, los resultados reflejan restricciones/señas del texto (ej.: prioriza "león" o "verde").
- Nuevo parámetro en API: `query_text` (opcional) y soporte en widget.

**Dependencias**:
- Posible reuso de `client_search_config` para peso α del híbrido.

**Estimación**: 1 semana (MVP)

---

## 🔧 PENDIENTES TÉCNICOS

### 1. Implementar SearchLog para Analytics
**Estado**: 🚧 Modelo creado, sin uso
**Complejidad**: Media
**Impacto**: Alto (métricas de negocio)
**Prioridad**: Alta

**Problema**:
- Modelo `SearchLog` existe pero no se está usando
- No hay tracking de búsquedas, clicks, conversiones
- Imposible medir calidad de resultados o ROI

**Tareas**:
- [ ] Activar logging en endpoint `/api/search`
- [ ] Guardar: client_id, image_hash, query_embedding, results, timestamp
- [ ] Implementar endpoint para tracking de clicks: `/api/search/click`
- [ ] Implementar endpoint para tracking de conversiones: `/api/search/convert`
- [ ] Dashboard en admin para ver métricas:
  - Búsquedas por día/semana
  - CTR (click-through rate)
  - Conversion rate
  - Productos más clickeados desde búsqueda
  - Búsquedas sin clicks (0 relevancia)

**Archivos a Crear/Modificar**:
- Modificar: `app/blueprints/api.py` (agregar logging)
- Nuevo: `app/blueprints/search_analytics.py`
- Modificar: Widget JS para enviar eventos de click/conversión

**Estimación**: 1 semana

---

### 2. Migrar Templates de Atributos por Industria a Base de Datos
**Estado**: 📋 Backlog (Fase 2)
**Complejidad**: Media
**Impacto**: Alto para escalabilidad
**Prioridad**: Media
**Relacionado con**: Sistema de atributos dinámicos + SearchOptimizer metadata scoring

**Contexto**:
- Actualmente los templates de atributos por industria están hardcoded en `app/utils/industry_templates.py`
- Funcionan bien para MVP pero limitan la flexibilidad de super_admin
- Cada industria (fashion, automotive, home, electronics, generic) tiene atributos diferentes con pesos de optimizer específicos

**Problema Actual**:
- Agregar nueva industria requiere modificar código y redesplegar
- Super admin no puede editar templates desde UI
- No hay historial de cambios en templates (solo Git)
- Testing requiere modificar diccionario Python

**Solución Propuesta**:
```sql
CREATE TABLE attribute_templates (
   id SERIAL PRIMARY KEY,
   industry VARCHAR(100) NOT NULL,     -- 'fashion', 'automotive', etc.
   key VARCHAR(100) NOT NULL,          -- 'color', 'marca', etc.
   label VARCHAR(200) NOT NULL,
   type VARCHAR(20) NOT NULL,          -- 'text', 'list', etc.
   is_system BOOLEAN DEFAULT TRUE,
   is_deletable BOOLEAN DEFAULT FALSE,
   optimizer_weight FLOAT,             -- Peso en SearchOptimizer
   description TEXT,
   options JSON,
   field_order INT DEFAULT 0,
   expose_in_search BOOLEAN DEFAULT TRUE,
   required BOOLEAN DEFAULT FALSE,
   created_at TIMESTAMP DEFAULT NOW(),
   updated_at TIMESTAMP DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_attr_templates_industry_key
ON attribute_templates(industry, key);
```

**Cambios Requeridos**:
1. **Migración Alembic**: Crear tabla `attribute_templates`
2. **Seed Script**: `python scripts/migrate_templates_to_db.py`
  - Lee `INDUSTRY_TEMPLATES` de `industry_templates.py`
  - Inserta todos los templates en BD
  - Verifica integridad de datos
3. **Modelo SQLAlchemy**: `app/models/attribute_template.py`
4. **Blueprint Admin**: `app/blueprints/attribute_templates.py`
  - CRUD para templates (solo super_admin)
  - UI para agregar/editar industrias
  - Validación de cambios (no romper configs existentes)
5. **Actualizar `seed_industry_attributes()`**:
  - Cambiar de leer dict a query DB
  ```python
  templates = AttributeTemplate.query.filter_by(industry=industry).all()
  ```

**Beneficios**:
- ✅ Super admin puede crear nuevas industrias desde UI
- ✅ Editar templates sin redesplegar
- ✅ Historial en DB con timestamps
- ✅ Testing más robusto (seed test DB)
- ✅ Multi-tenant escalable (diferentes templates por región?)

**Riesgos**:
- ⚠️ Migración de datos existentes (clientes con templates hardcoded)
- ⚠️ Validación compleja (cambios en templates no deben romper productos existentes)
- ⚠️ Caché necesario para performance (Redis?)

**Estimación**: 1-2 semanas
**Prioridad**: Baja (MVP funciona con hardcoded), Alta para multi-cliente/regiones

---

## ✅ COMPLETADOS - Pendientes Técnicos

### Eliminar Métodos Deprecados de Image Managers
**Estado**: ✅ COMPLETADO (20 Oct 2025)
**Complejidad**: Baja
**Impacto**: Medio (limpieza de código)

**Tareas Completadas**:
- ✅ Verificado que no hay usos de `image_manager.get_image_url()`
- ✅ Verificado que no hay usos de `cloudinary_manager.get_image_url()`
- ✅ Confirmado que todo usa `image.display_url` / `image.thumbnail_url`
- ✅ Eliminados métodos deprecados de `app/services/image_manager.py`
- ✅ Eliminados métodos deprecados de `app/services/cloudinary_manager.py`
- ✅ Documentado en `docs/IMAGE_HANDLING_GUIDE.md`

---

### Fix Duplicación de Paths en Cloudinary
**Estado**: ✅ COMPLETADO (20 Oct 2025)
**Complejidad**: Baja
**Impacto**: Medio (organización)

**Problema Resuelto**:
- Estructura anterior: `clip_v2/eve-s-store/products/eve-s-store/products/...` (duplicado)
- Estructura nueva: `clip_v2/eve-s-store/products/{product_id}/...`

**Solución Implementada**:
- ✅ Modificado `cloudinary_manager._generate_public_id()` para retornar solo path relativo
- ✅ Verificado en producción (Railway)
- ✅ Nuevas subidas usan estructura correcta

**Archivos Modificados**:
- `clip_admin_backend/app/services/cloudinary_manager.py`

---

### 4. Implementar SearchLog para Analytics
**Estado**: 🚧 Modelo creado, sin uso
**Complejidad**: Media
**Impacto**: Alto (métricas de negocio)

**Problema**:
- Modelo `SearchLog` existe pero no se está usando
- No hay tracking de búsquedas, clicks, conversiones
- Imposible medir calidad de resultados o ROI

**Tareas**:
- [ ] Activar logging en endpoint `/api/search`
- [ ] Guardar: client_id, image_hash, query_embedding, results, timestamp
- [ ] Implementar endpoint para tracking de clicks: `/api/search/click`
- [ ] Implementar endpoint para tracking de conversiones: `/api/search/convert`
- [ ] Dashboard en admin para ver métricas:
  - Búsquedas por día/semana
  - CTR (click-through rate)
  - Conversion rate
  - Productos más clickeados desde búsqueda
  - Búsquedas sin clicks (0 relevancia)

**Archivos a Crear/Modificar**:
- Modificar: `app/blueprints/api.py` (agregar logging)
- Nuevo: `app/blueprints/search_analytics.py`
- Modificar: Widget JS para enviar eventos de click/conversión

**Estimación**: 1 semana

---

## 🎨 MEJORAS DE UX/UI

### 5. Panel de "Entrenamiento" de Búsqueda (Admin)
**Estado**: 💡 Propuesto
**Complejidad**: Media
**Impacto**: Alto (relacionado con item #1)

**Funcionalidad Propuesta**:

**5.1. Modo Comparación**:
- Upload imagen de prueba desde admin
- Sistema muestra top 10 resultados actuales
- Admin puede arrastrar para reordenar como "debería ser"
- Sistema aprende preferencias y ajusta pesos

**5.2. Galería de Validación**:
- Muestra búsquedas reales de usuarios
- Admin valida con ✓ (buenos) / ✗ (malos)
- Acumula feedback para optimización automática

**5.3. Configuración Manual**:
- Sliders visuales para ajustar pesos:
  ```
  Prioridad en búsquedas:
  Contenido semántico (qué es):  ████████░░ 80%
  Apariencia visual (cómo se ve): ███░░░░░░░ 30%
  Color predominante:             █████░░░░░ 50%
  ```

**5.4. A/B Testing Automático**:
- Sistema prueba configuraciones alternativas
- Mide CTR y conversión
- Recomienda mejor config

**Dependencia**: Requiere implementar primero items #1 y #4

**Estimación**: 2 semanas (después de #1 y #4)

---

## 📊 MEJORAS DE DATOS

### 6. Enriquecer Metadata de Productos
**Estado**: 💡 Propuesto
**Complejidad**: Baja (técnica) / Alta (operativa - requiere trabajo manual)
**Impacto**: Alto para calidad de búsqueda

**Problema**:
- Productos tienen metadata mínima (nombre, SKU, precio)
- Sin tags semánticos: "león", "animal", "personaje"
- Sin descripciones detalladas para CLIP

**Soluciones**:

**6.1. Auto-Tagging con CLIP** (corto plazo):
- Usar CLIP para detectar objetos/conceptos en imágenes
- Generar tags automáticos: "animal", "león", "ropa deportiva", etc.
- Guardar en campo `auto_tags` (JSONB)
- Usar tags en generación de embeddings contextuales

**6.2. Interface de Tagging Manual** (mediano plazo):
- Campo "Tags" en formulario de producto
- Autocompletado de tags comunes
- Sugerencias basadas en detección automática

**6.3. Descripción Estructurada** (largo plazo):
- Template de descripción con campos específicos:
  - Tipo de prenda
  - Estilo (casual, formal, deportivo)
  - Elementos visuales (estampado, liso, rayas)
  - Temática/personajes (si aplica)
  - Público objetivo

**Archivos a Modificar**:
- `app/models/product.py` (agregar campo auto_tags)
- `app/blueprints/products.py` (form con tags)
- `app/blueprints/embeddings.py` (usar tags en contexto)
- Nueva función: `generate_auto_tags_with_clip()`

**Estimación**: 1 semana (auto-tagging) + 1 semana (UI manual)

---

## 🔐 SEGURIDAD Y PERFORMANCE

### 7. Rate Limiting Granular por Cliente
**Estado**: ⚠️ Básico implementado, mejorable
**Complejidad**: Media
**Impacto**: Medio

**Mejoras Propuestas**:
- Rate limiting diferenciado por plan (Free/Pro/Enterprise)
- Rate limiting por endpoint (search vs upload vs admin)
- Dashboard de uso en tiempo real
- Alertas cuando cliente se acerca al límite
- Upgrade automático de plan

**Estimación**: 1 semana

---

### 8. Caching de Embeddings de Búsqueda
**Estado**: 💡 Propuesto
**Complejidad**: Baja
**Impacto**: Medio (performance)

**Problema**:
- Cada búsqueda genera embedding desde cero
- Si dos usuarios buscan misma imagen → cálculo duplicado

**Solución**:
- Cache en Redis con key = hash de imagen
- TTL de 1 hora
- Invalidar si se actualizan pesos del cliente

**Estimación**: 2-3 días

---

## 🧪 TESTING Y CALIDAD

### 9. Suite de Tests
**Estado**: ❌ No existe
**Complejidad**: Alta
**Impacto**: Alto (calidad y confianza)

**Tests Prioritarios**:
- Unit tests para funciones de similitud
- Integration tests para pipeline de embeddings
- E2E tests para widget de búsqueda
- Tests de regresión para casos conocidos (león vs no-león)

**Estimación**: 2 semanas

---

### 10. Monitoring y Alertas
**Estado**: ⚠️ Logs básicos
**Complejidad**: Media
**Impacto**: Alto (operaciones)

**Mejoras**:
- Dashboard de salud del sistema
- Alertas por Slack/Email:
  - Errores en generación de embeddings
  - Búsquedas fallidas (400/500)
  - Alta latencia en API
  - Cliente excediendo rate limit
- Métricas en Railway dashboard

**Estimación**: 1 semana

---

## 📝 DOCUMENTACIÓN

### 11. Documentación de API Externa
**Estado**: ❌ Falta
**Complejidad**: Baja
**Impacto**: Alto (para clientes/integradores)

**Contenido Necesario**:
- Swagger/OpenAPI spec para `/api/search`
- Ejemplos de integración (JS, Python, cURL)
- Guía de troubleshooting
- Changelog de versiones

**Estimación**: 3 días

---

## 🚀 FEATURES NUEVAS

### 12. Búsqueda por Texto + Imagen Híbrida
**Estado**: 💡 Idea
**Complejidad**: Media
**Impacto**: Alto

**Descripción**:
- Usuario puede combinar texto + imagen: "remera roja de león"
- Sistema genera embedding híbrido CLIP text+image
- Resultados más precisos

**Estimación**: 1 semana

---

### 13. Búsqueda por Región de Interés (ROI)
**Estado**: 💡 Idea
**Complejidad**: Alta
**Impacto**: Medio

**Descripción**:
- Usuario dibuja recuadro en imagen para enfocarse en región específica
- Sistema genera embedding solo de esa región
- Útil para imágenes con múltiples objetos

**Estimación**: 2 semanas

---

### 14. Recomendaciones "También te puede interesar"
**Estado**: 💡 Idea
**Complejidad**: Baja
**Impacto**: Alto (ventas)

**Descripción**:
- Dado un producto, encontrar N productos similares
- Usar embeddings existentes
- Widget embebible para página de producto

**Estimación**: 1 semana

---

## 📋 RESUMEN DE PRIORIZACIÓN

### Sprint 1 (2 semanas)
1. 🧠 Validación Zero‑Shot Dinámica contra Catálogo (#2 Prioridad Alta)
2. 📝 Búsqueda Híbrida Texto + Imagen (MVP) (#3 Prioridad Alta)
3. ✅ Fix Cloudinary paths (30min)
4. 🔧 Eliminar métodos deprecados (#2 Pendientes Técnicos)

### Sprint 2 (2 semanas)
5. 🎯 MVP Sistema de Ponderación Adaptativa (#1 opción 1)
6. 📊 Implementar SearchLog y analytics básicas (#4)

### Sprint 3 (2 semanas)
6. 🎨 Panel de entrenamiento - Modo Comparación (#5.1)
7. 🎨 Interface de tagging manual (#6.2)

### Sprint 4 (2 semanas)
8. 🧪 Suite de tests básica (#9)
9. 🔐 Caching de embeddings (#8)

### Backlog (priorizar según feedback de clientes)
- Sistema completo de ponderación multi-factor (#1 opción 2)
- Panel completo de entrenamiento (#5 completo)
- Rate limiting granular (#7)
- Monitoring avanzado (#10)
- Documentación API (#11)
- Features nuevas (#12, #13, #14)

---

## 🔄 CHANGELOG

**24 Oct 2025**:
- ✅ Marcado como COMPLETADO: Sistema de Gestión de Inventario (API Externa + Panel Admin)
- ✅ Marcado como COMPLETADO: Eliminar Métodos Deprecados de Image Managers
- ✅ Marcado como COMPLETADO: Fix Duplicación de Paths en Cloudinary
- ➕ Agregado item: Análisis y Modularización de app.py (Arquitectura)
  - Análisis completo en `docs/APP_PY_ANALYSIS.md`
  - 408 líneas → propuesta de ~250 líneas en 5 archivos
  - Plan de refactorización en 5 fases
  - Código muerto detectado (3 elementos)
  - Acciones inmediatas identificadas
- 📝 Reorganizada sección "PENDIENTES TÉCNICOS" (completados → sección separada)

**23 Oct 2025**:
- ➕ Agregado item #1 URGENTE: Detección Multi-Producto con CLIP (Zero-Shot Multi-Categoría)
  - Pipeline completo diseñado
  - Casos de uso identificados
  - Estimación: 3-4 días
  - Prioridad MÁXIMA

**22 Oct 2025**:
- Documento creado
- Agregado item #1: Sistema de Aprendizaje Adaptativo (prioridad alta)
- Agregado item #2: Validación Zero‑Shot Dinámica contra Catálogo (prioridad alta)
- Agregado item #3: Búsqueda Híbrida Texto + Imagen (prioridad alta)
- Agregado item #3: Fix duplicación Cloudinary paths (pendiente push)
- Agregados items #2-#14 recopilados de TODOs y discusiones

---

## 📎 REFERENCIAS

- `docs/APP_PY_ANALYSIS.md` - Análisis completo y plan de refactorización de app.py (#ARQUITECTURA)
- `docs/IMAGE_HANDLING_GUIDE.md` - Métodos deprecados eliminados (#COMPLETADO)
- `docs/CENTROID_MIGRATION.md` - Optimización de centroides
- `docs/API_INVENTARIO_EXTERNA.md` - API Externa de Inventario (#COMPLETADO)
- `docs/TOOLS_REFERENCE.md` - Referencia de herramientas del proyecto
- `app/models/search_log.py` - Modelo para analytics (#1 Pendientes Técnicos)
- `REFACTOR_COMPLETE_20OCT2025.md` - Refactor reciente completado
- `.github/copilot-instructions.md` - Guías de desarrollo del proyecto

