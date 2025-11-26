# Sistema de Logs con 4 Niveles - Implementación Completa

## ✅ Implementado

### 1. **Módulo Centralizado de Logging**
- ✅ Archivo: `app/utils/logging_config.py`
- ✅ 4 niveles: ERROR_ONLY, REQUEST_LIFECYCLE, MAIN_PROCESSES, VERBOSE
- ✅ Categorías: ERROR, REQUEST, SEARCH, EMBEDDING, CATEGORY_DETECTION, COLOR, NLP, CACHE, DATABASE, SYSTEM
- ✅ Funciones helper: `log_error()`, `log_request()`, `log_search()`, etc.
- ✅ Decorador `@timed_operation` para medir tiempos

### 2. **Configuración del Sistema**
- ✅ Campo `log_level` agregado a `system_config.json`
- ✅ Valor por defecto: `REQUEST_LIFECYCLE` (recomendado para producción)
- ✅ Configuración actualizada en `app/utils/system_config.py`

### 3. **Panel de Super-Admin**
- ✅ Selector de nivel de log en `system_config/index.html`
- ✅ Blueprint `system_config_admin.py` actualizado
- ✅ Explicación clara de cada nivel
- ✅ Cambios se aplican inmediatamente sin reiniciar

### 4. **Integración Inicial**
- ✅ `api.py`: railway_log() y _get_spacy_nlp() actualizados
- ✅ `search_optimizer.py`: importaciones actualizadas
- ⚠️ Pendientes: embeddings.py, search_text.py, color_learning_service.py

---

## 📊 Los 4 Niveles de Log Explicados

### 🔴 **ERROR_ONLY** - Producción Normal (Mínimo)
**Qué se registra:**
- Solo errores críticos y excepciones
- Fallos de conexión a BD/Redis
- Errores de API Key inválida
- Excepciones no capturadas

**Cuándo usar:**
- Producción estable sin problemas
- Railway con mínimo uso de recursos
- Cuando TODO funciona correctamente

**Salida esperada en Railway:**
```
[ERROR] Database connection failed: timeout
[ERROR] Invalid API Key: clip_xyz123
[ERROR] Exception in /api/search: Division by zero
```

---

### 🟡 **REQUEST_LIFECYCLE** - Debugging Básico (⭐ RECOMENDADO)
**Qué se registra:**
- Todo de ERROR_ONLY
- + Inicio/fin de cada request HTTP
- + Métricas de tiempo (duración en ms)
- + Códigos de estado (200, 404, 500)
- + Cargas de modelos (CLIP, spaCy, MiniLM)

**Cuándo usar:**
- Producción normal
- Debugging básico de performance
- Monitoreo de uso del sistema
- **RECOMENDADO para Railway**

**Salida esperada en Railway:**
```
[REQUEST] POST /api/search
[SYSTEM] spaCy cargado: es_core_news_md
[SYSTEM] CLIP modelo cargado en memoria
[REQUEST] POST /api/search - 200 (342ms)
[REQUEST] GET /products/123
[REQUEST] GET /products/123 - 200 (45ms)
```

---

### 🟠 **MAIN_PROCESSES** - Debugging Intermedio
**Qué se registra:**
- Todo de REQUEST_LIFECYCLE
- + Operaciones de búsqueda (query recibida, resultados encontrados)
- + Detección de categorías (categorías detectadas, scores)
- + Generación de embeddings (producto X procesado)
- + Decisiones del sistema (threshold aplicado, fallback activado)

**Cuándo usar:**
- Debugging de búsquedas que no dan buenos resultados
- Entender por qué se detecta/no detecta una categoría
- Verificar embeddings generados correctamente
- Analizar decisiones del algoritmo

**Salida esperada en Railway:**
```
[REQUEST] POST /api/search
[SEARCH] Búsqueda textual: "remera blanca"
[NLP] Tokens extraídos: ['remera', 'blanca']
[CATEGORY] Detectando categorías para cliente Demo Fashion Store
[CATEGORY] ✅ Detección completa: 2/5 categorías sobre threshold
[CATEGORY]    Remeras: score=0.823 (best_crop=center_80)
[CATEGORY]    Blusas: score=0.645 (best_crop=tight_90)
[SEARCH] Ranking de 15 resultados con pesos: visual=60%, metadata=30%, business=10%
[SEARCH] ✅ Ranking completo: 15 productos ordenados por score final
[REQUEST] POST /api/search - 200 (487ms)
```

---

### 🟢 **VERBOSE** - Debugging Completo (Máximo Detalle)
**Qué se registra:**
- Todo de MAIN_PROCESSES
- + Detalles de crops generados (tamaños, escalas)
- + Scores individuales por crop
- + Tokens NLP paso a paso
- + Matching de colores (normalizaciones, grupos)
- + Cache hits/misses
- + Queries SQL ejecutadas
- + Embeddings individuales

**Cuándo usar:**
- Debugging profundo de algoritmos
- Desarrollo de nuevas features
- Análisis detallado de casos edge
- **NO recomendado para Railway producción** (demasiado output)

**Salida esperada en Railway:**
```
[REQUEST] POST /api/search
[SEARCH] Búsqueda textual: "remera blanca"
[NLP] Query original: 'remera blanca'
[NLP] Tokenización spaCy: [('remera', 'NOUN'), ('blanca', 'ADJ')]
[NLP] Categoría principal detectada: 'remera'
[NLP] Modificadores nivel 1: ['blanca']
[NLP] Query normalizada: 'remera blanca'
[CATEGORY] Generados 5 crops: ['full', 'center_80', 'center_90', 'tight_70', 'tight_90']
[CATEGORY] Tamaños de crops: [(800, 600), (640, 480), ...]
[CATEGORY] Embedding generado para crop 'center_80' (512-dim)
[CATEGORY] Remeras: score=0.823 (crop='center_80', centroid_sim=0.856)
[CATEGORY] Blusas: score=0.645 (crop='tight_90', centroid_sim=0.673)
[COLOR] Color detectado: 'blanco' → normalizado: 'BLANCO' (grupo: blancos)
[CACHE] Cache hit: embedding for 'BLANCO'
[SEARCH] Producto ABC123: visual=0.850*0.60 + metadata=0.600*0.30 + business=0.400*0.10 = 0.730
[SEARCH] Producto DEF456: visual=0.780*0.60 + metadata=0.700*0.30 + business=0.500*0.10 = 0.728
[DATABASE] Query: SELECT * FROM products WHERE category_id = 'uuid-123' LIMIT 50
[REQUEST] POST /api/search - 200 (487ms)
```

---

## 🔧 Cómo Usar el Nuevo Sistema

### Ejemplo 1: Log Simple por Categoría
```python
from app.utils.logging_config import log_error, log_search, log_category_detection

# Error (siempre se muestra)
log_error("No se pudo conectar a la base de datos")

# Búsqueda (MAIN_PROCESSES+)
log_search(f"Buscando productos para query: {query}")

# Detección de categoría (MAIN_PROCESSES+)
log_category_detection(f"✅ Categoría detectada: {category.name} (score={score:.3f})")
```

### Ejemplo 2: Log Verbose (solo en VERBOSE)
```python
from app.utils.logging_config import log_verbose, LogCategory

# Solo se muestra en nivel VERBOSE
log_verbose(LogCategory.NLP, f"Token procesado: {token.text} ({token.pos_})")
log_verbose(LogCategory.COLOR, f"Color raw '{raw}' → normalizado '{normalized}'")
```

### Ejemplo 3: Decorador de Tiempo
```python
from app.utils.logging_config import timed_operation, LogCategory

@timed_operation(LogCategory.SEARCH, "búsqueda de productos")
def search_products(query, client_id):
    # ... búsqueda ...
    return results

# Output (en MAIN_PROCESSES+):
# [SEARCH] ⏱️ Iniciando: búsqueda de productos
# [SEARCH] ✅ Completado: búsqueda de productos (342ms)
```

### Ejemplo 4: Request Logging
```python
from app.utils.logging_config import log_request
import time

@bp.route('/api/search', methods=['POST'])
def search_api():
    start = time.time()

    # ... procesamiento ...

    duration_ms = (time.time() - start) * 1000
    log_request('POST', '/api/search', duration_ms, 200)
    return jsonify(results)

# Output (en REQUEST_LIFECYCLE+):
# [REQUEST] POST /api/search - 200 (342ms)
```

---

## 📝 Archivos Pendientes de Actualizar

Para completar la migración, actualizar estos archivos:

### Alta Prioridad (Muy Verbosos):
1. ✅ `app/blueprints/api.py` - railway_log y spaCy actualizados
2. ⚠️ `app/blueprints/embeddings.py` - Muchos `clip_logger.info()`
3. ⚠️ `app/blueprints/search_text.py` - Muchos `print()` de debug NLP
4. ⚠️ `app/services/color_learning_service.py` - Logs de colores
5. ✅ `app/core/search_optimizer.py` - Importaciones actualizadas

### Media Prioridad:
6. `app/blueprints/gpt4v_detection.py` - Logs de GPT-4V
7. `app/utils/llm_query_normalizer.py` - Logs de MiniLM
8. `app/blueprints/search_visual.py` - Logs de búsqueda visual

### Baja Prioridad:
9. `app/blueprints/attributes.py` - Errores en CRUD
10. `app/services/conversacion_service.py` - Logs de conversación

---

## 🎯 Próximos Pasos

1. **Probar en Local**:
   ```bash
   # Cambiar nivel a VERBOSE para ver todo
   # Editar system_config.json: "log_level": "VERBOSE"
   python clip_admin_backend/app.py
   ```

2. **Probar en Railway**:
   - Acceder al panel super-admin
   - Ir a "Configuración del Sistema"
   - Cambiar nivel de log
   - Hacer búsquedas y ver logs en Railway

3. **Migrar Archivos Restantes**:
   - Usar patrón de `api.py` como ejemplo
   - Reemplazar `print()` por funciones del sistema
   - Reemplazar `logger.debug()` por `log_verbose()`
   - Reemplazar `logger.info()` por categoría específica

4. **Validar en Producción**:
   - Empezar con ERROR_ONLY
   - Subir a REQUEST_LIFECYCLE cuando sea necesario
   - Solo usar MAIN_PROCESSES para debugging específico
   - VERBOSE solo en casos extremos

---

## ✨ Beneficios del Nuevo Sistema

1. **Control Total**: 4 niveles configurables desde UI
2. **Sin Restart**: Cambios inmediatos
3. **Organizado**: Logs por categoría (REQUEST, SEARCH, EMBEDDING, etc.)
4. **Performance**: Menos overhead en producción
5. **Debugging**: Información precisa cuando se necesita
6. **Railway-Friendly**: Menos ruido en logs de producción
