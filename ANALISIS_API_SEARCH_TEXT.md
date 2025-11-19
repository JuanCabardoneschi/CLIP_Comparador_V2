# 🔍 ANÁLISIS DETALLADO: `/api/search/text` - Flujo Funcional Completo

## 📋 Ubicación
**Archivo**: `clip_admin_backend/app/blueprints/search_text.py`
**Endpoint**: `POST /api/search/text`
**Blueprint**: `search_text`

---

## 🎯 RESUMEN EJECUTIVO

`/api/search/text` es el endpoint **CORE** del sistema de búsqueda textual V2. Implementa un sistema **Two-Stage Retrieval**:
1. **Stage 1**: Broad Recall SQL con PostgreSQL fuzzy matching
2. **Stage 2**: Precise Reranking usando similitud semántica CLIP text-to-text

**Arquitectura**: Multi-tenant con soporte para módulos de búsqueda personalizados por cliente.

---

## 📊 DIAGRAMA DE FLUJO PRINCIPAL

```
REQUEST → Validación API Key
    ↓
Extracción Semántica (spaCy)
    ↓
Normalización de Tokens Color
    ↓
┌─────────────────────────────────────┐
│  STAGE 1: BROAD RECALL (SQL)       │
│  - Expansión con sinónimos          │
│  - Detección de categoría filtro    │
│  - Query PostgreSQL SIMILAR TO      │
│  Output: ~50 candidatos             │
└─────────────────────────────────────┘
    ↓
Validación de Categoría Detectada
    ↓
Extracción de Atributos (LLM)
    ↓
Inferencia de Color Semántico
    ↓
┌─────────────────────────────────────┐
│  STAGE 2: PRECISE RERANKING (CLIP) │
│  - Text embeddings del query        │
│  - Text embeddings de productos     │
│  - Similitud coseno                 │
│  Output: Top N rerankeados          │
└─────────────────────────────────────┘
    ↓
Matching de Atributos
    ↓
Filtrado por Atributos Solicitados
    ↓
Búsqueda de Colores Similares
    ↓
Reordenamiento Final
    ↓
Construcción de Feedback
    ↓
Agrupación por Categorías (opcional)
    ↓
RESPONSE → JSON con resultados
```

---

## 🔧 FLUJO DETALLADO PASO A PASO

### **FASE 0: Inicialización** (Líneas 803-845)

```python
# 1. Rollback defensivo
db.session.rollback()  # Limpia transacciones abortadas previas

# 2. Validación de API Key
client, error = verify_api_key()
# Busca en tabla `clients` por X-API-Key header
# Retorna objeto Client o error 401

# 3. Extracción de parámetros
query_text = data.get('query', '').strip()
limit = min(int(data.get('limit', 10)), 50)  # Max 50 resultados
```

**Dependencias**:
- `verify_api_key()` → Consulta `Client` table
- Headers HTTP: `X-API-Key`
- JSON body: `query`, `limit` (opcional)

---

### **FASE 1: Preprocesamiento Semántico** (Líneas 846-895)

#### 1.1 Extracción de Términos Clave (spaCy)

```python
cleaned_query = _extract_key_terms_with_dependency_parsing(query_text)
```

**Función**: `_extract_key_terms_with_dependency_parsing()` (líneas 56-232)

**Lógica**:
1. **Carga modelo spaCy español** con parser completo (no deshabilitado)
   - ✅ **RESUELTO (19-Nov-2025)**: Upgrade a `es_core_news_md` para mejor POS tagging
2. **AttributeRuler** pre-parsing (77 categorías de moda):
   - ✅ **RESUELTO (19-Nov-2025)**: Fuerza POS=NOUN para `vestido`, `remera`, `delantal`, etc. antes del parser
   - Previene mistagging ADJ para categorías principales
3. **Whitelist de términos moda**: Captura anglicismos (`top`, `short`, `jean`, `jogger`, etc.)
4. **Análisis de dependencias** sintácticas con reglas de profundidad estrictas:
   - **NOUN/PROPN**: Captura según rol sintáctico (ROOT, dobj, nsubj, obj, nmod, pobj)
   - **ADJ (amod)**: Solo si NO son modificadores de modificadores (evita anidación)
   - **Filtrado de modificadores NIVEL 2**: Ignora términos como "costado" en "cierre al costado"
   - ✅ **RESUELTO (19-Nov-2025)**: Fallback excluye términos NIVEL 2 explícitamente descartados
5. **Fallback robusto**: Si spaCy falla, captura TODOS los NOUN/PROPN/ADJ no procesados
6. **Output**: String con términos únicos ordenados alfabéticamente

**Ejemplo**:
```
Input:  "delantal chocolate con bolsillos amplios"
Output: "amplios bolsillos chocolate delantal"

Input:  "delantal con cierre al costado"
Output: "cierre delantal"  # ✅ "costado" correctamente descartado (NIVEL 2)
```

**Mejoras Recientes (19-Nov-2025)**:
- ✅ Tasa de éxito: **80% → 93.3%** (28/30 casos de prueba)
- ✅ Resueltos: "vestido fucsia", "delantal cieerre negro", "gorra con logo lateral"
- ✅ Nivel 2 correctamente excluido: "costado", "lateral", "mao"

#### 1.2 Normalización Temprana de Color

```python
# Mapeo de errores morfológicos comunes
COLOR_TOKEN_FIXES = {'grices': 'gris'}
```

**Propósito**: Corregir typos frecuentes ANTES del Stage 1 para mejorar recall SQL.

---

### **FASE 2: STAGE 1 - Broad Recall SQL** (Líneas 900-914)

```python
candidates, detection_metadata = stage1_broad_recall(
    query_text,
    client.id,
    client_slug,
    top_n=50
)
```

#### 2.1 Expansión con Sinónimos

**Función**: `expand_query_with_synonyms()` (líneas 442-495)

**Lógica**:
1. **Chequea módulo personalizado** del cliente (si existe)
   - Usa `get_client_module(client_slug)` si `has_custom_module()`
   - Módulo custom implementa `expand_query(text, categories)`
2. **Fallback genérico**:
   - Tokeniza query: `query_text.lower().split()`
   - Busca en `Category.alternative_terms` (campo coma-separado)
   - Si algún token coincide con sinónimos → agrega TODOS los sinónimos
3. **Output**: Lista expandida de tokens

**Ejemplo**:
```python
# Categoría "Shorts" con alternative_terms: "short,bermuda,shores"
Input:  "short rojo"
Output: ["short", "bermuda", "shores", "rojo"]
```

#### 2.2 Detección de Filtro de Categoría

**Lógica** (líneas 571-624):
1. **Con módulo custom**:
   - Normaliza tokens: `module.normalize_tokens(query_text)`
   - Detecta filtro: `module.detect_category_filter(tokens, categories)`
   - Retorna: `(category_ids, metadata)` o solo `category_ids`
2. **Fallback genérico**:
   - Normaliza con `_normalize_tokens_es()` (tokenización + lematización spaCy)
   - Filtra tokens de color (hardcoded set: rojo, verde, azul...)
   - Compara tokens con `_category_tokens()` de cada categoría
   - Si **EXACTAMENTE 1 root token** coincide → aplica filtro
   - Si múltiples o ninguno → búsqueda amplia (sin filtro)

**Metadata retornada**:
```python
{
    'requested_term': 'delantal',
    'matched_categories': ['Delantales', 'Delantales de cocina']
}
```

#### 2.3 Query SQL con SIMILAR TO

**Query** (líneas 626-658):
```sql
SELECT DISTINCT p.id
FROM products p
JOIN categories c ON c.id = p.category_id
WHERE p.client_id = :client_id
  AND p.is_active = TRUE
  AND ((:use_filter = FALSE) OR p.category_id = ANY(:category_ids))
  AND (
    -- Buscar en nombre del producto
    LOWER(p.name) SIMILAR TO :pattern
    OR
    -- Buscar en atributos JSONB
    (
      p.attributes IS NOT NULL
      AND jsonb_typeof(p.attributes) = 'object'
      AND EXISTS (
        SELECT 1 FROM jsonb_each_text(p.attributes) attr
        WHERE LOWER(attr.value) SIMILAR TO :pattern
      )
    )
    OR
    -- Buscar en categoría
    (
      LOWER(c.name) SIMILAR TO :pattern
      OR LOWER(c.name_en) SIMILAR TO :pattern
      OR LOWER(c.alternative_terms) SIMILAR TO :pattern
    )
  )
LIMIT :limit
```

**Pattern**: `%('term1'|'term2'|'term3')%` (regex-like de PostgreSQL)

**Output**: Lista de ~50 `Product` objects (líneas 660-673)

---

### **FASE 3: Validación de Categoría** (Líneas 917-952)

**Crítico**: Si `detection_metadata` no contiene `matched_categories` válidas:
- Query todas las categorías activas del cliente
- Retorna error con lista de categorías disponibles
- **EXIT TEMPRANO** sin ejecutar Stage 2

**Propósito**: Evitar búsquedas sin sentido en categorías inexistentes.

---

### **FASE 4: Extracción de Atributos (LLM)** (Líneas 957-958)

```python
attr_info = extract_query_attributes(query_text, client.id)
```

**Función**: `extract_query_attributes()` en `llm_query_normalizer.py`

**Proceso**:
1. Carga vocabulario dinámico del cliente desde DB:
   - `ProductAttributeConfig` table → atributos configurados
   - Atributos `list` → opciones válidas desde `options` JSONB
2. Usa modelo **MiniLM** (Sentence Transformers) para matching semántico
3. Compara embeddings del query con embeddings del vocabulario
4. Detecta atributos solicitados, contradicciones y no configurados

**Output**:
```python
{
    'attributes': {'color': 'chocolate', 'con_bolsillos': 'si'},
    'requested_count': 2,
    'contradictions': [],
    'not_configured': []
}
```

---

### **FASE 5: Inferencia de Color Semántico** (Líneas 961-1034)

**Objetivo**: Detectar menciones de color NO capturadas por el LLM de atributos.

**Lógica** (líneas 970-1034):
1. **Construir set de exclusiones**:
   - Tokens de categorías conocidas → evitar mapear "delantal" a "bordo"
   - Tokens de atributos configurados → evitar "bolsillos" como color
2. **Tokenizar query** y buscar tokens >= 3 caracteres
3. **Normalizar cada token** con `normalize_color(tok, client_id)`
   - Usa LLM (MiniLM) con vocabulario de colores del cliente
   - Cachea resultados para performance
4. **Capturar primer color detectado**:
   ```python
   detected_color_token = 'chocolate'       # Token original
   detected_color_normalized = 'marrón'     # Color base por LLM
   ```

**Importante**: NO se agrega a `requested_attrs` aún (se maneja en filtrado).

---

### **FASE 6: STAGE 2 - Precise Reranking CLIP** (Líneas 1036-1037)

```python
scored_results = stage2_precise_rerank(query_text, candidates, limit=limit)
```

**Función**: `stage2_precise_rerank()` (líneas 697-753)

#### 6.1 Carga de Modelo CLIP

```python
clip_model, clip_processor = get_clip_model()
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
```

**Modelo**: Por defecto `ViT-B/16` (configurable en `system_config.json`)
**Singleton**: Carga única con auto-descarga por inactividad (2 horas default)

#### 6.2 Generación de Embeddings

**Query**:
```python
query_prompt = f"a photo of {query_text}"  # CLIP prompt format
query_embedding = clip_model.get_text_features(**inputs)
query_embedding /= query_embedding.norm()  # Normalización L2
query_vec = query_embedding.cpu().numpy()[0]
```

**Productos** (loop sobre candidatos):
```python
# Construir descripción textual completa
product_parts = [product.name]
# + atributos clave: color, tipo, material, talla
# + categoría: name + name_en

product_prompt = f"a photo of {product_text}"
prod_embedding = clip_model.get_text_features(**inputs)
prod_embedding /= prod_embedding.norm()
prod_vec = prod_embedding.cpu().numpy()[0]

# Similitud coseno
similarity = float(np.dot(query_vec, prod_vec))
```

#### 6.3 Ranking

```python
scored_candidates.sort(key=lambda x: x['similarity'], reverse=True)
top_results = scored_candidates[:limit]  # Top N
```

**Output**: Lista de diccionarios con `product`, `similarity`, `product_text`.

---

### **FASE 7: Matching de Atributos** (Líneas 1042-1097)

**Propósito**: Calcular qué atributos solicitados cumple cada producto.

**Lógica**:
1. Para cada producto en `scored_results`:
   - Obtener `product.attributes` (JSONB)
   - Para cada `(key, value)` en `requested_attrs`:
     - Si el producto tiene ese key:
       - **Lista**: `any(str(x).lower() == str(v).lower() for x in pv)`
       - **Escalar**: `str(pv).lower() == str(v).lower()`
2. Calcular métricas:
   ```python
   matched_count = len(matched)
   match_ratio = matched_count / requested_count
   ```

**Output**: Agrega campos a cada resultado:
- `attributes_matched`: Dict de atributos cumplidos
- `attributes_match_count`: Cantidad cumplida
- `attributes_match_ratio`: Proporción (0.0 a 1.0)

---

### **FASE 8: Filtrado por Atributos** (Líneas 1100-1268)

**Condición**: Solo si `requested_count > 0`

#### 8.1 Recolección de Valores Disponibles

```python
all_available_values = {}  # {attr_key: [valores_unicos]}
for attr_key in requested_attrs.keys():
    for result in formatted_results:
        val = result['attributes'].get(attr_key)
        # Agregar a set (maneja listas también)
```

**Propósito**: Para feedback inteligente ("Tenemos disponibles en Talla: S, M, L").

#### 8.2 Filtrado por Color (caso especial)

**Flujo** (líneas 1116-1233):

```
¿Se solicitó/detectó color?
    ↓ SÍ
1. Buscar coincidencias EXACTAS con color normalizado
    ↓ ¿Encontró?
    ↓ SÍ → filtered_results = exact_matches
    ↓
    ↓ NO
2. Buscar colores SIMILARES usando embeddings
    ↓
    - Calcular embedding del token original (ej: "grices")
    - Para cada color en productos:
      - Calcular embedding
      - Similitud coseno
    - Filtrar por threshold 0.58 (permisivo)
    - Top 3 colores similares
    ↓
    filtered_results = productos con colores similares
    ↓
3. Actualizar requested_attrs con color que matcheó
    ↓
4. Recalcular attributes_match_count con nuevo color
```

**Búsqueda de Similares** (líneas 1159-1215):
```python
from app.utils.colors import _get_color_embedding

target_emb = _get_color_embedding(color_search_token, client_id)
for c in available_product_colors:
    emb_c = _get_color_embedding(c, client_id)
    sim = np.dot(target_emb, emb_c) / (norm(target_emb) * norm(emb_c))
    if sim >= 0.58:  # Threshold permisivo
        similar_colors.append((c, sim))

# Top 3 más similares
similar_colors.sort(reverse=True)[:3]
```

**Actualización del Color Matcheado** (líneas 1220-1243):
```python
if matched_similar_color:
    requested_attrs['color'] = matched_similar_color
    detected_color_normalized = matched_similar_color

    # RECALCULAR matching con nuevo color
    for r in filtered_results:
        # Repetir lógica de matching de Fase 7
        # con requested_attrs actualizado
```

#### 8.3 Filtrado por Otros Atributos

```python
# Si NO es color: mantener productos con al menos 1 atributo cumplido
filtered_results = [r for r in formatted_results
                   if r.get("attributes_match_count", 0) > 0]
```

---

### **FASE 9: Reordenamiento Final** (Líneas 1246-1267)

**Criterios** (en orden de prioridad):

1. **Con atributos solicitados**:
   ```python
   key=lambda r: (
       r["attributes_match_count"],  # Más atributos cumplidos
       1 if r["stock"] > 0 else 0,    # Stock disponible
       r["similarity"]                # Similitud CLIP
   )
   ```

2. **Sin atributos solicitados**:
   ```python
   key=lambda r: (
       1 if r["stock"] > 0 else 0,
       r["similarity"]
   )
   ```

**Orden**: DESCENDENTE (`reverse=True`)

---

### **FASE 10: Construcción de Feedback** (Líneas 1277-1290)

```python
user_feedback = _build_user_feedback(
    query_text=query_text,
    formatted_results=formatted_results,
    detected_category_info=detection_metadata,
    client_id=client.id,
    attrs_requested=requested_attrs,
    contradictions=attr_info.get('contradictions', []),
    not_configured=attr_info.get('not_configured', []),
    all_available_values=all_available_values,
    detected_color_token=detected_color_token,
    detected_color_normalized=detected_color_normalized
)
```

**Función**: `_build_user_feedback()` (líneas 233-411)

**Lógica de Construcción de Mensaje**:

1. **Categoría reinterpretada**:
   - Si `requested_term` != `matched_categories`:
     - "Buscaste 'X', mostrando resultados de Y y Z"

2. **Atributos solicitados**:
   - Para cada atributo (excepto color):
     - Si valor disponible: "Tenemos disponibles en Talla: S, M, L"
     - Si no disponible: "No disponemos en Talla: 'XL'. Tenemos: S, M, L"

3. **Color interpretado**:
   - Si hubo mapeo: "Interpretamos 'grices' como color 'gris'"
   - Con resultados: "También tenemos disponible en: negro, azul, verde"
   - Sin resultados: "No tenemos X en color 'Y'. Tenemos: lista_colores"

4. **Atributos no configurados**:
   - "El atributo 'manga_larga' no está configurado para este catálogo"

5. **Contradicciones**:
   - "Tu búsqueda contiene criterios contradictorios: manga corta, manga larga"

6. **Fallback**:
   - "Encontramos N productos para tu búsqueda"

**Output**:
```python
{
    'message': "Texto construido dinámicamente",
    'has_results': bool,
    'result_count': int,
    'categories_shown': [str],
    'colors_available': [str] or None,
    'requested_color': str or None,
    'attributes_requested': dict,
    'attributes_not_configured': [str],
    'contradictions': [str]
}
```

---

### **FASE 11: Carga de Configuración de Atributos** (Líneas 1292-1326)

**Propósito**: Proporcionar labels legibles para el frontend.

**Proceso**:
1. Query `ProductAttributeConfig` del cliente
2. Construir dos estructuras:
   ```python
   exposed_attribute_keys = []     # Solo los expose_in_search=True
   exposed_attribute_labels = {}   # Todos: {key: label}
   ```
3. **Fallback para atributos solicitados no configurados**:
   ```python
   def _beautify_label(k):
       # 'con_bolsillos' → 'Bolsillos'
       base = k.replace('con_', '').replace('sin_', '').replace('_', ' ')
       return base.capitalize()
   ```

---

### **FASE 12: Agrupación por Categorías** (Líneas 1328-1340)

**Condición**: Si `detection_metadata` tiene múltiples `matched_categories`.

**Lógica**:
```python
if len(matched_categories) > 1:
    group_by_category = True
    results_by_category = {}
    for result in formatted_results:
        cat_name = result['category']
        results_by_category.setdefault(cat_name, []).append(result)
```

**Output**: Diccionario agrupado por nombre de categoría.

---

### **FASE 13: Construcción de Response** (Líneas 1342-1371)

**Estructura JSON**:
```python
{
    "success": True,
    "query": str,                          # Query procesado
    "expanded_terms": [str],               # Tokens expandidos (Stage 1)
    "stage1_candidates": int,              # Candidatos SQL
    "total_results": int,                  # Resultados finales
    "processing_time": float,              # Segundos
    "search_module": "custom" | "generic", # Módulo usado
    "user_feedback": {                     # Feedback construido (Fase 10)
        "message": str,
        "has_results": bool,
        ...
    },
    "group_by_category": bool,             # Si se agrupó
    "exposed_attribute_keys": [str],       # Atributos visibles
    "exposed_attribute_labels": {key: label},

    # CONDICIONAL:
    "results": [...]                       # Si NO se agrupó
    # O
    "results_by_category": {cat: [...]}    # Si se agrupó
}
```

**Headers CORS**:
```python
response.headers['Access-Control-Allow-Origin'] = '*'
response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-API-Key'
```

---

## 🔴 PUNTOS CRÍTICOS Y PROBLEMAS CONOCIDOS

### 1. **Extractor Semántico puede fallar** (Fase 1.1)
- **Síntoma**: Query complejo retorna string vacío → Banner de ayuda
- **Causa**: spaCy no puede parsear sintácticamente la frase
- **Impacto**: Búsqueda completa falla sin ejecutar Stage 1
- **Línea**: 870-895

### 2. **Filtro de categoría demasiado estricto** (Fase 3)
- **Síntoma**: "La categoría solicitada no se encuentra"
- **Causa**: `detection_metadata` sin `matched_categories` válidas
- **Impacto**: Exit temprano sin resultados
- **Línea**: 917-952

### 3. **Normalización de color puede ser agresiva** (Fase 5)
- **Síntoma**: Términos válidos mapeados incorrectamente (ej: "delantal" → "bordo")
- **Causa**: LLM normaliza tokens que NO son colores
- **Mitigación**: Blacklist de categorías y atributos configurados (líneas 970-1006)
- **Línea**: 961-1034

### 4. **Búsqueda de colores similares puede no encontrar matches** (Fase 8.2)
- **Síntoma**: Threshold 0.58 muy permisivo O demasiado restrictivo
- **Causa**: Embeddings de colores poco discriminativos
- **Impacto**: Resultados vacíos o con colores incorrectos
- **Línea**: 1159-1215

### 5. **Recálculo de matching puede ser costoso** (Fase 8.2)
- **Síntoma**: Latencia adicional en búsquedas con color similar
- **Causa**: Loop doble sobre resultados filtrados
- **Impacto**: ~50-100ms extra en búsquedas complejas
- **Línea**: 1220-1243

### 6. **Transacciones DB pueden abortar** (Múltiples fases)
- **Síntoma**: Rollback defensivo necesario en Fase 0
- **Causa**: Transacciones previas no cerradas correctamente
- **Mitigación**: `db.session.rollback()` al inicio
- **Línea**: 806-808

### 7. **Stage 2 (CLIP) es CPU-bound** (Fase 6)
- **Síntoma**: Latencia 200-500ms con 50 candidatos
- **Causa**: Cálculo secuencial de embeddings (no batch)
- **Impacto**: Tiempo de respuesta total ~0.8-1.2s
- **Línea**: 722-748

---

## 🎯 DEPENDENCIAS CRÍTICAS

### Modelos ML
1. **spaCy** (`es_core_news_sm`):
   - Fase 1.1: Extracción de términos clave
   - Fase 2.1: Normalización de tokens (fallback)
   - **Auto-descarga**: No (debe estar instalado)

2. **CLIP** (ViT-B/16):
   - Fase 6: Text-to-text similarity
   - **Singleton**: Carga única, auto-descarga 2 horas inactividad
   - **Ubicación**: `app/blueprints/embeddings.py`

3. **MiniLM** (paraphrase-multilingual-MiniLM-L12-v2):
   - Fase 4: Extracción de atributos LLM
   - Fase 5: Normalización de colores
   - Fase 8.2: Similitud de colores
   - **Singleton**: Misma gestión que CLIP
   - **Ubicación**: `app/utils/llm_query_normalizer.py`

### Base de Datos
- **PostgreSQL SIMILAR TO**: Stage 1 query (regex-like)
- **JSONB**: Almacenamiento de atributos dinámicos
- **pgvector**: NO se usa en este endpoint (solo en visual search)

### Módulos Custom
- **Ubicación**: `app/search_modules/`
- **Métodos requeridos**:
  - `normalize_tokens(text) -> List[str]`
  - `expand_query(text, categories) -> List[str]`
  - `detect_category_filter(tokens, categories) -> (List[UUID], dict)`
- **Clientes con módulos custom**: `demo_fashion_store`, `eve_s_store`

---

## ⚡ OPTIMIZACIONES SUGERIDAS

### 1. **Batch Processing en Stage 2**
```python
# Calcular embeddings de TODOS los productos en un batch
all_prompts = [f"a photo of {text}" for text in product_texts]
prod_inputs = clip_processor(text=all_prompts, return_tensors="pt", padding=True)
prod_embeddings = clip_model.get_text_features(**prod_inputs)
```
**Impacto estimado**: Reducción 40-60% latencia Stage 2

### 2. **Caché de Embeddings de Productos**
```python
# Cachear en Redis con TTL 24h
cache_key = f"clip_text_emb:{product.id}:{product.updated_at}"
```
**Impacto estimado**: Reducción 70-90% latencia Stage 2 en queries repetidas

### 3. **Paralelizar Normalización de Color**
```python
# Usar ThreadPoolExecutor para normalizar múltiples tokens
with ThreadPoolExecutor(max_workers=4) as executor:
    futures = {executor.submit(normalize_color, tok): tok
               for tok in raw_tokens}
```
**Impacto estimado**: Reducción 30-50% latencia Fase 5

### 4. **Index en product.attributes JSONB**
```sql
CREATE INDEX idx_products_attributes_gin
ON products USING gin (attributes jsonb_path_ops);
```
**Impacto estimado**: Mejora 20-40% Stage 1 SQL query

### 5. **Lazy Loading de Imágenes**
```python
# No cargar images en Stage 2, solo al formatear resultados finales
# Evita joins innecesarios con tabla images
```
**Impacto estimado**: Reducción 10-15% queries DB

---

## 📈 MÉTRICAS DE PERFORMANCE

### Tiempos Promedio (CPU, 50 candidatos)
- **Fase 1 (Preprocesamiento)**: 20-50ms
- **Fase 2 (Stage 1 SQL)**: 50-150ms
- **Fase 4 (LLM Atributos)**: 80-200ms
- **Fase 5 (Inferencia Color)**: 10-30ms
- **Fase 6 (Stage 2 CLIP)**: 200-500ms
- **Fase 8 (Filtrado)**: 10-50ms
- **Total**: **800-1200ms**

### Casos Edge
- **Query vacía**: ~5ms (validación rápida)
- **Sin categoría detectada**: ~100ms (exit temprano)
- **Sin candidatos Stage 1**: ~150ms (sin Stage 2)
- **Con módulo custom**: +50-100ms (lógica adicional)

---

## 🛠️ DEBUGGING

### Variables de Entorno Relevantes
```bash
CLIP_IDLE_TIMEOUT_MINUTES=120   # Auto-descarga CLIP/MiniLM
LOG_LEVEL=DEBUG                  # Logs verbose
```

### Logs Clave
```python
print(f"🔍 [TEXT_SEARCH] Query original: '{query_text}'")
print(f"🧹 [TEXT_SEARCH] Preprocesamiento: '{cleaned_query}'")
print(f"⚡ STAGE 1: {len(candidates)} candidatos")
print(f"🎯 STAGE 2: Top {len(top_results)} rerankeados")
print(f"🎨 Color detectado: '{tok}' → '{normalized}'")
print(f"✅ Búsqueda completada: {len(results)} resultados")
```

### Herramientas
- **Postman/Insomnia**: Testear endpoint directamente
- **PostgreSQL EXPLAIN**: Analizar plan de ejecución Stage 1
- **Python profiler**: `cProfile` para identificar bottlenecks
- **Redis Monitor**: Si se implementa caché de embeddings

---

## 🔗 ARCHIVOS RELACIONADOS

1. **search_text.py** (1372 líneas):
   - Endpoint principal y funciones auxiliares

2. **llm_query_normalizer.py** (1001 líneas):
   - Extracción de atributos con MiniLM
   - Normalización de colores
   - Gestión de vocabulario dinámico

3. **colors.py** (199 líneas):
   - `normalize_color()`: LLM color normalization
   - `_get_color_embedding()`: Embeddings para similitud

4. **embeddings.py** (2108 líneas):
   - `get_clip_model()`: Singleton CLIP
   - Auto-descarga por inactividad

5. **search_modules/search_client_*.py**:
   - Módulos personalizados por cliente
   - Override de normalización y detección

6. **models/product.py**:
   - Modelo SQLAlchemy con `attributes` JSONB

7. **models/product_attribute_config.py**:
   - Configuración dinámica de atributos

---

## 📝 CONCLUSIONES

### Fortalezas
✅ **Two-Stage Retrieval** eficiente: SQL broad recall + CLIP precision
✅ **Módulos personalizables** por cliente
✅ **Feedback inteligente** y descriptivo
✅ **Búsqueda semántica de colores** robusta
✅ **Atributos dinámicos** sin hardcodeo

### Debilidades
❌ **Stage 2 secuencial** (no batch) → alta latencia
❌ **Sin caché de embeddings** → cálculos repetidos
~~❌ **Extractor spaCy puede fallar** → exit temprano~~ ✅ **RESUELTO** (19-Nov-2025: AttributeRuler + nivel2_discarded)
❌ **Filtro de categoría estricto** → falsos negativos
❌ **Normalización de color puede mapear mal** → necesita blacklists

### Recomendaciones Inmediatas
1. **Implementar batch processing en Stage 2**
2. **Agregar caché Redis para embeddings CLIP**
3. **Relajar validación de categoría** (permitir búsqueda amplia)
~~4. **Mejorar robustez del extractor** (mejor fallback)~~ ✅ **COMPLETADO** (19-Nov-2025)
5. **Agregar telemetría** (APM: NewRelic, Datadog, Sentry)

---

**Última actualización**: 19 de noviembre de 2025
**Analizado por**: GitHub Copilot (Claude Sonnet 4.5)
