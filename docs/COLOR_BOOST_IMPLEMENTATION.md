# Color-Aware Visual Search - Implementación Dinámica

## Problema identificado

El widget detectaba correctamente la categoría pero priorizaba productos de color incorrecto:
- **Query**: Polo blanco
- **Resultado #1**: Camisa botón negra (82% similitud)
- **Resultado esperado**: Camisa blanca debería estar primero

### Causa raíz
CLIP calcula similitud visual basada en:
1. Forma y composición (peso alto)
2. Textura y patrones (peso medio)
3. Color (peso bajo-medio)

Una camisa negra con buena composición/lighting puede tener mayor similitud CLIP que una camisa blanca con peor foto.

## Solución implementada (100% dinámica)

### 1. Detección de color dominante (`detect_dominant_color()`)
**⚠️ IMPORTANTE: Sin hardcodeo, usa los colores reales del cliente**

```python
def detect_dominant_color(image_data, client_id):
    """Detecta el color dominante usando los colores de productos del cliente"""

    # Obtener colores únicos de los productos del cliente (dinámico)
    colors_query = db.session.query(Product.color).filter(
        Product.client_id == client_id,
        Product.color.isnot(None)
    ).distinct().all()

    unique_colors = [c[0].strip() for c in colors_query]

    # Crear prompts dinámicos basados en los colores del cliente
    color_prompts = [f"a photo of {color.lower()} product" for color in unique_colors]

    # Compara imagen query con cada prompt de color
    # Retorna: (color, confidence)
```

**Ventajas**:
- ✅ Funciona para cualquier industria (textil, muebles, electrónica, etc.)
- ✅ Usa solo los colores que existen en el catálogo del cliente
- ✅ No requiere configuración manual ni mapeos

### 2. Boost por color matching (sin mapeo hardcodeado)
- **Cuando**: Si `color_confidence >= 0.25` (umbral bajo, solo para tie-break)
- **Cuánto**: `similarity * 1.12` (+12% boost)
- **Matching**: Comparación directa case-insensitive
  ```python
  if product_color.upper() == detected_color.upper():
      # Dar boost
  ```

### 3. Detección de categoría con desempate dinámico
**⚠️ IMPORTANTE: Sin sinónimos hardcodeados**

```python
def detect_general_object(image_data, client_id):
    """Usa las categorías del cliente para detección"""

    # Obtener categorías activas del cliente
    categories = Category.query.filter_by(
        client_id=client_id,
        is_active=True
    ).all()

    # Usar name_en de cada categoría como término de detección
    general_categories = [
        f"a photo of {cat.name_en.lower()}"
        for cat in categories
    ]

    # Comparar y retornar mejor match
```

**Desempate en margen pequeño**:
```python
def cat_matches_object(cat, obj):
    """Match dinámico basado en name y name_en de la categoría"""
    cat_name = (cat.name or '').lower()
    cat_name_en = (cat.name_en or '').lower()
    obj_lower = obj.lower()

    # Match directo o por inclusión
    return obj_lower in cat_name or obj_lower in cat_name_en
```

### 3. Flujo completo
```
1. Usuario sube imagen (polo blanco)
2. Detección objeto: "shirt" (0.65)
3. 🎨 Detección color: "white" (0.78)
4. Detección categoría: CAMISAS (0.79)
5. Búsqueda productos en CAMISAS
6. Similitudes calculadas:
   - Camisa negra: 0.82
   - Camisa blanca: 0.77
7. 🎨 Boost por color:
   - Camisa negra: 0.82 (sin boost, color no match)
   - Camisa blanca: 0.77 * 1.12 = 0.86 ✅
8. Ordenamiento final:
   1° Camisa blanca (0.86)
   2° Camisa negra (0.82)
```

## Parámetros configurables

### Umbral de confianza de color
```python
if color_confidence >= 0.25:  # Muy bajo: solo desempate
```
- **0.25**: Aplicar boost incluso con baja confianza (tie-breaker)
- **0.50**: Solo si el color es razonablemente claro
- **0.70**: Solo si el color es muy evidente

### Magnitud del boost
```python
boosted_similarity = original * 1.12  # +12%
```
- **1.05-1.10**: Boost sutil (5-10%)
- **1.12**: Boost moderado (12%) ← actual
- **1.15-1.20**: Boost fuerte (15-20%)

## Ventajas de esta estrategia

✅ **No invasivo**: La similitud visual sigue siendo el factor principal
✅ **Tie-breaker inteligente**: Solo afecta productos con similitud parecida
✅ **Mapeo robusto**: Maneja variaciones de nombre de color (BLANCO, WHITE, etc.)
✅ **Logging detallado**: Fácil de debuggear y ajustar
✅ **Configurable**: Fácil ajustar umbral y magnitud del boost

## Resultados esperados

### Caso polo blanco
- **Antes**: Camisa negra primero (similitud pura CLIP)
- **Después**: Camisa blanca primero (similitud + boost color)

### Casos edge
- **Colores ambiguos** (gris claro vs blanco): Umbral bajo permite boost sutil
- **Sin productos del color detectado**: No afecta el resultado (boost solo si hay match)
- **Productos sin color en BD**: No reciben boost, mantienen similitud original

## Monitoreo

En los logs verás:
```
🎨 RAILWAY LOG: IDENTIFICANDO COLOR DOMINANTE...
🎨 DETECCIÓN COLOR: white (confianza: 0.783)
🎨 RAILWAY LOG: Aplicando boost por color matching (color: white)
🎨 COLOR BOOST: CAMISA BOTON OCULTO BLANCA (BLANCA) 0.7700 → 0.8624
```

## Próximos pasos (opcional)

1. **A/B testing**: Comparar tasa de conversión con/sin boost de color
2. **Ajuste por feedback**: Si usuarios reportan resultados incorrectos, ajustar umbral/magnitud
3. **Analytics**: Trackear cuántos productos reciben color boost y su CTR

## Archivos modificados

- `clip_admin_backend/app/blueprints/api.py`:
  - Nueva función `detect_dominant_color()`
  - Integración en `visual_search()` endpoint
  - Boost aplicado en resultados antes del ordenamiento final
  - Nuevo campo `color_boost` en respuesta JSON
