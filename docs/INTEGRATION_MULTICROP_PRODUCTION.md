# Análisis de Integración: Multi-Crop Detection → Producción

> **Objetivo**: Integrar `detect_categories_multi_crop` en el endpoint de producción `/api/search` sin cambios en el frontend (demo-store).

---

## 📋 Estado Actual

### Endpoint Producción: `/api/search` (api.py línea 1847)

**Detección de categoría actual**:
- Función: `detect_image_category_with_centroids(image_data, client_id, threshold)`
- Estrategia: **Single-crop** (imagen completa solamente)
- Método: Similitud coseno contra centroides de categorías (promedio de embeddings de productos)
- Desempate: Si margen < 0.03, usa `detect_general_object()` para desambiguar
- Retorna: `(Category, confidence_score)` - **1 sola categoría**

**Características**:
- ✅ Rápido (1 embedding por consulta)
- ✅ Simple y predecible
- ❌ No discrimina bien objetos ambiguos (Delantal Completo vs Medio)
- ❌ No aprovecha evidencia regional (torso, chest, waist)

---

### Sistema Test: `/embeddings/test/multicrop` (embeddings.py línea 1313)

**Detección multi-crop implementada**:
- Función: `detect_categories_multi_crop(image_path, client_id, threshold, top_k, apply_pair_exclusion)`
- Estrategia: **Multi-escala con 8 crops**:
  - `full`: Imagen completa
  - `center_60`: Recorte central 60%
  - `upper_50`, `lower_50`, `left_50`, `right_50`: Mitades
  - `upper_torso`: Zona superior del torso (chest + shoulders)
  - `chest_focus`: Enfoque específico en pecho/bib area
- Método: Puntaje ponderado por región (category-specific weights)
- Reglas de exclusión: Pares dinámicos desde BD (`CategoryPairExclusion`)
- Retorna: **Lista de categorías** con scores, best_crop, crop_scores

**Características**:
- ✅ Alta precisión en casos ambiguos (31.1% de imágenes mejoran)
- ✅ Evidencia regional para desambiguar
- ✅ Reglas de exclusión configurables por cliente
- ⚠️ 8x más procesamiento (8 crops × embedding cada uno)
- ⚠️ Retorna lista en vez de categoría única

---

## 🔄 Comparación Técnica

| Aspecto | `detect_image_category_with_centroids` | `detect_categories_multi_crop` |
|---------|----------------------------------------|--------------------------------|
| **Crops procesados** | 1 (imagen completa) | 8 (multi-escala) |
| **Embeddings generados** | 1 embedding (512D) | 8 embeddings (512D cada uno) |
| **Tiempo procesamiento** | ~200-300ms | ~1.5-2.5s estimado |
| **Método scoring** | Similitud coseno vs centroides | Similitud coseno vs prompts + pesos regionales |
| **Referencia categoría** | Centroides (promedio productos) | Prompts textuales optimizados |
| **Retorno** | `(Category, float)` | `List[Dict]` con múltiples categorías |
| **Pair exclusion** | No | Sí (via BD o system_config) |
| **Desambiguación** | `detect_general_object()` | Evidencia regional (torso/waist) |
| **Configuración** | Solo threshold | Threshold + region_weights + exclusion_params |

---

## ⚖️ Ventajas y Desventajas

### ✅ Ventajas de integrar multi-crop

1. **Mayor precisión**: 31.1% de imágenes optimizadas (mejora promedio +1.06%)
2. **Discriminación avanzada**: Resuelve delantal completo vs medio mediante evidencia regional
3. **Configuración flexible**: Reglas de exclusión por cliente desde panel admin
4. **Evidencia detallada**: `crop_scores` permite debugging granular
5. **Escalabilidad funcional**: Mismo sistema para todas las categorías ambiguas

### ❌ Desventajas / Riesgos

1. **Latencia 8x mayor**: De ~300ms a ~2.5s por búsqueda (impacto en UX)
2. **Costo computacional**: 8 inferencias CLIP en vez de 1 (Railway Hobby Plan)
3. **Cambio de contrato**: Retorna lista en vez de categoría única
4. **Complejidad adicional**: Más lógica de configuración y debugging
5. **Pérdida de centroides**: Multi-crop usa prompts en vez de centroides reales

---

## 🎯 Estrategias de Integración

### Opción 1: **Reemplazo Total** (más arriesgado)

**Descripción**: Reemplazar `detect_image_category_with_centroids` por `detect_categories_multi_crop` directamente.

**Implementación**:
```python
# En api.py línea ~1931 (SINGLE MODE)
# ANTES:
detected_category, category_confidence = detect_image_category_with_centroids(
    image_data, client.id, confidence_threshold=category_confidence_threshold
)

# DESPUÉS:
multi_results = detect_categories_multi_crop(
    image_data,
    client.id,
    threshold=category_confidence_threshold,
    top_k=5,
    apply_pair_exclusion=True
)
# Tomar solo la primera categoría para mantener compatibilidad
detected_category = Category.query.get(multi_results[0]['category_id']) if multi_results else None
category_confidence = multi_results[0]['score'] if multi_results else 0.0
```

**Pros**:
- ✅ Máximo beneficio de precisión
- ✅ Código limpio (1 solo path)

**Contras**:
- ❌ Latencia 8x en todos los requests
- ❌ No hay rollback fácil
- ❌ Puede romper expectativas de tiempo de respuesta

---

### Opción 2: **Feature Flag con Fallback** (recomendado)

**Descripción**: Usar multi-crop solo para categorías problemáticas, mantener single-crop para el resto.

**Implementación**:
```python
# En api.py, agregar lógica condicional
use_multicrop = request.form.get('use_multicrop', 'false').lower() == 'true'

# O mejor: usar lista de categorías ambiguas desde system_config
ambiguous_categories = system_config.get('ambiguous_categories', [
    'DELANTAL COMPLETO', 'MEDIO DELANTAL', 'CASACAS'
])

# Detección tradicional primero
detected_category, category_confidence = detect_image_category_with_centroids(
    image_data, client.id, confidence_threshold=category_confidence_threshold
)

# Si la categoría detectada está en la lista ambigua, re-detectar con multi-crop
if detected_category and detected_category.name.upper() in [c.upper() for c in ambiguous_categories]:
    railway_log(f"🔄 Categoría ambigua detectada ({detected_category.name}), aplicando multi-crop")
    multi_results = detect_categories_multi_crop(
        image_data,
        client.id,
        threshold=category_confidence_threshold,
        top_k=3,
        apply_pair_exclusion=True
    )
    if multi_results:
        detected_category = Category.query.get(multi_results[0]['category_id'])
        category_confidence = multi_results[0]['score']
```

**Pros**:
- ✅ Latencia controlada (solo 8x en casos ambiguos)
- ✅ Backwards compatible (funciona igual para categorías simples)
- ✅ Configuración flexible (lista editable)

**Contras**:
- ⚠️ Lógica más compleja
- ⚠️ Requiere 2 detecciones en casos ambiguos

---

### Opción 3: **Gradual Rollout por Cliente** (más seguro)

**Descripción**: Activar multi-crop solo para clientes específicos via flag en BD.

**Implementación**:
```python
# Agregar campo a modelo Client:
# use_multicrop_detection = db.Column(db.Boolean, default=False)

# En api.py:
if client.use_multicrop_detection:
    multi_results = detect_categories_multi_crop(...)
    detected_category = Category.query.get(multi_results[0]['category_id']) if multi_results else None
    category_confidence = multi_results[0]['score'] if multi_results else 0.0
else:
    detected_category, category_confidence = detect_image_category_with_centroids(...)
```

**Pros**:
- ✅ Rollout controlado (A/B testing)
- ✅ Rollback inmediato (toggle flag)
- ✅ Permite validación en producción

**Contras**:
- ⚠️ Requiere migración de BD
- ⚠️ Divergencia temporal entre clientes

---

### Opción 4: **Híbrido: Multi-crop solo para autocrop images**

**Descripción**: Aplicar multi-crop solo a imágenes que fueron optimizadas con autocrop (tienen crops estratégicos).

**Implementación**:
```python
# Verificar si la imagen del producto tiene crop_params
primary_image = Image.query.filter_by(product_id=product.id, is_primary=True).first()

if primary_image and primary_image.crop_params:
    # Usar multi-crop (la imagen ya fue optimizada)
    multi_results = detect_categories_multi_crop(...)
else:
    # Usar detección tradicional
    detected_category, category_confidence = detect_image_category_with_centroids(...)
```

**Pros**:
- ✅ Enfoque quirúrgico (solo donde hay beneficio comprobado)
- ✅ Latencia mínima (31.1% de imágenes usan multi-crop)

**Contras**:
- ❌ No beneficia a imágenes nuevas sin autocrop
- ⚠️ Complejidad adicional (requiere acceso a Image model)

---

## 📊 Análisis de Impacto

### Performance (Railway Hobby Plan)

**Configuración actual**:
- 512MB RAM, CPU compartido
- Timeout: 30s por request
- Concurrencia: ~5 requests simultáneos

**Estimación de latencia**:
| Operación | Single-crop | Multi-crop | Overhead |
|-----------|-------------|------------|----------|
| Load model | 150ms | 150ms | - |
| Generate embeddings | 100ms | 800ms | +700ms |
| Category detection | 50ms | 100ms | +50ms |
| Product search | 200ms | 200ms | - |
| **TOTAL** | **~500ms** | **~1250ms** | **+750ms (150%)** |

**Conclusión**: Multi-crop agrega ~750ms por búsqueda. Aceptable para Railway (< 2s), pero puede afectar UX.

---

### Compatibilidad Frontend

**Contrato actual de `/api/search`** (modo SINGLE):
```json
{
  "success": true,
  "detected_category": "Delantal Completo",
  "category_confidence": 0.87,
  "detected_color": "BLANCO",
  "color_confidence": 0.65,
  "products": [
    {
      "id": "uuid",
      "name": "Delantal Chef Blanco",
      "similarity": 0.92,
      "image_url": "base64...",
      ...
    }
  ],
  "processing_time": 0.523
}
```

**Cambio necesario**: **NINGUNO** si usamos `multi_results[0]` para extraer categoría única.

---

## 🚀 Plan de Implementación Recomendado

### Fase 1: **Preparación** (1 día)

1. **Agregar configuración a `system_config.json`**:
```json
{
  "ambiguous_categories": [
    "DELANTAL COMPLETO",
    "MEDIO DELANTAL",
    "CASACAS",
    "GORRO",
    "GORROS"
  ],
  "multicrop_mode": "auto"  // "off", "auto", "always"
}
```

2. **Crear función adaptadora** en `api.py`:
```python
def detect_category_smart(image_data, client_id, threshold):
    """
    Detección inteligente: multi-crop para categorías ambiguas,
    single-crop para el resto.
    """
    mode = system_config.get('multicrop_mode', 'auto')
    
    if mode == 'off':
        return detect_image_category_with_centroids(image_data, client_id, threshold)
    
    if mode == 'always':
        results = detect_categories_multi_crop(image_data, client_id, threshold, top_k=5, apply_pair_exclusion=True)
        return (Category.query.get(results[0]['category_id']), results[0]['score']) if results else (None, 0)
    
    # mode == 'auto'
    detected_category, confidence = detect_image_category_with_centroids(image_data, client_id, threshold)
    
    ambiguous = system_config.get('ambiguous_categories', [])
    if detected_category and detected_category.name.upper() in [c.upper() for c in ambiguous]:
        results = detect_categories_multi_crop(image_data, client_id, threshold, top_k=3, apply_pair_exclusion=True)
        if results:
            detected_category = Category.query.get(results[0]['category_id'])
            confidence = results[0]['score']
    
    return detected_category, confidence
```

3. **Actualizar `/api/search`**:
```python
# Línea ~1931 en api.py
# ANTES:
# detected_category, category_confidence = detect_image_category_with_centroids(...)

# DESPUÉS:
detected_category, category_confidence = detect_category_smart(
    image_data,
    client.id,
    confidence_threshold=category_confidence_threshold
)
```

---

### Fase 2: **Testing Local** (1 día)

1. **Probar con multicrop_mode='off'**:
   - Verificar comportamiento igual a producción actual
   - Medir latencia baseline (~500ms)

2. **Probar con multicrop_mode='auto'**:
   - Subir imagen de "Delantal Completo" → debe usar multi-crop
   - Subir imagen de "Remera" → debe usar single-crop
   - Verificar latencia diferencial

3. **Probar con multicrop_mode='always'**:
   - Todas las búsquedas usan multi-crop
   - Medir latencia máxima (~1.5s)

4. **Validar contrato API**:
   - Respuesta JSON idéntica en los 3 modos
   - Frontend (demo-store) funciona sin cambios

---

### Fase 3: **Deploy a Railway** (0.5 días)

1. **Configurar en Railway**:
   - Setear `MULTICROP_MODE=auto` en variables de entorno
   - Deploy con commit tagged

2. **Smoke testing**:
   - 10 búsquedas con imágenes variadas
   - Verificar latencia < 2s
   - Revisar logs de Railway

---

### Fase 4: **Monitoreo y Optimización** (continuo)

1. **Métricas a trackear**:
   - Latencia promedio por modo (auto/off/always)
   - Tasa de uso de multi-crop (% de requests)
   - Accuracy mejora (comparar single vs multi)

2. **Optimizaciones futuras**:
   - Cache de embeddings de crops (Redis)
   - Batch processing de crops en paralelo
   - GPU support si se migra a plan superior

---

## 🎯 Respuesta a Preguntas Clave

### 1. ¿Debe aplicarse pair exclusion en producción?
**Sí**, es la ventaja principal del multi-crop. Sin pair exclusion, multi-crop solo aporta evidencia regional pero no resuelve la confusión Delantal Completo/Medio.

### 2. ¿Es aceptable la latencia 8x en tiempo real?
**Depende del modo**:
- `auto`: Solo categorías ambiguas (31% de casos) → **Aceptable**
- `always`: Todas las búsquedas → **Puede ser lento pero tolerable (<2s)**
- `off`: Mantener actual → **Rápido pero sin mejora**

**Recomendación**: Empezar con `auto`, medir, y ajustar.

### 3. ¿Rollout gradual o inmediato?
**Gradual** (Opción 2 + 3):
- Empezar con `multicrop_mode=off` en producción
- Activar `auto` para 1 cliente piloto
- Si funciona bien en 1 semana, activar `auto` para todos
- Mantener `off` como fallback en caso de problemas

### 4. ¿Mantener endpoint viejo como fallback?
**No necesario** si usamos feature flag. El mismo endpoint puede servir ambos modos.

---

## 📝 Checklist de Implementación

- [ ] Agregar `ambiguous_categories` y `multicrop_mode` a `system_config.json`
- [ ] Crear función `detect_category_smart()` en `api.py`
- [ ] Reemplazar llamada a `detect_image_category_with_centroids()` en línea ~1931
- [ ] Testing local con 3 modos (off/auto/always)
- [ ] Validar contrato API con demo-store local
- [ ] Deploy a Railway con `MULTICROP_MODE=auto`
- [ ] Smoke testing en Railway
- [ ] Documentar cambios en DEPLOYMENT_LOG.md
- [ ] Actualizar README.md con nueva feature
- [ ] Crear tag git `v2.5.0-multicrop-production`

---

## 🔧 Código de Integración Completo

Ver archivo complementario: `INTEGRATION_MULTICROP_CODE.md` (próximo documento)

---

**Fecha**: 12 Noviembre 2025  
**Versión**: v2.4.0-pair-exclusion → v2.5.0-multicrop-production  
**Autor**: GitHub Copilot + Usuario  
**Estado**: ✅ Análisis completo - Pendiente decisión de modo
