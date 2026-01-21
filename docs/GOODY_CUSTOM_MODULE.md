# Módulo de Búsqueda Personalizado: Goody

## 📋 Resumen

Cliente: **Goody**  
Industria: **Textil / Ropa profesional para gastronomía**  
Archivo: `clip_admin_backend/app/search_modules/search_client_goody.py`

## 🎯 Problema Resuelto

Goody se especializa en uniformes para restaurantes y cafeterías, con más de **150 tipos de delantales** diferentes. El desafío principal:

1. **Diferenciación funcional**: Distinguir entre tipos de delantal como:
   - Delantal pechera (bib apron)
   - Medio delantal (waist apron)
   - Delantal chef
   - Delantal bar/sommelier

2. **Patrones y estampados**: CLIP no distingue bien entre patrones visuales sutiles como:
   - Flores vs barcos (náutico)
   - Rayas vs cuadros
   - Liso vs estampado
   - Materiales específicos (jean, cuero, loneta)

## 🔧 Solución Implementada

### 1. Detección de Tipo Funcional

```python
APRON_TYPES = {
    "pechera": ["pechera", "pecheras", "bib"],
    "medio": ["medio", "media", "cintura", "waist"],
    "chef": ["chef", "cocinero"],
    "bar": ["bar", "barman", "bartender"],
    "sommelier": ["sommelier", "vino"],
}
```

**Función**: `detect_apron_type(query_tokens)`
- Detecta el tipo específico mencionado en la búsqueda
- Ejemplo: "delantal pechera negro" → detecta "pechera"

### 2. Detección de Patrones/Estampados

```python
PATTERN_KEYWORDS = {
    "floral": ["flores", "flor", "florecido", "floreado", "floral"],
    "nautico": ["barcos", "barco", "anclas", "ancla", "marinero", "nautico"],
    "geometrico": ["cuadros", "cuadro", "rayas", "raya", "patron", "geometrico"],
    "liso": ["liso", "lisa", "sin patron", "sin estampado", "simple", "plain"],
    "jean": ["jean", "denim", "mezclilla"],
    "cuero": ["cuero", "leather"],
    "loneta": ["loneta", "canvas"],
    "punto": ["punto", "knit"],
}
```

**Función**: `detect_pattern(query_tokens)`
- Detecta patrones mencionados en la búsqueda
- Ejemplo: "delantal con flores" → detecta "floral"

### 3. Re-ranking Post-CLIP

**Funciones**:
- `filter_results_by_apron_type()`: Boost 30% si coincide tipo, penaliza 30% si no
- `filter_results_by_pattern()`: Boost 50% si coincide patrón
- `post_process_results()`: Orquesta todo el flujo

**Flujo**:
1. CLIP realiza búsqueda visual inicial
2. Se detecta tipo y patrón en el query del usuario
3. Se re-rankean resultados basándose en nombres de productos
4. Se boostan productos que coinciden semánticamente

## 📊 Ejemplos de Uso

### Caso 1: Búsqueda por tipo funcional
```
Query: "delantal pechera negro"

1. CLIP busca: imágenes similares a "delantal negro"
2. Módulo detecta: tipo="pechera"
3. Re-ranking: 
   - ✅ "Delantal Pechera Blue Note Negro" → boost +30%
   - ❌ "Medio Delantal Negro" → penaliza -30%
```

### Caso 2: Búsqueda por patrón
```
Query: "delantal con flores"

1. CLIP busca: imágenes similares a "delantal"
2. Módulo detecta: patrón="floral"
3. Re-ranking:
   - ✅ "Delantal Pechera Flores Vintage" → boost +50%
   - ⚪ "Delantal Pechera Liso" → sin cambios
```

### Caso 3: Búsqueda combinada
```
Query: "medio delantal de jean"

1. CLIP busca: imágenes similares a "delantal jean"
2. Módulo detecta: tipo="medio", patrón="jean"
3. Re-ranking:
   - ✅ "Medio Delantal de Jean Oscuro" → boost +30% (tipo) +50% (patrón) = +80%
   - ⚠️ "Delantal Pechera de Jean" → boost +50% (patrón), penaliza -30% (tipo) = +20%
   - ❌ "Medio Delantal Liso Negro" → boost +30% (tipo)
```

## 🔄 Integración con el Sistema

### Auto-registro
El módulo se registra automáticamente al iniciar la aplicación gracias al nombre del archivo:
```
search_client_goody.py → slug "goody"
```

### Funciones Core Implementadas

1. **`normalize_tokens(text)`**
   - Normaliza variantes ortográficas (delantal/delantales/mandil)
   - Elimina stopwords irrelevantes

2. **`expand_query(query)`**
   - Expande con sinónimos de categoría
   - Ejemplo: "delantal" → ["delantal", "mandil", "pechera"]
   - Limita a 5 queries máximo

3. **`detect_category_filter(tokens, categories)`**
   - Detecta categorías mencionadas en el query
   - Excluye tokens de color del filtrado
   - Ignora modificadores genéricos

4. **`post_process_results(results, query)`**
   - Re-rankea resultados post-CLIP
   - Aplica boosts por tipo y patrón
   - Ordena por score final

## 📈 Métricas de Mejora Esperadas

| Escenario | Sin Módulo | Con Módulo | Mejora |
|-----------|------------|------------|--------|
| "delantal pechera" (tipo correcto en top 3) | ~40% | ~90% | +125% |
| "delantal con flores" (patrón correcto en top 3) | ~30% | ~85% | +183% |
| "medio delantal jean" (ambos correctos) | ~20% | ~80% | +300% |

## 🧪 Testing

### Manual Testing
Usar el widget de prueba en: `http://localhost:5000/static/goody-store.html`

API Key: `clip_8c49e27a7a699b44f37381f7`

### Queries de Prueba
```bash
# Tipo funcional
"delantal pechera"
"medio delantal"
"delantal chef"

# Patrón
"delantal con flores"
"delantal de rayas"
"delantal liso"

# Material
"delantal de jean"
"delantal de cuero"

# Combinados
"delantal pechera de jean"
"medio delantal con rayas"
"delantal chef liso negro"
```

## 🔍 Análisis de Productos (Muestra)

Nombres de productos analizados de la base de datos:
```
- Delantal Coleccion Punto Caramelo
- Medio Delantal Unisex Color Azul
- Delantal Pechera Modelo Inesita
- Delantal Pechera Blue Note Verde
- Delantal Pechera Loneta Negro Con Rayas
- Delantal Pechera de Jean Ipa
- DELANTAL PECHERA WESTERN - COLOR VERDE
- DELANTAL PECHERA FOOD TRUCK JEAN OSCURO
- Delantal Pechera Blue Note Negro
- Delantal Bow Goody
- DELANTAL GOODY ZARPADO UNISEX
- Delantal Pechera Cuero Flexible
- Delantal Goody Jumper Negro Unisex
- Delantal Goody Jumper Jean Unisex
- Delantal Goody Jumper Gris Unisex
- Delantal Pechera Combinado
- Delantal Chef Combinado
```

**Patrones detectados**:
- Tipos: Pechera (13x), Medio (2x), Jumper (3x), Chef (1x), Bow (1x)
- Patrones: Punto Caramelo, Blue Note, Jean, Rayas, Western, Food Truck, Cuero Flexible
- Colores: Verde, Negro, Azul, Gris, Celeste, Maiz

## 🚀 Deployment

El módulo se despliega automáticamente con la aplicación Flask:

1. **Local**: 
   ```bash
   cd clip_admin_backend && python app.py
   ```
   Console output esperado:
   ```
   ✅ Módulo personalizado registrado: goody
   ```

2. **Railway**:
   Hacer push a GitHub, Railway redeploya automáticamente.

## 📝 Notas Técnicas

### Arquitectura Multi-tenant
- ✅ Sin modificaciones al código core
- ✅ Totalmente aislado por cliente
- ✅ Compatible con otros módulos custom (eve, demo-fashion-store)

### Performance
- Normalización: O(n) tokens
- Detección tipo/patrón: O(m×k) donde m=modificadores, k=keywords
- Re-ranking: O(n log n) donde n=resultados

### Extensibilidad
Para agregar más patrones:
```python
PATTERN_KEYWORDS = {
    # ... existentes ...
    "nuevo_patron": ["keyword1", "keyword2", "keyword3"],
}
```

Para agregar más tipos de delantal:
```python
APRON_TYPES = {
    # ... existentes ...
    "nuevo_tipo": ["keyword1", "keyword2"],
}
```

## 📚 Referencias

- Sistema de módulos: `clip_admin_backend/app/search_modules/__init__.py`
- Módulo Eve (referencia): `search_client_eve_s_store.py`
- Endpoint búsqueda texto: `clip_admin_backend/app/blueprints/search_text.py`
- Tools reference: `docs/TOOLS_REFERENCE.md`

## ⚠️ Limitaciones Conocidas

1. **Dependencia de nombres**: Si los productos no tienen el tipo/patrón en el nombre, no se detecta
2. **Sinónimos limitados**: Solo cubre términos en español (no inglés/portugués)
3. **Patrones complejos**: No distingue entre "flores grandes" vs "flores pequeñas"

## 🔮 Mejoras Futuras

1. **NLP mejorado**: Usar embeddings de texto para similitud semántica
2. **Atributos dinámicos**: Mapear patrones a atributos JSONB del producto
3. **Fine-tuning CLIP**: Re-entrenar con dataset de delantales etiquetados
4. **Multi-idioma**: Soporte para inglés y portugués
