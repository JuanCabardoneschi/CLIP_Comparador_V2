# BACKLOG DE MEJORAS Y PENDIENTES
**Fecha de Creación**: 22 Octubre 2025
**Última Actualización**: 15 Noviembre 2025

---

## 🎯 WIDGET DUAL-TAB & CONFIGURACIÓN - FUNCIONALIDADES PENDIENTES (Agregado 15 Nov 2025)

### Estado Actual
El widget v3 (`clip-widget-embed-v3.js`) tiene búsqueda dual:
- **Tab 1 (Visual)**: GPT-4V + CLIP vía `/api/search/gpt4v-unified`
- **Tab 2 (Texto)**: MiniLM + CLIP vía `/api/search/text`

**✅ IMPLEMENTADO (15 Nov 2025)**:
- Dual-tab widget funcional (Visual + Texto)
- Configuración simplificada en UI (solo "Similitud Visual Mínima" y "Max Results")
- Thresholds MiniLM optimizados (0.45 color, 0.50 tipo, 0.40 contexto)
- Pesos del Optimizer deshabilitados (grises) para futura implementación
- Endpoint GPT4V-unified usa `StoreSearchConfig` en lugar de valores hardcodeados

### 🟡 ALTA PRIORIDAD - Próxima Versión

#### 1. SearchOptimizer Lite con Pesos Configurables
**Estado**: 📋 PENDIENTE
**Prioridad**: ALTA
**Complejidad**: MEDIA
**Estimación**: 5-6 horas

**Funcionalidad**:
Reactivar los sliders de "Balanceo de Resultados" en la UI y conectarlos a una lógica de scoring multi-capa:
- **Visual Weight**: Similitud CLIP (imagen vs imagen)
- **Metadata Weight**: Coincidencia de atributos (color, marca, material)
- **Business Weight**: Lógica de negocio (stock, destacados, descuentos)

**Beneficio**: Rankings más sofisticados que consideran no solo parecido visual sino también atributos semánticos y estrategia comercial.

**Implementación**:
```python
# En gpt4v_unified_search() y text_search():
config = StoreSearchConfig.query.filter_by(client_id=client.id).first()
visual_w = config.visual_weight if config else 0.6
metadata_w = config.metadata_weight if config else 0.3
business_w = config.business_weight if config else 0.1

final_score = (
    visual_w * clip_similarity +
    metadata_w * metadata_score +  # Color/brand matching
    business_w * business_score    # Stock + featured
)
```

**Requiere**:
- Reactivar sliders en `search_config/edit.html`
- Agregar función `calculate_metadata_score()` y `calculate_business_score()`
- Actualizar endpoints para usar scoring multi-capa

---

#### 2. Detección Multi-Prenda en Queries de Texto
**Estado**: 💡 IDEA / DISEÑO
**Prioridad**: MEDIA
**Complejidad**: MEDIA
**Estimación**: 4-5 horas

**Funcionalidad**:
- Usuario escribe: "remera blanca y jean azul"
- Sistema detecta múltiples tipos de prenda en una sola query
- Retorna resultados por cada categoría detectada (remeras + jeans)

**Beneficio**: UX más natural para búsquedas combinadas (outfits completos).

**Implementación Actual**:
- `llm_query_normalizer.py` ya tiene `_semantic_match_multiple()` pero solo se usa para contextos
- Necesita extender para tipos de prenda:
```python
tipos_detectados = _semantic_match_multiple(query, tipos, threshold=0.50, top_k=3)
# Ejecutar búsqueda por cada tipo y consolidar resultados
```

**Requiere**:
- Modificar `text_search()` para procesar múltiples tipos
- Ajustar widget para mostrar resultados agrupados por categoría
- UI con tabs/secciones para cada tipo de prenda

---

## 🎯 ENDPOINT GPT4V-UNIFIED - FUNCIONALIDADES PENDIENTES (Agregado 13 Nov 2025)

### Estado Actual
El endpoint `/api/search/gpt4v-unified` usa GPT-4V para detección de categorías + CLIP para búsqueda visual.

**✅ IMPLEMENTADO (13 Nov 2025)**:
- Imagen primaria (`is_primary=True`) con fallback
- Filtrado de atributos por `product_attribute_config` (`expose_in_search=true`)
- Extracción de `url_producto` del JSONB (link a ficha externa)
- Stock con manejo de valores `None`
- Autenticación por API Key
- CORS para widget cross-origin
- Threshold y max_results configurables

### 🟡 MEDIA PRIORIDAD - Para Evaluar

#### 1. Color Matching Simplificado
**Estado**: 📋 PENDIENTE
**Prioridad**: MEDIA
**Complejidad**: BAJA
**Estimación**: 2-3 horas

**Funcionalidad**:
- Parsear `user_intent` de GPT-4V para detectar colores mencionados (ej: "camisa negra", "vestido rojo")
- Aplicar boost +0.30 a productos que tengan ese color en `attributes->>'color'`
- Mejora el ranking cuando GPT-4V menciona colores específicos

**Razón**: GPT-4V ya menciona colores en `mensaje_usuario`, no necesitamos detección separada.

**Implementación**:
```python
# En gpt4v_unified_search(), después de calcular similitudes:
detected_colors = _extract_colors_from_user_intent(gpt4v_result.get('mensaje_usuario', ''))
if detected_colors:
    for result in product_similarities:
        product_color = result['product'].attributes.get('color', '').lower()
        if any(color in product_color for color in detected_colors):
            result['similarity'] += 0.30  # Color boost
```

---

#### 2. SearchOptimizer Lite (Sistema de Scoring 3 Capas)
**Estado**: 📋 PENDIENTE
**Prioridad**: MEDIA
**Complejidad**: MEDIA
**Estimación**: 4-5 horas

**Funcionalidad**:
Recalcular score final combinando 3 dimensiones:
- **Visual Layer (70%)**: Similitud CLIP (ya calculada)
- **Metadata Layer (20%)**: Color matching si GPT-4V lo detecta
- **Business Layer (10%)**:
  - Boost por `stock > 0`
  - Boost por `is_featured = True`
  - Boost por descuentos activos

**Beneficio**: Rankings más sofisticados considerando aspectos de negocio, no solo similitud visual.

**Versión Simplificada** (sin `StoreSearchConfig`, pesos fijos):
```python
final_score = (
    0.70 * visual_similarity +
    0.20 * metadata_score +  # Solo color matching
    0.10 * business_score    # stock + featured
)
```

**Migración Futura**: Usar `StoreSearchConfig` para pesos configurables por cliente.

---

### 🔵 FUTURO - Diseño Estratégico

#### 3. Búsqueda Híbrida Texto + Imagen
**Estado**: 💡 IDEA / DISEÑO
**Prioridad**: BAJA (Post-MVP)
**Complejidad**: ALTA
**Estimación**: 8-10 horas

**Funcionalidad**:
- Usuario sube foto + escribe texto adicional
- Ejemplo: Foto de camisa roja + texto "pero en azul"
- GPT-4V analiza imagen + texto simultáneamente
- Detecta categoría (camisa) + override de atributos (color: azul)

**Beneficios**:
- UX avanzada: refinamiento de búsqueda visual con lenguaje natural
- Casos de uso: "igual pero más barato", "similar pero en talla L"

**Requiere**:
- Modificar widget para campo de texto opcional
- Ajustar prompt de GPT-4V para procesar ambos inputs
- Lógica de merging: imagen (categoría) + texto (filtros/modificadores)

**Bloqueantes**:
- Validar con usuarios si necesitan esta feature
- Definir casos de uso prioritarios

---

### ❌ NO IMPLEMENTAR (Redundantes con GPT-4V)

- **Category Boost** (+15%): GPT-4V ya filtra por categoría explícitamente antes de CLIP
- **Normalización LLM de queries**: No hay input de texto actualmente
- **Detección de color separada**: GPT-4V ya lo menciona en `mensaje_usuario`
- **Nombre/SKU matching**: Solo relevante para búsqueda por texto (no implementada)
- **Búsqueda multi-categoría con centroides**: GPT-4V ya detecta múltiples categorías

---

## 🔧 MEJORAS TÉCNICAS PENDIENTES (Agregado 13 Nov 2025)

### 1. Reemplazar googletrans por deep-translator
**Estado**: 📋 PENDIENTE
**Prioridad**: MEDIA
**Complejidad**: BAJA
**Estimación**: 1-2 horas

**Problema**:
- `googletrans==4.0.0rc1` (release candidate) está roto con versiones modernas de httpcore
- Requiere fijar `httpcore==0.18.0` y `httpx==0.25.0` (versiones viejas)
- Genera conflictos de dependencias en pip

**Solución Propuesta**:
Migrar a `deep-translator` que es más moderna, estable y mantenida:
```python
# Antes (googletrans)
from googletrans import Translator
translator = Translator()
result = translator.translate("camisa", src='es', dest='en')

# Después (deep-translator)
from deep_translator import GoogleTranslator
result = GoogleTranslator(source='es', target='en').translate("camisa")
```

**Beneficios**:
- ✅ Librería activamente mantenida (última versión 2024)
- ✅ Sin dependencias problemáticas
- ✅ Soporta múltiples servicios de traducción (Google, DeepL, etc.)
- ✅ API más simple y limpia

**Archivos a Modificar**:
- `clip_admin_backend/app/blueprints/api.py` (línea 30: import googletrans)
- `requirements.txt` (reemplazar googletrans + httpcore por deep-translator)

**Testing**:
```bash
pip install deep-translator
# Probar endpoint de búsqueda con categorías en español
```

---

## 🚨 CRÍTICO - ANTES DE SUBIR A PRODUCCIÓN

### ⚠️ Migración de Búsqueda Textual - Preservar Configuraciones de Cliente
**Estado**: ✅ COMPLETADO (CERRADO 31 Octubre 2025)
**Complejidad**: Media
**Impacto**: CRÍTICO (puede borrar datos de clientes en producción)
**Prioridad**: MÁXIMA - BLOQUEANTE PARA DEPLOY
**Fecha agregada**: 31 Octubre 2025

**Problema Identificado**:
Durante el desarrollo local de la búsqueda textual (31 Oct 2025), se detectó que algunas migraciones/actualizaciones relacionadas con:
- Migración de embeddings CLIP
- Extracción de información de vectores
- Actualización de atributos dinámicos

**Pueden haber borrado/sobrescrito**:
- ✅ Configuraciones de `product_attribute_config` (atributos custom del cliente)
- ✅ Campo `expose_in_search` (configuración de visibilidad en resultados)
- ✅ Atributos JSONB de productos existentes
- ✅ URLs de productos (`url_producto`)
- ✅ Valores de atributos custom

**Riesgo en Producción**:
Si se ejecutan los mismos comandos/migraciones en Railway sin validación previa:
- Los clientes perderían sus configuraciones de atributos
- Los productos perderían campos custom configurados
- Las integraciones con ecommerce (URLs) dejarían de funcionar
- Pérdida de datos sin backup

**Acciones Requeridas ANTES del Deploy**:

1. **Backup Completo de Railway** (OBLIGATORIO):
   ```bash
   python railway_db_tool.py sql -e "SELECT * FROM product_attribute_config;" > backup_attr_config.sql
   python railway_db_tool.py sql -e "SELECT id, attributes FROM products;" > backup_products_attrs.sql
   ```

2. **Validar Scripts de Migración**:
   - [ ] Revisar `migrations/` para scripts que modifiquen `product_attribute_config`
   - [ ] Verificar que NO hagan `DELETE` o `UPDATE` sin `WHERE client_id`
   - [ ] Confirmar que scripts usen `INSERT ... ON CONFLICT DO NOTHING` (no `UPDATE`)

3. **Testing en Staging/Restauración Local**:
   ```bash
   # Restaurar BD de Railway a local
   .\restore_from_railway.ps1

   # Ejecutar migraciones en local
   # Validar que NO se pierdan datos

   # Comparar antes/después
   python check_clients_id.py
   ```

4. **Deploy Seguro en Railway**:
   - [ ] Crear backup manual en Railway dashboard
   - [ ] Ejecutar migraciones UNA POR UNA (no batch)
   - [ ] Validar después de cada migración con `railway_db_tool.py counts`
   - [ ] Tener rollback plan (SQL scripts de restore)

5. **Validación Post-Deploy**:
   - [ ] Verificar que cliente Demo Fashion Store mantiene sus atributos
   - [ ] Confirmar que `expose_in_search` no se resetee a `false`
   - [ ] Validar que URLs de productos sigan presentes
   - [ ] Probar búsqueda textual con resultados completos (atributos + URLs)

**Archivos a Revisar Antes de Deploy**:
- `migrations/*.sql` - Todos los scripts SQL
- `migrations/*.py` - Scripts Python de migración
- `tools/migrations/*.py` - Herramientas de migración
- `setup_local_postgres.py` - Setup inicial
- Cualquier script que modifique `product_attribute_config` o `products.attributes`

**Contexto**:
Esta funcionalidad (búsqueda textual) es la primera feature grande desarrollada post-Railway deploy.
Las migraciones locales pueden haber sido más agresivas porque se asumía BD limpia.
Railway tiene datos reales de clientes que NO pueden perderse.

**Checklist de Deploy Seguro**: COMPLETADO
- [x] Backup completo de Railway descargado y validado
- [x] Scripts de migración revisados y aprobados
- [x] Testing en local con datos de Railway restaurados
- [x] Plan de rollback documentado
- [x] Validación de que atributos custom se preservan
- [x] Confirmación de que `expose_in_search` no se resetea
- [x] Testing post-deploy de búsqueda textual en Railway
- [x] Verificación de que URLs de productos funcionan

**Responsable**: Validar antes del próximo deploy a Railway
**Deadline**: ANTES de ejecutar cualquier migración en producción

---

## ✅ COMPLETADO - Octubre 2025

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

### 🎯 Admin Panel de Atributos de Productos (30 Oct 2025)
**Estado**: ✅ COMPLETADO
**Complejidad**: Media
**Impacto**: Alto

**Implementado**:
- ✅ Blueprint `/attributes/` con CRUD completo
- ✅ `GET /attributes/` → Lista todos los atributos del cliente
- ✅ `GET /attributes/create` → Formulario crear atributo
- ✅ `POST /attributes/create` → Guardar nuevo atributo
- ✅ `GET /attributes/edit/<id>` → Formulario editar
- ✅ `POST /attributes/edit/<id>` → Guardar cambios
- ✅ `POST /attributes/delete/<id>` → Eliminar atributo
- ✅ Formulario incluye: Key, Label, Type, Required, Options, Field Order
- ✅ Campo `expose_in_search` implementado (checkbox)
- ✅ Templates: `app/templates/attributes/index.html`, `form.html`

**Archivos Creados**:
- `clip_admin_backend/app/blueprints/attributes.py`
- `clip_admin_backend/app/templates/attributes/index.html`
- `clip_admin_backend/app/templates/attributes/form.html`

**Nota**: Default de `expose_in_search` es `False`. Si se desea cambiar a `True`, es decisión de negocio (no bloqueante).

---

### 🖼️ Fix Duplicación de Paths en Cloudinary (30 Oct 2025)
**Estado**: ✅ COMPLETADO Y EN PRODUCCIÓN
**Complejidad**: Baja
**Impacto**: Medio

**Implementado**:
- ✅ Modificado `cloudinary_manager._generate_public_id()`
- ✅ Estructura actual: `products/{product_id}/{filename}`
- ✅ Eliminada duplicación anterior: `clip_v2/{client}/products/{client}/products/...`

**Archivo Modificado**:
- `clip_admin_backend/app/services/cloudinary_manager.py` (línea 50)

---

### 🤖 Auto-Completado de Atributos con CLIP (31 Oct 2025)
**Estado**: ✅ COMPLETADO
**Complejidad**: Media
**Impacto**: Alto (mejora UX y calidad de datos)
**Fecha agregada**: 31 Octubre 2025

**Implementado**:
- ✅ Servicio `AttributeAutofillService` con análisis CLIP
- ✅ Detección automática de atributos visuales (color, material, estilo, etc.)
- ✅ Clasificación de tags (formal, casual, deportivo, etc.)
- ✅ Integración en creación de productos (automático)
- ✅ Endpoint API para trigger manual: `POST /products/<id>/autofill-attributes`
- ✅ Modo conservador: NO sobrescribe valores del usuario (overwrite=False por defecto)
- ✅ Soporte para atributos multi-select
- ✅ Templates de prompts específicos por tipo de atributo
- ✅ Ponderación de imagen primaria (1.5x weight)

**Funcionalidades**:
1. **Auto-completado al crear producto**:
   - Se ejecuta automáticamente después de subir imágenes
   - Solo completa atributos vacíos
   - Respeta valores ingresados manualmente por el usuario
   - Muestra mensaje con atributos detectados

2. **Endpoint API Manual**:
   ```bash
   POST /products/<product_id>/autofill-attributes
   Body: {"overwrite": false}  # opcional
   ```
   - Permite re-analizar producto existente
   - `overwrite=false`: Solo completa vacíos (default)
   - `overwrite=true`: Sobrescribe todos los atributos

3. **Algoritmo de Detección**:
   - Analiza todas las imágenes del producto
   - Usa templates de prompts contextualizados por categoría
   - Sistema de votación ponderado por confianza
   - Threshold de confianza: 0.2 (20%)
   - Top 3 tags por relevancia

**Archivos Creados**:
- `clip_admin_backend/app/services/attribute_autofill_service.py`

**Archivos Modificados**:
- `clip_admin_backend/app/blueprints/products.py`:
  - Integración en `create()` función
  - Nuevo endpoint `autofill_attributes()`

**Script Original** (usado como referencia):
- `auto_fill_attributes.py` (raíz del proyecto)

**Próximos Pasos** (Opcionales):
- [ ] Agregar botón UI en panel de productos para trigger manual
- [ ] Mostrar preview de atributos detectados antes de guardar
- [ ] Estadísticas de confianza en UI
- [ ] Batch autofill para múltiples productos
- [ ] Configurar threshold de confianza por cliente

**Notas**:
- El servicio usa lazy loading de CLIP (solo se carga al primer uso)
- Compatible con Railway (CPU-only)
- No bloquea creación de producto si falla el autofill
- Reutiliza modelo CLIP ya cargado si existe

---

## 🔥 URGENTE - FASE 5 (Sistema en Producción)

### 0. **[LUNES 4 NOV] Parametrizar Ranking de Búsqueda en system_config.json**
**Estado**: 💡 Propuesto
**Complejidad**: Baja (2 horas)
**Impacto**: Medio (permite ajustes sin código)
**Prioridad**: MEDIA
**Fecha agregada**: 1 Noviembre 2025

**Problema**:
- Thresholds y pesos de ranking están hardcodeados en `api.py` (0.75, 0.45, 0.50, 0.35, etc.)
- No se pueden ajustar sin modificar código
- Dificulta tuning fino por cliente

**Solución Propuesta**:

**1. Agregar a `system_config.json`**:
```json
{
  "search": {
    "weight_clip": 0.5,
    "weight_attributes": 0.35,
    "weight_color": 0.05,
    "weight_text": 0.1,
    "color_threshold_strong": 0.75,
    "color_threshold_medium": 0.45,
    "color_soft_boost_max": 0.2,
    "diversity_threshold": 0.75
  }
}
```

**2. Modificar `_calculate_attribute_match()` y scoring en `text_search()`**:
```python
# En lugar de:
if color_sim >= 0.75:

# Leer de config:
search_cfg = system_config.get_section('search')
th_strong = float(search_cfg.get('color_threshold_strong', 0.75))
if color_sim >= th_strong:
```

**3. Aplicar a todos los thresholds/pesos hardcodeados**

**Beneficios**:
- ✅ Ajustes en caliente sin redeploy (editar JSON y reiniciar app)
- ✅ A/B testing de parámetros fácil
- ✅ Documentación clara de valores default
- ✅ Preparación para config per-client

**Archivos a modificar**:
- `system_config.json` (agregar claves)
- `clip_admin_backend/app/blueprints/api.py`:
  - `_calculate_attribute_match()`: líneas 2806, 2822, 2836
  - `text_search()`: líneas 2548-2550, 2565
  - `_filter_diverse_categories()`: línea 1543, 1721

**Testing**:
- Verificar que valores default funcionan igual
- Probar modificar thresholds y ver cambios en ranking
- Validar que valores inválidos usan fallback

#### 0.a Análisis: impacto real de 60/30/10 en búsqueda visual (multi-categoría)
- Hoy el SearchOptimizer se inicializa con v=0.6, m=0.3, b=0.1, pero en la ruta visual multi‑categoría se llama con `detected_attributes = {}` → la capa Metadata aporta 0.0.
- La capa Business aporta prácticamente un binario por stock>0 (≈1.0) y penaliza solo sin stock. No ordena entre productos con stock.
- Efecto neto actual: score ≈ 60% Visual + 10% Business (si hay stock) + 0% Metadata. Por eso el color NO desempata (p. ej., chaqueta negra vs blanca con scores cercanos).

Opciones consideradas (opt‑in por tienda):
- A) Pasar `{'color': detected_color}` al optimizer solo si la confianza de color por categoría ≥ 0.70; activa realmente el 30% Metadata como desempate. Controlado por flag de tienda.
- B) Tie‑break local por color cuando |Δvisual| < ε (p.ej. 0.02), sin tocar optimizer. Más acotado, menos consistente.

Recomendación: A) con flag por tienda y logs; mantener paridad por defecto (flag OFF).

Implicancias de UI (diales personalizados):
- Exponer en Panel → Configuración de Búsqueda:
  - Toggle: “Usar metadata en búsqueda visual”
  - Toggle: “Usar color como desempate en visual”
  - Slider de confianza de color (0.5–0.9, default 0.70)
  - Pesos por atributo dentro de Metadata (color_weight, brand_weight, …)

Hardcodes a consolidar (relacionado con este item y el punto 0):
- Thresholds de color, pesos de scoring y diversidad actualmente en `api.py` (ver referencias existentes en este backlog) y en lógica de text search. Centralizar en `system_config.json` y/o `StoreSearchConfig.metadata_config`.

Checklist para Lunes 4 Nov (tuning sin tocar código):
- [ ] Agregar toggles/valores por tienda en `StoreSearchConfig.metadata_config` (sin migración; defaults OFF)
- [ ] Habilitar lectura de thresholds/pesos desde `system_config.json` (punto 0)
- [ ] Definir contrato de claves por atributo para el optimizer (color_weight, brand_weight, …)
- [ ] Validar en Eve Store (dev) con imagen de chaqueta blanca vs negra y shorts+musculosa

---

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

## 🎯 PRIORIDAD ALTA

### 1. Generalizar Auto-Clasificación de Atributos (Desacoplar de Ropa)
**Estado**: 💡 Propuesto
**Complejidad**: Media-Alta
**Impacto**: Crítico (sistema actualmente sesgado a ropa)
**Prioridad**: Alta
**Fecha agregada**: 30 Octubre 2025

**Problema Identificado**:
El sistema de auto-clasificación de atributos (`auto_fill_attributes.py`) tiene componentes hardcoded orientados a ropa:

1. **TAG_OPTIONS Hardcoded**:
   ```python
   TAG_OPTIONS = [
       "formal", "casual", "deportivo", "elegante", "moderno", "clásico",
       "vintage", "urbano", "profesional", "juvenil", "trabajo", "fiesta",
       "verano", "invierno", "unisex", "masculino", "femenino", "infantil",
       "premium", "económico", "cómodo", "ajustado", "holgado"
   ]
   ```
   ❌ No funciona para autos, muebles, electrónica, etc.

2. **ATTRIBUTE_PROMPT_TEMPLATES Hardcoded**:
   ```python
   ATTRIBUTE_PROMPT_TEMPLATES = {
       "color": "a {value} colored {category}",
       "material": "a {category} made of {value}",
       "estilo": "a {value} style {category}",
       ...
   }
   ```
   ❌ Templates funcionan para ropa pero no para otros verticales

3. **Sinónimos de Boost Hardcoded**:
   ```python
   value_synonyms = {
       "negra": ["negro", "negra", "black"],
       "casual": ["casual", "informal"],
       ...
   }
   ```
   ❌ Solo incluye sinónimos de moda/ropa

**Impacto en Otros Verticales**:
- **Vendedor de Autos**: Necesita tags como "sedan", "suv", "deportivo", "4x4", "híbrido"
- **Mueblería**: Tags como "moderno", "minimalista", "rústico", "vintage", "funcional"
- **Electrónica**: Tags como "portátil", "gaming", "profesional", "inalámbrico"

**Solución Propuesta**:

**Opción 1 - MVP (1-2 semanas)**:
- Mover `TAG_OPTIONS` a tabla `client_tag_config` (similar a `product_attribute_config`)
- Admin UI para configurar tags por cliente
- Mantener templates actuales como default (funcionan razonablemente bien)
- Permitir override de templates en tabla `client_attribute_template_config`

**Opción 2 - Sistema Completo (3-4 semanas)**:
- Templates dinámicos por cliente y tipo de negocio
- Sinónimos configurables por cliente (tabla `client_synonym_config`)
- Biblioteca de presets por vertical: "ROPA", "AUTOS", "MUEBLES", "ELECTRONICA"
- Sistema de sugerencias automáticas de tags basado en catálogo existente
- UI en admin: "Crear desde preset" → copiar configuración base

**Estructura DB Propuesta**:
```sql
-- Tags configurables por cliente
CREATE TABLE client_tag_config (
    id UUID PRIMARY KEY,
    client_id UUID REFERENCES clients(id),
    tag_name VARCHAR(50) NOT NULL,
    tag_category VARCHAR(50), -- ej: "style", "season", "audience"
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Templates de prompts por cliente
CREATE TABLE client_attribute_template_config (
    id UUID PRIMARY KEY,
    client_id UUID REFERENCES clients(id),
    attribute_key VARCHAR(50) NOT NULL, -- ej: "color", "tipo_motor"
    prompt_template TEXT NOT NULL, -- ej: "a {value} {category} car"
    created_at TIMESTAMP DEFAULT NOW()
);

-- Sinónimos configurables
CREATE TABLE client_synonym_config (
    id UUID PRIMARY KEY,
    client_id UUID REFERENCES clients(id),
    base_word VARCHAR(50) NOT NULL,
    synonyms JSONB NOT NULL, -- ["palabra1", "palabra2"]
    language VARCHAR(10) DEFAULT 'es',
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Presets por Vertical** (archivo JSON):
```json
{
  "ROPA": {
    "tags": ["formal", "casual", "deportivo", ...],
    "templates": {
      "color": "a {value} colored {category}",
      "material": "a {category} made of {value}"
    },
    "synonyms": {"negra": ["negro", "negra", "black"], ...}
  },
  "AUTOS": {
    "tags": ["sedan", "suv", "deportivo", "4x4", "híbrido", "eléctrico"],
    "templates": {
      "color": "a {value} {category} car",
      "tipo_motor": "a {category} with {value} engine",
      "carroceria": "a {value} body style {category}"
    },
    "synonyms": {"roja": ["rojo", "roja", "red"], ...}
  },
  "MUEBLES": {
    "tags": ["moderno", "minimalista", "rústico", "vintage", "funcional"],
    "templates": {
      "color": "a {value} colored {category} furniture",
      "material": "{category} furniture made of {value}",
      "estilo": "{value} style {category}"
    }
  }
}
```

**Archivos a Crear/Modificar**:
- Nuevo: `migrations/create_client_vertical_config.sql`
- Nuevo: `app/models/client_vertical_config.py`
- Nuevo: `app/blueprints/vertical_config.py` (admin CRUD)
- Nuevo: `shared/vertical_presets.json` (biblioteca de presets)
- Modificar: `auto_fill_attributes.py` (leer de DB en lugar de constantes)
- Nuevo: `app/templates/vertical_config/` (UI admin)

**Flujo de Onboarding Mejorado**:
1. Cliente nuevo → Admin selecciona vertical ("ROPA", "AUTOS", etc.)
2. Sistema copia preset automáticamente
3. Admin revisa y ajusta tags/templates/sinónimos
4. Cliente ejecuta `auto_fill_attributes.py` → usa configuración personalizada

**Backward Compatibility**:
- Clientes existentes sin configuración → usar defaults actuales (ropa)
- Migración opcional: detectar vertical por categorías existentes

**Testing**:
- Tienda de ropa (actual)
- Concesionaria de autos (nuevo)
- Tienda de muebles (nuevo)
- Tienda de electrónica (nuevo)

**Métricas de Éxito**:
- Sistema funciona en ≥3 verticales diferentes
- Accuracy ≥80% en clasificación de atributos no-ropa
- Tiempo de onboarding nuevo vertical < 30 minutos

**Estimación**: 3-4 semanas (completo) / 1-2 semanas (MVP)

**Próximo Paso**: Definir si MVP o completo según roadmap

---

### 2. Sistema de Aprendizaje Adaptativo por Cliente
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

### 1. Sistema de Logs Configurables por Niveles
**Estado**: 📋 Backlog
**Complejidad**: Baja
**Impacto**: Alto (reducción de ruido en logs, mejor debugging)
**Prioridad**: Alta
**Fecha agregada**: 31 Octubre 2025

**Contexto**:
Actualmente el sistema genera muchos logs (embeddings, comparaciones, Cloudinary, etc.) que dificultan el debugging en producción Railway. Se necesita un sistema de niveles configurable desde panel de superadmin.

**Niveles Propuestos**:

1. **Nivel 1 - Solo Errores** (ERROR):
   - ❌ Errores de BD
   - ❌ Fallos de Cloudinary
   - ❌ Excepciones no controladas
   - ❌ API requests fallidos

2. **Nivel 2 - Operaciones Básicas** (INFO - Default):
   - ✅ Nivel 1 +
   - ℹ️ Login/logout usuarios
   - ℹ️ CRUD de productos/clientes
   - ℹ️ Regeneración de embeddings (inicio/fin)
   - ℹ️ Búsquedas API (sin detalles)

3. **Nivel 3 - Extendido** (DEBUG):
   - ✅ Nivel 2 +
   - 🔍 Cada embedding generado
   - 🔍 Comparaciones CLIP individuales
   - 🔍 Descargas de Cloudinary
   - 🔍 Query normalizer matches
   - 🔍 Autofill de atributos por producto
   - 🔍 Cache hits/misses

**Implementación**:

```python
# En system_config.json
{
  "logging": {
    "level": 2,  # 1=ERROR, 2=INFO, 3=DEBUG
    "clip_operations": true,  # Toggle específico para CLIP
    "api_requests": true,     # Toggle para API requests
    "database_queries": false # Toggle para SQL queries
  }
}
```

**Panel de Superadmin**:
- Route: `/system-config/logging`
- Form con radio buttons para nivel (1/2/3)
- Toggles individuales para subsistemas
- Preview de qué tipo de logs aparecerán
- Botón "Aplicar sin reinicio" (actualiza en caliente)

**Archivos a Modificar**:
- `app/blueprints/system_config_admin.py` - Nuevo endpoint `/logging`
- `app/templates/system_config/logging.html` - UI de configuración
- `app/utils/logger.py` (nuevo) - Wrapper de logging con niveles
- `app/config.py` - Leer config de logging
- Todos los blueprints - Reemplazar `print()` por `logger.debug()`

**Beneficios**:
- Railway logs más limpios en producción
- Debugging granular cuando se necesita
- Ahorro de espacio en logs (Railway limita a 10MB)
- Mejor performance (menos I/O en producción)

---

### 2. Migrar Templates de Atributos por Industria a Base de Datos
**Estado**: 📋 Backlog (Fase 2)
**Complejidad**: Media
**Impacto**: Alto para escalabilidad
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

## ⚠️ PENDIENTES TÉCNICOS (Deuda Técnica)
**Estado**: ⏳ Programado para 10 Nov 2025
**Complejidad**: Baja
**Impacto**: Medio (limpieza de código)

**Tareas**:
- [ ] Verificar que no hay nuevos usos de `image_manager.get_image_url()`
- [ ] Verificar que no hay nuevos usos de `cloudinary_manager.get_image_url()`
- [ ] Confirmar que todo usa `image.display_url` / `image.thumbnail_url`
- [ ] Eliminar métodos deprecados de `app/services/image_manager.py`
- [ ] Eliminar métodos deprecados de `app/services/cloudinary_manager.py`
- [ ] Actualizar tests si existen

**Deadline**: 10 Noviembre 2025
**Estimación**: 2 horas

## ⚠️ PENDIENTES TÉCNICOS (Deuda Técnica)

### 1. Eliminar Métodos Deprecados de Image Managers
**Estado**: ⏳ Programado para 10 Nov 2025
**Complejidad**: Baja
**Impacto**: Medio (limpieza de código)

**Tareas**:
- [ ] Verificar que no hay nuevos usos de `image_manager.get_image_url()`
- [ ] Verificar que no hay nuevos usos de `cloudinary_manager.get_image_url()`
- [ ] Confirmar que todo usa `image.display_url` / `image.thumbnail_url`
- [ ] Eliminar métodos deprecados de `app/services/image_manager.py`
- [ ] Eliminar métodos deprecados de `app/services/cloudinary_manager.py`
- [ ] Actualizar tests si existen

**Deadline**: 10 Noviembre 2025
**Estimación**: 2 horas

---

### 2. Implementar SearchLog para Analytics
**Estado**: 🚧 **30% COMPLETADO**
**Complejidad**: Media
**Impacto**: Alto (métricas de negocio)

**Completado**:
- ✅ Modelo `SearchLog` creado en `app/models/search_log.py`
- ✅ Importado en `api.py`
- ✅ Query de conteo diario: `searches_today` en dashboard

**Problema**:
- ❌ No se registran búsquedas individuales en endpoint `/api/search`
- ❌ No hay tracking de búsquedas, clicks, conversiones
- ❌ Imposible medir calidad de resultados o ROI

**Tareas Pendientes**:
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
**Estado**: ✅ COMPLETADO (CERRADO 31 Octubre 2025)
**Complejidad**: Baja (técnica) / Alta (operativa - requiere trabajo manual)
**Impacto**: Alto para calidad de búsqueda

**Problema**:
- Productos tienen metadata mínima (nombre, SKU, precio)
- Sin tags semánticos: "león", "animal", "personaje"
- Sin descripciones detalladas para CLIP

**Implementado**:
- Auto‑Tagging con CLIP (detección de conceptos y guardado en `auto_tags`)
- UI de tags manuales en formulario de producto (con autocompletado)
- Descripciones estructuradas basadas en template

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
**Estado**: ⚠️ **BÁSICO IMPLEMENTADO** (mejorable)
**Complejidad**: Media
**Impacto**: Medio

**Implementado**:
- ✅ Rate limiting básico en API funcional

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
**Estado**: ⚠️ **LOGS BÁSICOS** (expandible)
**Complejidad**: Media
**Impacto**: Alto (operaciones)

**Implementado**:
- ✅ Logging básico en sistema

**Mejoras Propuestas**:
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
**Estado**: ⚠️ **PARCIAL** (API Inventario documentada, falta API Search)
**Complejidad**: Baja
**Impacto**: Alto (para clientes/integradores)

**Completado**:
- ✅ `docs/API_INVENTARIO_EXTERNA.md` - Completa con ejemplos
- ✅ Ejemplos en JavaScript, Python, cURL

**Contenido Faltante**:
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

## � INVESTIGACIÓN Y DESARROLLO

### 15. Integrar Auto-Clasificación de Atributos en Sistema de Embeddings
**Estado**: 💡 Propuesto (30 Oct 2025)
**Complejidad**: Media-Alta
**Impacto**: Alto (enriquece embeddings con información semántica)
**Fecha agregada**: 30 Octubre 2025

**Contexto**:
- Actualmente existe `auto_fill_attributes.py` como script standalone
- Usa CLIP para clasificar atributos visuales (color, material, tags)
- Sistema dinámico que lee configuración de `product_attribute_config`
- Utiliza `categories.clip_prompt` y `categories.name_en` para contexto
- Implementa CLIP-guided cropping y weighted scoring de múltiples imágenes

**Problema**:
- Los embeddings se generan solo desde imágenes visuales
- No se aprovecha la información semántica de atributos auto-clasificados
- Búsqueda textual ("delantal marrón") requiere enriquecimiento manual

**Solución Propuesta**:
Integrar la auto-clasificación en el pipeline de generación de embeddings:

**Opción 1: Embeddings Híbridos (CLIP Text + Visual)**
```python
# Pipeline integrado:
1. Al subir producto/imagen → auto-clasificar atributos con CLIP
2. Generar embedding visual: clip.encode_image(image)
3. Generar embedding textual enriquecido:
   text = f"a photo of {category.clip_prompt} {color} {material}"
   text_emb = clip.encode_text(text)
4. Combinar embeddings:
   hybrid_emb = α*visual_emb + β*text_emb  # pesos configurables
5. Almacenar hybrid_emb como embedding principal
```

**Opción 2: Embeddings Duales (Search Optimizer)**
```python
# Mantener separados para flexibilidad:
1. visual_embedding (actual) → productos visualmente similares
2. semantic_embedding (nuevo) → productos conceptualmente similares
3. SearchOptimizer combina según configuración:
   - Solo visual: búsqueda por imagen pura
   - Solo semántico: búsqueda por concepto/tags
   - Híbrido: balance configurable por cliente
```

**Ventajas**:
- ✅ Búsqueda textual mejorada ("delantal marrón" match atributos)
- ✅ Sinónimos gratuitos (CLIP entiende "chocolate" ≈ "marrón")
- ✅ Cross-modal search (texto → productos, imagen → productos)
- ✅ Aprovecha infraestructura existente (CLIP, product_attribute_config)
- ✅ No requiere modelos adicionales

**Cambios Requeridos**:

**Backend**:
- Modificar: `app/blueprints/embeddings.py`
  - Integrar lógica de `auto_fill_attributes.py`
  - Agregar generación de embeddings textuales enriquecidos
  - Nuevos campos en `images` tabla: `semantic_embedding`, `hybrid_embedding`
- Modificar: `app/blueprints/api.py`
  - Endpoint `/api/search` con parámetro `search_mode`: `visual|semantic|hybrid`
  - Lógica de similaridad según modo seleccionado
- Nuevo: `app/services/attribute_classifier.py`
  - Refactor de `auto_fill_attributes.py` como servicio
  - Reutilizable en diferentes contextos

**Database**:
- Migración Alembic:
  ```sql
  ALTER TABLE images
  ADD COLUMN semantic_embedding TEXT,
  ADD COLUMN hybrid_embedding TEXT,
  ADD COLUMN attribute_classification_metadata JSONB;
  ```

**Admin**:
- Panel de configuración por cliente:
  - ☑️ Auto-clasificar atributos al subir imágenes
  - Pesos de embeddings híbridos: α (visual) / β (semántico)
  - Threshold de confianza para atributos
  - Search mode por defecto: visual/semantic/hybrid

**Widget**:
- Selector de modo de búsqueda (opcional, para testing):
  ```html
  <select name="search_mode">
    <option value="hybrid">Buscar por apariencia + concepto</option>
    <option value="visual">Solo por apariencia visual</option>
    <option value="semantic">Solo por concepto/tags</option>
  </select>
  ```

**Testing**:
- Casos de prueba:
  1. "delantal marrón" → debe matchear atributos color=marrón, categoria=delantal
  2. Imagen de gorro negro → debe matchear visual + semántico
  3. Sinónimos: "chocolate" debe matchear productos color=marrón
  4. Cross-modal: texto "camisa azul" vs imagen de camisa azul

**Riesgos**:
- ⚠️ Dimensionalidad: Embeddings híbridos pueden requerir más almacenamiento
- ⚠️ Performance: Clasificación automática agrega latencia al upload
- ⚠️ Precisión: Atributos auto-clasificados pueden tener errores
- ⚠️ Complejidad: Mantener 2-3 tipos de embeddings por imagen

**Mitigación**:
- Clasificación asíncrona (background job) para no bloquear upload
- Cache de CLIP model para reutilizar entre clasificaciones
- Validación manual de atributos en admin panel
- Feature flag para habilitar/deshabilitar por cliente

**Estimación**: 3-4 semanas (completo con testing)

**Prioridad**: Media-Alta (depende de feedback de clientes sobre búsqueda textual)

**Referencias**:
- Script actual: `auto_fill_attributes.py`
- Modelo: `app/models/product_attribute_config.py`
- Categorías: `app/models/category.py` (campos `clip_prompt`, `name_en`)

---

## �📋 RESUMEN DE PRIORIZACIÓN

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

**30 Oct 2025**:
- 📊 **Auditoría completa del backlog vs código real**
- ✅ Movido Item "Admin Panel de Atributos" a COMPLETADO
- ✅ Movido Item "Fix Cloudinary Paths" a COMPLETADO
- ⚠️ Actualizado Item "SearchLog Analytics" - 30% completado
- ⚠️ Actualizado Item "Rate Limiting" - Básico implementado
- ⚠️ Actualizado Item "Monitoring" - Logs básicos
- ⚠️ Actualizado Item "Documentación API" - API Inventario documentada
- 📝 Agregado Item #15: Integrar Auto-Clasificación de Atributos en Sistema de Embeddings
  - Contexto: Sistema actual de auto_fill_attributes.py como standalone
  - Propuesta: Embeddings híbridos (visual + semántico) para búsqueda textual enriquecida
  - Estimación: 3-4 semanas (completo con testing)
- 📄 Creado `BACKLOG_STATUS_AUDIT_30OCT2025.md` con análisis detallado
- 💡 **Agregado Item #16**: Pre-bake modelo LLM en Docker para Railway
  - Contexto: Modelo sentence-transformers descarga en primer arranque (slow cold-start)
  - Propuesta: Incluir modelo pre-descargado en imagen Docker + variable HF_HUB_DISABLE_SYMLINKS_WARNING
  - Estimación: 2-3 horas (modificar Dockerfile + testing)
  - Beneficios: Cold-start rápido, sin warnings de symlinks, sin descargas en cada deploy

**22 Oct 2025**:
- Documento creado
- Agregado item #1: Sistema de Aprendizaje Adaptativo (prioridad alta)
- Agregado item #2: Validación Zero‑Shot Dinámica contra Catálogo (prioridad alta)
- Agregado item #3: Búsqueda Híbrida Texto + Imagen (prioridad alta)
- Agregado item #3: Fix duplicación Cloudinary paths (pendiente push)
- Agregados items #2-#14 recopilados de TODOs y discusiones

---

## 📎 REFERENCIAS

- `docs/IMAGE_HANDLING_GUIDE.md` - Métodos deprecados (#2)
- `docs/CENTROID_MIGRATION.md` - Optimización de centroides
- `app/models/search_log.py` - Modelo para analytics (#4)
- `REFACTOR_COMPLETE_20OCT2025.md` - Refactor reciente completado
