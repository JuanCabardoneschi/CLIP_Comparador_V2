# Especificación Funcional: Búsqueda por Descripción

**Sistema**: CLIP Comparador V2
**Fecha**: 17 de Noviembre, 2025
**Versión**: 1.0
**Autor**: Especificación consolidada del cliente

---

## 🎯 Objetivo

Implementar búsqueda textual inteligente que detecte categoría y atributos del producto solicitado, devolviendo resultados ordenados por cumplimiento de criterios y mostrando información clara al usuario sobre qué encontró y qué no.

---

## 📋 Flujo Funcional Completo

### 1. Detección de Categoría

**🚨 CRÍTICO**: La detección de categoría es **MANDATORIA**. Si no se detecta una categoría válida, **NO se devuelven resultados** (aunque haya atributos en la query).

**Comportamiento**:
- Analizar la query y detectar si menciona una categoría específica
- Si se detecta UNA categoría inequívoca → filtrar resultados a esa categoría
- Si se detectan categorías hermanas/similares → incluir todas las hermanas en el filtro
- Si NO se detecta categoría válida → **DETENER búsqueda y mostrar categorías disponibles**

**⚠️ Cambio 17 Nov 2025**: Anteriormente, si no se detectaba categoría pero había atributos (ej. "campera azul"), el sistema devolvía productos por atributos. **Esto es incorrecto**. La categoría es obligatoria.

**Casos especiales**:
- **Categoría inexacta**: Si el usuario busca "short" y existen "shores tiro alto" y "shores tiro bajo" → incluir ambas
- **Categoría no existe**: Si pide "notebook" en tienda de ropa → **NO devolver productos**, mostrar mensaje con categorías disponibles
- **Sin categoría explícita**: Query "azul" sin mencionar tipo de prenda → **NO devolver productos**, indicar que debe especificar categoría

**⭐ AGRUPACIÓN POR CATEGORÍAS HERMANAS**:
Cuando se detectan múltiples categorías hermanas (ej. "short" → "shores tiro alto", "shores tiro bajo"):
- El backend debe devolver `results_by_category` con productos agrupados por categoría
- El frontend debe mostrar un banner/header por cada categoría
- Orden de presentación: primero todos los productos de categoría 1, luego categoría 2, etc.

**Ejemplo visual esperado**:
```
[Banner: "Shores Tiro Alto" - 4 productos]
  [Card producto 1] [Card producto 2] [Card producto 3] [Card producto 4]

[Banner: "Shores Tiro Bajo" - 6 productos]
  [Card producto 1] [Card producto 2] ... [Card producto 6]
```

**Output esperado**:
```python
detected_category_info = {
    'requested_term': 'short',  # término que detectamos
    'matched_categories': ['shores tiro alto', 'shores tiro bajo'],  # categorías aplicadas
    'group_by_category': True  # indica que se deben agrupar en el front
}

# Respuesta del backend cuando hay múltiples categorías hermanas:
{
  "results_by_category": {
    "shores tiro alto": [
      { "id": "...", "name": "short berlin", ... },
      { "id": "...", "name": "short milan", ... }
    ],
    "shores tiro bajo": [
      { "id": "...", "name": "short mendoza", ... },
      { "id": "...", "name": "short aleman", ... }
    ]
  },
  "results": []  # vacío cuando se usa results_by_category
}
```

---

### 2. Extracción de Atributos

**Fuente de verdad**: Tabla `product_attribute_config` del cliente
- Cada cliente define sus propios atributos (color, talla, material, etc.)
- Tipo de atributo: `text`, `list`, `url`, `number`, `boolean`

**Proceso de extracción**:

#### A. Atributos tipo `list` (color, talla, material)
- Usar MiniLM para matching semántico entre query y opciones del atributo
- Threshold: 0.75 para match
- Fallback léxico: si no hay match semántico, buscar coincidencia exacta en texto

**Ejemplo**:
```python
# ProductAttributeConfig para "color"
{
    "key": "color",
    "label": "Color",
    "type": "list",
    "options": ["rojo", "azul", "verde", "negro", "blanco"]
}

# Query: "short verde"
# Resultado: {"color": "verde"}  # match exacto
```

#### B. Atributos tipo `boolean` (bolsillos, capucha, cierre)
- Detectar patrones "con X" → True
- Detectar patrones "sin X" → False
- Sin mención → No solicitar

**Ejemplo**:
```python
# Query: "short con bolsillos"
# Resultado: {"bolsillos": True}

# Query: "remera sin capucha"
# Resultado: {"capucha": False}
```

#### C. Atributos tipo `text`, `number`, `url`
- Heurísticas básicas por tipo
- No priorizar (enfoque en list y boolean)

**Contradicciones**:
- Si detectamos "con bolsillos" Y "sin bolsillos" → registrar contradicción
- Mostrar en banner: "Tu búsqueda contiene criterios contradictorios: bolsillos"

**Atributos no configurados**:
- Si el usuario pide "bolsillos" pero NO existe en `product_attribute_config` del cliente
- Registrar como "no configurado"
- Mostrar en banner: "El atributo 'bolsillos' no está configurado para este catálogo"

**Output esperado**:
```python
{
    'attributes': {
        'color': 'verde',
        'bolsillos': True  # aunque no exista en config
    },
    'requested_count': 2,
    'contradictions': [],  # o ['bolsillos'] si hay "con" y "sin"
    'not_configured': ['bolsillos']  # si no está en ProductAttributeConfig
}
```

---

### 3. Matching de Atributos por Producto

Para cada producto candidato:

**Proceso**:
1. Leer `product.attributes` (campo JSONB)
2. Para cada atributo solicitado en la query, verificar si el producto lo cumple
3. Soportar listas multi-valor en atributos (ej. `colors: ["rojo", "negro"]`)

**Lógica de matching**:
```python
# Atributo simple
requested = {"color": "verde"}
product.attributes = {"color": "VERDE"}
# Match: True (case-insensitive)

# Atributo lista
requested = {"color": "verde"}
product.attributes = {"color": ["verde", "azul"]}
# Match: True (está en la lista)

# Atributo boolean
requested = {"bolsillos": True}
product.attributes = {"bolsillos": True}  # o "si", "sí", 1
# Match: True

# Atributo faltante
requested = {"bolsillos": True}
product.attributes = {}  # no tiene el campo
# Match: False (no cumple)
```

**Output por producto**:
```python
{
    "attributes_matched": {
        "color": "verde"  # solo atributos que SÍ cumplió
    },
    "attributes_match_count": 1,  # cantidad cumplida
    "attributes_match_ratio": 0.5  # 1/2 = 50% (cumplió color, no bolsillos)
}
```

---

### 4. Ordenamiento de Resultados (Opción A)

**Prioridad de ordenamiento**:
1. **Cantidad de atributos cumplidos** (mayor es mejor)
2. **Disponibilidad de stock** (con stock > sin stock)
3. **Similitud CLIP** (mayor es mejor)

**Pseudocódigo**:
```python
if requested_count > 0:
    # Hay atributos solicitados
    formatted_results.sort(
        key=lambda r: (
            r['attributes_match_count'],  # primero: cumplimiento
            1 if r['stock'] > 0 else 0,    # segundo: disponibilidad
            r['similarity']                 # tercero: similitud
        ),
        reverse=True
    )
else:
    # Sin atributos solicitados (búsqueda genérica)
    formatted_results.sort(
        key=lambda r: (
            1 if r['stock'] > 0 else 0,    # primero: disponibilidad
            r['similarity']                 # segundo: similitud
        ),
        reverse=True
    )
```

**Resultado esperado**:
- Productos que cumplen 2/2 atributos con stock → arriba
- Productos que cumplen 2/2 atributos sin stock → después
- Productos que cumplen 1/2 atributos con stock → después
- Productos que cumplen 1/2 atributos sin stock → después
- Productos que cumplen 0/2 atributos con stock → después
- Productos que cumplen 0/2 atributos sin stock → al final

---

### 5. Manejo de Stock

**Reglas**:
- **Producto con stock > 0**: mostrar "Stock: X"
- **Producto con stock = 0**: mostrar "SIN STOCK" (color rojo)
- Priorizar productos con stock en el ordenamiento (ver sección 4)

**NO sugerir productos alternativos** automáticamente (el usuario puede ver otros resultados en la lista)

---

### 6. ⭐ Filtrado Estricto por Atributos (NUEVO - 17 Nov 2025)

**Comportamiento**:
- Cuando la query contiene atributos solicitados (color, talla, etc.), **SOLO mostrar productos que cumplan AL MENOS 1 atributo**
- Productos que no cumplen ningún atributo solicitado son excluidos de los resultados

**Proceso**:
1. Detectar atributos en la query (ej. "pantalon azul" → color=azul)
2. Recopilar valores disponibles para cada atributo en todos los candidatos
3. Filtrar: mantener solo productos donde `attributes_match_count >= 1`
4. Si después del filtro no quedan productos → no filtrar (mostrar todos)

**Mensaje en el banner**:
- **Si el valor solicitado existe**: `"Tenemos disponibles en {atributo}: {valores}"`
- **Si el valor NO existe**: `"No disponemos en {atributo}: '{valor_solicitado}'. Tenemos disponibles en {atributo}: {valores}"`

**Ejemplo**:
```
Query: "pantalon azul"
Candidatos antes del filtro: 10 pantalones (3 azules, 4 negros, 3 grises)
Candidatos después del filtro: 3 pantalones azules
Banner: "Tenemos disponibles en color: azul, gris, negro"
```

**Ejemplo (valor no disponible)**:
```
Query: "pantalon verde"
Candidatos antes del filtro: 10 pantalones (0 verdes, 4 azules, 3 negros, 3 grises)
Candidatos después del filtro: 10 pantalones (sin filtrar porque ningún match)
Banner: "No disponemos en color: 'verde'. Tenemos disponibles en color: azul, gris, negro"
```

**Nota importante**: Este filtrado aplica SOLO cuando hay atributos solicitados. Si es búsqueda genérica (sin atributos), mostrar todos los resultados ordenados por similitud.

---

### 7. ⭐ Manejo de Categoría Inexistente (NUEVO - 17 Nov 2025)

**Comportamiento**:
- Si NO se detecta ninguna categoría válida → **DETENER búsqueda inmediatamente**
- Devolver respuesta exitosa con `results: []` y mensaje especial
- **NO continuar** con Stage 2 aunque haya atributos en la query

**🚨 Cambio Crítico (17 Nov 2025)**: Anteriormente, si no había categoría pero había atributos (ej. "campera azul"), el sistema devolvía productos que cumplían los atributos. **Esto es incorrecto**. La categoría es mandatoria.

**Mensaje**:
```
"La categoría solicitada no se encuentra entre las comercializables. Categorías disponibles: {cat1, cat2, cat3, ...}"
```

**Estilo del banner**:
- ⭐ **Color**: Azul/índigo sutil (NO rojo agresivo)
- **Gradient**: `linear-gradient(135deg, #667eea 0%, #764ba2 100%)`
- **Tono**: Informativo, no de error

**Ejemplo**:
```
Query: "notebook"
Catálogo del cliente: remeras, pantalones, shorts, zapatillas
Resultado: 0 productos
Banner: "La categoría solicitada no se encuentra entre las comercializables. Categorías disponibles: remeras, pantalones, shorts, zapatillas"
```

**Ejemplo 2 (sin categoría explícita)**:
```
Query: "campera azul"
Detección: No se encuentra categoría "campera"
Resultado: 0 productos (aunque "azul" sea un atributo válido)
Banner: "La categoría solicitada no se encuentra entre las comercializables. Categorías disponibles: remeras, pantalones, shorts, zapatillas"
```

**Response JSON**:
```json
{
  "success": true,
  "results": [],
  "total_results": 0,
  "user_feedback": {
    "message": "La categoría solicitada no se encuentra entre las comercializables. Categorías disponibles: remeras, pantalones, shorts, zapatillas",
    "has_results": false,
    "categories_available": ["remeras", "pantalones", "shorts", "zapatillas"]
  }
}
```

**Validación en código**:
```python
# 🚫 VALIDACIÓN CRÍTICA: Si no hay categoría válida detectada, NO continuar
if not detection_metadata or not detection_metadata.get('matched_categories'):
    # Mostrar categorías disponibles y detener
    return response_with_categories_available()

# Solo si hay categoría válida, continuar con Stage 2
```

**Nota**: Este mensaje aparece cuando:
1. No se detectó ninguna categoría válida en la query
2. No hay relación semántica con las categorías del catálogo
3. **Incluso si hay atributos válidos** (color, talla, etc.) en la query

---

### 8. Mensajería al Usuario (Banner)

**Contenido del banner** (`user_feedback.message`):

#### Caso 1: Categoría detectada y reinterpretada
```
"Buscaste 'short', mostrando resultados de shores tiro alto y shores tiro bajo."
```

**⭐ IMPORTANTE (17 Nov 2025)**: El banner debe mostrar SOLO las categorías donde realmente hay productos en los resultados, **NO** todas las categorías detectadas.

**Ejemplo**:
- Query: "pantalon"
- Categorías detectadas: "pantalones de jeans rectos", "pantalones de jeans chupin", "Pantalones", "pantalon de jeans boca ancha"
- Productos en resultados: Solo de "pantalones de jeans chupin" y "pantalon de jeans boca ancha"
- ✅ Banner correcto: `"Buscaste 'pantalon', mostrando resultados de pantalones de jeans chupin y pantalon de jeans boca ancha"`
- ❌ Banner incorrecto: `"Buscaste 'pantalon', mostrando resultados de pantalones de jeans rectos, pantalones de jeans chupin, Pantalones y pantalon de jeans boca ancha"`

**Implementación**: Usar `shown_categories` (extraídas de `formatted_results`) en lugar de `matched_categories` (del módulo de detección).

#### Caso 2: Atributos con valores disponibles
```
"Tenemos disponibles en color: azul, negro, gris"
```

#### Caso 3: Atributos con valor solicitado no disponible
```
"No disponemos en color: 'verde'. Tenemos disponibles en color: azul, celeste, negro"
```

#### Caso 4: Atributos no configurados
```
"El atributo 'bolsillos' no está configurado para este catálogo."
```

#### Caso 5: Contradicciones
```
"Tu búsqueda contiene criterios contradictorios: bolsillos (con y sin)."
```

#### Caso 6: Sin resultados
```
"No encontramos productos que coincidan con tu búsqueda."
```

#### Caso 7: Búsqueda genérica exitosa
```
"Encontramos 10 productos para tu búsqueda."
```

**Combinaciones** (separar con punto):
```
"Buscaste 'pantalon', mostrando resultados de pantalones de jeans chupin y pantalon de jeans boca ancha. Tenemos disponibles en color: azul, negro, gris."
```

**Estructura del objeto `user_feedback`**:
```python
{
    'message': "Mensaje descriptivo completo",
    'has_results': True,
    'result_count': 10,
    'categories_shown': ['pantalones de jeans chupin', 'pantalon de jeans boca ancha'],  # SOLO las que tienen productos
    'attributes_requested': {
        'color': 'azul'
    },
    'attributes_not_configured': ['bolsillos'],
    'contradictions': []
}
```

---

### 7. UI/UX en el Widget

#### A. Banner Informativo
- **Ubicación**: Debajo del botón "Buscar productos"
- **Estilo**: Fondo azul (#4a6cf7), texto blanco, borde redondeado
- **Contenido**: `user_feedback.message`
- **Visibilidad**: Mostrar siempre que haya `user_feedback.message`

#### B. Badges por Producto (Cards)

**Badge de similitud** (verde, esquina superior derecha de imagen):
```
"67% Match"
```

**Badge de cumplimiento de atributos** (debajo del nombre, si cumple alguno):
```html
<span class="badge-attr">Color: verde</span>
<span class="badge-attr">Bolsillos: Sí</span>
<span class="badge-percent">100% atributos</span>
```
- Fondo: #eef2ff (azul claro), texto: #374151 (gris oscuro)
- Badge de porcentaje: #ecfdf5 (verde claro), texto: #065f46 (verde oscuro)

**Badge de stock**:
- **Con stock**: `✓ Stock: 4` (verde, #10b981)
- **Sin stock**: `✗ Sin stock` (rojo, #ef4444)

**Ejemplo de card completo**:
```
[Imagen con "67% Match" en esquina]
short mendoza
$27000.00
[Color: azul] [50% atributos]
✗ Sin stock
```

---

### 9. Siempre Devolver Resultados (Excepto Categoría Inexistente)

**Regla de oro**: NUNCA devolver lista vacía si hay productos en el catálogo y la categoría solicitada existe

**Excepción**: Si la categoría solicitada NO existe en el catálogo → devolver `results: []` con mensaje de categorías disponibles (ver sección 7)

**Estrategia de fallback**:
1. Si hay atributos solicitados pero ningún producto los cumple → devolver productos de la categoría ordenados por similitud
2. Si la categoría existe pero es ambigua → devolver productos más similares de todas las categorías relacionadas
3. Siempre explicar en el banner qué se encontró y qué no

**Ejemplo**:
```
Query: "short verde con bolsillos"
- Categoría: OK (shores)
- Color verde: NO disponible
- Bolsillos: NO configurado

Resultado: Devolver todos los shorts ordenados por similitud
Banner: "Buscaste 'short', mostrando resultados de shores tiro alto y shores tiro bajo. No disponemos en 'verde', mostrando opciones en azul, celeste, negro. El atributo 'bolsillos' no está configurado para este catálogo."
```

---

## 📊 Ejemplo Completo: "short verde con bolsillos"

### Input
```json
{
  "query": "short verde con bolsillos",
  "limit": 20
}
```

### Procesamiento

**1. Detección de categoría**:
- Token "short" → match con "shores tiro alto" y "shores tiro bajo"
- Filtro aplicado: 2 categorías

**2. Extracción de atributos**:
- "verde" → atributo `color` (tipo list) → valor: "verde"
- "bolsillos" → atributo booleano → valor: True
- "bolsillos" NO está en ProductAttributeConfig → marcar como no configurado

**3. Stage 1: Broad Recall**:
- SQL con filtro de categoría → 10 candidatos

**4. Stage 2: CLIP Reranking**:
- Similitud text-to-text → 10 productos con scores

**5. Matching de atributos**:
- Producto 1: color=AZUL, sin campo bolsillos → 0/2 cumplidos (0%)
- Producto 2: color=NEGRO, sin campo bolsillos → 0/2 cumplidos (0%)
- Producto 3: color=CELESTE, sin campo bolsillos → 0/2 cumplidos (0%)
- (ninguno cumple "verde" ni tiene "bolsillos")

**6. Ordenamiento (Opción A)**:
- Por attributes_match_count (todos 0) → por stock → por similitud
- Productos con stock suben, sin stock bajan

**7. Mensajería**:
```
"Buscaste 'short', mostrando resultados de shores tiro alto y shores tiro bajo. No disponemos en 'verde', mostrando opciones en azul, celeste, negro. El atributo 'bolsillos' no está configurado para este catálogo."
```

### Output
```json
{
  "success": true,
  "query": "short verde con bolsillos",
  "expanded_terms": ["short", "shorts", "shores", "verde", "bolsillos"],
  "stage1_candidates": 10,
  "results": [
    {
      "id": "...",
      "name": "short simil pollera",
      "price": 30000.0,
      "similarity": 0.651,
      "final_score": 0.651,
      "image_url": "https://...",
      "category": "shores tiro alto",
      "attributes": {
        "color": "CELESTE"
      },
      "attributes_matched": {},
      "attributes_match_count": 0,
      "attributes_match_ratio": 0.0,
      "stock": 4
    },
    {
      "id": "...",
      "name": "short mendoza",
      "price": 27000.0,
      "similarity": 0.671,
      "final_score": 0.671,
      "image_url": "https://...",
      "category": "shores tiro bajo",
      "attributes": {
        "color": "AZUL"
      },
      "attributes_matched": {},
      "attributes_match_count": 0,
      "attributes_match_ratio": 0.0,
      "stock": 0
    }
  ],
  "total_results": 10,
  "processing_time": 7.869,
  "search_module": "custom",
  "user_feedback": {
    "message": "Buscaste 'short', mostrando resultados de shores tiro alto y shores tiro bajo. No disponemos en 'verde', mostrando opciones en azul, celeste, negro. El atributo 'bolsillos' no está configurado para este catálogo.",
    "has_results": true,
    "result_count": 10,
    "categories_shown": ["shores tiro alto", "shores tiro bajo"],
    "colors_available": ["azul", "negro", "celeste"],
    "requested_color": "verde",
    "attributes_requested": {
      "color": "verde",
      "bolsillos": true
    },
    "attributes_not_configured": ["bolsillos"],
    "contradictions": []
  }
}
```

### UI Esperada
- **Banner**: Mensaje completo explicando qué se encontró y qué no
- **Cards**:
  - Producto con stock=4 aparece primero (ordenado por stock)
  - Cada card muestra: "X% Match", precio, "Stock: 4" o "SIN STOCK"
  - NO muestran badges de atributos (porque attributes_match_count=0)

---

## ⚠️ Casos Edge Importantes

### 1. Atributo solicitado pero no configurado
**Query**: "short con bolsillos"
**Escenario**: `bolsillos` no existe en `product_attribute_config`
**Comportamiento**:
- Extraer de todas formas: `{"bolsillos": True}`
- Marcar como no configurado
- Banner: "El atributo 'bolsillos' no está configurado para este catálogo"
- Ningún producto tendrá match de ese atributo
- Ordenar solo por similitud y stock

### 2. Contradicción en atributos
**Query**: "remera con capucha sin capucha"
**Comportamiento**:
- Detectar contradicción
- Banner: "Tu búsqueda contiene criterios contradictorios: capucha"
- No aplicar ese atributo al matching
- Buscar solo por otros criterios

### 3. Todos los productos sin stock
**Comportamiento**:
- Devolver resultados ordenados por cumplimiento y similitud
- Mostrar "SIN STOCK" en todos
- NO sugerir alternativas (el usuario ve la lista completa)

### 4. Sin categoría detectada
**Query**: "verde con bolsillos" (sin mencionar tipo de prenda)
**Comportamiento**:
- Buscar en TODAS las categorías
- Banner: "Encontramos X productos para tu búsqueda"
- Ordenar por cumplimiento → stock → similitud

### 5. Categoría no existe
**Query**: "pantalones rojos" pero cliente no tiene categoría pantalones
**Comportamiento**:
- No aplicar filtro de categoría
- Buscar en todas las categorías por similitud
- Banner: "No encontramos la categoría 'pantalones', mostrando resultados similares en [categorías_encontradas]"

---

## 🚫 Restricciones Importantes

1. **NO tocar el flujo de búsqueda visual** bajo ningún concepto
2. **NO hacer fallback genérico** en el endpoint si el módulo custom falla → el módulo DEBE implementar el contrato
3. **NO hardcodear colores** → usar siempre vocabulario del cliente + embeddings semánticos
4. **NO sugerir productos alternativos** automáticamente → el usuario ve la lista completa y decide
5. **NO crear atributos** que no estén en `product_attribute_config` → solo marcar como "no configurado"

---

## ✅ Checklist de Validación

### Funcionalidades Core
- [ ] Detección de categoría con hermanas incluidas
- [ ] Extracción de atributos tipo list con MiniLM
- [ ] Extracción de atributos tipo boolean con patrones "con/sin"
- [ ] Detección de contradicciones en atributos
- [ ] Detección de atributos no configurados
- [ ] Matching de atributos por producto (incluyendo listas multi-valor)
- [ ] Ordenamiento Opción A: atributos → stock → similitud
- [ ] Banner con mensaje descriptivo completo
- [ ] Badges por producto: similitud, atributos cumplidos, porcentaje, stock
- [ ] Evitar normalizaciones LLM para tokens no-color
- [ ] No afectar búsqueda visual en absoluto

### ⭐ Filtrado Estricto por Atributos (17 Nov 2025)
- [ ] Cuando hay atributos solicitados, filtrar productos que no cumplan ninguno
- [ ] Recopilar valores disponibles para cada atributo solicitado
- [ ] Mostrar en banner "Tenemos disponibles en {atributo}: {valores}"
- [ ] Si valor solicitado no existe, indicar "No disponemos en {atributo}: '{valor}'"
- [ ] Si después del filtro no quedan productos, no aplicar filtro (mostrar todos)
- [ ] Mantener ordenamiento Option A dentro de productos filtrados

### ⭐ Manejo de Categoría Inexistente (17 Nov 2025)
- [ ] Detectar cuando no hay categoría válida y no hay relación semántica
- [ ] Devolver `results: []` con mensaje especial
- [ ] Listar todas las categorías activas del cliente en el banner
- [ ] Mensaje: "La categoría solicitada no se encuentra entre las comercializables. Categorías disponibles: ..."
- [ ] Incluir `categories_available` en `user_feedback`

### ⭐ Agrupación por Categorías (NUEVO)
- [ ] Backend detecta múltiples categorías hermanas (`matched_categories > 1`)
- [ ] Backend agrupa resultados en `results_by_category` por nombre de categoría
- [ ] Response incluye flag `group_by_category: true`
- [ ] Widget detecta `group_by_category` y llama función `displayTextResultsByCategory`
- [ ] Widget renderiza banner global con `user_feedback.message`
- [ ] Widget renderiza banner por categoría con nombre + cantidad
- [ ] Widget renderiza grid de productos por cada categoría
- [ ] Ordenamiento Option A se preserva dentro de cada categoría
- [ ] Badges (atributos, stock, similarity) se muestran correctamente en cada producto
- [ ] Comportamiento backward-compatible: sin múltiples categorías → lista plana

### Test End-to-End
- [ ] Query: "short verde con bolsillos" en Eve's Store
  - [ ] Detecta categorías "shores tiro alto" + "shores tiro bajo"
  - [ ] Muestra 2 secciones con banners de categoría
  - [ ] Banner global indica sustitución de "verde" → "azul, celeste, negro"
  - [ ] Banner global indica "bolsillos no configurado"
  - [ ] Productos ordenados por color similar primero, luego stock
  - [ ] Badges de atributos muestran "color: azul", etc.
  - [ ] JSON response coincide con spec sección 8

---
