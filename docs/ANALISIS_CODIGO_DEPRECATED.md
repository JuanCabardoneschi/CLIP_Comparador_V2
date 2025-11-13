# ANÁLISIS DE CÓDIGO Y BD DEPRECATED
**Fecha**: 15 Noviembre 2025
**Tag de referencia**: `v1.1-dual-tab-text-search`
**Estado**: ANÁLISIS PRELIMINAR - NO ELIMINAR AÚN

---

## 📋 RESUMEN EJECUTIVO

El sistema ha evolucionado desde múltiples experimentos (DINO, BLIP-2, ViT-L/14, etc.) hasta la arquitectura actual **GPT-4V + CLIP (ViT-B/16) + MiniLM**. Este análisis identifica código y estructuras de BD deprecated que podríamos eliminar de forma segura.

---

## 🔴 DEPRECATED - CANDIDATOS PARA ELIMINACIÓN TOTAL

### 1. Grounding DINO (Detección de objetos - NO SE USA)
**Estado**: ❌ Completamente deprecated
**Razón**: Reemplazado por GPT-4V para detección de categorías

**Archivos a eliminar**:
- `clip_admin_backend/app/utils/grounding_dino.py` (140 líneas)
- Referencias en `embeddings.py` (líneas 1006-1021)

**Dependencias en requirements.txt**:
- `groundingdino-py` (si existe) - NO instalar

**Impacto**: CERO. GPT-4V hace detección de categorías mucho mejor.

---

### 2. Scripts de Migración BLIP-2 (Experimentos abandonados)
**Estado**: ❌ Deprecated - Nunca llegó a producción
**Razón**: Se descartó BLIP-2, seguimos con CLIP ViT-B/16

**Archivos a eliminar**:
```
reembed_with_blip2.py                # 350+ líneas
recalculate_blip2_centroids.py      # 200+ líneas
migrate_to_blip2.py                 # 300+ líneas
migrate_clip_to_blip2_auto.py       # 250+ líneas
test_blip2_new_version.py           # 100+ líneas
README_BLIP2.md                      # Documentación obsoleta
```

**Dependencias en requirements.txt**:
- `salesforce-blip` o `transformers` para BLIP-2 (verificar si alguna versión está instalada)

**Impacto**: CERO. Nunca se usó en producción.

---

### 3. Scripts de Test Experimentales
**Estado**: ⚠️ Deprecated - Solo útiles para debugging puntual
**Razón**: Pruebas de concepto ya validadas/descartadas

**Archivos a eliminar**:
```
test_multi_crop_simple.py           # Crop detection tests
test_multi_crop_detection.py        # Multi-crop experiments
test_multi_category.py              # Ya implementado en GPT4V
test_vitl14_vs_vitb16.py           # Ya decidimos usar ViT-B/16
test_api_import.py                  # Test básico de imports
migrate_to_vitl14.py                # Migración descartada
```

**Archivos a CONSERVAR** (útiles para debugging):
```
test_text_search.py                 # Test de búsqueda textual (ACTIVO)
test_api_search_quick.ps1          # Quick test del endpoint
```

**Impacto**: BAJO. Solo eliminamos scripts de experimentos descartados.

---

## 🟡 MANTENER INACTIVO - FUNCIONALIDAD FUTURA

<!-- Sección de Training/Calibración eliminada -->

### 5. Endpoint Legacy `/api/search` (Backup para rollback)
**Estado**: ✅ MANTENER INACTIVO - Rollback safety
**Razón**: Backup si GPT4V-unified falla

**Código** (CONSERVAR):
- Endpoint en `api.py` (si existe la función `search()`)
- Usa `StoreSearchConfig` con todos los pesos

**Uso actual**: CERO (widget usa `/api/search/gpt4v-unified`)

**Justificación**: Mantener como fallback durante 1-2 meses más. Si no hay problemas con GPT4V-unified, eliminar en v1.2.

---

## 🟢 CONSERVAR - CÓDIGO ACTIVO

### 6. Color Mapping (Usado en búsqueda textual)
**Estado**: ✅ ACTIVO
**Modelo**: `color_mapping.py`
**Tabla BD**: `color_mappings`

**Justificación**: Usado por búsqueda textual para normalizar colores.

---

### 7. Product Attribute Config (Dinámico JSONB)
**Estado**: ✅ ACTIVO
**Modelo**: `product_attribute_config.py`
**Tabla BD**: `product_attribute_configs`

**Justificación**: Core del sistema de atributos dinámicos por cliente.

---

### 8. Category Pair Exclusion (Pair-exclusion logic)
**Estado**: ✅ ACTIVO
**Modelo**: `category_pair_exclusion.py`
**Tabla BD**: `category_pair_exclusions`

**Justificación**: Filtrado de resultados contradictorios (ej: "delantal completo" excluye "torso").

---

### 9. Search Log (Analytics)
**Estado**: ✅ ACTIVO
**Modelo**: `search_log.py`
**Tabla BD**: `search_logs`

**Justificación**: Tracking de búsquedas para analytics.

---

## 📊 BACKUPS Y ARCHIVOS .BACKUP

### Archivos .backup (Snapshots de seguridad)
```
clip_admin_backend/app/blueprints/api.py.backup             # Backup pre-GPT4V
clip_admin_backend/app/blueprints/api.py.backup_gpt4v       # Backup GPT4V migration
clip_admin_backend/app/blueprints/embeddings.py.backup      # Backup embeddings refactor
clip_admin_backend/app/blueprints/gpt4v_detection.py.backup # Backup GPT4V
clip_admin_backend/app/templates/search_config/edit.html.backup  # Backup config UI
requirements.txt.backup                                      # Backup deps
requirements.txt.backup_20251113_004847                     # Snapshot timestamped
requirements.txt.backup_corrupted                           # Corrupted snapshot
```

**Acción recomendada**:
- ✅ Conservar `.backup` más recientes (últimos 2-3 meses)
- ❌ Eliminar backups `_corrupted` o muy antiguos (>6 meses)

---

## 🗄️ BASE DE DATOS - ANÁLISIS DE TABLAS

### Tablas ACTIVAS (CONSERVAR)
```sql
clients                         -- ✅ Core: clientes del SaaS
categories                      -- ✅ Core: categorías por cliente
products                        -- ✅ Core: productos del catálogo
images                          -- ✅ Core: imágenes con embeddings CLIP
users                           -- ✅ Core: usuarios admin
store_search_config             -- ✅ Config: pesos del optimizer (futuro)
color_mappings                  -- ✅ Búsqueda textual: normalización colores
product_attribute_configs       -- ✅ Atributos dinámicos JSONB
category_pair_exclusions        -- ✅ Lógica pair-exclusion
search_logs                     -- ✅ Analytics de búsquedas
```

### Tablas INACTIVAS - CONSERVAR PARA FUTURO (SearchOptimizer)
```sql
training_events                 -- 🟡 Training visual (futuro)
client_category_variants        -- 🟡 Variantes por categoría (futuro)
training_images                 -- 🟡 Dataset calibración (futuro)
calibration_runs                -- 🟡 Historial calibraciones (futuro)
```

### Columnas DEPRECATED - CANDIDATAS PARA ELIMINACIÓN

**Tabla `images`**:
```sql
-- Posibles columnas de experimentos BLIP-2 (verificar si existen):
blip_embedding                  -- ❌ BLIP-2 nunca se usó
blip2_embedding                 -- ❌ BLIP-2 nunca se usó
embedding_model_version         -- ❌ Solo si referencia BLIP
```

**Tabla `categories`**:
```sql
-- Posibles columnas de experimentos BLIP-2 (verificar si existen):
centroid_embedding_blip         -- ❌ BLIP-2 nunca se usó
centroid_embedding_blip2        -- ❌ BLIP-2 nunca se usó
centroid_updated_at_blip        -- ❌ BLIP-2 nunca se usó
centroid_image_count_blip       -- ❌ BLIP-2 nunca se usó
```

**Acción**: Ejecutar query para verificar existencia antes de eliminar:
```sql
-- PostgreSQL: listar columnas de tabla
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'images'
  AND column_name LIKE '%blip%';
```

---

## 📝 PLAN DE LIMPIEZA PROPUESTO

### FASE 1: Eliminación Segura (BAJO RIESGO)
**Timeframe**: Inmediato
**Tag de rollback**: `v1.1-dual-tab-text-search`

1. **Scripts de experimentos descartados**:
   ```
   reembed_with_blip2.py
   recalculate_blip2_centroids.py
   migrate_to_blip2.py
   migrate_clip_to_blip2_auto.py
   test_blip2_new_version.py
   migrate_to_vitl14.py
   test_vitl14_vs_vitb16.py
   test_multi_crop_simple.py
   test_multi_crop_detection.py
   test_multi_category.py
   test_api_import.py
   README_BLIP2.md
   ```

2. **Utilidad Grounding DINO**:
   ```
   clip_admin_backend/app/utils/grounding_dino.py
   ```
   - Remover referencias en `embeddings.py` (líneas 1006-1021)

3. **Backups corruptos/antiguos**:
   ```
   requirements.txt.backup_corrupted
   requirements.txt.backup (conservar solo el más reciente)
   ```

### FASE 2: Limpieza de BD (MEDIO RIESGO)
**Timeframe**: Después de 1 semana sin issues
**Requiere**: Backup completo de BD antes de ejecutar

1. **Verificar columnas BLIP-2** (si existen):
   ```sql
   -- Backup primero
   pg_dump -U postgres -d clip_comparador_v2 > backup_pre_cleanup.sql

   -- Eliminar columnas BLIP (solo si existen)
   ALTER TABLE images DROP COLUMN IF EXISTS blip_embedding;
   ALTER TABLE images DROP COLUMN IF EXISTS blip2_embedding;
   ALTER TABLE categories DROP COLUMN IF EXISTS centroid_embedding_blip;
   ALTER TABLE categories DROP COLUMN IF EXISTS centroid_embedding_blip2;
   ```

### FASE 3: Deprecación Endpoint Legacy (BAJO RIESGO)
**Timeframe**: v1.2 (después de 1-2 meses con GPT4V estable)

1. **Marcar `/api/search` como deprecated**:
   - Agregar header de respuesta: `X-Deprecated: true`
   - Agregar warning en logs
   - Documentar en CHANGELOG

2. **Eliminar en v1.3** (si no hay rollbacks):
   - Remover endpoint completamente
   - Limpiar código asociado

---

## 🔍 VERIFICACIONES ANTES DE ELIMINAR

### Checklist de Seguridad

**Antes de eliminar CUALQUIER archivo**:
- [ ] Verificar que NO esté importado en código activo
- [ ] Verificar que NO esté en `requirements.txt` activo
- [ ] Buscar referencias con `grep -r "nombre_archivo"`
- [ ] Tag de Git creado como rollback point

**Antes de eliminar CUALQUIER columna de BD**:
- [ ] Backup completo de PostgreSQL
- [ ] Verificar que NO esté en modelos SQLAlchemy activos
- [ ] Verificar que NO esté en queries (grep por nombre columna)
- [ ] Probar en BD local primero, luego producción

**Antes de eliminar CUALQUIER endpoint**:
- [ ] Verificar logs de uso (search_logs tabla)
- [ ] Verificar que widget NO lo llame
- [ ] Verificar que NO esté en documentación activa
- [ ] Período de deprecación de 30 días mínimo

---

## 💾 ESTIMACIÓN DE ESPACIO LIBERADO

**Archivos Python**:
- Scripts BLIP-2: ~1,200 líneas
- Grounding DINO: ~160 líneas
- Tests deprecated: ~400 líneas
- **TOTAL**: ~1,760 líneas de código eliminadas

**Archivos Markdown**:
- README_BLIP2.md: ~300 líneas

**Espacio en disco**:
- Scripts: ~80 KB
- Backups corruptos: ~50 KB
- Documentación: ~15 KB
- **TOTAL**: ~145 KB (insignificante, pero más limpio)

**Base de Datos**:
- Columnas BLIP (si existen): Espacio variable según cantidad de registros
- Estimado: 0 bytes (probablemente nunca se agregaron)

---

## ⚠️ ADVERTENCIAS

### NO ELIMINAR

1. **`calibration.py` y `training_admin.py`**: Necesarios para SearchOptimizer futuro
2. **Tablas de training/calibration**: Funcionalidad planificada en backlog
3. **`StoreSearchConfig` model**: Usado en v1.2 para SearchOptimizer Lite
4. **Endpoint `/api/search/text`**: ACTIVO en widget Tab 2
5. **Endpoint `/api/search/gpt4v-unified`**: ACTIVO en widget Tab 1
6. **`color_mapping.py`**: Usado en búsqueda textual

### CONSULTAR ANTES DE ELIMINAR

1. **Backups `.backup`**: Revisar fechas, conservar solo los más recientes
2. **Scripts en `tools/`**: Verificar si son utilities activas
3. **Archivos en root del proyecto**: Verificar que NO sean configs activas

---

## 📅 PRÓXIMOS PASOS

1. **REVISAR**: Usuario valida este análisis
2. **APROBAR**: Decidir qué eliminar en Fase 1
3. **CREAR TAG**: `v1.1.1-pre-cleanup` antes de empezar
4. **EJECUTAR**: Fase 1 de limpieza
5. **VALIDAR**: Sistema sigue funcionando correctamente
6. **COMMIT**: `chore: Eliminación de código deprecated (Fase 1)`
7. **MONITOREAR**: 1 semana sin issues → Fase 2

---

**Fin del análisis**
Este documento es un análisis preliminar. NO ejecutar eliminaciones sin aprobación explícita del usuario.
