# Backlog de Mejoras

## 🔹 Vocabulario por Cliente en BD (client_vocabulary_cache)
**Estado**: Lectura en runtime integrada; faltan hooks de invalidación

### Qué
- Tabla `client_vocabulary_cache` con JSONB `{colores, tipos, contextos}` por `client_id`.

### Por qué
- Evitar recálculo costoso de vocabulario por request.
- Consistencia entre instancias, persistencia entre deploys y reinicios.

### Cuándo regenerar (igual criterio que embeddings LLM)
- Productos: create/update/delete que afecten `tags` o atributos relevantes.
- Importaciones/bulk updates de productos.
- Categorías: create/update/delete que afecten `name`, `name_en`, `alternative_terms`.
- Manual: botón en Admin o script CLI.
- TTL opcional como red de seguridad (p. ej., 5 minutos) si se habilita.

### Cómo
- Pre-carga inicial: `python tools/populate_vocabulary_cache.py` (local) y sincronizar a Railway.
- Invalidación en CRUD: borrar fila por `client_id`; el próximo uso la regenerará.
- Alternativa futura: triggers en BD (pospuesto, decisión abierta).

### Pendiente
- Hooks de invalidación automática de `client_vocabulary_cache` en CRUD de productos/tags/categorías.
- Métricas de cache hit/miss y tiempos.
- Tests de carga multi-cliente.

### Nueva tarea: Invalidación automática del vocabulario (client_vocabulary_cache)
**Objetivo**: Mantener consistente el vocabulario por cliente sin tareas manuales.

**Disparadores (por cliente)**
- Productos: create/update/delete que modifiquen `attributes->'color'`, `tags`, `name` o `sku` (si participan en vocabulario/tokens).
- Categorías: create/update/delete que modifiquen `name`, `name_en`, `alternative_terms`, `is_active`.
- Configuración de atributos: cambios en `ProductAttributeConfig` cuando `type='list'` y `key='color'`.

**Estrategia**
- Opción A (recomendada): ORM hooks (post-commit) que marquen invalidación por `client_id` y regeneren en background o en el próximo acceso.
- Opción B: Triggers en BD + canal `NOTIFY/LISTEN` para invalidar en memoria y forzar reconstrucción.
- En ambos casos: invalidar fila de `client_vocabulary_cache` (DELETE/UPDATE `updated_at`) para provocar rebuild determinístico.

**Criterios de aceptación**
- CA1: Un cambio en categorías/atributos/productos del cliente invalida su fila en `client_vocabulary_cache` en < 1s.
- CA2: En el siguiente `normalize_query(...)`, si falta la fila, se reconstruye y persiste sin bloquear más de 1 request.
- CA3: Logs con eventos `vocab_cache.invalidate` y `vocab_cache.rebuild` por cliente.
- CA4: Métricas básicas: tiempo de rebuild, tamaño del vocabulario, cache hit/miss.

**Riesgos/Notas**
- Evitar tormenta de invalidaciones en updates masivos: aplicar coalescencia por ventana (p. ej., 30s).
- Limitar rebuild concurrente por cliente (lock per client_id).
- Mantener fallback en memoria (TTL corto) para resiliencia si BD no está disponible.

### Nueva tarea: Precarga Masiva de Embeddings de Vocabulario
**Estado**: Implementado script `tools/populate_embeddings.py` ampliado.

**Objetivo**: Eliminar cálculos on-the-fly de embeddings para términos (colores/tipos/contextos) que causan latencias >400s en BOOST_LOOP en primer uso.

**Cómo**:
- Ejecutar en cada deploy (local y Railway):
  - `python tools/populate_embeddings.py --target railway`
- Genera embeddings con claves `vocab:<term>` para todas las variantes morfológicas (singular/plural/género) y paleta extendida de colores.
- Reutiliza `client_vocabulary_cache` si existe; si no, construye dinámicamente.

**Pendiente**:
- Memoización per-request en `text_search` para evitar requery de los mismos embeddings.
- Prefijo opcional por cliente si se detectan colisiones semánticas entre clientes (evaluar necesidad real).
- Métricas de: porcentaje términos cubiertos, misses residuales.
- Integrar en pipeline de deploy (hook automático).

**Riesgos**:
- Crecimiento descontrolado si el vocabulario excede ~5000 términos → implementar límite + pruning.
- Diferencias de significado cross-cliente para mismo término (‘camisa’ vs contexto específico) → evaluar segregación futura `vocab:<client_id>:<term>`.

**Criterios de aceptación**:
✅ Primer request de `text_search` no supera 3s (sin reconstrucción completa de vocabulario).
✅ BOOST_LOOP < 1s para ≤500 productos cuando embeddings existentes.
✅ Misses de embeddings <5% de términos en primeros 10 requests tras deploy.

## 🔄 1) Sistema de Recálculo Automático de Embeddings de Vocabulario [EN PROCESO]
**Estado**: En Proceso (Prioridad Alta)
**Fecha inicio**: 15 Nov 2025
**Responsable**: Implementación pendiente

### Contexto y Problema Identificado

Durante la optimización de performance del endpoint `/api/search/text` (que estaba tardando 80 segundos en Railway), se implementó un sistema de **caché de embeddings de vocabulario** en la tabla `embeddings` de PostgreSQL.

**El problema original**:
- La función `normalize_query()` en `llm_query_normalizer.py` calculaba embeddings en tiempo real para ~84 términos de vocabulario en **cada request**
- Estos términos incluyen:
  - **Colores**: Extraídos de `ProductAttributeConfig` (type='list', key='color') + valores reales en `products.attributes->>'color'`
  - **Tipos**: Extraídos de `Category.name` de categorías activas
  - **Contextos**: Extraídos de `Product.tags` (valores separados por comas)
- El proceso de encoding (`model.encode()`) tomaba ~1 segundo por término → 80-84 segundos total
- **Solución implementada**: Pre-calcular embeddings y almacenarlos en BD con key `vocab:{term}`, type='vocabulary'

### El Problema Nuevo: Vocabulario Desactualizado

El vocabulario es **dinámico y se extrae de la base de datos**, por lo que puede cambiar cuando:

1. **Se crea/edita/elimina una Categoría** (`categories.py`)
   - Impacto: Términos de "tipos" quedan desactualizados
   - Rutas: `/categories/create`, `/categories/<id>/edit`, `/categories/<id>/delete`

2. **Se modifica ProductAttributeConfig de colores** (`attributes.py`)
   - Impacto: Términos de "colores" quedan obsoletos
   - Rutas: `/attributes/create`, `/attributes/<id>/edit`, `/attributes/<id>/delete`
   - Condición: Cuando `type='list'` y `key='color'`

3. **Se crean/editan productos con tags** (`products.py`)
   - Impacto: Nuevos "contextos" no tienen embedding
   - Rutas: `/products/create`, `/products/<id>/edit`
   - Nota: Tags son texto libre separado por comas

4. **Se procesan/regeneran embeddings CLIP** (`embeddings.py`)
   - Impacto: Puede generar/modificar tags contextuales automáticamente
   - Rutas: `/embeddings/process_pending`, `/embeddings/process-single/<id>`

5. **Se sincronizan datos externos** (scripts)
   - Impacto: Datos de Railway pueden incluir categorías/colores/tags nuevos
   - Scripts: `sync_from_railway.py`, `restore_from_railway.ps1`

### Consecuencias de No Resolverlo

❌ **Búsquedas textuales pueden fallar** si:
- Usuario busca un color nuevo que fue agregado pero no tiene embedding
- Se crea una categoría nueva y no matchea en queries
- Tags nuevos no se detectan en `normalize_query()`

⚠️ **Fallback actual**: Si un término no tiene embedding en BD, se calcula on-the-fly, pero:
- Introduce latencia (1s por término)
- No se persiste, se vuelve a calcular en próximo request
- Log muestra warnings de términos faltantes

### Solución Propuesta

Implementar un **sistema de invalidación y recálculo automático** de embeddings de vocabulario.

#### Opción A: Invalidación por Cliente (Recomendada)
```python
# Tabla: embedding_refresh_queue
# Columnas: client_id (UUID), needs_refresh (bool), last_refresh (timestamp)

def schedule_vocabulary_refresh(client_id: str):
    """Marca que el vocabulario de un cliente necesita recalcularse"""
    from app.models.embedding_refresh_queue import EmbeddingRefreshQueue
    queue_entry = EmbeddingRefreshQueue.query.filter_by(client_id=client_id).first()
    if not queue_entry:
        queue_entry = EmbeddingRefreshQueue(client_id=client_id, needs_refresh=True)
        db.session.add(queue_entry)
    else:
        queue_entry.needs_refresh = True
        queue_entry.updated_at = datetime.utcnow()
    db.session.commit()
```

**Ventajas**:
- No bloquea la operación actual (async)
- Se ejecuta en background o próximo request del cliente
- Evita recálculos innecesarios (batch updates)

**Implementación**:
1. Agregar llamada a `schedule_vocabulary_refresh(client_id)` en los 5 puntos críticos
2. Background worker o trigger en próximo request text_search que verifique `needs_refresh=True`
3. Ejecutar `populate_vocabulary_embeddings()` solo para ese cliente
4. Marcar `needs_refresh=False` y actualizar `last_refresh`

#### Opción B: Recálculo Síncrono Inmediato
- Llamar `populate_vocabulary_embeddings(client_id)` directamente después de commit
- **Desventaja**: Bloquea request del admin (puede tardar 2-5 segundos)
- **Uso**: Solo en sincronizaciones batch o scripts externos

### Puntos de Integración (Dónde Agregar Hooks)

```python
# 1. En categories.py - después de create/edit/delete
@bp.route("/create", methods=["POST"])
def create():
    # ... crear categoría ...
    db.session.commit()
    schedule_vocabulary_refresh(current_user.client_id)  # ← AGREGAR
    flash("Categoría creada exitosamente")

# 2. En attributes.py - solo para atributos de color
@bp.route("/create", methods=["POST"])
def create():
    # ... crear atributo ...
    if attribute.type == 'list' and attribute.key == 'color':
        schedule_vocabulary_refresh(current_user.client_id)  # ← AGREGAR

# 3. En products.py - después de create/edit con tags
@bp.route("/create", methods=["POST"])
def create():
    # ... crear producto ...
    if product.tags and product.tags.strip():
        schedule_vocabulary_refresh(product.client_id)  # ← AGREGAR

# 4. En embeddings.py - después de process_pending/process_single
@bp.route("/process_pending", methods=["POST"])
def process_pending():
    # ... procesar embeddings ...
    affected_clients = set([img.product.client_id for img in processed_images])
    for client_id in affected_clients:
        schedule_vocabulary_refresh(client_id)  # ← AGREGAR

# 5. En sync_from_railway.py - al final de sincronización
def sync_data():
    # ... sincronizar datos ...
    affected_clients = Client.query.all()
    for client in affected_clients:
        schedule_vocabulary_refresh(client.id)  # ← AGREGAR
```

### Criterios de Aceptación

✅ Cuando se crea/edita/elimina una categoría → vocabulario se marca para refresh
✅ Cuando se modifica atributo de color → vocabulario se marca para refresh
✅ Cuando se crean/editan productos con tags → vocabulario se marca para refresh
✅ Cuando se procesan embeddings CLIP → vocabulario se marca para refresh
✅ Función `populate_vocabulary_embeddings()` puede ejecutarse para un solo cliente
✅ Background worker procesa cola de refresh periódicamente
✅ Logs claros cuando se detecta vocabulario desactualizado
✅ Fallback on-the-fly sigue funcionando si refresh falla

### Archivos a Modificar

- `app/models/embedding_refresh_queue.py` (nuevo)
- `app/blueprints/categories.py` (3 rutas)
- `app/blueprints/attributes.py` (3 rutas)
- `app/blueprints/products.py` (2 rutas)
- `app/blueprints/embeddings.py` (2 rutas)
- `tools/populate_embeddings.py` (agregar parámetro `client_id`)
- `sync_from_railway.py` (agregar hook al final)
- `app/services/vocabulary_refresh_service.py` (nuevo - lógica centralizada)

### Estimación

- **Tiempo**: 3-4 horas
- **Prioridad**: Alta (afecta calidad de búsquedas textuales)
- **Riesgo**: Bajo (fallback actual mitiga impacto)

### Notas Adicionales

- El script `tools/populate_embeddings.py` ya tiene la lógica de generación, solo falta:
  - Parametrizarlo para ejecutar por `client_id` específico
  - Crear sistema de cola/scheduling
- Considerar rate limiting: no recalcular si último refresh fue hace menos de 5 minutos
- Monitorear tamaño de vocabulario: si crece mucho (>500 términos), considerar sampling o límites

---

## 2) Búsqueda de Texto en Modo Multi-Categoría (futuro)
- Estado: Pendiente (no implementado). Mantener por ahora búsqueda de texto en una sola categoría.
- Descripción: Permitir que la búsqueda textual recupere resultados organizados por múltiples categorías (similar al flujo visual multi-categoría), mostrando secciones por categoría candidata.
- Activación: Detrás de feature flag (p. ej., `text_multi_category=true` o configuración en `system_config`). Por defecto desactivado.
- Heurística de categorías candidatas:
  - Prioridad: exacta (nombre/alt/name_en) → tokens (score) → LLM (similitud).
  - Limitar a top-N categorías con productos activos y similitud/score por encima de umbral.
- Respuesta API (propuesta):
  - `mode: "multi_category"`
  - `results_by_category: [{ category_id, category_name, confidence, product_count, products: [...] }, ...]`
  - `category_selection_info: { query, candidates: [{name, method: 'exact|tokens|llm', score|similarity}], thresholds }`
- UI/Widget:
  - Reutilizar el layout de multi-categoría del flujo visual.
  - Mostrar banner si se trató de una sustitución (closest category) con `category_substitution_info`.
- Criterios de Aceptación:
  - Flag en OFF: comportamiento actual (una sola categoría, sin cambios).
  - Flag en ON: organizar resultados de texto por categorías seleccionadas; sin fallbacks globales.
  - Documentación de thresholds y métricas para ajuste.
- Riesgos:
  - Ambigüedad alta en consultas cortas puede generar ruido. Mitigar con límites de N, umbrales y mensajes de guía/refinamiento.
